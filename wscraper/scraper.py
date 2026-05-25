"""
Core scraper engine with anti-detection, proxy support, and retry logic.
"""

import time
import random
import requests
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


class Scraper:
    """Web scraper with anti-detection features."""

    DEFAULT_TIMEOUT = 30
    DEFAULT_DELAY = 2
    DEFAULT_RETRIES = 3

    def __init__(self, timeout=None, delay=None, retries=None, proxies=None, headers=None):
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.delay = delay or self.DEFAULT_DELAY
        self.retries = retries or self.DEFAULT_RETRIES
        self.proxies = proxies or []
        self.ua = UserAgent()
        self.session = requests.Session()

    def _get_headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def fetch(self, url):
        """Fetch a URL with retry and anti-detection."""
        headers = self._get_headers()

        for attempt in range(self.retries):
            try:
                proxy = random.choice(self.proxies) if self.proxies else None
                proxies = {"http": proxy, "https": proxy} if proxy else {}

                resp = self.session.get(
                    url,
                    headers=headers,
                    proxies=proxies,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding
                time.sleep(self.delay * random.uniform(0.5, 1.5))
                return resp.text
            except (requests.RequestException, ConnectionError) as e:
                if attempt == self.retries - 1:
                    raise RuntimeError(f"Failed to fetch {url} after {self.retries} attempts: {e}")
                time.sleep((self.delay + 1) * (attempt + 1))

    def parse(self, html, base_url="", select=None):
        """Parse HTML with CSS selectors or XPath."""
        soup = BeautifulSoup(html, "html.parser")

        if not select:
            return {"text": soup.get_text(strip=True, separator="\n")}

        results = []
        for sel in [s.strip() for s in select.split(",")]:
            elements = soup.select(sel)
            for el in elements:
                results.append({
                    "selector": sel,
                    "text": el.get_text(strip=True),
                    "html": str(el)[:500],
                    "attrs": {k: v for k, v in el.attrs.items()},
                })
        return results

    def extract_links(self, html, base_url, relative_only=True):
        """Extract all links from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if relative_only and href.startswith("//"):
                href = "https:" + href
            full = urljoin(base_url, href)
            links.append({"url": full, "text": a.get_text(strip=True)})
        return links

    def extract_table(self, html, selector=None):
        """Extract table data into list of dicts."""
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.select(selector) if selector else soup.find_all("table")
        data = []
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue
            headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if cells and len(cells) == len(headers):
                    data.append(dict(zip(headers, cells)))
        return data

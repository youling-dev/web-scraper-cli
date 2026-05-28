"""
Core scraper engine with anti-detection, proxy support, and retry logic.
"""

import time
import random
import re
import requests
from urllib.parse import urljoin, quote, urlparse
from xml.etree import ElementTree as ET
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

    def extract_sitemap(self, base_url, sitemap_url=None):
        """Fetch and parse sitemap.xml, returning a list of URLs.

        Supports standard sitemap format and sitemap index files.
        Auto-detects sitemap location if sitemap_url is None.
        """
        parsed = urlparse(base_url)
        if sitemap_url:
            sitemap_url = urljoin(base_url, sitemap_url)
        else:
            sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"

        print(f"🗺️  Fetching sitemap: {sitemap_url}")
        xml_text = self.fetch(sitemap_url)

        root = ET.fromstring(xml_text)
        urls = []

        # Check if it's a sitemap index
        ns = ''
        test_tag = root.tag
        if test_tag.startswith('{'):
            ns = test_tag.split('}')[0] + '}'

        children = list(root)
        if children and children[0].tag.replace(ns, '') == 'sitemap':
            # Sitemap index - recursively extract URLs from each sitemap
            for child in root:
                loc_elem = child.find(f'{ns}loc')
                if loc_elem is not None and loc_elem.text:
                    urls.extend(self.extract_sitemap(base_url, loc_elem.text))
        else:
            # Standard sitemap with <url> entries
            for url_entry in root:
                loc_elem = url_entry.find(f'{ns}loc')
                if loc_elem is not None and loc_elem.text:
                    urls.append(loc_elem.text.strip())

        print(f"📋 Found {len(urls)} URLs in sitemap")
        return urls

    def filter_results(self, data, filter_expr=None, unique=False, field=None):
        """Filter and transform scraped results.

        Args:
            data: List of result dicts
            filter_expr: Filter expression in 'field:op:value' format.
                Operators: contains, notcontains, eq, gt, lt, startswith, endswith
                Examples: 'text:contains:价格', 'text:notcontains:广告'
            unique: Deduplicate by text content
            field: Extract only this field from each result

        Returns:
            Filtered/transformed list
        """
        if not data:
            return []

        result = list(data)

        # Apply filter
        if filter_expr:
            parts = filter_expr.split(":", 2)
            if len(parts) == 3:
                f_field, op, value = parts
                filtered = []
                for item in result:
                    if not isinstance(item, dict):
                        continue
                    item_val = str(item.get(f_field, ""))
                    match = False
                    if op == "contains":
                        match = value in item_val
                    elif op == "notcontains":
                        match = value not in item_val
                    elif op == "eq":
                        match = item_val == value
                    elif op == "startswith":
                        match = item_val.startswith(value)
                    elif op == "endswith":
                        match = item_val.endswith(value)
                    elif op == "gt":
                        try:
                            match = float(item_val) > float(value)
                        except ValueError:
                            pass
                    elif op == "lt":
                        try:
                            match = float(item_val) < float(value)
                        except ValueError:
                            pass
                    if match:
                        filtered.append(item)
                result = filtered

        # Deduplicate
        if unique:
            seen = set()
            unique_result = []
            for item in result:
                key = item.get("text", str(item)) if isinstance(item, dict) else str(item)
                if key not in seen:
                    seen.add(key)
                    unique_result.append(item)
            result = unique_result

        # Extract specific field
        if field:
            result = [item.get(field, "") if isinstance(item, dict) else item for item in result]

        return result

    def recursive_crawl(self, start_url, max_depth=2, same_domain=True):
        """Recursively crawl from a start URL up to max_depth.

        Returns list of {url, depth, text} dicts.
        """
        parsed_start = urlparse(start_url)
        start_domain = parsed_start.netloc
        visited = set()
        results = []

        def crawl(url, depth):
            if depth > max_depth:
                return
            if url in visited:
                return

            # Domain restriction
            if same_domain:
                curr_domain = urlparse(url).netloc
                if curr_domain != start_domain:
                    return

            visited.add(url)
            print(f"🕸️  [{depth}/{max_depth}] {url}")

            try:
                html = self.fetch(url)
                links = self.extract_links(html, url, relative_only=False)
                results.append({
                    "url": url,
                    "depth": depth,
                    "links_found": len(links),
                })

                # Crawl sub-links
                for link in links:
                    link_url = link["url"]
                    # Strip fragments and normalize
                    clean = re.sub(r'#[^/]*$', '', link_url)
                    if clean not in visited:
                        crawl(clean, depth + 1)
            except Exception as e:
                results.append({"url": url, "depth": depth, "error": str(e)})

        crawl(start_url, 0)
        print(f"📋 Crawled {len(results)} pages (depth 0-{max_depth})")
        return results

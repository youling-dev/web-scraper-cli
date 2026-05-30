"""
Core scraper engine with anti-detection, proxy support, retry logic, and async crawling.
"""

import os
import time
import random
import re
import sqlite3
import asyncio
import requests
import httpx
from urllib.parse import urljoin, quote, urlparse
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from .cache import HTTPCache


class Scraper:
    """Web scraper with anti-detection features."""

    DEFAULT_TIMEOUT = 30
    DEFAULT_DELAY = 2
    DEFAULT_RETRIES = 3

    def __init__(self, timeout=None, delay=None, retries=None, proxies=None, headers=None, cache=None, cache_ttl=300):
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.delay = delay or self.DEFAULT_DELAY
        self.retries = retries or self.DEFAULT_RETRIES
        self.proxies = proxies or []
        self.ua = UserAgent()
        self.session = requests.Session()

        # HTTP cache (v1.8.0)
        if cache is True or (cache is None and os.environ.get("WSRAPPER_CACHE", "").lower() == "true"):
            self.cache = HTTPCache(enabled=True, default_ttl=cache_ttl)
        elif isinstance(cache, HTTPCache):
            self.cache = cache
        else:
            self.cache = HTTPCache(enabled=False, default_ttl=cache_ttl)
        self._cache_hits = 0
        self._cache_misses = 0

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
        """Fetch a URL with retry, anti-detection, and optional HTTP cache."""
        # Check cache first
        cached = self.cache.get(url)
        if cached is not None:
            self._cache_hits += 1
            print(f"  ⚡ Cache hit: {url}")
            return cached
        self._cache_misses += 1

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
                html = resp.text

                # Store in cache
                self.cache.put(url, html, dict(resp.headers))

                time.sleep(self.delay * random.uniform(0.5, 1.5))
                return html
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

    # ------------------------------------------------------------------ #
    #  Async crawling methods (v1.3.0)                                     #
    # ------------------------------------------------------------------ #

    def _get_async_headers(self):
        """Return headers for async requests."""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def async_fetch_one(self, url, client):
        """Fetch a single URL asynchronously with retry."""
        headers = self._get_async_headers()

        for attempt in range(self.retries):
            try:
                proxy = random.choice(self.proxies) if self.proxies else None

                resp = await client.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                resp.raise_for_status()
                # httpx returns bytes; decode
                content = resp.content
                # Try to detect encoding from content-type or fallback
                try:
                    encoding = resp.headers.get("content-type", "").split("charset=")[-1] if "charset" in resp.headers.get("content-type", "") else None
                except Exception:
                    encoding = None
                text = content.decode(encoding or "utf-8", errors="replace")
                await asyncio.sleep(self.delay * random.uniform(0.3, 1.0))
                return text
            except (httpx.HTTPError, httpx.RequestError, Exception) as e:
                if attempt == self.retries - 1:
                    raise RuntimeError(f"Failed to fetch {url} after {self.retries} attempts: {e}")
                await asyncio.sleep((self.delay + 1) * (attempt + 1))

    async def async_fetch_many(self, urls, concurrency=5):
        """Fetch multiple URLs concurrently.

        Args:
            urls: List of URL strings or list of (url, selector) tuples.
            concurrency: Max concurrent requests (default 5).

        Returns:
            List of dicts: {"url": ..., "html": ...} or {"url": ..., "error": ...}
        """
        sem = asyncio.Semaphore(concurrency)
        results = []

        async def fetch_with_limit(item):
            url = item[0] if isinstance(item, tuple) else item
            async with sem:
                try:
                    html = await self.async_fetch_one(url, client=self._async_client)
                    results.append({"url": url, "html": html})
                except Exception as e:
                    results.append({"url": url, "error": str(e)})

        self._async_client = httpx.AsyncClient(
            http2=False,
            verify=True,
        )
        try:
            await asyncio.gather(*(fetch_with_limit(u) for u in urls))
        finally:
            await self._async_client.aclose()

        return results

    async def async_batch_scrape(self, url_selectors, concurrency=5):
        """Asynchronously scrape multiple URLs with CSS selectors.

        Args:
            url_selectors: List of (url, selector) tuples.
            concurrency: Max concurrent requests.

        Returns:
            List of result dicts with url, selector, and extracted data.
        """
        all_html = await self.async_fetch_many(
            [(u, s) for u, s in url_selectors],
            concurrency=concurrency,
        )

        final = []
        for item in all_html:
            if "error" in item:
                final.append({"url": item["url"], "error": item["error"]})
                continue
            url, selector = url_selectors[[u[0] for u in url_selectors].index(item["url"])]
            parsed = self.parse(item["html"], base_url=url, select=selector)
            final.append({"url": url, "data": parsed})

        return final

    async def async_recursive_crawl(self, start_url, max_depth=2, same_domain=True, concurrency=3):
        """Asynchronously recursive crawl from a start URL.

        Returns list of {url, depth, links_found} dicts.
        """
        parsed_start = urlparse(start_url)
        start_domain = parsed_start.netloc
        visited = set()
        results = []
        sem = asyncio.Semaphore(concurrency)

        self._async_client = httpx.AsyncClient(http2=False, verify=True)

        async def crawl(url, depth):
            if depth > max_depth:
                return
            if url in visited:
                return
            if same_domain:
                if urlparse(url).netloc != start_domain:
                    return

            visited.add(url)
            print(f"🕸️  [{depth}/{max_depth}] {url}")

            async with sem:
                try:
                    html = await self.async_fetch_one(url, client=self._async_client)
                    links = self.extract_links(html, url, relative_only=False)
                    results.append({
                        "url": url,
                        "depth": depth,
                        "links_found": len(links),
                    })
                except Exception as e:
                    results.append({"url": url, "depth": depth, "error": str(e)})
                    links = []

            # Crawl sub-links
            if depth < max_depth:
                tasks = []
                for link in links:
                    link_url = link["url"]
                    clean = re.sub(r'#[^/]*$', '', link_url)
                    if clean not in visited:
                        visited.add(clean)
                        tasks.append(crawl(clean, depth + 1))
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

        try:
            await crawl(start_url, 0)
        finally:
            await self._async_client.aclose()

        print(f"📋 Async crawled {len(results)} pages (depth 0-{max_depth})")
        return results

    # ------------------------------------------------------------------ #
    #  Data export methods (v1.4.0)                                        #
    # ------------------------------------------------------------------ #

    def to_markdown(self, data, title=None):
        """Convert list of dicts to Markdown table string.

        Args:
            data: List of result dicts
            title: Optional table title

        Returns:
            Markdown table string
        """
        if not data:
            return "*(no data)*"

        if not isinstance(data[0], dict):
            return "\n".join(str(item) for item in data)

        # Collect all keys preserving insertion order
        keys = list(data[0].keys())
        for item in data[1:]:
            for k in item.keys():
                if k not in keys:
                    keys.append(k)

        lines = []
        if title:
            lines.append(f"### {title}")
            lines.append("")

        # Header
        lines.append("| " + " | ".join(keys) + " |")
        # Separator
        lines.append("| " + " | ".join("---" for _ in keys) + " |")
        # Rows
        for row in data:
            cells = []
            for k in keys:
                val = str(row.get(k, "")).replace("|", "\\|").replace("\n", " ")
                cells.append(val[:200])  # Truncate very long cells
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def to_sqlite(self, data, db_path, table_name="scraped"):
        """Export list of dicts to SQLite database.

        Args:
            data: List of result dicts
            db_path: Path to SQLite database file
            table_name: Table name (default: 'scraped')

        Returns:
            Number of rows inserted
        """
        if not data or not isinstance(data[0], dict):
            print("⚠️  No valid dict data to export")
            return 0

        keys = list(data[0].keys())
        for item in data[1:]:
            for k in item.keys():
                if k not in keys:
                    keys.append(k)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table if not exists
        col_defs = ", ".join(
            f'"{k}" TEXT' for k in keys
        )
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                {col_defs}
            )
        """)

        # Insert rows
        placeholders = ", ".join([f'"{k}"' for k in keys])
        question_marks = ", ".join(["?" for _ in keys])
        # Insert all rows
        for row in data:
            cursor.execute(f"""
                INSERT INTO "{table_name}" ({placeholders})
                VALUES ({question_marks})
            """, [str(row.get(k, "")) for k in keys])

        conn.commit()
        conn.close()
        return len(data)

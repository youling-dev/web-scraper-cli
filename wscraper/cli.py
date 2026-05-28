#!/usr/bin/env python3
"""
wscraper CLI - 轻量网页爬虫工具

Examples:
    wscraper https://example.com --select ".title,.content"
    wscraper https://example.com --select ".price" --format csv --output out.csv
    wscraper https://example.com --interval 5m
    wscraper https://example.com --proxy http://proxy:8080
"""

import argparse
import json
import csv
import time
import sys
from pathlib import Path

from .scraper import Scraper


def parse_interval(s):
    """Parse interval string like '5m', '1h', '30s' to seconds."""
    s = s.strip().lower()
    if s.endswith("m"):
        return int(s[:-1]) * 60
    elif s.endswith("h"):
        return int(s[:-1]) * 3600
    elif s.endswith("s"):
        return int(s[:-1])
    else:
        return int(s)


def export_data(data, fmt, output):
    """Export data to CSV, JSON, or print to stdout."""
    if fmt == "json":
        content = json.dumps(data, ensure_ascii=False, indent=2)
    elif fmt == "csv":
        if not data:
            content = ""
        else:
            import io
            buf = io.StringIO()
            keys = list(data[0].keys()) if isinstance(data[0], dict) else ["text"]
            writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for row in data:
                writer.writerow({k: row.get(k, "") for k in keys})
            content = buf.getvalue()
    else:
        content = json.dumps(data, ensure_ascii=False, indent=2)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        print(f"✅ Saved to {output}")
    else:
        print(content)


def main():
    parser = argparse.ArgumentParser(
        prog="wscraper",
        description="轻量网页爬虫 CLI 工具",
    )
    parser.add_argument("url", help="目标 URL")
    parser.add_argument("--select", "-s", help="CSS 选择器（逗号分隔）")
    parser.add_argument("--format", "-f", choices=["json", "csv", "text"], default="json", help="输出格式")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--interval", "-i", help="定时抓取间隔（如 5m, 1h）")
    parser.add_argument("--proxy", "-p", action="append", help="代理地址（可多次指定）")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="超时秒数")
    parser.add_argument("--delay", "-d", type=float, default=2.0, help="请求延迟秒数")
    parser.add_argument("--retries", "-r", type=int, default=3, help="重试次数")
    parser.add_argument("--links", action="store_true", help="提取所有链接")
    parser.add_argument("--table", action="store_true", help="提取表格数据")
    parser.add_argument("--table-selector", help="表格 CSS 选择器")
    parser.add_argument("--pages", help="翻页范围（如 1-10，URL 中用 {page} 占位）")
    parser.add_argument("--sitemap", action="store_true", help="从 sitemap.xml 提取所有 URL 并抓取")
    parser.add_argument("--sitemap-url", help="指定 sitemap URL（默认自动检测 /sitemap.xml）")
    parser.add_argument("--depth", type=int, help="递归爬取深度（从入口页发现子页面）")
    parser.add_argument("--same-domain", action="store_true", default=True, help="仅抓取同域名页面（默认开启）")
    parser.add_argument("--max-pages", type=int, help="递归爬取时最大抓取页数")

    args = parser.parse_args()

    scraper = Scraper(
        timeout=args.timeout,
        delay=args.delay,
        retries=args.retries,
        proxies=args.proxy or [],
    )

    # Handle URL discovery
    urls = [args.url]

    # Sitemap mode
    if args.sitemap:
        urls = scraper.extract_sitemap(args.url, args.sitemap_url)
        if not urls:
            print("❌ No URLs found in sitemap", file=sys.stderr)
            sys.exit(1)
        if args.max_pages:
            urls = urls[:args.max_pages]
            print(f"📋 Limited to {args.max_pages} pages")

    # Recursive crawl mode
    elif args.depth is not None:
        crawl_results = scraper.recursive_crawl(
            args.url,
            max_depth=args.depth,
            same_domain=args.same_domain,
        )
        if args.max_pages:
            crawl_results = crawl_results[:args.max_pages]

        all_data = []
        for result in crawl_results:
            if "error" in result:
                continue
            if args.select:
                try:
                    html = scraper.fetch(result["url"])
                    data = scraper.parse(html, result["url"], args.select)
                    all_data.extend(data)
                except Exception as e:
                    print(f"⚠️  Failed to parse {result['url']}: {e}")

        print(f"\n📊 Extracted {len(all_data)} items from {len(crawl_results)} pages\n")
        export_data(all_data, args.format, args.output)
        sys.exit(0)

    # Pagination
    if args.pages:
        start, end = map(int, args.pages.split("-"))
        urls = [args.url.replace("{page}", str(p)) for p in range(start, end + 1)]

    interval = parse_interval(args.interval) if args.interval else None

    try:
        while True:
            all_data = []
            for url in urls:
                print(f"🕷️  Fetching: {url}")
                html = scraper.fetch(url)

                if args.links:
                    data = scraper.extract_links(html, url)
                elif args.table:
                    data = scraper.extract_table(html, args.table_selector)
                else:
                    data = scraper.parse(html, url, args.select)

                all_data.extend(data)

            print(f"\n📊 Extracted {len(all_data)} items\n")
            export_data(all_data, args.format, args.output)

            if not interval:
                break

            print(f"\n⏰ Next fetch in {interval}s...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n👋 Stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

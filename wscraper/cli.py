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
import asyncio
import sys
from pathlib import Path

from .scraper import Scraper
from .watcher import Watcher
from .cache import HTTPCache


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


def export_data(data, fmt, output, scraper=None, sqlite_path=None, markdown_title=None):
    """Export data to CSV, JSON, Markdown table, or SQLite."""
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
    elif fmt == "markdown":
        if scraper and data:
            content = scraper.to_markdown(data, title=markdown_title)
        elif data:
            # Fallback: simple manual table
            content = _manual_markdown(data)
        else:
            content = "*(no data)*"
    else:
        content = json.dumps(data, ensure_ascii=False, indent=2)

    # SQLite export (can be combined with other formats)
    if sqlite_path and scraper and data:
        count = scraper.to_sqlite(data, sqlite_path)
        print(f"💾 Exported {count} rows to SQLite: {sqlite_path}")

    if output and fmt != "markdown":
        Path(output).write_text(content, encoding="utf-8")
        print(f"✅ Saved to {output}")
    elif output and fmt == "markdown":
        Path(output).write_text(content, encoding="utf-8")
        print(f"✅ Saved Markdown to {output}")
    elif not sqlite_path:  # Only print if not already handled by SQLite-only mode
        print(content)


def _manual_markdown(data):
    """Fallback Markdown table generator when scraper is not available."""
    if not data:
        return "*(no data)*"
    if not isinstance(data[0], dict):
        return "\n".join(str(item) for item in data)
    keys = list(data[0].keys())
    for item in data[1:]:
        for k in item.keys():
            if k not in keys:
                keys.append(k)
    lines = []
    lines.append("| " + " | ".join(keys) + " |")
    lines.append("| " + " | ".join("---" for _ in keys) + " |")
    for row in data:
        cells = [str(row.get(k, "")).replace("|", "\\|").replace("\n", " ")[:200] for k in keys]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_scrape_parser(sub):
    """Build the scrape subcommand parser (also serves as the default)."""
    sub.add_argument("url", help="目标 URL")
    sub.add_argument("--select", "-s", help="CSS 选择器（逗号分隔）")
    sub.add_argument("--format", "-f", choices=["json", "csv", "text", "markdown"], default="json", help="输出格式")
    sub.add_argument("--output", "-o", help="输出文件路径")
    sub.add_argument("--interval", "-i", help="定时抓取间隔（如 5m, 1h）")
    sub.add_argument("--proxy", "-p", action="append", help="代理地址（可多次指定）")
    sub.add_argument("--timeout", "-t", type=int, default=30, help="超时秒数")
    sub.add_argument("--delay", "-d", type=float, default=2.0, help="请求延迟秒数")
    sub.add_argument("--retries", "-r", type=int, default=3, help="重试次数")
    sub.add_argument("--links", action="store_true", help="提取所有链接")
    sub.add_argument("--table", action="store_true", help="提取表格数据")
    sub.add_argument("--table-selector", help="表格 CSS 选择器")
    sub.add_argument("--pages", help="翻页范围（如 1-10，URL 中用 {page} 占位）")
    sub.add_argument("--sitemap", action="store_true", help="从 sitemap.xml 提取所有 URL 并抓取")
    sub.add_argument("--sitemap-url", help="指定 sitemap URL（默认自动检测 /sitemap.xml）")
    sub.add_argument("--depth", type=int, help="递归爬取深度（从入口页发现子页面）")
    sub.add_argument("--same-domain", action="store_true", default=True, help="仅抓取同域名页面（默认开启）")
    sub.add_argument("--max-pages", type=int, help="递归爬取时最大抓取页数")
    sub.add_argument("--unique", action="store_true", help="去重（按 text 字段）")
    sub.add_argument("--filter", help="过滤表达式 field:op:value，如 text:contains:价格")
    sub.add_argument("--field", help="只提取指定字段，如 text/url/price")
    sub.add_argument("--async", "-A", action="store_true", help="启用异步并发抓取")
    sub.add_argument("--concurrency", "-c", type=int, default=5, help="异步并发数（默认 5）")
    sub.add_argument("--markdown", "-M", action="store_true", help="输出 Markdown 表格格式")
    sub.add_argument("--sqlite", "-S", help="导出到 SQLite 数据库（指定数据库文件路径）")
    sub.add_argument("--table-name", default="scraped", help="SQLite 表名（默认: scraped）")
    sub.add_argument("--cache", dest="cache", action="store_true", default=None, help="启用 HTTP 缓存")
    sub.add_argument("--no-cache", dest="cache", action="store_false", help="禁用 HTTP 缓存")
    sub.add_argument("--cache-ttl", type=int, default=300, help="缓存默认 TTL（秒，默认 300）")


def _parse_notifies(notify_strs):
    """Parse --notify JSON strings into list of notification config dicts."""
    configs = []
    for s in notify_strs:
        try:
            cfg = json.loads(s)
            configs.append(cfg)
        except json.JSONDecodeError:
            # Fallback: try to parse as type=url format
            if "=" in s:
                key, val = s.split("=", 1)
                configs.append({"type": key.strip(), "url": val.strip()})
            else:
                print(f"⚠️  Could not parse notify config: {s}", file=sys.stderr)
    return configs


def run_scrape(args):
    """Execute the scrape command."""
    scraper = Scraper(
        timeout=args.timeout,
        delay=args.delay,
        retries=args.retries,
        proxies=args.proxy or [],
        cache=args.cache,
        cache_ttl=args.cache_ttl,
    )

    urls = [args.url]

    if args.sitemap:
        urls = scraper.extract_sitemap(args.url, args.sitemap_url)
        if not urls:
            print("❌ No URLs found in sitemap", file=sys.stderr)
            sys.exit(1)
        if args.max_pages:
            urls = urls[:args.max_pages]
            print(f"📋 Limited to {args.max_pages} pages")

    elif args.depth is not None:
        if args.async_:
            crawl_results = asyncio.run(
                scraper.async_recursive_crawl(
                    args.url,
                    max_depth=args.depth,
                    same_domain=args.same_domain,
                    concurrency=args.concurrency,
                )
            )
        else:
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

        if args.filter or args.unique or args.field:
            all_data = scraper.filter_results(
                all_data,
                filter_expr=args.filter,
                unique=args.unique,
                field=args.field,
            )

        fmt = "markdown" if args.markdown else args.format
        print(f"\n📊 Extracted {len(all_data)} items from {len(crawl_results)} pages\n")
        export_data(all_data, fmt, args.output, scraper=scraper, sqlite_path=args.sqlite, markdown_title=args.url)
        sys.exit(0)

    if args.pages:
        start, end = map(int, args.pages.split("-"))
        urls = [args.url.replace("{page}", str(p)) for p in range(start, end + 1)]

    interval = parse_interval(args.interval) if args.interval else None

    try:
        while True:
            all_data = []

            if args.async_ and len(urls) > 1:
                print(f"⚡ Async mode: fetching {len(urls)} URLs (concurrency={args.concurrency})")
                url_selectors = [(u, args.select) for u in urls]
                batch_results = asyncio.run(
                    scraper.async_batch_scrape(
                        url_selectors,
                        concurrency=args.concurrency,
                    )
                )
                for br in batch_results:
                    if "error" in br:
                        print(f"⚠️  Failed: {br['url']}: {br['error']}")
                        continue
                    all_data.extend(br.get("data", []))
            else:
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

            if args.filter or args.unique or args.field:
                all_data = scraper.filter_results(
                    all_data,
                    filter_expr=args.filter,
                    unique=args.unique,
                    field=args.field,
                )

            fmt = "markdown" if args.markdown else args.format
            print(f"\n📊 Extracted {len(all_data)} items\n")
            export_data(all_data, fmt, args.output, scraper=scraper, sqlite_path=args.sqlite, markdown_title=args.url)

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


def run_watch(args):
    """Execute watch subcommands."""
    watcher = Watcher(db_path=args.db)

    if args.watch_command == "add":
        result = watcher.add(
            url=args.url,
            name=args.name,
            selector=args.select,
            interval=args.interval or 3600,
        )
        print(result["message"])

    elif args.watch_command == "check":
        on_change = _parse_notifies(args.notify) if args.notify else None
        results = watcher.check_all(on_change=on_change)
        for r in results:
            print(r["message"])
            if r.get("diff"):
                print("\n".join(r["diff"]))
                print()
            if r.get("notifications"):
                for n in r["notifications"]:
                    status = "✅" if n["ok"] else "❌"
                    print(f"  {status} Notification [{n['type']}]: {'sent' if n['ok'] else n['result'].get('error', 'failed')}")

    elif args.watch_command == "list":
        watches = watcher.list_watches()
        if not watches:
            print("📋 No watches configured.")
            return
        print(f"{'ID':<5} {'Name':<30} {'URL':<40} {'Changes':<8} {'Last Checked':<20}")
        print("-" * 110)
        for w in watches:
            name = (w["name"] or w["url"])[:28]
            url = w["url"][:38]
            lc = w["last_checked"] or "never"
            print(f"{w['id']:<5} {name:<30} {url:<40} {w['change_count']:<8} {lc:<20}")

    elif args.watch_command == "history":
        h = watcher.history(args.watch_id or 1, limit=args.limit)
        if not h:
            print("❌ Watch not found.")
            return
        print(f"📋 {h['name']} (total changes: {h['total_changes']})")
        for c in h["history"]:
            print(f"  [{c['timestamp']}] +{c['added_lines']} -{c['removed_lines']} lines")
            if c["diff"]:
                print("\n".join(c["diff"]))
                print()

    elif args.watch_command == "remove":
        result = watcher.remove(args.watch_id or 1)
        print(result.get("message", result.get("error", "Unknown error")))

    elif args.watch_command == "watch":
        """Continuous monitoring loop."""
        interval = args.interval or 3600
        on_change = _parse_notifies(args.notify) if args.notify else None
        print(f"👀 Watching for changes (interval: {interval}s, Ctrl+C to stop)\n")
        try:
            while True:
                results = watcher.check_all(on_change=on_change)
                for r in results:
                    if r["status"] == "changed":
                        print(r["message"])
                        if r.get("diff"):
                            print("\n".join(r["diff"]))
                            print()
                        if r.get("notifications"):
                            for n in r["notifications"]:
                                status = "✅" if n["ok"] else "❌"
                                print(f"  {status} Notification [{n['type']}]: {'sent' if n['ok'] else n['result'].get('error', 'failed')}")
                print(f"⏰ Next check in {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 Stopped.")


def main():
    parser = argparse.ArgumentParser(
        prog="wscraper",
        description="轻量网页爬虫 CLI 工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # Scrape subcommand (also default when no subcommand given)
    scrape_parser = subparsers.add_parser("scrape", help="抓取网页数据")
    build_scrape_parser(scrape_parser)

    # Watch subcommands
    watch_parser = subparsers.add_parser("watch", help="监控网页变更")
    watch_parser.add_argument("--db", default="wscraper_watches.db", help="数据库路径")
    watch_sub = watch_parser.add_subparsers(dest="watch_command")

    # watch add
    wa = watch_sub.add_parser("add", help="添加监控 URL")
    wa.add_argument("url", help="要监控的 URL")
    wa.add_argument("--name", "-n", help="监控名称")
    wa.add_argument("--select", "-s", help="CSS 选择器")
    wa.add_argument("--interval", "-i", type=int, help="检查间隔（秒，默认 3600）")
    wa.add_argument("--notify", "-N", action="append", help="变更通知配置（JSON，可多次指定）")

    # watch check
    wc = watch_sub.add_parser("check", help="检查所有监控项")
    wc.add_argument("--notify", "-N", action="append", help="变更通知配置（JSON，可多次指定）")

    # watch list
    watch_sub.add_parser("list", help="列出所有监控项")

    # watch history
    wh = watch_sub.add_parser("history", help="查看变更历史")
    wh.add_argument("--id", type=int, help="监控 ID（默认 1）")
    wh.add_argument("--limit", type=int, default=5, help="显示条数（默认 5）")

    # watch remove
    wr = watch_sub.add_parser("remove", help="删除监控项")
    wr.add_argument("--id", type=int, help="监控 ID")

    # watch watch (continuous)
    ww = watch_sub.add_parser("watch", help="持续监控（循环检查）")
    ww.add_argument("--interval", "-i", type=int, help="检查间隔（秒，默认 3600）")
    ww.add_argument("--notify", "-N", action="append", help="变更通知配置（JSON，可多次指定）")

    # Run subcommand (config-driven tasks)
    run_parser = subparsers.add_parser("run", help="运行配置文件中的任务")
    run_parser.add_argument("config", help="YAML 配置文件路径")
    run_parser.add_argument("--task", "-t", help="只运行指定名称的任务（支持模糊匹配）")
    run_parser.add_argument("--watch", "-w", action="store_true", help="持续监控模式（循环运行）")
    run_parser.add_argument("--interval", "-i", type=int, help="持续监控时的间隔（秒，默认 3600）")

    args = parser.parse_args()

    # Watch commands
    if args.command == "watch":
        run_watch(args)
        return

    # Run commands (config-driven)
    if args.command == "run":
        _run_config(
            config_path=args.config,
            task_filter=args.task,
            watch=args.watch,
            interval=args.interval,
        )
        return

    # Scrape: if subcommand was given or URL provided, run scrape
    if args.command == "scrape" or hasattr(args, "url"):
        run_scrape(args)
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()

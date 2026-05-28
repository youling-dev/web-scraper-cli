#!/usr/bin/env python3
"""
wscraper config - YAML 配置文件驱动爬虫任务

用法:
    wscraper run tasks.yml
    wscraper run tasks.yml --task "任务名称"
    wscraper run tasks.yml --watch
"""

import yaml
import sys
import time
import asyncio
from pathlib import Path

from .scraper import Scraper
from .cli import export_data, parse_interval


def load_config(config_path):
    """加载 YAML 配置文件，返回配置字典。

    支持两种格式：

    1. 简单格式（单任务）：
        url: "https://example.com"
        select: ".title"
        format: json

    2. 任务列表格式：
        tasks:
          - name: "任务1"
            url: "..."
            ...
          - name: "任务2"
            url: "..."
            ...

    可选全局配置：
        global:
          timeout: 30
          delay: 2.0
          retries: 3
          proxy: "http://proxy:8080"
    """
    path = Path(config_path)
    if not path.exists():
        print(f"❌ 配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    try:
        cfg = yaml.safe_load(content)
    except yaml.YAMLError as e:
        print(f"❌ YAML 解析错误: {e}", file=sys.stderr)
        sys.exit(1)

    if not cfg:
        print("❌ 配置文件为空", file=sys.stderr)
        sys.exit(1)

    return cfg


def resolve_tasks(cfg):
    """从配置中提取任务列表。

    返回 (tasks_list, global_cfg) 元组。
    """
    global_cfg = cfg.get("global", {})
    if isinstance(global_cfg, str) or global_cfg is None:
        global_cfg = {}

    # 简单格式（单任务）
    if "tasks" not in cfg:
        tasks = [cfg]
    else:
        tasks = cfg.get("tasks", [])

    # 给每个任务加上 name（如果没有）
    for i, task in enumerate(tasks):
        if not task.get("name"):
            task["name"] = f"任务-{i + 1}"

    return tasks, global_cfg


def run_task(task, global_cfg=None):
    """执行单个爬虫任务。

    Args:
        task: 任务配置字典
        global_cfg: 全局配置字典

    Returns:
        {"name": ..., "status": "ok"/"error", "count": N, "error": ...}
    """
    if global_cfg is None:
        global_cfg = {}

    name = task.get("name", "未命名")
    url = task.get("url")
    if not url:
        return {"name": name, "status": "error", "count": 0, "error": "缺少 url 字段"}

    # 合并全局配置
    timeout = task.get("timeout", global_cfg.get("timeout", 30))
    delay = task.get("delay", global_cfg.get("delay", 2.0))
    retries = task.get("retries", global_cfg.get("retries", 3))
    proxies = task.get("proxy", global_cfg.get("proxy", []))
    if isinstance(proxies, str):
        proxies = [proxies]
    if not isinstance(proxies, list):
        proxies = []

    scraper = Scraper(
        timeout=timeout,
        delay=delay,
        retries=retries,
        proxies=proxies,
    )

    try:
        # URL 列表支持
        urls = task.get("urls", [url])
        if not isinstance(urls, list):
            urls = [urls]

        # Sitemap
        if task.get("sitemap"):
            urls = scraper.extract_sitemap(url, task.get("sitemap_url"))
            if not urls:
                return {"name": name, "status": "error", "count": 0, "error": "sitemap 未找到 URL"}
            if task.get("max_pages"):
                urls = urls[:task["max_pages"]]

        # 递归爬取
        if task.get("depth") is not None:
            depth = task["depth"]
            same_domain = task.get("same_domain", True)
            max_pages = task.get("max_pages")

            if task.get("async") or task.get("async_"):
                crawl_results = asyncio.run(
                    scraper.async_recursive_crawl(
                        url, max_depth=depth,
                        same_domain=same_domain,
                        concurrency=task.get("concurrency", 5),
                    )
                )
            else:
                crawl_results = scraper.recursive_crawl(
                    url, max_depth=depth, same_domain=same_domain
                )

            if max_pages:
                crawl_results = crawl_results[:max_pages]

            all_data = []
            for result in crawl_results:
                if "error" in result:
                    continue
                if task.get("select"):
                    try:
                        html = scraper.fetch(result["url"])
                        data = scraper.parse(html, result["url"], task["select"])
                        all_data.extend(data)
                    except Exception as e:
                        print(f"  ⚠️  Failed to parse {result['url']}: {e}")

            all_data = _apply_filters(scraper, all_data, task)
            result = _export(scraper, all_data, task)
            return {"name": name, "status": "ok", "count": len(all_data)}

        # 翻页
        if task.get("pages"):
            start, end = map(int, task["pages"].split("-"))
            urls = [url.replace("{page}", str(p)) for p in range(start, end + 1)]

        # 抓取
        all_data = []
        if task.get("async") or task.get("async_"):
            if len(urls) > 1:
                url_selectors = [(u, task.get("select")) for u in urls]
                batch_results = asyncio.run(
                    scraper.async_batch_scrape(
                        url_selectors,
                        concurrency=task.get("concurrency", 5),
                    )
                )
                for br in batch_results:
                    if "error" in br:
                        print(f"  ⚠️  Failed: {br['url']}: {br['error']}")
                        continue
                    all_data.extend(br.get("data", []))
            else:
                html = scraper.fetch(urls[0])
                all_data = _parse_html(scraper, html, urls[0], task)
        else:
            for u in urls:
                html = scraper.fetch(u)
                all_data = _parse_html(scraper, html, u, task)

        all_data = _apply_filters(scraper, all_data, task)
        result = _export(scraper, all_data, task)
        return {"name": name, "status": "ok", "count": len(all_data)}

    except Exception as e:
        return {"name": name, "status": "error", "count": 0, "error": str(e)}


def _parse_html(scraper, html, url, task):
    """根据任务配置解析 HTML。"""
    if task.get("links"):
        return scraper.extract_links(html, url)
    elif task.get("table"):
        return scraper.extract_table(html, task.get("table_selector"))
    elif task.get("select"):
        return scraper.parse(html, url, task["select"])
    else:
        return scraper.parse(html, url)


def _apply_filters(scraper, data, task):
    """应用过滤、去重、字段提取。"""
    return scraper.filter_results(
        data,
        filter_expr=task.get("filter"),
        unique=task.get("unique", False),
        field=task.get("field"),
    )


def _export(scraper, data, task):
    """导出数据到指定格式。"""
    fmt = task.get("format", "json")
    output = task.get("output")
    sqlite_path = task.get("sqlite")
    markdown_title = task.get("markdown_title") or task.get("name")

    if task.get("markdown"):
        fmt = "markdown"

    export_data(data, fmt, output, scraper=scraper, sqlite_path=sqlite_path,
                markdown_title=markdown_title)


def run_config(config_path, task_filter=None, watch=False, interval=None):
    """运行配置文件中的所有任务（或指定任务）。

    Args:
        config_path: YAML 配置文件路径
        task_filter: 任务名称过滤器（只运行匹配的任务）
        watch: 是否持续监控模式
        interval: 监控间隔（秒），默认读取配置中的 interval

    Returns:
        结果列表 [{"name": ..., "status": ..., "count": ..., ...}]
    """
    cfg = load_config(config_path)
    tasks, global_cfg = resolve_tasks(cfg)

    if task_filter:
        tasks = [t for t in tasks if task_filter in t.get("name", "")]
        if not tasks:
            print(f"❌ 未找到匹配的任务: {task_filter}", file=sys.stderr)
            sys.exit(1)

    print(f"📋 配置文件: {config_path}")
    print(f"🔧 任务数: {len(tasks)}")
    print()

    while True:
        results = []
        for task in tasks:
            name = task.get("name", "未命名")
            print(f"🕷️  运行任务: {name}")
            result = run_task(task, global_cfg)
            status = "✅" if result["status"] == "ok" else "❌"
            if result["status"] == "ok":
                print(f"  {status} {name} — 提取 {result['count']} 条数据")
            else:
                print(f"  {status} {name} — {result.get('error', '未知错误')}")
            results.append(result)
            print()

        ok = sum(1 for r in results if r["status"] == "ok")
        print(f"📊 总计: {ok}/{len(results)} 成功")

        if not watch:
            break

        # 持续监控模式
        watch_interval = interval or global_cfg.get("interval", 3600)
        print(f"\n⏰ 下次检查: {watch_interval}s 后 (Ctrl+C 停止)")
        try:
            time.sleep(watch_interval)
        except KeyboardInterrupt:
            print("\n👋 已停止。")
            break

    return results

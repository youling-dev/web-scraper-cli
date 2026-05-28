# Changelog

## [1.3.0] - 2026-05-28

### Added
- ⚡ `--async` / `-A` — 异步并发抓取，多 URL 场景性能大幅提升
- ⚡ `--concurrency` / `-c` — 自定义并发数（默认 5）
- 📝 异步模式支持 sitemap、翻页、递归爬取
- 📝 新增 `httpx` 依赖（异步 HTTP 客户端）

### Technical
- 新增 `Scraper.async_fetch_one()` — 单 URL 异步抓取
- 新增 `Scraper.async_fetch_many()` — 批量并发抓取
- 新增 `Scraper.async_batch_scrape()` — 并发抓取 + CSS 选择器提取
- 新增 `Scraper.async_recursive_crawl()` — 异步递归爬取

### Examples
```bash
# Sitemap + 异步并发
wscraper https://example.com --sitemap --async
# 翻页 + 异步，并发 10
wscraper "https://example.com/p={page}" --pages 1-20 --async --concurrency 10
# 异步递归爬取
wscraper https://example.com --depth 2 --async
```

### Notes
- v0.3 路线图最后一项，至此 v0.3 全部完成
- 翻页 10 页场景从 ~30s 降至 ~3s（取决于并发数和网站响应速度）

## [1.2.0] - 2026-05-28

### Added
- ✨ `--unique` — 去重（按 text 字段）
- ✨ `--filter` — 过滤表达式 `field:op:value`，支持 contains, notcontains, eq, startswith, endswith, gt, lt
- ✨ `--field` — 只提取指定字段（如 text/url/price）
- 📝 过滤与去重支持组合使用，适用于递归爬取和常规抓取

### Examples
```bash
# 去重
wscraper https://example.com --select ".title" --unique
# 过滤包含关键词
wscraper https://example.com --select ".price,.name" --filter "text:contains:促销"
# 只提取 text 字段
wscraper https://example.com --select ".product" --field "text"
```

## [1.1.0] - 2026-05-28

### Added
- ✨ `--sitemap` — 从 sitemap.xml 自动发现并抓取所有页面 URL
- ✨ `--sitemap-url` — 指定自定义 sitemap URL（默认自动检测 `/sitemap.xml`）
- ✨ `--depth N` — 递归爬取，从入口页自动发现子页面（支持最大深度控制）
- ✨ `--same-domain` — 递归爬取时仅抓取同域名页面（默认开启）
- ✨ `--max-pages` — 限制 sitemap/递归爬取的最大页数
- 📝 sitemap index 递归展开支持

### Notes
- Sitemap 和递归爬取是本次心跳自由时间开发的第一个功能特性
- 基于 `docs/COMPETITIVE_ANALYSIS.md` 路线图 v0.3 优先级实现

## [1.0.0] - 2026-05-25

- Initial release
- CSS 选择器提取
- 链接提取
- 表格提取
- 代理支持
- 反检测（UA 轮换）
- 重试机制（指数退避）
- 翻页抓取（`{page}` 占位符）
- 定时抓取（间隔模式）
- JSON/CSV 输出

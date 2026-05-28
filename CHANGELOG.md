# Changelog

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

# Changelog

## [1.8.0] - 2026-05-29

### Added
- 💾 **HTTP 缓存层** — 自动缓存 GET 响应，减少重复请求
- 💾 `--cache` / `--no-cache` — 启用/禁用 HTTP 缓存
- 💾 `--cache-ttl` — 缓存默认 TTL（秒，默认 300）
- 💾 尊重 `Cache-Control` / `max-age` / `no-store` / `ETag` 头
- 💾 环境变量 `WSRAPPER_CACHE=true` 可全局启用缓存
- 💾 本地文件缓存，存于 `~/.cache/wscraper/`
- 💾 大幅降低对目标服务器的请求频率，提升重复抓取速度

### Usage
```bash
# 启用缓存（默认 TTL 5 分钟）
wscraper https://example.com --select ".title" --cache

# 自定义 TTL（30 分钟）
wscraper https://example.com --select ".title" --cache --cache-ttl 1800

# 显式禁用缓存
wscraper https://example.com --select ".title" --no-cache

# 环境变量全局启用
export WSCRAPER_CACHE=true
wscraper https://example.com --select ".title"
```

### Technical
- 新增 `cache.py` 模块 — `HTTPCache` 类
- `Scraper.__init__()` 新增 `cache` / `cache_ttl` 参数
- `Scraper.fetch()` 集成缓存命中/未命中逻辑
- 缓存键为 URL 的 SHA256 哈希
- 元数据（TTL、ETag、Last-Modified）与内容分离存储

---

## [1.7.0] - 2026-05-28

### Added
- 📋 **配置化任务** — YAML 配置文件驱动爬虫任务
- 📋 `wscraper run tasks.yml` — 运行配置文件中的全部任务
- 📋 `--task "名称"` — 只运行指定任务（支持模糊匹配）
- 📋 `--watch` / `-w` — 持续监控模式，循环运行所有任务
- 📋 `--interval` — 持续监控间隔（秒）
- 📋 全局配置 `global:` — 统一设置 timeout/delay/retries/proxy
- 📋 简单格式支持 — 无需 tasks 列表，单任务直接配置
- 📋 所有 scrape 参数均可在配置中使用（sitemap/depth/pages/async/filter 等）

### Usage
```bash
# 运行全部任务
wscraper run tasks.yml

# 只运行指定任务
wscraper run tasks.yml --task "竞品价格"

# 持续监控模式
wscraper run tasks.yml --watch --interval 3600
```

### Technical
- 新增 `config.py` 模块 — YAML 配置加载与任务执行引擎
- 新增 `pyyaml>=6.0` 依赖
- 新增 `examples/config-tasks.yml` 示例配置

---

## [1.6.0] - 2026-05-28

### Added
- 📬 **变更通知** — 检测到网页变更后自动推送通知
- 📬 Feishu 飞书通知 — `--notify '{"type": "feishu", "webhook": "..."}'`
- 📬 DingTalk 钉钉通知 — `--notify '{"type": "dingtalk", "webhook": "..."}'`
- 📬 Slack 通知 — `--notify '{"type": "slack", "webhook": "..."}'`
- 📬 通用 Webhook — `--notify '{"type": "webhook", "url": "..."}'`
- 📬 邮件通知 — `--notify '{"type": "email", ...}'`
- 📬 多渠道同时通知 — `--notify` 可多次指定
- 📬 持续监控模式支持通知 — `watch watch --notify ...`

### Technical
- 新增 `Notifier` 类 — 统一的通知发送接口
- `check_one()` / `check_all()` 新增 `on_change` 参数
- 通知结果实时打印（✅ 发送成功 / ❌ 失败原因）
- JSON 解析容错，支持简单 `type=url` 快捷格式

### Examples
```bash
# 飞书通知
wscraper watch check --notify '{"type": "feishu", "webhook": "https://open.feishu.cn/..."}'

# 多渠道
wscraper watch watch --notify '{"type": "feishu", "webhook": "..."}' --notify '{"type": "email", ...}'
```

### Notes
- v0.4 路线图最后一项，至此 v0.4 全部完成
- 与 watch 变更检测形成完整闭环：发现变更 → 推送通知 → 人工处理

## [1.5.0] - 2026-05-28

### Added
- 🔔 `watch add <url>` — 添加网页监控，支持自定义名称和 CSS 选择器
- 🔔 `watch check` — 一次性检查所有监控项的变更
- 🔔 `watch watch` — 持续监控模式（循环检查，Ctrl+C 停止）
- 🔔 `watch list` — 列出所有监控项及变更统计
- 🔔 `watch history --id N` — 查看指定监控项的变更历史
- 🔔 `watch remove --id N` — 删除监控项
- 💾 变更数据持久化存储在 SQLite（wscraper_watches.db）
- 📊 自动生成 unified diff 对比变更内容
- 📈 变更统计（+N 行 / -N 行）

### Technical
- 新增 `Watcher` 类 — 完整的监控生命周期管理
- SQLite 三表结构：watches（监控配置）、snapshots（历史快照）、changes（变更记录）
- SHA256 哈希比变检测（前 16 位）
- 支持 CSS 选择器定向监控（只监控页面指定区域）
- 内置 fallback fetch（requests + fake-useragent）

### Examples
```bash
# 添加监控
wscraper watch add https://example.com --name "首页" --select ".price" --interval 3600

# 检查变更
wscraper watch check

# 持续监控（每 30 分钟检查一次）
wscraper watch watch --interval 1800

# 查看监控列表
wscraper watch list

# 查看变更历史
wscraper watch history --id 1 --limit 10

# 删除监控
wscraper watch remove --id 1
```

### Notes
- v0.4 路线图第二项，与 SQLite 导出形成完整的数据追踪闭环
- 适用场景：价格监控、内容更新提醒、竞品追踪

## [1.4.0] - 2026-05-28

### Added
- 📊 `--markdown` / `-M` — Markdown 表格输出，直接用于文档和报告
- 💾 `--sqlite` / `-S` — SQLite 数据库导出，支持长期数据存储和查询
- 🏷️ `--table-name` — SQLite 表名自定义（默认: scraped）
- 📝 `--format markdown` — 新增 markdown 为可选输出格式
- 📝 SQLite 自动添加 `id` 自增主键和 `scraped_at` 时间戳

### Technical
- 新增 `Scraper.to_markdown()` — 数据转 Markdown 表格
- 新增 `Scraper.to_sqlite()` — 数据写入 SQLite，自动建表
- Markdown 单元格自动转义 `|` 符号、截断超长内容
- SQLite 支持增量追加（表不存在时自动创建）

### Examples
```bash
# Markdown 表格输出
wscraper https://example.com --select ".name,.price" --markdown
# Markdown 到文件
wscraper https://example.com --select ".title,.desc" -M -o report.md
# SQLite 导出
wscraper https://example.com --select ".product" -S products.db
# Markdown + SQLite 同时输出
wscraper https://example.com --select ".item" -M -o data.md -S data.db
```

### Notes
- v0.4 路线图第一项，数据导出能力增强
- Markdown 输出可直接嵌入飞书文档、GitHub README 等

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

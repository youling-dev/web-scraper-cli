# Changelog

## [2.0.0] - 2026-05-31

### Breaking
- 大版本升级，功能完整度大幅提升
- `setup.py` 重构，引入 `extras_require` 可选依赖分组

### Added
- ✅ **JS 渲染支持** — Playwright 驱动的 SPA 页面抓取（`wscraper/renderer.py`）
- ✅ `--render` — 启用 JS 渲染模式
- ✅ `--headless` / `--no-headless` — 无头/有头浏览器切换
- ✅ `--wait-for <selector>` — 等待指定选择器加载完成
- ✅ `--wait-until <strategy>` — 加载策略（load/networkidle/domcontentloaded）
- ✅ **Python API 模式** — `from wscraper import Scraper` 作为库使用
- ✅ `docs/API.md` — 完整 Python API 参考文档
- ✅ `MANIFEST.in` — 规范打包文件范围
- ✅ setup.py `extras_require`：`[render]`、`[test]`、`[dev]`

### Technical
- `Scraper.__init__()` 新增 `render_js`、`render_wait_for`、`render_wait_until` 参数
- `Scraper.fetch()` 自动切换渲染/普通抓取
- `renderer.py` 实现 `JSRenderer` 类（222 行），支持懒加载
- 新增 `tests/test_renderer.py`（10 个测试）
- 测试总数：126 个，全部通过

### Usage
```bash
# JS 渲染抓取
wscraper https://spa.example.com --render --select ".content"

# 等待特定元素加载
wscraper https://app.example.com --render --wait-for "#app-loaded"

# 作为 Python 库
from wscraper import Scraper
scraper = Scraper()
html = scraper.fetch("https://example.com")
results = scraper.parse(html, select="title, p")
```

---

## [1.9.0] - 2026-05-31

### Added
- ✅ **认证支持** — Basic Auth、Bearer Token、Cookie 注入（`wscraper/auth.py`）
- ✅ `--auth user:pass` — HTTP Basic 认证
- ✅ `--token <bearer>` — Bearer Token 认证
- ✅ `--cookie-jar <path>` — Netscape 格式 Cookie 文件
- ✅ `--cookie key=value` — 单个 Cookie 注入
- ✅ **测试套件** — 116 个单元测试，覆盖 auth、cache、robots、schema、scraper
- ✅ 使用 pytest，支持 CI 集成

### Fixed
- ✅ 修复 cache.py 中的潜在问题
- ✅ 修复 robots.py 路径匹配逻辑（`_url_matches` → `_path_matches`）
- ✅ 修复 RateLimiter 在 Python 3.10+ 的 `asyncio.get_event_loop()` 报错
- ✅ CLI 参数补全（认证相关）

### Usage
```bash
# Basic Auth
wscraper https://api.example.com --select ".data" --auth user:pass

# Bearer Token
wscraper https://api.example.com --select ".data" --token YOUR_TOKEN

# Cookie
wscraper https://example.com --select ".content" --cookie-jar cookies.txt
```

## [1.8.0] - 2026-05-30

### Added
- ✅ **JSON Schema 输出验证** — 自动校验抓取结果是否符合预期结构，防止网站改版导致数据断裂
- ✅ `--schema <path|json>` — JSON Schema 文件路径或 JSON 字符串
- ✅ `--schema-mode warn|filter|strict` — 验证模式（默认 warn：保留全部+警告）
- ✅ 支持标准 JSON Schema Draft 7 子集及简化语法
- ✅ **robots.txt 解析器** — 自动获取并遵守目标网站的 robots.txt 规则
- ✅ `--robotstxt` — 启用 robots.txt 检查
- ✅ **按域名限速** — Token bucket 算法，多域名独立限速
- ✅ `--rate-limit rpm=30,delay=2.0` — 配置每域名请求频率
- ✅ `--user-agent` — 自定义 User-Agent
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

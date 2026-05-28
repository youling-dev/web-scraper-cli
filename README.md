# 🕷️ Web Scraper CLI

> 一个轻量、实用的 Python 网页爬虫命令行工具。支持代理、定时、反检测、数据导出。

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/youling-dev/web-scraper-cli?style=social)](https://github.com/youling-dev/web-scraper-cli)

---

## ✨ 特点

- 🎯 **零配置** — 一条命令开始抓取
- 🔄 **定时抓取** — 自动定时刷新数据
- 🛡️ **反检测** — 随机 UA、延迟、代理支持
- 📊 **数据导出** — CSV / JSON / SQLite
- 📝 **结构化提取** — CSS 选择器 / XPath
- 🌐 **多页面** — 支持翻页、分页、sitemap、递归爬取

---

## 🚀 快速开始

```bash
# 安装
pip install web-scraper-cli

# 抓取单个页面
wscraper https://example.com --select ".title,.content"

# 导出 CSV
wscraper https://example.com/products --select ".price,.name" --format csv --output products.csv

# 定时抓取（每30分钟）
wscraper https://example.com --interval 30m

# 使用代理
wscraper https://example.com --proxy http://proxy:8080
```

---

## 📖 使用示例

### 基本抓取

```bash
# 提取标题
wscraper https://news.example.com --select "h1.title"

# 提取表格数据
wscraper https://data.example.com --select "table.data td" --format json
```

### 结果过滤与去重

```bash
# 去重（按 text 字段）
wscraper https://example.com --select ".title" --unique

# 过滤包含特定关键词的结果
wscraper https://example.com --select ".price,.name" --filter "text:contains:促销"

# 只提取指定字段
wscraper https://example.com --select ".product" --field "text"

# 组合使用
wscraper https://example.com --select ".item" --filter "text:notcontains:广告" --unique --field "text"
```

### 定时监控

```bash
# 每5分钟检查价格变化
wscraper https://shop.example.com/product/123 \
  --select ".price" \
  --interval 5m \
  --on-change "echo '价格变动！'" \
  --output price_history.csv
```

### 多页面抓取

```bash
# 翻页抓取前10页
wscraper "https://example.com/search?p={page}" \
  --pages 1-10 \
  --select ".item .title, .item .price" \
  --format csv \
  --output results.csv
```

### Sitemap 抓取

```bash
# 从 sitemap.xml 自动发现并抓取所有页面
wscraper https://example.com --sitemap

# 指定 sitemap URL
wscraper https://example.com --sitemap --sitemap-url https://example.com/custom-sitemap.xml

# 限制抓取页数
wscraper https://example.com --sitemap --max-pages 20 --select "h1"
```

### 递归爬取

```bash
# 从入口页开始递归爬取，深度为 2
wscraper https://example.com --depth 2

# 递归爬取并提取标题
wscraper https://example.com --depth 2 --select "h1.title" --max-pages 50
```

### 异步并发抓取

```bash
# 多 URL 并发抓取（默认并发数 5）
wscraper https://example.com --sitemap --async

# 自定义并发数
wscraper https://example.com --sitemap --async --concurrency 10

# 翻页抓取 + 异步
wscraper "https://example.com/search?p={page}" --pages 1-20 --async --select ".item"

# 异步递归爬取
wscraper https://example.com --depth 2 --async --max-pages 100
```

> 💡 `--async` 模式下，多个 URL 会并发抓取，大幅提升效率。翻页 10 页通常可从 ~30s 降至 ~3s。

### Markdown 表格输出

```bash
# Markdown 表格输出
wscraper https://example.com --select ".name,.price" --markdown

# 输出到文件
wscraper https://example.com --select ".title,.desc" -M -o report.md
```

> 💡 Markdown 输出可直接嵌入飞书文档、GitHub README、Notion 等。

### SQLite 数据库导出

```bash
# 导出到 SQLite
wscraper https://example.com --select ".product" -S products.db

# 自定义表名
wscraper https://example.com --select ".item" -S data.db --table-name items

# Markdown + SQLite 同时输出
wscraper https://example.com --select ".item" -M -o data.md -S data.db
```

> 💡 SQLite 自动创建表并添加 `id` 自增主键和 `scraped_at` 时间戳。支持增量追加。

### 🔔 网页变更监控

```bash
# 添加监控（默认每小时检查一次）
wscraper watch add https://shop.example.com/product/123 \
  --name "商品价格" --select ".price" --interval 3600

# 一次性检查所有监控项
wscraper watch check

# 持续监控模式（每 30 分钟检查，Ctrl+C 停止）
wscraper watch watch --interval 1800

# 列出所有监控项
wscraper watch list

# 查看变更历史
wscraper watch history --id 1 --limit 10

# 删除监控项
wscraper watch remove --id 1
```

> 💡 监控数据存储在 `wscraper_watches.db`（SQLite），支持持久化追踪。
> 变更检测基于 SHA256 哈希对比，自动生成 unified diff。

### 📬 变更通知

支持多种通知渠道，在检测到变更时自动推送：

```bash
# Feishu 飞书通知
wscraper watch check \
  --notify '{"type": "feishu", "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/..."}'

# DingTalk 钉钉通知
wscraper watch check \
  --notify '{"type": "dingtalk", "webhook": "https://oapi.dingtalk.com/robot/send?access_token=..."}'

# Slack 通知
wscraper watch check \
  --notify '{"type": "slack", "webhook": "https://hooks.slack.com/services/..."}'

# 通用 Webhook
wscraper watch check \
  --notify '{"type": "webhook", "url": "https://your-webhook.com/hook"}'

# 邮件通知
wscraper watch check \
  --notify '{"type": "email", "host": "smtp.qq.com", "port": 465, "user": "you@qq.com", "pass": "xxx", "to": "admin@example.com"}'

# 多渠道同时通知
wscraper watch watch --interval 1800 \
  --notify '{"type": "feishu", "webhook": "https://..."}' \
  --notify '{"type": "email", "host": "smtp.x", "port": 465, "user": "u@x", "pass": "p", "to": "v@x"}'
```

> 💡 `--notify` 参数可多次指定，每个监控项检测到变更时将按配置推送通知。
> 持续监控模式（`watch watch`）同样支持通知功能。

### 📋 配置化任务

使用 YAML 配置文件驱动爬虫任务，告别冗长的命令行参数：

```bash
# 运行配置文件中的所有任务
wscraper run tasks.yml

# 只运行指定名称的任务（模糊匹配）
wscraper run tasks.yml --task "竞品价格"

# 持续监控模式（循环运行所有任务）
wscraper run tasks.yml --watch --interval 3600
```

**配置文件示例 (`tasks.yml`)：**

```yaml
# 全局配置（可选）
global:
  timeout: 30
  delay: 2.0
  retries: 3

tasks:
  - name: "竞品价格监控"
    url: "https://shop.example.com/products"
    select: ".product-name,.price"
    format: csv
    output: "data/prices.csv"
    filter: "text:contains:元"
    unique: true

  - name: "新闻标题抓取"
    urls:
      - "https://news.example.com/tech"
      - "https://news.example.com/business"
    select: "h2.title"
    format: json
    output: "data/news.json"
    async: true
    concurrency: 5

  - name: "全站 sitemap 抓取"
    url: "https://example.com"
    sitemap: true
    select: "h1"
    max_pages: 50
    format: markdown
    output: "data/all_titles.md"
```

**支持的配置项（与 CLI 参数一一对应）：**

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `name` | 任务名称 | `"竞品监控"` |
| `url` / `urls` | 目标 URL（单个或列表） | `"https://..."` / `["url1", "url2"]` |
| `select` | CSS 选择器 | `".title,.price"` |
| `format` | 输出格式 | `json` / `csv` / `markdown` |
| `output` | 输出文件路径 | `"data/output.json"` |
| `async` | 异步并发 | `true` |
| `concurrency` | 并发数 | `10` |
| `sitemap` | 启用 sitemap | `true` |
| `depth` | 递归爬取深度 | `2` |
| `pages` | 翻页范围 | `"1-10"` |
| `filter` | 过滤表达式 | `"text:contains:促销"` |
| `unique` | 去重 | `true` |
| `field` | 指定字段 | `"text"` |
| `sqlite` | SQLite 导出路径 | `"data/db.sqlite"` |

> 💡 配置化任务适合定时调度（cron）、CI/CD 集成或批量管理多个爬虫任务。
> 完整示例见 `examples/config-tasks.yml`。

---

## 🔧 配置

配置文件 `~/.wscraper/config.json`：

```json
{
  "default_timeout": 30,
  "default_delay": 2,
  "user_agents": [],
  "proxies": [],
  "max_retries": 3
}
```

---

## 📂 项目结构

```
web-scraper-cli/
├── wscraper/
│   ├── cli.py          # 命令行入口
│   ├── scraper.py      # 核心抓取逻辑
│   ├── extractor.py    # 数据提取（CSS/XPath）
│   ├── scheduler.py    # 定时调度
│   ├── proxy.py        # 代理管理
│   └── export.py       # 数据导出（CSV/JSON/SQLite）
├── tests/
├── examples/
│   ├── price_monitor.py
│   ├── news_scraper.py
│   └── sitemap_crawler.py
├── requirements.txt
└── README.md
```

---

## 🛡️ 反检测策略

- 随机 User-Agent 轮换
- 随机请求延迟
- 代理池支持
- 请求频率控制
- Cookie 保持

---


## 💖 支持项目

如果你觉得这个工具对你有帮助，欢迎打赏支持开源：

<p align="center">
  <img src="assets/alipay_qrcode.jpg" alt="支付宝收款码" width="220" />
  <br />
  <sub>扫码支持有灵 ✨</sub>
</p>

## 📜 License

MIT License

---

## 🙋 贡献

欢迎提交 Issue 和 Pull Request！

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/youling-dev">有灵</a> ✨</sub>
</p>

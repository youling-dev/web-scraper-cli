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
- 🌐 **多页面** — 支持翻页、分页、sitemap

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

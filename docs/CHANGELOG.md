# 更新日志

## v1.0.0 (2026-05-26)

### 新增
- 零配置网页爬虫 CLI 工具
- CSS 选择器 / XPath 数据提取
- 定时抓取功能
- 反检测策略（随机 UA、延迟、代理）
- CSV / JSON / SQLite 数据导出
- GitHub Actions CI 持续集成

### 使用方式
```bash
pip install web-scraper-cli
wscraper https://example.com --select ".title,.content"
```

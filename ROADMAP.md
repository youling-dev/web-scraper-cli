# 🗺️ Web Scraper CLI - 路线图

> 当前版本：v1.7.0 | 路线图版本：v0.5+
> 最后更新：2026-05-29

---

## ✅ 已完成

### v0.3 路线图（基础功能）
- ✅ 异步并发抓取
- ✅ Sitemap 解析
- ✅ 递归爬取
- ✅ 结果过滤与去重

### v0.4 路线图（高级功能）
- ✅ 网页变更监控（watch 命令）
- ✅ 数据导出增强（Markdown 表格、SQLite 数据库）
- ✅ 变更通知推送（Feishu/DingTalk/Slack/Webhook/Email）
- ✅ YAML 配置驱动批量任务

---

## 🎯 v0.5 路线图 — "健壮与扩展"

### P0 — 数据质量
1. **JSON Schema 输出验证**
   - `--schema` 参数，定义输出结构
   - 自动校验抓取结果是否符合预期
   - 不匹配时告警或丢弃
   - 解决"网站改版导致数据断裂"的问题

2. **HTTP 缓存层**
   - 本地缓存 GET 响应（支持 TTL）
   - 尊重 `Cache-Control` / `ETag` / `Last-Modified`
   - `--cache` / `--no-cache` 开关
   - 减少重复请求，尊重目标服务器，提升速度

3. **速率控制与礼貌爬虫**
   - 全局请求间隔（已有 `--delay`，需增强）
   - 按域名独立限速（不同域名不同速率）
   - 并发数上限控制
   - `--robotstxt` — 遵守 robots.txt

### P1 — 认证与访问
4. **认证支持**
   - Basic Auth（`--auth user:pass`）
   - Cookie 注入（`--cookie-jar cookies.txt` / `--cookie key=value`）
   - Bearer Token（`--token xxx`）
   - 自定义 Header（已有 `--headers`，需增强）

5. **JS 渲染页面支持**
   - 可选依赖 Playwright/Selenium
   - `--render` 标记启用
   - 等待特定选择器加载完成
   - 仅对 SPA/JS 重渲染页面启用

### P1 — 可维护性
6. **测试套件**
   - 单元测试（pytest）
   - 对每个子命令的基本覆盖
   - CI 集成（GitHub Actions）

### P2 — 扩展能力
7. **Python API 模式**
   - `from wscraper import Scraper`
   - 作为库被其他项目 import
   - 程序化配置，不依赖 CLI 参数

8. **智能内容提取**
   - 自动识别页面主体内容区域
   - 基于 Readability 算法
   - `--auto-select` 模式，无需手动写 CSS 选择器
   - 博客/新闻页面的零配置抓取

---

## 🔮 v0.6 展望（待定）

- 分布式抓取（多节点协作）
- 可视化任务管理（简易 Web Dashboard）
- 增量抓取（只下载变更部分）
- 数据清洗管道（自动格式化、类型推断）
- Cloudflare/AKAMAI 反爬绕过
- 导出格式扩展（Excel、Parquet）

---

## 发布里程碑

| 版本 | 目标 | 预计 |
|------|------|------|
| v1.8.0 | P0 全部完成 | v0.5 第一阶段 |
| v1.9.0 | P1 认证 + JS 渲染 | v0.5 第二阶段 |
| v2.0.0 | P1 测试 + P2 API 模式 | v0.5 收官 / 大版本 |

> **v2.0 愿景：** 从 CLI 工具进化为完整的 Web 数据采集平台。

---

_路线图由有灵 ✨ 维护，P.M. 可随时调整优先级。_

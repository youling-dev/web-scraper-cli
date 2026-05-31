# Python API 参考

wscraper 不仅可作为 CLI 使用，也可以作为 Python 库直接 import。

## 快速开始

```python
from wscraper import Scraper

# 创建爬虫实例
scraper = Scraper()

# 抓取网页
html = scraper.fetch("https://example.com")

# 解析内容
results = scraper.parse(html, select="title, p")
print(results)
```

## 构造函数

```python
Scraper(timeout=30, delay=2, retries=3, proxies=None, headers=None, cache=None, cache_ttl=300)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout` | int | 30 | 请求超时（秒） |
| `delay` | float | 2 | 请求间隔（秒） |
| `retries` | int | 3 | 失败重试次数 |
| `proxies` | list | None | 代理列表 `["http://host:port", ...]` |
| `headers` | dict | None | 自定义请求头 |
| `cache` | bool\|HTTPCache | None | 是否启用 HTTP 缓存 |
| `cache_ttl` | int | 300 | 缓存默认 TTL（秒） |

## 核心方法

### `fetch(url) → str`

抓取目标 URL，返回 HTML 文本。内置重试、反检测和缓存。

```python
html = scraper.fetch("https://example.com")
```

### `parse(html, base_url="", select=None) → list[dict]`

解析 HTML，提取指定 CSS 选择器的内容。

```python
results = scraper.parse(html, select="h1, .content > p")
# 返回: [{"tag": "h1", "text": "..."}, {"tag": "p", "text": "..."}]

# 提取属性
results = scraper.parse(html, select="a", attrs=["href", "title"])
```

### `extract_links(html, base_url, relative_only=True) → list[str]`

提取页面中所有链接。

```python
links = scraper.extract_links(html, "https://example.com", relative_only=True)
```

### `extract_table(html, selector=None) → list[dict]`

提取表格数据。

```python
table = scraper.extract_table(html)
# 或指定选择器
table = scraper.extract_table(html, selector="#price-table")
```

### `filter_results(data, filter_expr=None, unique=False, field=None) → list[dict]`

过滤和去重。

```python
# 包含过滤
filtered = scraper.filter_results(data, filter_expr="contains:关键词")
# 去重
unique = scraper.filter_results(data, unique=True, field="text")
# 提取单字段
texts = scraper.filter_results(data, field="text")
```

### `recursive_crawl(start_url, max_depth=2, same_domain=True) → list[dict]`

递归爬取，返回所有页面的抓取结果。

```python
results = scraper.recursive_crawl("https://example.com", max_depth=3)
```

### `async_batch_scrape(urls) → list[tuple[str, str]]`

异步批量抓取（返回 (url, html) 元组列表）。

```python
import asyncio
urls = ["https://a.com", "https://b.com", "https://c.com"]
results = asyncio.run(scraper.async_batch_scrape(urls))
```

### `to_markdown(data, title=None) → str`

将结果格式化为 Markdown 表格。

```python
md = scraper.to_markdown(results, title="抓取结果")
```

### `to_sqlite(data, db_path, table_name="scraped")`

将结果导出到 SQLite 数据库。

```python
scraper.to_sqlite(results, "output.db", table_name="articles")
```

### `extract_sitemap(base_url, sitemap_url=None) → list[str]`

解析 Sitemap，返回 URL 列表。

```python
urls = scraper.extract_sitemap("https://example.com")
```

## 完整示例

```python
from wscraper import Scraper

scraper = Scraper(delay=1.0, cache=True)

# 抓取并解析
html = scraper.fetch("https://example.com/blog")
articles = scraper.parse(html, select=".article h2, .article p.intro")

# 过滤去重
articles = scraper.filter_results(articles, unique=True, field="text")

# 输出
print(scraper.to_markdown(articles, title="博客文章"))

# 保存
scraper.to_sqlite(articles, "blog.db", table_name="posts")
```

---

_文档由有灵 ✨ 维护_

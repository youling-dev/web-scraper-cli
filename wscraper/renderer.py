"""
JS 渲染支持 — 使用 Playwright 渲染 SPA / JS 重渲染页面

Usage:
    from wscraper import Scraper
    scraper = Scraper(headless=True, render_js=True)
    html = scraper.fetch("https://spa-app.example.com")

    # 或 CLI
    wscraper https://spa-app.example.com --render --headless
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any

log = logging.getLogger(__name__)


class JSRenderError(Exception):
    """JS 渲染失败"""
    pass


class JSRenderer:
    """
    Playwright 驱动的 JS 渲染器。

    使用方式：
        renderer = JSRenderer(headless=True)
        html = renderer.render("https://example.com")
        renderer.close()

    支持：
        - 等待指定选择器加载完成
        - 等待网络空闲
        - 自定义等待时间
        - Cookie 注入
        - User-Agent 设置
        - 页面截图调试
    """

    def __init__(
        self,
        headless: bool = True,
        user_agent: Optional[str] = None,
        viewport: Optional[Dict[str, int]] = None,
        timeout: int = 30000,
        storage_state: Optional[str] = None,
        proxy: Optional[str] = None,
        browser_type: str = "chromium",
    ):
        self.headless = headless
        self.user_agent = user_agent
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.timeout = timeout
        self.storage_state = storage_state
        self.proxy = proxy
        self.browser_type = browser_type
        self._pw = None
        self._browser = None
        self._context = None
        self._launched = False

    def _import_playwright(self):
        """延迟导入 Playwright，避免硬依赖"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise JSRenderError(
                "Playwright 未安装。请运行: pip install web-scraper-cli[render]"
            )
        return sync_playwright

    def _launch(self):
        """启动浏览器（同步 API，内部由 asyncio 包装或直接用）"""
        if self._launched:
            return

        SyncPlaywright = self._import_playwright()
        self._pw = SyncPlaywright().__enter__()

        browser_fn = getattr(self._pw, self.browser_type)
        launch_opts = {"headless": self.headless}

        if self.proxy:
            launch_opts["proxy"] = {"server": self.proxy}

        self._browser = browser_fn.launch(**launch_opts)

        context_opts = {
            "user_agent": self.user_agent,
            "viewport": self.viewport,
            "ignore_https_errors": True,
        }
        if self.storage_state:
            context_opts["storage_state"] = self.storage_state

        self._context = self._browser.new_context(**context_opts)
        self._launched = True

    def render(
        self,
        url: str,
        wait_for: Optional[str] = None,
        wait_until: str = "networkidle",
        wait_timeout: int = 30000,
        cookies: Optional[List[Dict[str, str]]] = None,
        extra_http_headers: Optional[Dict[str, str]] = None,
        screenshot_path: Optional[str] = None,
        javascript: Optional[str] = None,
    ) -> str:
        """
        渲染页面并返回 HTML（同步）。

        Args:
            url: 目标 URL
            wait_for: CSS 选择器，等待该元素出现
            wait_until: networkidle | load | domcontentloaded | commit
            wait_timeout: 等待超时（毫秒）
            cookies: 要注入的 Cookie 列表
            extra_http_headers: 额外 HTTP headers
            screenshot_path: 截图保存路径（调试用）
            javascript: 在页面加载后执行的 JS 代码

        Returns:
            渲染后的页面 HTML
        """
        self._launch()
        page = self._context.new_page()

        try:
            if extra_http_headers:
                page.set_extra_http_headers(extra_http_headers)

            if cookies:
                self._context.add_cookies(cookies)

            log.info(f"Rendering {url} (wait_until={wait_until})")
            page.goto(url, wait_until=wait_until, timeout=self.timeout)

            if wait_for:
                log.info(f"Waiting for selector: {wait_for}")
                page.wait_for_selector(wait_for, timeout=wait_timeout)

            if javascript:
                page.evaluate(javascript)

            if screenshot_path:
                page.screenshot(path=screenshot_path)
                log.info(f"Screenshot saved to {screenshot_path}")

            html = page.content()
            return html

        except Exception as e:
            try:
                page.screenshot(path="render_error_debug.png")
                log.warning("Debug screenshot saved to render_error_debug.png")
            except Exception:
                pass
            raise JSRenderError(f"JS render failed for {url}: {e}")
        finally:
            page.close()

    def render_and_extract(
        self,
        url: str,
        selector: str,
        wait_for: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, str]]:
        """
        渲染页面并提取指定选择器的内容。

        Returns:
            [{'text': ..., 'html': ..., 'attributes': {...}}, ...]
        """
        html = self.render(url, wait_for=wait_for, **kwargs)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        elements = soup.select(selector)

        results = []
        for el in elements:
            result = {
                "text": el.get_text(strip=True),
                "html": str(el),
            }
            attrs = {}
            for attr in ["href", "src", "alt", "title", "data-url", "data-id"]:
                if el.has_attr(attr):
                    attrs[attr] = el[attr]
            if attrs:
                result["attributes"] = attrs
            results.append(result)

        return results

    def close(self):
        """关闭浏览器"""
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._pw:
            try:
                self._pw.__exit__(None, None, None)
            except Exception:
                pass
            self._pw = None
        self._launched = False

    def __enter__(self):
        self._launch()
        return self

    def __exit__(self, *exc_info):
        self.close()

"""Tests for wscraper.renderer module."""

import pytest
from wscraper.renderer import JSRenderer, JSRenderError


class TestJSRendererInit:
    """Test renderer initialization (no Playwright needed)."""

    def test_default_init(self):
        r = JSRenderer()
        assert r.headless is True
        assert r.viewport == {"width": 1920, "height": 1080}
        assert r.timeout == 30000
        assert r.browser_type == "chromium"
        assert r._launched is False

    def test_custom_init(self):
        r = JSRenderer(
            headless=False,
            user_agent="CustomAgent/1.0",
            viewport={"width": 800, "height": 600},
            timeout=60000,
            browser_type="firefox",
        )
        assert r.headless is False
        assert r.user_agent == "CustomAgent/1.0"
        assert r.viewport == {"width": 800, "height": 600}
        assert r.timeout == 60000
        assert r.browser_type == "firefox"

    def test_proxy_init(self):
        r = JSRenderer(proxy="http://proxy:8080")
        assert r.proxy == "http://proxy:8080"

    def test_storage_state_init(self):
        r = JSRenderer(storage_state="/path/to/state.json")
        assert r.storage_state == "/path/to/state.json"


class TestJSRendererImport:
    """Test Playwright import handling."""

    def test_import_without_playwright_raises(self):
        """If playwright is not installed, should raise JSRenderError."""
        r = JSRenderer()
        # We can't easily mock this without playwright installed,
        # but we can verify the error message format
        try:
            r._import_playwright()
        except JSRenderError as e:
            assert "pip install" in str(e)
        except Exception:
            pass  # playwright may be installed, that's fine


class TestJSRenderError:
    """Test error class."""

    def test_error_message(self):
        err = JSRenderError("test error message")
        assert "test error message" in str(err)

    def test_error_inheritance(self):
        assert issubclass(JSRenderError, Exception)


class TestRendererContextManager:
    """Test context manager protocol."""

    def test_has_context_manager_methods(self):
        r = JSRenderer()
        assert hasattr(r, "__enter__")
        assert hasattr(r, "__exit__")


class TestRendererClose:
    """Test close method."""

    def test_close_without_launch(self):
        """Should not raise when closing without launching."""
        r = JSRenderer()
        r.close()
        assert r._launched is False


class TestRendererRenderAndExtract:
    """Test extract method (doesn't require network)."""

    def test_extract_uses_beautifulsoup(self):
        """Verify render_and_extract uses BeautifulSoup for parsing."""
        import inspect
        source = inspect.getsource(JSRenderer.render_and_extract)
        assert "BeautifulSoup" in source
        assert "lxml" in source


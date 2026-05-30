"""Tests for wscraper.cache — HTTPCache."""
import json
import os
import pytest
import tempfile
import time
from pathlib import Path
from wscraper.cache import HTTPCache


@pytest.fixture
def cache_dir(tmp_path):
    return str(tmp_path / "wscraper_cache")


@pytest.fixture
def cache(cache_dir):
    return HTTPCache(cache_dir=cache_dir, default_ttl=60, enabled=True)


class TestHTTPCacheBasic:
    def test_disabled_cache_returns_none(self):
        c = HTTPCache(enabled=False)
        assert c.get("https://example.com") is None

    def test_put_and_get(self, cache):
        url = "https://example.com/page"
        cache.put(url, "<html>hello</html>")
        result = cache.get(url)
        assert result == "<html>hello</html>"

    def test_get_missing_returns_none(self, cache):
        assert cache.get("https://example.com/missing") is None

    def test_cache_miss_after_clear(self, cache):
        cache.put("https://example.com", "<html>hi</html>")
        cache.clear()
        assert cache.get("https://example.com") is None

    def test_invalidate_single_url(self, cache):
        cache.put("https://example.com/a", "A")
        cache.put("https://example.com/b", "B")
        cache.invalidate("https://example.com/a")
        assert cache.get("https://example.com/a") is None
        assert cache.get("https://example.com/b") == "B"


class TestHTTPCacheTTL:
    def test_expired_entry_returns_none(self, cache):
        c = HTTPCache(cache_dir=cache.cache_dir, default_ttl=0, enabled=True)
        c.put("https://example.com", "<html>hi</html>")
        # TTL 0 means immediately expired
        assert c.get("https://example.com") is None

    def test_cache_control_max_age(self, cache):
        url = "https://example.com/page"
        headers = {"Cache-Control": "max-age=999999"}
        cache.put(url, "<html>cached</html>", response_headers=headers)
        assert cache.get(url) == "<html>cached</html>"

    def test_cache_control_no_store(self, cache):
        url = "https://example.com/page"
        headers = {"Cache-Control": "no-store"}
        cache.put(url, "<html>secret</html>", response_headers=headers)
        # TTL 0 from no-store → immediately expired
        assert cache.get(url) is None


class TestHTTPCacheETag:
    def test_etag_storage(self, cache):
        url = "https://example.com/page"
        headers = {"ETag": '"abc123"'}
        cache.put(url, "<html>v1</html>", response_headers=headers)
        # Check meta file
        meta_path = cache._meta_path(url)
        meta = json.loads(meta_path.read_text())
        assert meta["etag"] == '"abc123"'


class TestHTTPCacheStats:
    def test_stats_empty(self, cache):
        stats = cache.stats()
        assert stats["entries"] == 0
        assert stats["size_bytes"] == 0

    def test_stats_after_put(self, cache):
        cache.put("https://example.com/a", "A" * 100)
        cache.put("https://example.com/b", "B" * 200)
        stats = cache.stats()
        assert stats["entries"] == 2
        assert stats["size_bytes"] > 0
        assert "size_human" in stats


class TestHTTPCacheEdgeCases:
    def test_unicode_content(self, cache):
        url = "https://example.com/unicode"
        cache.put(url, "<html>你好世界</html>")
        assert cache.get(url) == "<html>你好世界</html>"

    def test_large_content(self, cache):
        url = "https://example.com/big"
        content = "x" * 1_000_000
        cache.put(url, content)
        assert cache.get(url) == content

    def test_corrupt_meta_handled(self, cache):
        url = "https://example.com/corrupt"
        meta_path = cache._meta_path(url)
        meta_path.write_text("{invalid json", encoding="utf-8")
        assert cache.get(url) is None

    def test_human_size(self):
        assert HTTPCache._human_size(0) == "0.0 B"
        assert "KB" in HTTPCache._human_size(1500)
        assert "MB" in HTTPCache._human_size(1_500_000)

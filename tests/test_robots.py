"""Tests for wscraper.robots — RobotsParser and RateLimiter."""
import pytest
import time
import asyncio
from wscraper.robots import RobotsParser, RateLimiter


class TestRobotsParserBasic:
    def test_empty_parser_is_permissive(self):
        r = RobotsParser()
        assert r.is_permissive is True
        assert r.is_allowed("https://example.com/anything") is True

    def test_parse_basic_disallow(self):
        txt = """User-agent: *
Disallow: /admin
Allow: /
"""
        r = RobotsParser.from_text(txt)
        assert r.is_permissive is False
        assert r.is_allowed("https://example.com/page") is True
        assert r.is_allowed("https://example.com/admin") is False
        assert r.is_allowed("https://example.com/admin/settings") is False

    def test_parse_allow_overrides_disallow(self):
        """Longest matching rule wins; Allow >= Disallow in length means allowed."""
        txt = """User-agent: *
Disallow: /files
Allow: /files/public
"""
        r = RobotsParser.from_text(txt)
        assert r.is_allowed("https://example.com/files/private") is False
        assert r.is_allowed("https://example.com/files/public") is True

    def test_parse_crawl_delay(self):
        txt = """User-agent: *
Crawl-delay: 5
Disallow:
"""
        r = RobotsParser.from_text(txt)
        assert r.crawl_delay == 5.0

    def test_parse_comments_ignored(self):
        txt = """# This is a comment
User-agent: *
Disallow: /private  # private area
"""
        r = RobotsParser.from_text(txt)
        assert r.is_allowed("https://example.com/private") is False

    def test_empty_disallow_allows_all(self):
        txt = """User-agent: *
Disallow:
"""
        r = RobotsParser.from_text(txt)
        assert r.is_allowed("https://example.com/anything") is True


class TestRobotsParserWildcards:
    def test_wildcard_disallow(self):
        txt = """User-agent: *
Disallow: /*.pdf$
"""
        r = RobotsParser.from_text(txt)
        assert r.is_allowed("https://example.com/doc.pdf") is False
        assert r.is_allowed("https://example.com/page.html") is True

    def test_wildcard_in_path(self):
        txt = """User-agent: *
Disallow: /search?*
"""
        r = RobotsParser.from_text(txt)
        assert r.is_allowed("https://example.com/search?q=test") is False
        assert r.is_allowed("https://example.com/page") is True


class TestRobotsParserUserAgent:
    def test_specific_user_agent(self):
        txt = """User-agent: Googlebot
Disallow:

User-agent: *
Disallow: /private
"""
        r = RobotsParser.from_text(txt)
        # Googlebot should be allowed everywhere
        assert r.is_allowed("https://example.com/private", user_agent="Googlebot") is True
        # Default user agent should be blocked from /private
        assert r.is_allowed("https://example.com/private", user_agent="wscraper") is False

    def test_wildcard_user_agent(self):
        txt = """User-agent: *
Disallow: /blocked
"""
        r = RobotsParser.from_text(txt)
        assert r.is_allowed("https://example.com/blocked", user_agent="anything") is False


class TestRobotsParserFetch:
    def test_fetch_returns_permissive_on_failure(self):
        r = RobotsParser.fetch("https://nonexistent-domain-xyz123.com/", timeout=2)
        assert r.is_permissive is True


class TestRateLimiterBasic:
    def test_new_domain_returns_zero_wait(self):
        rl = RateLimiter(default_delay=1.0, default_rpm=60)
        assert rl.wait_time("https://example.com/page") == 0

    def test_records_request(self):
        rl = RateLimiter(default_delay=0.01, default_rpm=60)
        rl.record_request("https://example.com/page")
        stats = rl.get_stats()
        assert "example.com" in stats
        assert stats["example.com"]["requests_last_minute"] == 1

    def test_different_domains_independent(self):
        rl = RateLimiter(default_delay=0.01, default_rpm=60)
        rl.record_request("https://example.com/a")
        rl.record_request("https://other.com/b")
        stats = rl.get_stats()
        assert stats["example.com"]["requests_last_minute"] == 1
        assert stats["other.com"]["requests_last_minute"] == 1

    def test_set_rate(self):
        rl = RateLimiter(default_delay=2.0, default_rpm=30)
        rl.set_rate("example.com", requests_per_minute=10, delay_range=(0.5, 1.5))
        stats = rl.get_stats()
        assert "example.com" in stats
        assert stats["example.com"]["rpm_limit"] == 10

    def test_rpm_limit(self):
        rl = RateLimiter(default_delay=0.0, default_rpm=3)
        for i in range(3):
            rl.record_request(f"https://example.com/page{i}")
        # Should need to wait
        wait = rl.wait_time("https://example.com/page3")
        assert wait > 0

    def test_stats_format(self):
        rl = RateLimiter(default_delay=0.01, default_rpm=60)
        rl.record_request("https://example.com/a")
        stats = rl.get_stats()
        entry = stats["example.com"]
        assert "requests_last_minute" in entry
        assert "rpm_limit" in entry
        assert "remaining" in entry
        assert "last_request_ago" in entry


class TestRateLimiterAsync:
    @pytest.mark.asyncio
    async def test_async_acquire(self):
        rl = RateLimiter(default_delay=0.01, default_rpm=60)
        await rl.async_acquire("https://example.com/test")
        stats = rl.get_stats()
        assert stats["example.com"]["requests_last_minute"] == 1

    @pytest.mark.asyncio
    async def test_async_wait_time(self):
        rl = RateLimiter(default_delay=0.01, default_rpm=60)
        wait = await rl.async_wait_time("https://example.com/new")
        assert wait == 0

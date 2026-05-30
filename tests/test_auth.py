"""Tests for wscraper.auth module (v1.9.0)."""

import pytest
import time
import tempfile
import os
from wscraper.auth import BasicAuth, BearerToken, CookieJar, AuthManager


class TestBasicAuth:
    def test_to_headers_basic(self):
        auth = BasicAuth("user", "pass")
        headers = auth.to_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        token = headers["Authorization"].split(" ")[1]
        import base64
        decoded = base64.b64decode(token).decode("ascii")
        assert decoded == "user:pass"

    def test_empty_password(self):
        auth = BasicAuth("user", "")
        headers = auth.to_headers()
        token = headers["Authorization"].split(" ")[1]
        import base64
        decoded = base64.b64decode(token).decode("ascii")
        assert decoded == "user:"

    def test_to_requests_auth(self):
        auth = BasicAuth("user", "pass")
        assert auth.to_requests_auth() == ("user", "pass")

    def test_to_httpx_auth(self):
        auth = BasicAuth("user", "pass")
        h = auth.to_httpx_auth()
        assert h is not None


class TestBearerToken:
    def test_bearer(self):
        auth = BearerToken("abc123")
        headers = auth.to_headers()
        assert headers["Authorization"] == "Bearer abc123"

    def test_custom_prefix(self):
        auth = BearerToken("xyz", prefix="Token")
        headers = auth.to_headers()
        assert headers["Authorization"] == "Token xyz"


class TestCookieJar:
    def test_add_single(self):
        jar = CookieJar()
        jar.add("session", "abc123", domain="example.com")
        assert len(jar.cookies) == 1
        assert jar.cookies[0]["name"] == "session"

    def test_add_many(self):
        jar = CookieJar()
        jar.add_many([("a", "1"), ("b", "2")], domain="test.com")
        assert len(jar.cookies) == 2

    def test_get_for_url_match(self):
        jar = CookieJar()
        jar.add("sid", "xyz", domain="example.com", path="/")
        cookies = jar.get_for_url("https://example.com/page")
        assert cookies["sid"] == "xyz"

    def test_get_for_url_no_match(self):
        jar = CookieJar()
        jar.add("sid", "xyz", domain="other.com", path="/")
        cookies = jar.get_for_url("https://example.com/page")
        assert cookies == {}

    def test_subdomain_match(self):
        jar = CookieJar()
        jar.add("sid", "xyz", domain=".example.com", path="/")
        cookies = jar.get_for_url("https://www.example.com/page")
        assert cookies["sid"] == "xyz"

    def test_expired_cookie_skipped(self):
        jar = CookieJar()
        jar.add("old", "123", domain="example.com", path="/")
        jar.cookies[0]["expires"] = int(time.time()) - 100
        cookies = jar.get_for_url("https://example.com/page")
        assert cookies == {}

    def test_load_netscape(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text(
            "# Netscape HTTP Cookie File\n"
            "example.com\tFALSE\t/\tFALSE\t1800000000\tsession\tabc123\n"
            "example.com\tFALSE\t/\tFALSE\t1800000000\tuser\tjohn\n"
        )
        jar = CookieJar()
        jar.load_netscape(str(cookie_file))
        assert len(jar.cookies) == 2
        assert jar.cookies[0]["name"] == "session"

    def test_load_netscape_expired_skipped(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        expired = int(time.time()) - 1000
        cookie_file.write_text(
            f"example.com\tFALSE\t/\tFALSE\t{expired}\told\tgone\n"
            "example.com\tFALSE\t/\tFALSE\t1800000000\tfresh\talive\n"
        )
        jar = CookieJar()
        jar.load_netscape(str(cookie_file))
        assert len(jar.cookies) == 1
        assert jar.cookies[0]["name"] == "fresh"

    def test_file_not_found(self):
        jar = CookieJar()
        with pytest.raises(FileNotFoundError):
            jar.load_netscape("/nonexistent/cookies.txt")

    def test_to_headers(self):
        jar = CookieJar()
        jar.add("a", "1")
        jar.add("b", "2")
        headers = jar.to_headers()
        assert "Cookie" in headers
        assert "a=1" in headers["Cookie"]
        assert "b=2" in headers["Cookie"]


class TestAuthManager:
    def test_combined(self):
        am = AuthManager()
        am.set_basic("user", "pass")
        am.set_bearer("token123")
        am.add_header("X-Custom", "value")
        headers = am.get_headers()
        assert "Authorization" in headers
        assert "X-Custom" in headers
        assert headers["X-Custom"] == "value"

    def test_basic_only(self):
        am = AuthManager()
        am.set_basic("admin", "secret")
        headers = am.get_headers()
        assert headers["Authorization"].startswith("Basic ")

    def test_bearer_only(self):
        am = AuthManager()
        am.set_bearer("ghp_xxx")
        headers = am.get_headers()
        assert "Bearer ghp_xxx" in headers["Authorization"]

    def test_chain(self):
        am = (AuthManager()
              .set_basic("u", "p")
              .add_header("X-Foo", "bar"))
        assert am.basic is not None
        assert am.extra_headers["X-Foo"] == "bar"

    def test_requests_auth_basic(self):
        am = AuthManager()
        am.set_basic("u", "p")
        assert am.get_requests_auth() == ("u", "p")

    def test_requests_auth_none(self):
        am = AuthManager()
        assert am.get_requests_auth() is None

    def test_requests_cookies(self):
        am = AuthManager()
        am.set_cookies_from_pairs([("sid", "123")], domain="example.com")
        cookies = am.get_requests_cookies("https://example.com/")
        assert cookies["sid"] == "123"

    def test_cookies_from_file(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text(
            "example.com\tFALSE\t/\tFALSE\t1800000000\ttest\tval\n"
        )
        am = AuthManager()
        am.set_cookies_from_file(str(cookie_file))
        assert am.cookies is not None
        assert len(am.cookies.cookies) == 1

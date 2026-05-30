"""
Authentication helpers for wscraper (v1.9.0).

Supports:
- Basic Auth (user:pass)
- Bearer Token
- Cookie injection (Netscape cookie jar or key=value pairs)
- Session cookie persistence
"""

import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse


class BasicAuth:
    """HTTP Basic Authentication.

    Usage:
        auth = BasicAuth("user", "pass")
        headers = auth.to_headers()
        # or: auth.to_requests_auth() for requests.Session.auth
    """

    def __init__(self, username: str, password: str = ""):
        self.username = username
        self.password = password

    def to_headers(self) -> dict:
        import base64
        creds = f"{self.username}:{self.password}"
        token = base64.b64encode(creds.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def to_requests_auth(self):
        """Return tuple for requests.auth."""
        return (self.username, self.password)

    def to_httpx_auth(self):
        """Return httpx.BasicAuth instance."""
        import httpx
        return httpx.BasicAuth(self.username, self.password)


class BearerToken:
    """Bearer Token authentication.

    Usage:
        auth = BearerToken("ghp_xxxxx")
        headers = auth.to_headers()
    """

    def __init__(self, token: str, prefix: str = "Bearer"):
        self.token = token
        self.prefix = prefix

    def to_headers(self) -> dict:
        return {"Authorization": f"{self.prefix} {self.token}"}


class CookieJar:
    """Cookie management supporting Netscape cookie jar format and simple key=value pairs.

    Supports:
    - Loading from Netscape/Mozilla cookie file
    - Adding individual cookies
    - Exporting as dict for requests headers
    - Exporting as httpx Cookies object
    """

    # Netscape cookie file format:
    # # Netscape HTTP Cookie File
    # domain	flag	path	secure	expires	name	value

    def __init__(self):
        self.cookies: list[dict] = []

    def add(self, name: str, value: str, domain: str = "", path: str = "/") -> None:
        """Add a single cookie."""
        self.cookies.append({
            "domain": domain,
            "path": path,
            "name": name,
            "value": value,
            "secure": False,
            "expires": 0,
        })

    def add_many(self, pairs: list[tuple[str, str]], domain: str = "") -> None:
        """Add multiple cookies from (name, value) pairs."""
        for name, value in pairs:
            self.add(name, value, domain)

    def load_netscape(self, filepath: str) -> None:
        """Load cookies from a Netscape/Mozilla cookie jar file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Cookie jar not found: {filepath}")

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                # Skip old-style cookie files (no domain flag column)
                if len(parts) == 6:
                    continue

                domain = parts[0]
                flag = parts[1].lower() == "true"
                path_val = parts[2]
                secure = parts[3].lower() == "true"
                expires = int(parts[4])
                name = parts[5]
                value = "\t".join(parts[6:])  # Value might contain tabs

                if expires > 0 and expires < time.time():
                    continue  # Skip expired cookies

                self.cookies.append({
                    "domain": domain,
                    "path": path_val,
                    "name": name,
                    "value": value,
                    "secure": secure,
                    "expires": expires,
                })

        print(f"🍪 Loaded {len(self.cookies)} cookies from {filepath}")

    def get_for_url(self, url: str) -> dict:
        """Get applicable cookies for a given URL as a dict."""
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path or "/"
        result = {}

        for cookie in self.cookies:
            # Check domain match
            cookie_domain = cookie["domain"]
            if cookie_domain:
                if not self._domain_matches(domain, cookie_domain):
                    continue
            # Check path match (simple prefix)
            if not path.startswith(cookie["path"]):
                continue
            # Check expiry
            if cookie["expires"] > 0 and cookie["expires"] < time.time():
                continue
            result[cookie["name"]] = cookie["value"]

        return result

    def to_headers(self, url: str = "") -> dict:
        """Export cookies as Cookie header dict for a specific URL."""
        cookie_dict = self.get_for_url(url) if url else {c["name"]: c["value"] for c in self.cookies}
        if not cookie_dict:
            return {}
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        return {"Cookie": cookie_str}

    def to_requests_cookies(self, url: str = "") -> dict:
        """Export as dict compatible with requests cookies parameter."""
        if url:
            return self.get_for_url(url)
        return {c["name"]: c["value"] for c in self.cookies}

    @staticmethod
    def _domain_matches(host: str, pattern: str) -> bool:
        """Check if host matches cookie domain pattern.

        .example.com matches www.example.com and example.com
        example.com matches only example.com
        """
        if pattern.startswith("."):
            pattern = pattern[1:]
        return host == pattern or host.endswith("." + pattern)


class AuthManager:
    """Unified auth manager that combines multiple auth methods.

    Merges headers from BasicAuth, BearerToken, and CookieJar into
    a single headers dict.
    """

    def __init__(self):
        self.basic: BasicAuth | None = None
        self.bearer: BearerToken | None = None
        self.cookies: CookieJar | None = None
        self.extra_headers: dict = {}

    def set_basic(self, username: str, password: str = "") -> "AuthManager":
        self.basic = BasicAuth(username, password)
        return self

    def set_bearer(self, token: str, prefix: str = "Bearer") -> "AuthManager":
        self.bearer = BearerToken(token, prefix)
        return self

    def set_cookies_from_file(self, filepath: str) -> "AuthManager":
        self.cookies = CookieJar()
        self.cookies.load_netscape(filepath)
        return self

    def set_cookies_from_pairs(self, pairs: list[tuple[str, str]], domain: str = "") -> "AuthManager":
        self.cookies = CookieJar()
        self.cookies.add_many(pairs, domain)
        return self

    def add_header(self, key: str, value: str) -> "AuthManager":
        self.extra_headers[key] = value
        return self

    def get_headers(self, url: str = "") -> dict:
        """Merge all auth methods into a single headers dict."""
        headers = {}
        if self.basic:
            headers.update(self.basic.to_headers())
        if self.bearer:
            headers.update(self.bearer.to_headers())
        if self.cookies:
            headers.update(self.cookies.to_headers(url))
        headers.update(self.extra_headers)
        return headers

    def get_requests_auth(self):
        """Get requests-compatible auth tuple (Basic Auth only)."""
        if self.basic:
            return self.basic.to_requests_auth()
        return None

    def get_requests_cookies(self, url: str = "") -> dict:
        """Get requests-compatible cookies dict."""
        if self.cookies:
            return self.cookies.to_requests_cookies(url)
        return {}

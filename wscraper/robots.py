"""
robots.txt parser and rate limiter for wscraper.

Parses robots.txt rules and enforces per-domain rate limiting
for polite crawling.

Usage:
    from .robots import RobotsParser, RateLimiter

    # Check if a URL is allowed
    robots = RobotsParser.fetch("https://example.com/robots.txt")
    allowed = robots.is_allowed("https://example.com/secret", user_agent="wscraper")

    # Rate limiting per domain
    limiter = RateLimiter()
    limiter.set_rate("example.com", requests_per_minute=10, delay_range=(1.0, 3.0))
    await limiter.acquire("example.com")  # Blocks until allowed
"""

import asyncio
import time
import re
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional, Tuple
import requests


def _url_path(url: str) -> str:
    """Extract path from URL for robots.txt matching."""
    parsed = urlparse(url)
    return parsed.path or "/"


class RobotsParser:
    """Parse and evaluate robots.txt rules."""

    def __init__(self, rules: List[Tuple[str, List[str], List[str]]] = None):
        """
        Args:
            rules: List of (group_user_agents, allow_rules, disallow_rules)
        """
        self.rules = rules or []
        self.crawl_delay = None  # Global crawl-delay if specified

    @classmethod
    def from_text(cls, text: str) -> "RobotsParser":
        """Parse robots.txt text content."""
        rules = []
        crawl_delay = None
        current_ua = []
        current_allow = []
        current_disallow = []

        def save_group():
            if current_ua or current_allow or current_disallow:
                rules.append((current_ua[:], current_allow[:], current_disallow[:]))
            current_ua.clear()
            current_allow.clear()
            current_disallow.clear()

        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()  # Remove comments
            if not line:
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                save_group()
                current_ua.append(value.lower())
            elif key == "allow":
                current_allow.append(value)
            elif key == "disallow":
                current_disallow.append(value)
            elif key == "crawl-delay":
                try:
                    crawl_delay = float(value)
                except ValueError:
                    pass
            elif key == "sitemap":
                pass  # Could be used elsewhere

        save_group()
        instance = cls(rules)
        instance.crawl_delay = crawl_delay
        return instance

    @classmethod
    def fetch(cls, url: str, timeout: int = 10) -> "RobotsParser":
        """Fetch and parse robots.txt from a URL.

        Args:
            url: The base URL or robots.txt URL
            timeout: Request timeout in seconds

        Returns:
            RobotsParser instance (always permissive if fetch fails)
        """
        if url.endswith("/robots.txt"):
            robots_url = url
        else:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            resp = requests.get(robots_url, timeout=timeout)
            if resp.status_code == 200:
                return cls.from_text(resp.text)
        except (requests.RequestException, Exception):
            pass

        # If fetch fails, return permissive parser
        return cls()

    def is_allowed(self, url: str, user_agent: str = "wscraper") -> bool:
        """Check if a URL is allowed by robots.txt rules.

        Args:
            url: URL to check
            user_agent: User-Agent string to match against

        Returns:
            True if allowed, False if disallowed
        """
        ua_lower = user_agent.lower()
        path = _url_path(url)

        # Find matching rule group
        matched_group = None
        for group_uas, allows, disallows in self.rules:
            if "*" in group_uas or ua_lower in group_uas:
                if matched_group is None:
                    matched_group = (group_uas, allows, disallows)

        # No matching group = allowed
        if matched_group is None:
            return True

        _, allows, disallows = matched_group

        # Check rules (longest match wins)
        best_allow = None
        best_disallow = None

        for rule in allows:
            if self._path_matches(path, rule):
                if best_allow is None or len(rule) > len(best_allow):
                    best_allow = rule

        for rule in disallows:
            if rule and self._path_matches(path, rule):
                if best_disallow is None or len(rule) > len(best_disallow):
                    best_disallow = rule

        # Empty disallow = all allowed
        if not disallows or all(r == "" for r in disallows):
            return True

        # Longest match wins
        if best_allow is None and best_disallow is None:
            return True
        if best_allow is None:
            return False
        if best_disallow is None:
            return True

        return len(best_allow) >= len(best_disallow)

    @staticmethod
    def _path_matches(path: str, rule: str) -> bool:
        """Check if URL path matches a robots.txt rule (prefix match with wildcard)."""
        if not rule:
            return True
        if rule == "*":
            return True

        # Handle wildcard
        if "*" in rule:
            pattern = re.escape(rule).replace(r"\*", ".*")
            return bool(re.match(f"^{pattern}$", path, re.IGNORECASE))

        # Simple prefix match on path
        return path.lower().startswith(rule.lower())

    @property
    def is_permissive(self) -> bool:
        """Check if this parser has no rules (always allows)."""
        return len(self.rules) == 0


class RateLimiter:
    """Per-domain rate limiter with token bucket algorithm.

    Supports both sync and async usage.
    """

    def __init__(self, default_delay: float = 2.0, default_rpm: int = 30):
        """
        Args:
            default_delay: Default delay between requests (seconds)
            default_rpm: Default max requests per minute per domain
        """
        self.default_delay = default_delay
        self.default_rpm = default_rpm
        self._domains: Dict[str, Dict] = {}
        self._lock = None

    def set_rate(self, domain: str, requests_per_minute: int = None,
                 delay_range: Tuple[float, float] = None) -> None:
        """Configure rate limit for a specific domain.

        Args:
            domain: Domain name
            requests_per_minute: Max requests per minute (None = default)
            delay_range: (min_delay, max_delay) in seconds (None = uses default)
        """
        self._domains[domain] = {
            "rpm": requests_per_minute or self.default_rpm,
            "delay_min": (delay_range[0] if delay_range else self.default_delay) * 0.5,
            "delay_max": (delay_range[1] if delay_range else self.default_delay) * 1.5,
            "timestamps": [],
            "last_request": 0,
        }

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc or urlparse(url).hostname or "unknown"

    def _get_config(self, domain: str) -> Dict:
        """Get or create rate config for domain."""
        if domain not in self._domains:
            self._domains[domain] = {
                "rpm": self.default_rpm,
                "delay_min": self.default_delay * 0.5,
                "delay_max": self.default_delay * 1.5,
                "timestamps": [],
                "last_request": 0,
            }
        return self._domains[domain]

    def wait_time(self, url: str) -> float:
        """Calculate how long to wait before next request to this domain.

        Args:
            url: Target URL

        Returns:
            Seconds to wait (0 if request can proceed immediately)
        """
        domain = self._get_domain(url)
        config = self._get_config(domain)
        now = time.time()

        # Clean old timestamps (older than 60s)
        config["timestamps"] = [t for t in config["timestamps"] if now - t < 60]

        # Check RPM limit
        if len(config["timestamps"]) >= config["rpm"]:
            oldest = config["timestamps"][0]
            wait = 60 - (now - oldest)
            return max(0, wait)

        # Check minimum delay
        time_since_last = now - config["last_request"] if config["last_request"] else 999
        min_delay = config["delay_min"]
        if time_since_last < min_delay:
            return min_delay - time_since_last

        return 0

    def record_request(self, url: str) -> None:
        """Record that a request was made to this URL's domain."""
        domain = self._get_domain(url)
        config = self._get_config(domain)
        now = time.time()
        config["timestamps"].append(now)
        config["last_request"] = now

    async def async_wait_time(self, url: str) -> float:
        """Async version of wait_time."""
        return self.wait_time(url)

    async def async_acquire(self, url: str) -> None:
        """Block until rate limit allows request, then record it.

        Args:
            url: Target URL
        """
        wait = await self.async_wait_time(url)
        if wait > 0:
            await asyncio.sleep(wait)
        self.record_request(url)

    def get_stats(self) -> Dict[str, Dict]:
        """Return current rate limiting stats for all domains."""
        now = time.time()
        stats = {}
        for domain, config in self._domains.items():
            active = [t for t in config["timestamps"] if now - t < 60]
            stats[domain] = {
                "requests_last_minute": len(active),
                "rpm_limit": config["rpm"],
                "remaining": max(0, config["rpm"] - len(active)),
                "last_request_ago": round(now - config["last_request"], 1) if config["last_request"] else None,
            }
        return stats

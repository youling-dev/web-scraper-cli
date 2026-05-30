"""
HTTP response cache for wscraper.

File-based cache using SHA256 hash of URL as filename.
Respects Cache-Control, ETag, and Last-Modified headers.
Default TTL is 300 seconds (5 minutes).

Usage:
    from .cache import HTTPCache

    cache = HTTPCache(default_ttl=300, enabled=True)
    html = cache.get(url)  # Returns cached content or None
    # ... fetch from network ...
    cache.put(url, html, response_headers)
"""

import os
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse


class HTTPCache:
    """Simple file-based HTTP response cache."""

    def __init__(self, cache_dir=None, default_ttl=300, enabled=True):
        """
        Args:
            cache_dir: Directory for cache files. Defaults to ~/.cache/wscraper
            default_ttl: Default TTL in seconds when no Cache-Control header.
            enabled: Whether caching is active.
        """
        self.enabled = enabled
        self.default_ttl = default_ttl
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "wscraper"

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url):
        """Generate cache filename from URL."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _meta_path(self, url):
        """Path to metadata JSON file."""
        return self.cache_dir / f"{self._key(url)}.meta.json"

    def _content_path(self, url):
        """Path to cached content file."""
        return self.cache_dir / f"{self._key(url)}.html"

    def _parse_cache_control(self, headers):
        """Parse Cache-Control header, return max-age or None."""
        cc = headers.get("Cache-Control", headers.get("cache-control", ""))
        if not cc:
            return None
        for part in cc.split(","):
            part = part.strip().lower()
            if part.startswith("max-age="):
                try:
                    return int(part.split("=")[1])
                except (ValueError, IndexError):
                    pass
            if part in ("no-store", "no-cache", "must-revalidate"):
                return 0
        return None

    def get(self, url, response_headers=None):
        """
        Get cached content if valid.

        Args:
            url: The URL to check.
            response_headers: Optional fresh headers for conditional request validation.

        Returns:
            Cached HTML string if valid and not expired, None otherwise.
        """
        if not self.enabled:
            return None

        meta_path = self._meta_path(url)
        if not meta_path.exists():
            return None

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        # Check expiration
        age = time.time() - meta.get("fetched_at", 0)
        ttl = meta.get("ttl", self.default_ttl)

        if age > ttl:
            # Check ETag conditional reuse
            etag = meta.get("etag")
            if etag and response_headers:
                # If server still returns same ETag, cache is still valid
                fresh_etag = response_headers.get("ETag", response_headers.get("etag", ""))
                if fresh_etag and fresh_etag == etag:
                    return self._content_path(url).read_text(encoding="utf-8", errors="replace")
            return None

        content_path = self._content_path(url)
        if content_path.exists():
            return content_path.read_text(encoding="utf-8", errors="replace")

        return None

    def put(self, url, content, response_headers=None):
        """
        Cache response content.

        Args:
            url: The URL that was fetched.
            content: The HTML/content to cache.
            response_headers: Response headers dict for TTL/ETag extraction.
        """
        if not self.enabled:
            return

        headers = response_headers or {}

        # Determine TTL
        max_age = self._parse_cache_control(headers)
        if max_age is not None and max_age > 0:
            ttl = max_age
        elif max_age == 0:
            # no-store / no-cache: don't cache at all
            return
        else:
            ttl = self.default_ttl

        # Store metadata
        meta = {
            "url": url,
            "fetched_at": time.time(),
            "ttl": ttl,
            "content_length": len(content),
            "status": headers.get("status", 200),
        }

        # Store ETag if present
        etag = headers.get("ETag", headers.get("etag", ""))
        if etag:
            meta["etag"] = etag

        # Store Last-Modified if present
        lm = headers.get("Last-Modified", headers.get("last-modified", ""))
        if lm:
            meta["last_modified"] = lm

        meta_path = self._meta_path(url)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        # Store content
        content_path = self._content_path(url)
        content_path.write_text(content, encoding="utf-8")

    def invalidate(self, url):
        """Remove cached entry for a URL."""
        meta_path = self._meta_path(url)
        content_path = self._content_path(url)
        if meta_path.exists():
            meta_path.unlink()
        if content_path.exists():
            content_path.unlink()

    def clear(self):
        """Clear all cached entries."""
        if not self.cache_dir.exists():
            return
        for f in self.cache_dir.iterdir():
            if f.suffix in (".html", ".meta.json"):
                f.unlink()

    def stats(self):
        """Return cache statistics."""
        if not self.cache_dir.exists():
            return {"entries": 0, "size_bytes": 0, "hit_rate": 0}

        meta_files = list(self.cache_dir.glob("*.meta.json"))
        content_files = list(self.cache_dir.glob("*.html"))

        total_size = sum(f.stat().st_size for f in content_files)
        now = time.time()
        valid = 0
        for mf in meta_files:
            try:
                meta = json.loads(mf.read_text(encoding="utf-8"))
                age = now - meta.get("fetched_at", 0)
                ttl = meta.get("ttl", self.default_ttl)
                if age <= ttl:
                    valid += 1
            except (json.JSONDecodeError, OSError):
                pass

        return {
            "entries": len(meta_files),
            "valid": valid,
            "expired": len(meta_files) - valid,
            "size_bytes": total_size,
            "size_human": self._human_size(total_size),
        }

    @staticmethod
    def _human_size(nbytes):
        """Convert bytes to human-readable string."""
        for unit in ("B", "KB", "MB", "GB"):
            if nbytes < 1024:
                return f"{nbytes:.1f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.1f} TB"

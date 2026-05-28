"""
Change detection / watch module (v1.5.0).

Monitor URLs for content changes using hash-based comparison.
Stores snapshots in SQLite for persistent tracking.
"""

import sqlite3
import hashlib
import difflib
import time
from datetime import datetime
from pathlib import Path


class Watcher:
    """Watch URLs for content changes."""

    def __init__(self, db_path="wscraper_watches.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS watches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                selector TEXT,
                interval_seconds INTEGER DEFAULT 3600,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP,
                last_hash TEXT,
                change_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER NOT NULL,
                hash TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sample_text TEXT,
                FOREIGN KEY (watch_id) REFERENCES watches(id)
            );
            CREATE TABLE IF NOT EXISTS changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                old_hash TEXT,
                new_hash TEXT,
                diff TEXT,
                added_lines INTEGER DEFAULT 0,
                removed_lines INTEGER DEFAULT 0,
                FOREIGN KEY (watch_id) REFERENCES watches(id)
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_watch ON snapshots(watch_id);
            CREATE INDEX IF NOT EXISTS idx_changes_watch ON changes(watch_id);
        """)
        conn.close()

    def add(self, url, name=None, selector=None, interval=3600):
        """Add a URL to watch list.

        Args:
            url: URL to monitor
            name: Friendly name
            selector: CSS selector to extract text from
            interval: Check interval in seconds (default 3600)

        Returns:
            dict with id, status, and message
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO watches (url, name, selector, interval_seconds)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(url) DO UPDATE SET
                       name=EXCLUDED.name,
                       selector=EXCLUDED.selector,
                       interval_seconds=EXCLUDED.interval_seconds""",
                (url, name, selector, interval),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM watches WHERE url=?", (url,)).fetchone()
            return {
                "id": row["id"],
                "url": url,
                "name": name or url,
                "status": "added",
                "message": f"✅ Added watch: {name or url}",
            }
        finally:
            conn.close()

    def check_one(self, watch_id, fetch_fn=None, parser_fn=None):
        """Check a single watched URL for changes.

        Args:
            watch_id: Watch record ID
            fetch_fn: Optional custom fetch function (url) -> html
            parser_fn: Optional custom parse function (html, selector) -> text

        Returns:
            dict with change status and diff if changed
        """
        conn = self._get_conn()
        watch = conn.execute("SELECT * FROM watches WHERE id=?", (watch_id,)).fetchone()
        if not watch:
            conn.close()
            return {"error": "Watch not found"}

        url = watch["url"]
        selector = watch["selector"]
        old_hash = watch["last_hash"]

        # Fetch page
        if fetch_fn:
            html = fetch_fn(url)
        else:
            # Use built-in requests with basic headers
            try:
                import requests
                from fake_useragent import UserAgent
                ua = UserAgent()
                resp = requests.get(
                    url,
                    headers={"User-Agent": ua.random},
                    timeout=30,
                )
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding
                html = resp.text
            except Exception as e:
                conn.close()
                return {"error": f"Failed to fetch: {e}"}

        # Extract text
        if parser_fn:
            text = parser_fn(html, selector)
        else:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            if selector:
                elements = soup.select(selector)
                texts = [el.get_text(strip=True) for el in elements]
                text = "\n".join(t for t in texts if t)
            else:
                text = soup.get_text(separator="\n")

        # Compute hash
        current_hash = self._hash(text)

        # Save snapshot
        sample = text[:2000]
        conn.execute(
            "INSERT INTO snapshots (watch_id, hash, sample_text) VALUES (?, ?, ?)",
            (watch_id, current_hash, sample),
        )

        # Update watch
        conn.execute(
            """UPDATE watches SET last_checked=CURRENT_TIMESTAMP, last_hash=? WHERE id=?""",
            (current_hash, watch_id),
        )

        result = {
            "id": watch_id,
            "url": url,
            "name": watch["name"] or url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hash": current_hash,
        }

        if old_hash is None:
            result["status"] = "initial"
            result["message"] = f"📋 Initial snapshot saved for {watch['name'] or url}"
            conn.commit()
            conn.close()
            return result
        elif current_hash == old_hash:
            result["status"] = "no_change"
            result["message"] = f"✅ No changes for {watch['name'] or url}"
            conn.commit()
            conn.close()
            return result
        else:
            # Generate diff
            diff = self._diff(old_hash, current_hash, conn, watch_id)
            added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
            removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

            result["status"] = "changed"
            result["added"] = added
            result["removed"] = removed
            result["diff"] = diff

            # Record change
            conn.execute(
                """INSERT INTO changes
                   (watch_id, old_hash, new_hash, diff, added_lines, removed_lines)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (watch_id, old_hash, current_hash, "".join(diff), added, removed),
            )
            conn.execute(
                "UPDATE watches SET change_count=change_count+1 WHERE id=?",
                (watch_id,),
            )
            result["message"] = (
                f"🔔 Change detected for {watch['name'] or url}: "
                f"+{added} -{removed} lines"
            )
            conn.commit()
            conn.close()
            return result

    def check_all(self, fetch_fn=None, parser_fn=None):
        """Check all watched URLs. Returns list of results."""
        conn = self._get_conn()
        watches = conn.execute("SELECT id FROM watches ORDER BY id").fetchall()
        conn.close()
        results = []
        for w in watches:
            r = self.check_one(w["id"], fetch_fn=fetch_fn, parser_fn=parser_fn)
            results.append(r)
        return results

    def list_watches(self):
        """List all watched URLs with status."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT id, url, name, selector, interval_seconds,
                      created_at, last_checked, change_count
               FROM watches ORDER BY id"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def history(self, watch_id, limit=10):
        """Get change history for a watch."""
        conn = self._get_conn()
        watch = conn.execute("SELECT * FROM watches WHERE id=?", (watch_id,)).fetchone()
        if not watch:
            conn.close()
            return None

        changes = conn.execute(
            """SELECT timestamp, old_hash, new_hash, diff, added_lines, removed_lines
               FROM changes WHERE watch_id=?
               ORDER BY id DESC LIMIT ?""",
            (watch_id, limit),
        ).fetchall()
        conn.close()

        return {
            "url": watch["url"],
            "name": watch["name"] or watch["url"],
            "total_changes": watch["change_count"],
            "history": [dict(c) for c in changes],
        }

    def remove(self, watch_id):
        """Remove a watch entry."""
        conn = self._get_conn()
        watch = conn.execute("SELECT * FROM watches WHERE id=?", (watch_id,)).fetchone()
        if not watch:
            conn.close()
            return {"error": "Watch not found"}
        url = watch["url"]
        conn.execute("DELETE FROM changes WHERE watch_id=?", (watch_id,))
        conn.execute("DELETE FROM snapshots WHERE watch_id=?", (watch_id,))
        conn.execute("DELETE FROM watches WHERE id=?", (watch_id,))
        conn.commit()
        conn.close()
        return {"status": "removed", "url": url, "message": f"🗑️ Removed watch: {url}"}

    @staticmethod
    def _hash(text):
        """Compute SHA256 hash of text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _diff(old_hash, new_hash, conn, watch_id):
        """Generate unified diff between old and new snapshots."""
        old_snap = conn.execute(
            "SELECT sample_text FROM snapshots WHERE watch_id=? AND hash=? LIMIT 1",
            (watch_id, old_hash),
        ).fetchone()
        new_snap = conn.execute(
            "SELECT sample_text FROM snapshots WHERE watch_id=? AND hash=? LIMIT 1",
            (watch_id, new_hash),
        ).fetchone()

        if not old_snap or not new_snap:
            return ["(snapshots not available for diff)"]

        old_lines = (old_snap["sample_text"] or "").splitlines(keepends=True)
        new_lines = (new_snap["sample_text"] or "").splitlines(keepends=True)

        return list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="old",
                tofile="new",
                lineterm="",
            )
        )

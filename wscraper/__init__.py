"""
Web Scraper CLI - 轻量网页爬虫工具

Usage:
    pip install web-scraper-cli
    wscraper https://example.com --select ".title,.content"

As a library:
    from wscraper import Scraper
    scraper = Scraper()
    html = scraper.fetch("https://example.com")
    results = scraper.parse(html, select="title, p")

Author: 有灵 ✨ | youling-dev
License: MIT
"""

__version__ = "1.9.0"

from .scraper import Scraper

__all__ = ["Scraper"]

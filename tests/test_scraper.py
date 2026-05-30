"""Tests for wscraper.scraper — Scraper (offline portions)."""
import pytest
from wscraper.scraper import Scraper


class TestScraperParse:
    def test_parse_no_selector(self):
        s = Scraper()
        html = "<html><body><p>Hello</p><p>World</p></body></html>"
        result = s.parse(html)
        assert "text" in result
        assert "Hello" in result["text"]

    def test_parse_css_selector(self):
        s = Scraper()
        html = '<div><h1 class="title">Main</h1><p>Body text</p></div>'
        result = s.parse(html, select="h1.title")
        assert len(result) == 1
        assert result[0]["text"] == "Main"

    def test_parse_multiple_selectors(self):
        s = Scraper()
        html = '<div><a href="/1">A</a><a href="/2">B</a></div>'
        result = s.parse(html, select="a")
        assert len(result) == 2

    def test_parse_attrs(self):
        s = Scraper()
        html = '<a href="https://example.com" title="Link">Go</a>'
        result = s.parse(html, select="a")
        assert result[0]["attrs"]["href"] == "https://example.com"


class TestScraperExtractLinks:
    def test_basic_links(self):
        s = Scraper()
        html = '<a href="/page1">One</a><a href="/page2">Two</a>'
        links = s.extract_links(html, "https://example.com")
        assert len(links) == 2
        assert links[0]["url"] == "https://example.com/page1"

    def test_protocol_relative_links(self):
        s = Scraper()
        html = '<a href="//example.com/page">Link</a>'
        links = s.extract_links(html, "https://example.com", relative_only=True)
        assert links[0]["url"] == "https://example.com/page"

    def test_external_links(self):
        s = Scraper()
        html = '<a href="https://other.com/page">External</a>'
        links = s.extract_links(html, "https://example.com", relative_only=False)
        assert any("other.com" in l["url"] for l in links)


class TestScraperExtractTable:
    def test_basic_table(self):
        s = Scraper()
        html = """
        <table>
            <tr><th>Name</th><th>Age</th></tr>
            <tr><td>Alice</td><td>30</td></tr>
            <tr><td>Bob</td><td>25</td></tr>
        </table>
        """
        data = s.extract_table(html)
        assert len(data) == 2
        assert data[0]["Name"] == "Alice"
        assert data[1]["Age"] == "25"

    def test_no_table(self):
        s = Scraper()
        data = s.extract_table("<p>No tables here</p>")
        assert data == []


class TestScraperFilterResults:
    def test_filter_contains(self):
        s = Scraper()
        data = [
            {"text": "iPhone 15 Pro"},
            {"text": "Samsung Galaxy S24"},
            {"text": "Pixel 8 Pro"},
        ]
        result = s.filter_results(data, filter_expr="text:contains:Pro")
        assert len(result) == 2

    def test_filter_notcontains(self):
        s = Scraper()
        data = [
            {"text": "iPhone 15"},
            {"text": "广告链接"},
            {"text": "Samsung S24"},
        ]
        result = s.filter_results(data, filter_expr="text:notcontains:广告")
        assert len(result) == 2

    def test_filter_eq(self):
        s = Scraper()
        data = [
            {"status": "active"},
            {"status": "inactive"},
            {"status": "active"},
        ]
        result = s.filter_results(data, filter_expr="status:eq:active")
        assert len(result) == 2

    def test_filter_gt(self):
        s = Scraper()
        data = [
            {"price": "100"},
            {"price": "250"},
            {"price": "50"},
        ]
        result = s.filter_results(data, filter_expr="price:gt:80")
        assert len(result) == 2

    def test_filter_lt(self):
        s = Scraper()
        data = [
            {"price": "100"},
            {"price": "250"},
            {"price": "50"},
        ]
        result = s.filter_results(data, filter_expr="price:lt:120")
        assert len(result) == 2

    def test_deduplicate(self):
        s = Scraper()
        data = [
            {"text": "Hello"},
            {"text": "World"},
            {"text": "Hello"},
        ]
        result = s.filter_results(data, unique=True)
        assert len(result) == 2

    def test_extract_field(self):
        s = Scraper()
        data = [
            {"text": "A", "html": "<a>A</a>"},
            {"text": "B", "html": "<b>B</b>"},
        ]
        result = s.filter_results(data, field="text")
        assert result == ["A", "B"]

    def test_empty_data(self):
        s = Scraper()
        assert s.filter_results([], filter_expr="text:contains:x") == []


class TestScraperToMarkdown:
    def test_basic_table(self):
        s = Scraper()
        data = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        md = s.to_markdown(data, title="People")
        assert "### People" in md
        assert "| name | age |" in md
        assert "| Alice | 30 |" in md

    def test_empty_data(self):
        s = Scraper()
        assert s.to_markdown([]) == "*(no data)*"

    def test_pipe_in_content_escaped(self):
        s = Scraper()
        data = [{"text": "A|B"}]
        md = s.to_markdown(data)
        assert "\\|" in md

    def test_newlines_in_content_replaced(self):
        s = Scraper()
        data = [{"text": "A\nB"}]
        md = s.to_markdown(data)
        assert "A B" in md


class TestScraperToSQLite:
    def test_export(self, tmp_path):
        s = Scraper()
        data = [
            {"name": "Alice", "score": "95"},
            {"name": "Bob", "score": "88"},
        ]
        db_path = str(tmp_path / "test.db")
        count = s.to_sqlite(data, db_path, table_name="scores")
        assert count == 2

        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scores")
        assert cursor.fetchone()[0] == 2
        conn.close()

    def test_export_empty(self, tmp_path):
        s = Scraper()
        db_path = str(tmp_path / "empty.db")
        count = s.to_sqlite([], db_path)
        assert count == 0


class TestScraperSitemap:
    def test_parse_standard_sitemap(self):
        s = Scraper()
        # We can't test live fetch, but we can test the parsing logic
        # by mocking fetch to return known XML
        import unittest.mock as mock
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>
        """
        with mock.patch.object(s, 'fetch', return_value=sitemap_xml):
            urls = s.extract_sitemap("https://example.com")
            assert len(urls) == 2
            assert "https://example.com/page1" in urls

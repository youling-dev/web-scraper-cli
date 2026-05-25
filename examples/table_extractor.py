#!/usr/bin/env python3
"""
表格数据提取示例

Usage:
    python examples/table_extractor.py https://example.com/data-table
"""
import sys
import json
from wscraper.scraper import Scraper

def main():
    if len(sys.argv) < 2:
        print("Usage: python table_extractor.py <url> [table_selector]")
        sys.exit(1)
    
    url = sys.argv[1]
    selector = sys.argv[2] if len(sys.argv) > 2 else None
    
    scraper = Scraper()
    html = scraper.fetch(url)
    data = scraper.extract_table(html, selector)
    
    print(f"\n📊 提取到 {len(data)} 行数据\n")
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

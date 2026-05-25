#!/usr/bin/env python3
"""
价格监控示例 — 定时抓取商品价格并记录变化

Usage:
    python examples/price_monitor.py
"""
import time
import csv
import os
from datetime import datetime
from wscraper.scraper import Scraper

URL = "https://example.com/product/123"
PRICE_SELECTOR = ".product-price"
INTERVAL = 300  # 5 minutes
OUTPUT_FILE = "price_history.csv"

def main():
    scraper = Scraper(delay=3, retries=3)
    
    # Create CSV if not exists
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "price", "url"])
    
    print(f"🕷️  开始监控: {URL}")
    print(f"⏰  间隔: {INTERVAL}秒")
    print(f"📊  记录: {OUTPUT_FILE}")
    print()
    
    while True:
        try:
            html = scraper.fetch(URL)
            data = scraper.parse(html, URL, PRICE_SELECTOR)
            
            if data:
                price = data[0].get("text", "")
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                with open(OUTPUT_FILE, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([ts, price, URL])
                
                print(f"  [{ts}] {price}")
            else:
                print(f"  [{datetime.now()}] 未找到价格元素")
            
            time.sleep(INTERVAL)
            
        except KeyboardInterrupt:
            print("\n👋 已停止监控")
            break
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    main()

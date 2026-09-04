import asyncio
import sys
from loguru import logger
from website_scraper.crawler import WebsiteCrawler
from website_scraper.config import config

async def test():
    # We will test on a common URL or one passed by arg
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.propertyfinder.ae/"
    
    # We can override config for a quick test
    config.max_pages = 10
    config.request_delay = 0.5
    
    print(f"\n==============================================")
    print(f"Testing Intelligent Crawler on: {test_url}")
    print(f"Max Pages: {config.max_pages}")
    print(f"==============================================\n")
    
    crawler = WebsiteCrawler(test_url)
    results = await crawler.crawl()
    
    print(f"\n==============================================")
    print(f"CRAWL COMPLETED")
    print(f"Total Pages Processed: {len(results)}")
    print(f"==============================================\n")
    
    for idx, page in enumerate(results):
        print(f"[{idx+1}] Category: {page.page_type: <12} | Priority: {page.priority: <3} | URL: {page.url}")
        if page.clean_text:
            snippet = page.clean_text[:100].replace('\n', ' ')
            print(f"    Snipppet: {snippet}...\n")

if __name__ == "__main__":
    asyncio.run(test())

import asyncio
import urllib.parse
import re
from typing import List, Dict, Any
# pyrefly: ignore [missing-import]
from playwright.async_api import async_playwright, Page
# pyrefly: ignore [missing-import]
from loguru import logger

class GoogleMapsDiscovery:
    def __init__(self, headless: bool = True):
        self.headless = headless

    def _extract_place_id(self, url: str) -> str:
        """Attempts to extract place ID from URL if present."""
        # E.g. !1s0x...:0x... or ?q=place_id:...
        match = re.search(r'!1s([^!]+)', url)
        if match:
            return match.group(1)
        return None

    async def _scroll_to_load_results(self, page: Page, max_results: int) -> int:
        """Scrolls the results pane to load more results until max_results is reached or no more results."""
        logger.info(f"Scrolling to load up to {max_results} results...")
        
        try:
            await page.wait_for_selector('a[href*="/maps/place/"]', timeout=15000)
        except Exception:
            logger.warning("No results found or timeout waiting for results.")
            return 0

        previous_count = 0
        stagnant_count = 0
        
        while True:
            elements = await page.locator('a[href*="/maps/place/"]').all()
            current_count = len(elements)
            
            if current_count >= max_results:
                logger.info(f"Reached desired max results: {current_count}")
                break
                
            if current_count == previous_count:
                stagnant_count += 1
                if stagnant_count >= 5:
                    logger.info("No more results loading.")
                    break
            else:
                stagnant_count = 0
                
            previous_count = current_count
            
            if elements:
                try:
                    await elements[-1].scroll_into_view_if_needed()
                    await page.mouse.wheel(0, 2000)
                except Exception as e:
                    logger.debug(f"Scroll error: {e}")
                    
            await page.wait_for_timeout(2000)
            
            end_element = page.get_by_text("You've reached the end of the list.")
            if await end_element.count() > 0:
                logger.info("Reached the end of the list.")
                break

        return current_count

    async def discover(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Executes a search query on Google Maps and returns structured discovery results.
        """
        results = []
        seen_urls = set()
        logger.info(f"Starting discovery for query: '{query}'")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/maps/search/{encoded_query}?hl=en"
            
            try:
                await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                
                try:
                    accept_button = page.locator('button:has-text("Accept all")')
                    if await accept_button.count() > 0:
                        await accept_button.first.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass
                
                await self._scroll_to_load_results(page, max_results)
                
                elements = await page.locator('a[href*="/maps/place/"]').all()
                rank = 1
                
                for el in elements:
                    url = await el.get_attribute('href')
                    if url:
                        clean_url = url.split('?')[0]
                        
                        if clean_url in seen_urls:
                            continue
                            
                        seen_urls.add(clean_url)
                        
                        # Try to get business name from aria-label
                        name = await el.get_attribute('aria-label')
                        if not name:
                            # Fallback to inner text
                            name = await el.inner_text()
                        
                        place_id = self._extract_place_id(clean_url)
                        
                        results.append({
                            "business_name": name.strip() if name else None,
                            "url": clean_url,
                            "place_id": place_id,
                            "rank": rank
                        })
                        
                        rank += 1
                        
                        if len(results) >= max_results:
                            break
                            
            except Exception as e:
                logger.error(f"Error during discovery: {e}")
            finally:
                await browser.close()
                
        logger.info(f"Discovered {len(results)} unique businesses for query '{query}'.")
        return results

if __name__ == "__main__":
    async def test():
        disc = GoogleMapsDiscovery(headless=False)
        results = await disc.discover("restaurants in Dubai Marina", max_results=5)
        for r in results:
            print(r)
    
    asyncio.run(test())

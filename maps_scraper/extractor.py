import asyncio
import re
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page
from loguru import logger

class ProfileExtractor:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        try:
            element = await page.wait_for_selector(selector, timeout=3000)
            if element:
                text = await element.inner_text()
                return text.strip() if text else None
        except Exception:
            return None
        return None

    async def extract_profile(self, url: str) -> Dict[str, Any]:
        """
        Visits a Google Maps business profile URL and extracts detailed information.
        """
        logger.info(f"Extracting profile data from: {url}")
        
        # Initialize dictionary to avoid NoneType errors
        data: Dict[str, Any] = {
            "raw_name": None,
            "primary_category": None,
            "raw_address": None,
            "phone": None,
            "website": None,
            "google_rating": None,
            "review_count": None,
            "google_maps_url": url,
            "place_id": None,
            "latitude": None,
            "longitude": None,
            "status": None
        }
        
        # Extract place_id or latitude/longitude from URL if possible
        lat_lng_match = re.search(r'@([0-9.-]+),([0-9.-]+)', url)
        if lat_lng_match:
            try:
                data["latitude"] = float(lat_lng_match.group(1))
                data["longitude"] = float(lat_lng_match.group(2))
            except ValueError:
                pass
                
        id_match = re.search(r'0x[0-9a-f]+:0x[0-9a-f]+', url)
        if id_match:
            data["place_id"] = id_match.group(0)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            try:
                lang_url = url
                if '?' in url:
                    lang_url += "&hl=en"
                else:
                    lang_url += "?hl=en"
                    
                await page.goto(lang_url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_selector('h1', timeout=10000)
                
                # Extract Name
                data["raw_name"] = await self._extract_text(page, 'h1')
                
                # Extract Rating and Review Count robustly
                rating_text = await self._extract_text(page, 'div.F7nice')
                if rating_text:
                    rating_match = re.search(r'([0-9.]+)', rating_text)
                    if rating_match:
                        try:
                            data["google_rating"] = float(rating_match.group(1))
                        except ValueError:
                            pass
                            
                    review_match = re.search(r'\(([\d,]+)\)', rating_text)
                    if review_match:
                        reviews_str = review_match.group(1).replace(',', '').strip()
                        try:
                            data["review_count"] = int(reviews_str)
                        except ValueError:
                            pass

                # Extract Category
                category_button = await page.query_selector('button[jsaction="pane.rating.category"]')
                if category_button:
                    data["primary_category"] = await category_button.inner_text()
                
                # Address, Website, Phone in buttons/links with specific aria-labels or data attributes
                # Also try looking at 'a' tags for website
                all_links = await page.locator('a, button').all()
                for el in all_links:
                    try:
                        aria_label = await el.get_attribute('aria-label') or ""
                        href = await el.get_attribute('href') or ""
                        text = await el.inner_text()
                        
                        if 'Address:' in aria_label:
                            data["raw_address"] = aria_label.split('Address:')[-1].strip()
                        elif 'Website:' in aria_label or aria_label.startswith('Website'):
                            if href and href.startswith('http'):
                                data["website"] = href
                            else:
                                data["website"] = text.strip()
                        elif 'Phone:' in aria_label or aria_label.startswith('Phone'):
                            data["phone"] = aria_label.split('Phone:')[-1].strip()
                            
                        # Social profiles might be present as external links
                        if href and href.startswith('http'):
                            href_lower = href.lower()
                            if 'facebook.com' in href_lower:
                                data["social_facebook"] = href
                            elif 'instagram.com' in href_lower:
                                data["social_instagram"] = href
                            elif 'linkedin.com' in href_lower:
                                data["social_linkedin"] = href
                            elif 'twitter.com' in href_lower or 'x.com' in href_lower:
                                data["social_x"] = href
                                
                    except Exception:
                        pass
                        
                # Alternative extraction for status
                status_element = await page.query_selector('div.OqYYle, span.ZDu9vd, span:has-text("Permanently closed"), span:has-text("Closed"), span:has-text("Open")')
                if status_element:
                    status_text = await status_element.inner_text()
                    if status_text:
                        data["status"] = status_text.strip()
                    
            except Exception as e:
                logger.error(f"Error extracting {url}: {e}")
            finally:
                await browser.close()
                
        return data

if __name__ == "__main__":
    # Quick test
    async def test():
        url = "https://www.google.com/maps/place/At.mosphere+Burj+Khalifa/@25.197197,55.2743764,15z/data=!4m6!3m5!1s0x3e5f43348a67e24b:0x685f62e879008bc5!8m2!3d25.197197!4d55.2743764!16s%2Fg%2F11b6ddv1d8?hl=en"
        ext = ProfileExtractor(headless=False)
        data = await ext.extract_profile(url)
        print(data)
    
    asyncio.run(test())

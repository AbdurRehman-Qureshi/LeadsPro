import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from loguru import logger
from typing import List, Dict, Set, Optional

from .config import config
from .page_classifier import PageClassifier
from .page_prioritizer import PagePrioritizer
from .models import ScrapedPage

class WebsiteCrawler:
    def __init__(self, base_url: str):
        self.base_url = self._normalize_url(base_url)
        self.base_domain = urlparse(self.base_url).netloc
        
        self.visited_urls: Set[str] = set()
        self.queue: List[ScrapedPage] = []  # List managed as a priority queue
        self.results: List[ScrapedPage] = []
        
        # Add homepage to queue
        self.queue.append(ScrapedPage(
            url=self.base_url,
            page_type="HOME",
            priority=100
        ))

    def _normalize_url(self, url: str) -> str:
        """Removes fragments and normalizes trailing slashes"""
        url, _ = urldefrag(url)
        if url.endswith('/'):
            url = url[:-1]
        return url

    def _is_valid_internal_url(self, url: str) -> bool:
        """Checks if URL is valid for crawling (same domain, no media files)"""
        if not url:
            return False
            
        # Ignore media/document extensions
        ignored_extensions = ('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.doc', '.docx', '.mp4')
        if any(url.lower().endswith(ext) for ext in ignored_extensions):
            return False
            
        # Ignore special schemas and paths
        if url.startswith(('mailto:', 'tel:', 'javascript:')):
            return False
        
        # Ignore common non-intel paths
        ignored_paths = ['/login', '/cart', '/checkout', '/account', '/wp-admin']
        if any(path in url.lower() for path in ignored_paths):
            return False

        parsed = urlparse(url)
        # Check domain
        if parsed.netloc and parsed.netloc != self.base_domain:
            return False
            
        return True

    def _extract_clean_text(self, soup: BeautifulSoup) -> str:
        """Removes boilerplate and extracts readable text"""
        # Decompose useless tags
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'meta', 'link']):
            tag.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        # Collapse multiple spaces
        import re
        return re.sub(r'\s+', ' ', text)

    async def fetch_page(self, session: aiohttp.ClientSession, page_obj: ScrapedPage) -> Optional[BeautifulSoup]:
        """Fetches a single page with retries"""
        for attempt in range(config.max_retries):
            try:
                async with session.get(page_obj.url, timeout=config.request_timeout) as response:
                    page_obj.status_code = response.status
                    if response.status == 200:
                        html = await response.text()
                        return BeautifulSoup(html, 'html.parser')
                    elif response.status in (403, 404, 429):
                        logger.warning(f"Skipping {page_obj.url} (Status: {response.status})")
                        return None
            except Exception as e:
                logger.debug(f"Attempt {attempt+1} failed for {page_obj.url}: {e}")
                if attempt < config.max_retries - 1:
                    await asyncio.sleep(config.request_delay * (attempt + 1))
        
        return None

    async def crawl(self) -> List[ScrapedPage]:
        """Main orchestrator for priority-based concurrent crawling"""
        logger.info(f"Starting crawl for: {self.base_url}")
        
        sem = asyncio.Semaphore(config.max_concurrent_requests)
        
        async def fetch_and_process(session: aiohttp.ClientSession, page_obj: ScrapedPage, delay: float):
            await asyncio.sleep(delay) # Stagger requests slightly to avoid triggering anti-bot firewalls
            async with sem:
                soup = await self.fetch_page(session, page_obj)
                return page_obj, soup
        
        async with aiohttp.ClientSession() as session:
            while self.queue and len(self.visited_urls) < config.max_pages:
                # Sort queue by priority (descending)
                self.queue.sort(key=lambda x: x.priority, reverse=True)
                
                # Pop a batch of tasks
                batch_size = min(config.max_concurrent_requests, config.max_pages - len(self.visited_urls))
                batch_pages = []
                
                # Safely extract from queue
                temp_queue = []
                while self.queue and len(batch_pages) < batch_size:
                    p = self.queue.pop(0)
                    if p.url not in self.visited_urls:
                        self.visited_urls.add(p.url)
                        batch_pages.append(p)
                    else:
                        temp_queue.append(p)
                self.queue.extend(temp_queue)
                
                if not batch_pages:
                    break
                    
                logger.info(f"Crawling batch of {len(batch_pages)} pages for {self.base_domain}...")
                
                # Stagger the start times so we don't blast the server at the exact same millisecond
                coroutines = [
                    fetch_and_process(session, page, idx * (config.request_delay / config.max_concurrent_requests)) 
                    for idx, page in enumerate(batch_pages)
                ]
                
                results = await asyncio.gather(*coroutines, return_exceptions=True)
                
                for res in results:
                    if isinstance(res, Exception):
                        logger.error(f"Unhandled crawl exception: {res}")
                        continue
                        
                    current_page, soup = res
                    if soup:
                        # 1. Update current page data
                        title_tag = soup.find('title')
                        current_page.title = title_tag.text.strip() if title_tag else ""
                        current_page.raw_html = str(soup)
                        current_page.clean_text = self._extract_clean_text(soup)
                        self.results.append(current_page)
                        
                        # 2. Extract and queue new links (if max depth not reached)
                        if current_page.depth < config.max_depth:
                            links = soup.find_all('a', href=True)
                            for link in links:
                                href = link.get('href')
                                if not href:
                                    continue
                                absolute_url = urljoin(current_page.url, href)
                                normalized_url = self._normalize_url(absolute_url)
                                
                                if self._is_valid_internal_url(normalized_url) and normalized_url not in self.visited_urls:
                                    if not any(p.url == normalized_url for p in self.queue):
                                        link_text = link.get_text(strip=True)
                                        category = PageClassifier.classify(normalized_url, link_text)
                                        priority = PagePrioritizer.calculate_priority(category, normalized_url, link_text)
                                        
                                        self.queue.append(ScrapedPage(
                                            url=normalized_url,
                                            page_type=category,
                                            priority=priority,
                                            title=link_text,
                                            depth=current_page.depth + 1
                                        ))
                
                # Base delay between batches
                await asyncio.sleep(config.request_delay)
                
        logger.info(f"Crawl completed. Processed {len(self.results)} pages for {self.base_domain}")
        return self.results

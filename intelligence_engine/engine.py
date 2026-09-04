import asyncio
from typing import Optional
# pyrefly: ignore [missing-import]
from loguru import logger
from datetime import datetime

from .config import config
from .models import BusinessIntelligenceProfile
from .crawler import WebsiteCrawler
from .contact_extractor import ContactExtractor
from .signal_detector import DeterministicSignalDetector
from .signal_analyzer import SignalAnalyzer
from .ai import AIBusinessAnalyzer

class AdvertiserIntelligenceEngine:
    """The main orchestrator for turning a website URL into a BusinessIntelligenceProfile."""
    
    def __init__(self):
        self.ai_analyzer = AIBusinessAnalyzer()

    async def run(self, url: str) -> BusinessIntelligenceProfile:
        logger.info(f"--- STARTING ADVERTISER INTELLIGENCE ENGINE FOR: {url} ---")
        
        profile = BusinessIntelligenceProfile(website=url)
        profile.crawl_status = "RUNNING"
        
        try:
            # 1. Intelligent Crawl
            crawler = WebsiteCrawler(url)
            scraped_pages = await crawler.crawl()
            
            profile.pages_crawled = len(scraped_pages)
            if not scraped_pages:
                profile.crawl_status = "FAILED"
                profile.crawl_errors.append({"type": "CRAWL_FAILED", "message": "No pages discovered or access blocked."})
                return profile
                
            # Keep top 10 important pages based on our prioritizer
            important_pages = sorted(scraped_pages, key=lambda p: p.priority, reverse=True)[:10]
            profile.important_pages = [p.url for p in important_pages]
            
            # 2. Extract Contacts & Deterministic Signals from Important Pages
            all_signals = []
            for page in important_pages:
                # Extract contacts/socials
                contacts, socials = ContactExtractor.extract_from_html(page.raw_html, page.url) # Note: we pass clean_text here instead of raw HTML for simplicity, though passing HTML might be slightly better for 'href' extraction. Wait, ContactExtractor expects raw HTML.
                
                # Merge contacts
                profile.contacts.emails.extend([e for e in contacts.emails if e not in profile.contacts.emails])
                profile.contacts.phones.extend([p for p in contacts.phones if p not in profile.contacts.phones])
                
                # Merge socials
                if socials.facebook and not profile.socials.facebook: profile.socials.facebook = socials.facebook
                if socials.instagram and not profile.socials.instagram: profile.socials.instagram = socials.instagram
                if socials.linkedin and not profile.socials.linkedin: profile.socials.linkedin = socials.linkedin
                if socials.x and not profile.socials.x: profile.socials.x = socials.x
                if socials.youtube and not profile.socials.youtube: profile.socials.youtube = socials.youtube
                if socials.tiktok and not profile.socials.tiktok: profile.socials.tiktok = socials.tiktok
                
                # Detect deterministic signals
                page_signals = DeterministicSignalDetector.detect_signals(page)
                all_signals.extend(page_signals)
            # Deduplicate deterministic signals before sending to AI
            all_signals = SignalAnalyzer.deduplicate(all_signals)
            
            # 3. AI Analysis & Scoring
            profile = await self.ai_analyzer.analyze(profile, important_pages, all_signals)
            
            # 4. Final Post-Processing (Freshness, Deduplication, Quality)
            if profile.buying_signals:
                profile.buying_signals = SignalAnalyzer.calculate_freshness(profile.buying_signals)
                profile.buying_signals = SignalAnalyzer.deduplicate(profile.buying_signals)
                
            profile.data_quality_score = SignalAnalyzer.calculate_data_quality(profile)
            
            profile.crawl_status = "COMPLETED"
            profile.processed_at = datetime.utcnow().isoformat()
            logger.info(f"--- SUCCESS: Generated Intelligence for {profile.company_name} ---")
            
        except Exception as e:
            logger.error(f"Engine failed for {url}: {e}")
            profile.crawl_status = "FAILED"
            profile.crawl_errors.append({"type": "ENGINE_ERROR", "message": str(e)})
            
        return profile

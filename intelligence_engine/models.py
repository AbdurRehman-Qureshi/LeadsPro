from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ContactInfo(BaseModel):
    emails: List[Dict[str, str]] = Field(default_factory=list) # {"email": "...", "type": "...", "source": "..."}
    phones: List[Dict[str, str]] = Field(default_factory=list) # {"phone": "...", "source": "..."}

class SocialLinks(BaseModel):
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None
    x: Optional[str] = None

class BuyingSignal(BaseModel):
    type: str
    strength: int # 0-100
    confidence: float # 0.0-1.0
    description: str
    evidence: str
    source_url: str
    date: Optional[str] = None
    freshness: str # VERY_FRESH, FRESH, RECENT, OLD, EXPIRED, UNKNOWN

class AdvertisingOpportunity(BaseModel):
    relevant: bool = False
    reason: Optional[str] = None
    campaign_angle: Optional[str] = None
    urgency: Optional[str] = None

class ScrapedPage(BaseModel):
    url: str
    title: Optional[str] = None
    page_type: str = "OTHER"
    priority: int = 0
    depth: int = 0
    clean_text: str = ""
    raw_html: str = ""
    status_code: int = 200

class BusinessIntelligenceProfile(BaseModel):
    company_name: Optional[str] = None
    website: str
    industry: Optional[str] = None
    description: Optional[str] = None
    
    locations: List[str] = Field(default_factory=list)
    branches: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    
    contacts: ContactInfo = Field(default_factory=ContactInfo)
    socials: SocialLinks = Field(default_factory=SocialLinks)
    
    pages_crawled: int = 0
    important_pages: List[str] = Field(default_factory=list)
    
    buying_signals: List[BuyingSignal] = Field(default_factory=list)
    advertising_opportunity: AdvertisingOpportunity = Field(default_factory=AdvertisingOpportunity)
    
    lead_score: int = 0
    lead_grade: str = "UNKNOWN"
    data_quality_score: int = 0
    
    crawl_status: str = "PENDING"
    crawl_errors: List[Dict[str, str]] = Field(default_factory=list)
    
    discovered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    processed_at: Optional[str] = None

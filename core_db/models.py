from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class SearchJobConfig(BaseModel):
    industry: str
    location: str
    keywords: str
    max_results: int = 50

class RawBusinessData(BaseModel):
    raw_name: Optional[str] = None
    primary_category: Optional[str] = None
    raw_address: Optional[str] = None
    raw_phone: Optional[str] = None
    website: Optional[str] = None
    google_rating: Optional[float] = None
    review_count: Optional[int] = None
    google_maps_url: Optional[str] = None
    place_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    
    # Social links
    social_facebook: Optional[str] = None
    social_instagram: Optional[str] = None
    social_linkedin: Optional[str] = None
    social_x: Optional[str] = None
    
    discovery_query: str
    search_location: Optional[str] = None
    source: str = "Google Maps"
    discovery_timestamp: datetime = Field(default_factory=datetime.utcnow)

class CleanBusinessData(BaseModel):
    scrape_job_id: str
    raw_name: str
    normalized_name: str
    primary_category: Optional[str] = None
    raw_address: Optional[str] = None
    normalized_address: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None
    country: Optional[str] = None
    raw_phone: Optional[str] = None
    normalized_phone: Optional[str] = None
    website: Optional[str] = None
    google_rating: Optional[float] = None
    review_count: Optional[int] = None
    google_maps_url: Optional[str] = None
    place_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    
    # Social links
    social_facebook: Optional[str] = None
    social_instagram: Optional[str] = None
    social_linkedin: Optional[str] = None
    social_x: Optional[str] = None
    
    discovery_query: str
    search_location: Optional[str] = None
    source: str
    discovery_timestamp: datetime
    scrape_timestamp: datetime


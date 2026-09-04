import json
from loguru import logger
from typing import Dict, Any
from supabase import create_client, Client
from .config import config
from .models import BusinessIntelligenceProfile

class SupabaseExporter:
    def __init__(self):
        self.url: str = config.supabase_url
        self.key: str = config.supabase_key
        self.client: Client = None
        
        if self.url and self.key and "your-project" not in self.url:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")

    def export(self, profile: BusinessIntelligenceProfile) -> bool:
        if not self.client:
            logger.warning("Supabase client is not initialized. Skipping export. Please check .env")
            return False
            
        try:
            # We transform the Pydantic model into a dictionary suitable for Supabase insertion
            # Assuming a table named 'advertiser_intelligence' exists in Supabase with these columns
            data: Dict[str, Any] = {
                "website": profile.website,
                "company_name": profile.company_name,
                "industry": profile.industry,
                "description": profile.description,
                "locations": profile.locations,
                "services": profile.services,
                "products": profile.products,
                "projects": profile.projects,
                "contacts": profile.contacts.model_dump(),
                "socials": profile.socials.model_dump(),
                "important_pages": profile.important_pages,
                "buying_signals": [s.model_dump() for s in profile.buying_signals],
                "advertising_opportunity": profile.advertising_opportunity.model_dump(),
                "lead_score": profile.lead_score,
                "lead_grade": profile.lead_grade,
                "data_quality_score": profile.data_quality_score,
                "discovered_at": profile.discovered_at,
                "processed_at": profile.processed_at
            }
            
            # Using 'upsert' assuming 'website' is the unique primary key in Supabase
            response = self.client.table("advertiser_intelligence").upsert(data, on_conflict="website").execute()
            
            logger.info(f"Successfully exported {profile.company_name or profile.website} to Supabase.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export to Supabase: {e}")
            return False

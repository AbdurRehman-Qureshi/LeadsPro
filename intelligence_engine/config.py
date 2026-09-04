import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class CrawlerConfig(BaseModel):
    max_pages: int = Field(default=5, description="Maximum number of pages to crawl per website")
    max_depth: int = Field(default=2, description="Maximum depth of links to follow")
    request_timeout: int = Field(default=10, description="Timeout for HTTP requests in seconds")
    request_delay: float = Field(default=0.5, description="Delay between requests to avoid rate limits")
    max_retries: int = Field(default=2, description="Maximum retries for failed requests")
    max_concurrent_requests: int = Field(default=5, description="Maximum concurrent async requests")
    
    # Feature Flags
    enable_ai_analysis: bool = Field(default=True)
    enable_serper_fallback: bool = Field(default=False)
    
    # API Keys
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    supabase_url: str = Field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_key: str = Field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_KEY", ""))
    serper_api_key: str = Field(default_factory=lambda: os.getenv("SERPER_API_KEY", ""))
    airtable_api_key: str = Field(default_factory=lambda: os.getenv("AIRTABLE_API_KEY", ""))

# Global config instance
config = CrawlerConfig()

import argparse
import asyncio
import json
import sys
from loguru import logger
from .engine import AdvertiserIntelligenceEngine
from .exporters import SupabaseExporter

async def run_single(url: str):
    engine = AdvertiserIntelligenceEngine()
    profile = await engine.run(url)
    
    # Export to Database
    exporter = SupabaseExporter()
    exporter.export(profile)
    
    print("\n" + "="*80)
    print(f"ADVERTISER INTELLIGENCE PROFILE FOR: {url}")
    print("="*80 + "\n")
    
    # Exclude raw html and clean text from dump to keep it clean
    dump_dict = profile.model_dump()
    print(json.dumps(dump_dict, indent=2))
    
    print("\n" + "="*80)
    print(f"Lead Score: {profile.lead_score} | Grade: {profile.lead_grade}")
    print("="*80 + "\n")
    
def main():
    parser = argparse.ArgumentParser(description="Advertiser Intelligence Website Scraper")
    parser.add_argument("--url", type=str, help="Single URL to crawl and analyze")
    
    args = parser.parse_args()
    
    if args.url:
        asyncio.run(run_single(args.url))
    else:
        logger.error("Please provide a --url parameter.")
        sys.exit(1)

if __name__ == "__main__":
    main()

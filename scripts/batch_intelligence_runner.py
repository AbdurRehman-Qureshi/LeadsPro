import asyncio
import os
import json
# pyrefly: ignore [missing-import]
from loguru import logger
from prisma import Prisma

from intelligence_engine.engine import AdvertiserIntelligenceEngine

async def process_single_lead(sem: asyncio.Semaphore, ai_engine: AdvertiserIntelligenceEngine, db: Prisma, lead, max_retries: int = 3):
    url = lead.website
    if not url:
        return None
        
    if not url.startswith('http'):
        url = 'https://' + url
        
    attempts = 0
    while attempts < max_retries:
        attempts += 1
        logger.info(f"Processing (Attempt {attempts}/{max_retries}): {url}")
        
        try:
            async with sem:
                profile = await ai_engine.run(url)
                
            if profile.crawl_status == "FAILED":
                logger.error(f"Engine failed on {url} (Attempt {attempts}): {profile.crawl_errors}")
                if attempts >= max_retries:
                    await db.businesslead.update(
                        where={"id": lead.id},
                        data={
                            "crawlStatus": "FAILED",
                            "crawlErrors": json.dumps(profile.crawl_errors)
                        }
                    )
                    return None
                await asyncio.sleep(2)
                continue
                
            # Prepare update payload
            update_data = {
                "crawlStatus": "COMPLETED",
                "pagesCrawled": profile.pages_crawled,
                "importantPages": profile.important_pages,
                "emails": json.dumps([dict(c) for c in profile.contacts.emails]) if profile.contacts.emails else json.dumps([]),
                "alternativePhones": json.dumps([dict(p) for p in profile.contacts.phones]) if profile.contacts.phones else json.dumps([]),
                "socialFacebook": profile.socials.facebook,
                "socialInstagram": profile.socials.instagram,
                "socialLinkedin": profile.socials.linkedin,
                "socialX": profile.socials.x,
                "socialYoutube": profile.socials.youtube,
                "socialTiktok": profile.socials.tiktok,
                
                "aiCompanyName": profile.company_name,
                "aiIndustry": profile.industry,
                "aiDescription": profile.description,
                "aiLocations": profile.locations,
                "aiBranches": profile.branches,
                "aiServices": profile.services,
                "aiProducts": profile.products,
                "aiProjects": profile.projects,
                
                "leadScore": profile.lead_score,
                "leadGrade": profile.lead_grade,
                "dataQualityScore": profile.data_quality_score,
                
                "advRelevant": profile.advertising_opportunity.relevant,
                "advReason": profile.advertising_opportunity.reason,
                "advCampaignAngle": profile.advertising_opportunity.campaign_angle,
                "advUrgency": profile.advertising_opportunity.urgency,
            }
            
            # Update the lead in Prisma
            await db.businesslead.update(
                where={"id": lead.id},
                data=update_data
            )
            
            # Clear old signals if retrying
            await db.buyingsignal.delete_many(where={"businessId": lead.id})
            
            # Insert buying signals
            for sig in profile.buying_signals:
                await db.buyingsignal.create(
                    data={
                        "businessId": lead.id,
                        "type": sig.type,
                        "strength": sig.strength,
                        "confidence": sig.confidence,
                        "description": sig.description,
                        "evidence": sig.evidence,
                        "sourceUrl": sig.source_url,
                        "date": sig.date,
                        "freshness": sig.freshness
                    }
                )
                
            return profile.lead_score
            
        except Exception as e:
            logger.error(f"Unexpected error processing {url} on attempt {attempts}: {e}")
            if attempts >= max_retries:
                await db.businesslead.update(
                    where={"id": lead.id},
                    data={
                        "crawlStatus": "FAILED",
                        "crawlErrors": json.dumps([{"type": "UNEXPECTED", "message": str(e)}])
                    }
                )
                return None
            await asyncio.sleep(2)
            
    return None

async def process_batch():
    async with Prisma() as db:
        # Get pending leads
        pending_leads = await db.businesslead.find_many(
            where={
                "crawlStatus": "PENDING", 
                "website": {"not": None}
            },
            take=500
        )
        
        logger.info(f"Found {len(pending_leads)} pending leads to process in Supabase.")
        
        if not pending_leads:
            logger.warning("No pending leads found.")
            return
            
        ai_engine = AdvertiserIntelligenceEngine()
        sem = asyncio.Semaphore(50)
        
        logger.info("Starting concurrent batch processing to Supabase...")
        
        tasks = [process_single_lead(sem, ai_engine, db, lead) for lead in pending_leads]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"A task threw an unhandled exception: {res}")
            elif res is not None:
                success_count += 1
                
        logger.info(f"Batch completed! Successfully processed {success_count}/{len(pending_leads)} leads and saved to Supabase.")

if __name__ == "__main__":
    asyncio.run(process_batch())


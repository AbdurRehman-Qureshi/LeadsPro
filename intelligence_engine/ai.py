import json
from typing import List
from openai import AsyncOpenAI
from loguru import logger
from .config import config
from .models import BusinessIntelligenceProfile, ScrapedPage, BuyingSignal

class AIBusinessAnalyzer:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai_api_key)

    async def analyze(self, profile: BusinessIntelligenceProfile, important_pages: List[ScrapedPage], deterministic_signals: List[BuyingSignal]) -> BusinessIntelligenceProfile:
        if not config.enable_ai_analysis or not config.openai_api_key:
            logger.warning("AI Analysis is disabled or API key is missing.")
            return profile

        logger.info(f"Starting AI analysis for {profile.website}")
        
        # Prepare context limit (avoid massive token usage)
        # We only send the top 5 most important pages based on our priority queue
        context_texts = []
        for page in important_pages[:5]:
            snippet = page.clean_text[:3000] # Cap each page at 3000 chars
            context_texts.append(f"--- URL: {page.url} (Type: {page.page_type}) ---\n{snippet}")
            
        full_context = "\n\n".join(context_texts)
        
        # Serialize existing signals for AI context
        existing_signals_json = [s.model_dump() for s in deterministic_signals]
        
        prompt = f"""
        You are an Advertiser Intelligence Expert. Your job is to analyze website data to determine if a company is a good prospect for mobile billboard advertising.
        
        Website: {profile.website}
        
        Website Content:
        {full_context}
        
        Deterministically Detected Signals:
        {json.dumps(existing_signals_json, indent=2)}
        
        Task:
        1. Identify the company name, industry, and a short business description.
        2. Identify locations, services, products, and projects.
        3. Validate the deterministic signals and find ANY NEW buying signals (e.g., Grand openings, new branches, events, campaigns).
        4. Calculate a Lead Score (0-100) and grade (HOT, HIGH, MEDIUM, LOW, REJECT) based on how likely they are to need mobile advertising.
        5. Explain the advertising opportunity and campaign angle.
        
        Output strictly in JSON matching this schema:
        {{
            "company_name": "string",
            "industry": "string",
            "description": "string",
            "locations": ["string"],
            "services": ["string"],
            "products": ["string"],
            "projects": ["string"],
            "buying_signals": [
                {{
                    "type": "string (e.g., NEW_BRANCH, PROJECT_LAUNCH, EVENT)",
                    "strength": int (0-100),
                    "confidence": float (0.0-1.0),
                    "description": "string",
                    "evidence": "string (exact quote from text)",
                    "source_url": "string",
                    "date": "string (YYYY-MM-DD) or null",
                    "freshness": "string (VERY_FRESH, FRESH, RECENT, OLD, EXPIRED)"
                }}
            ],
            "advertising_opportunity": {{
                "relevant": boolean,
                "reason": "string",
                "campaign_angle": "string",
                "urgency": "string (HIGH, MEDIUM, LOW)"
            }},
            "lead_score": int (0-100),
            "lead_grade": "string"
        }}
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" },
                temperature=0.1
            )
            
            result_json = json.loads(response.choices[0].message.content)
            
            # Map AI output back to the profile
            profile.company_name = result_json.get("company_name", profile.company_name)
            profile.industry = result_json.get("industry")
            profile.description = result_json.get("description")
            profile.locations = result_json.get("locations", [])
            profile.services = result_json.get("services", [])
            profile.products = result_json.get("products", [])
            profile.projects = result_json.get("projects", [])
            
            # Reconstruct BuyingSignals
            ai_signals = result_json.get("buying_signals", [])
            profile.buying_signals = [BuyingSignal(**s) for s in ai_signals]
            
            # Reconstruct Advertising Opportunity
            opp = result_json.get("advertising_opportunity", {})
            if opp:
                profile.advertising_opportunity.relevant = opp.get("relevant", False)
                profile.advertising_opportunity.reason = opp.get("reason")
                profile.advertising_opportunity.campaign_angle = opp.get("campaign_angle")
                profile.advertising_opportunity.urgency = opp.get("urgency")
                
            profile.lead_score = result_json.get("lead_score", 0)
            profile.lead_grade = result_json.get("lead_grade", "UNKNOWN")
            
            logger.info(f"AI Analysis completed. Lead Score: {profile.lead_score} ({profile.lead_grade})")
            
        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            profile.crawl_errors.append({"type": "AI_ERROR", "message": str(e)})

        return profile

from typing import List
from datetime import datetime
import re
from dateutil.parser import parse as date_parse
# pyrefly: ignore [missing-import]
from loguru import logger
from .models import BuyingSignal

class SignalAnalyzer:
    """Handles advanced processing of signals including Date Freshness and Deduplication."""
    
    @staticmethod
    def calculate_freshness(signals: List[BuyingSignal]) -> List[BuyingSignal]:
        now = datetime.now()
        
        for signal in signals:
            if not signal.date:
                signal.freshness = "UNKNOWN"
                continue
                
            try:
                # Basic string cleanup for parser
                clean_date_str = signal.date.replace("th", "").replace("st", "").replace("nd", "").replace("rd", "")
                parsed_date = date_parse(clean_date_str, fuzzy=True)
                
                delta_days = (parsed_date - now).days
                
                if delta_days > 0:
                    # Future date (Upcoming event, launch)
                    if delta_days <= 30:
                        signal.freshness = "VERY_FRESH"
                    elif delta_days <= 90:
                        signal.freshness = "FRESH"
                    else:
                        signal.freshness = "RECENT" # Far future
                else:
                    # Past date
                    past_days = abs(delta_days)
                    if past_days <= 30:
                        signal.freshness = "FRESH"
                    elif past_days <= 90:
                        signal.freshness = "RECENT"
                    elif past_days <= 365:
                        signal.freshness = "OLD"
                    else:
                        signal.freshness = "EXPIRED"
                        
            except Exception as e:
                logger.debug(f"Could not parse date '{signal.date}' for freshness: {e}")
                signal.freshness = "UNKNOWN"
                
        return signals

    @staticmethod
    def deduplicate(signals: List[BuyingSignal]) -> List[BuyingSignal]:
        unique_signals: List[BuyingSignal] = []
        
        for new_sig in signals:
            is_duplicate = False
            for existing_sig in unique_signals:
                # If they are the exact same type and share the same date
                if new_sig.type == existing_sig.type:
                    if new_sig.date and existing_sig.date and new_sig.date == existing_sig.date:
                        is_duplicate = True
                        break
                    
                    # Or if their evidence strings are extremely similar (subset)
                    if new_sig.evidence and existing_sig.evidence:
                        if new_sig.evidence.lower() in existing_sig.evidence.lower() or existing_sig.evidence.lower() in new_sig.evidence.lower():
                            is_duplicate = True
                            break
                            
            if not is_duplicate:
                unique_signals.append(new_sig)
            else:
                # Optional: We could merge source_urls here if we change source_url to a list
                pass
                
        return unique_signals

    @staticmethod
    def calculate_data_quality(profile) -> int:
        """Calculates a 0-100 score based on extraction completeness."""
        score = 0
        
        if profile.company_name and profile.company_name != "Unknown": score += 10
        if profile.industry and profile.industry != "Unknown": score += 15
        if profile.description: score += 15
        
        # Checking for Contacts/Socials
        has_social = any([profile.socials.facebook, profile.socials.instagram, profile.socials.linkedin, profile.socials.x])
        if profile.contacts.emails or profile.contacts.phones or has_social:
            score += 20
            
        if profile.buying_signals:
            score += 20
            
        if profile.advertising_opportunity and profile.advertising_opportunity.relevant:
            score += 20
            
        return min(score, 100)


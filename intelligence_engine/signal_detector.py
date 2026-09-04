import re
from typing import List, Dict, Optional
from datetime import datetime
from .models import ScrapedPage, BuyingSignal

class DeterministicSignalDetector:
    """Scans crawled text for high-value advertising signals using deterministic keyword matching."""
    
    SIGNAL_PATTERNS = {
        "NEW_BRANCH": [r"opening\s+(?:our\s+)?(?:new|second|third)\s+(?:branch|location)", r"new\s+location\s+in", r"expanding\s+to"],
        "GRAND_OPENING": [r"grand\s+opening", r"opening\s+soon", r"doors\s+open"],
        "PRODUCT_LAUNCH": [r"launching\s+(?:our\s+)?new\s+product", r"new\s+arrival", r"introducing\s+the\s+new"],
        "PROJECT_LAUNCH": [r"new\s+(?:residential|commercial)\s+project", r"off-plan\s+launch", r"project\s+launch"],
        "UPCOMING_EVENT": [r"upcoming\s+event", r"join\s+us\s+at\s+the", r"register\s+for\s+our\s+event"],
        "EXHIBITION": [r"exhibiting\s+at", r"visit\s+our\s+stand", r"trade\s+show"],
        "PROMOTION": [r"limited\s+time\s+offer", r"special\s+promotion", r"discount\s+on"],
        "SALE": [r"mega\s+sale", r"clearance\s+sale", r"flash\s+sale", r"% off"],
        "REBRANDING": [r"we\s+are\s+rebranding", r"our\s+new\s+look"],
    }
    
    # Simple date extraction (YYYY-MM-DD or Month YYYY)
    DATE_REGEX = re.compile(r"\b(?:202[4-9]|203[0-9])-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:202[4-9]|203[0-9])\b")

    @staticmethod
    def detect_signals(page: ScrapedPage) -> List[BuyingSignal]:
        signals = []
        text_lower = page.clean_text.lower()
        
        for signal_type, patterns in DeterministicSignalDetector.SIGNAL_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Extract a snippet for evidence (50 chars before and after)
                    start_idx = max(0, match.start() - 50)
                    end_idx = min(len(text_lower), match.end() + 50)
                    evidence = page.clean_text[start_idx:end_idx].strip()
                    
                    # Try to extract a date near the match
                    date_match = DeterministicSignalDetector.DATE_REGEX.search(evidence)
                    detected_date = date_match.group(0) if date_match else None
                    
                    signals.append(BuyingSignal(
                        type=signal_type,
                        strength=80, # Base deterministic strength
                        confidence=0.8,
                        description=f"Detected '{pattern.replace(r's+', ' ')}' keyword pattern.",
                        evidence=evidence,
                        source_url=page.url,
                        date=detected_date,
                        freshness="UNKNOWN" # Will be upgraded by AI or Date analyzer
                    ))
                    # Prevent duplicate same-type signals from the same pattern on one page
                    break 
                    
        return signals

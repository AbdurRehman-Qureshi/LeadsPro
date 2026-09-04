import re
from urllib.parse import urlparse

class PageClassifier:
    """Classifies a page into a specific intelligence category based on URL and title."""
    
    CATEGORIES = {
        "HOME": r"^/$|/home",
        "ABOUT": r"about|company|who-we-are|our-story",
        "SERVICES": r"service|what-we-do|solutions",
        "PRODUCTS": r"product|shop|store|collection",
        "PROJECTS": r"project|portfolio|case-study|our-work",
        "LOCATIONS": r"location|branch|find-us|where-to-buy",
        "EVENTS": r"event|exhibition|trade-show|webinar",
        "NEWS": r"news|press|media|announcement",
        "BLOG": r"blog|article|insight",
        "PROMOTIONS": r"promotion|offer|sale|discount|deal",
        "CAMPAIGNS": r"campaign|special",
        "LAUNCHES": r"launch|new-arrival|coming-soon|grand-opening",
        "CAREERS": r"career|job|join-us|vacanc",
        "CONTACT": r"contact|get-in-touch|reach-us"
    }

    @staticmethod
    def classify(url: str, title: str = "") -> str:
        parsed = urlparse(url)
        path = parsed.path.lower()
        query = parsed.query.lower()
        combined_text = f"{path} {query} {title.lower()}"
        
        # Check HOME explicitly
        if path == "" or path == "/":
            return "HOME"
            
        for category, pattern in PageClassifier.CATEGORIES.items():
            if re.search(pattern, combined_text):
                return category
                
        return "OTHER"

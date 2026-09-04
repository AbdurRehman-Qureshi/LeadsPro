class PagePrioritizer:
    """Calculates a crawl priority score based on page classification and high-value keywords."""
    
    BASE_SCORES = {
        "HOME": 100,
        "EVENTS": 95,
        "PROMOTIONS": 95,
        "CAMPAIGNS": 95,
        "LAUNCHES": 95,
        "NEWS": 90,
        "PROJECTS": 90,
        "LOCATIONS": 85,
        "PRODUCTS": 75,
        "SERVICES": 70,
        "BLOG": 60,
        "ABOUT": 50,
        "CONTACT": 40,
        "CAREERS": 20,
        "OTHER": 10
    }
    
    # High-value keywords that boost priority regardless of category
    BOOST_KEYWORDS = [
        "new", "launch", "opening", "opened", "grand opening", "coming soon", 
        "expansion", "branch", "location", "promotion", "offer", "sale", 
        "event", "exhibition", "festival", "campaign", "project", 
        "development", "announcement", "rebrand"
    ]

    @staticmethod
    def calculate_priority(category: str, url: str, title: str = "") -> int:
        score = PagePrioritizer.BASE_SCORES.get(category, 10)
        
        # Apply boosts based on high-value keywords in URL or Title
        combined_text = f"{url.lower()} {title.lower()}"
        for keyword in PagePrioritizer.BOOST_KEYWORDS:
            if keyword in combined_text:
                score += 5 # Add small boost per keyword
                
        # Cap at 100
        return min(score, 100)

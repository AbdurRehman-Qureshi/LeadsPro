import re
from typing import List, Dict, Set
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from .models import ContactInfo, SocialLinks

class ContactExtractor:
    EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    # Basic phone regex; can be improved
    PHONE_REGEX = re.compile(r"\+?(?:[0-9]\s?){6,14}[0-9]")

    @staticmethod
    def extract_from_html(html: str, source_url: str) -> tuple[ContactInfo, SocialLinks]:
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator=' ')
        
        # 1. Extract Emails
        emails = set(re.findall(ContactExtractor.EMAIL_REGEX, text))
        email_dicts = []
        for em in emails:
            # Simple heuristic for type
            em_lower = em.lower()
            em_type = "general"
            if "sales" in em_lower: em_type = "sales"
            elif "info" in em_lower: em_type = "info"
            elif "support" in em_lower: em_type = "support"
            elif "career" in em_lower or "hr@" in em_lower: em_type = "careers"
            
            email_dicts.append({
                "email": em,
                "type": em_type,
                "source": source_url
            })
            
        # 2. Extract Phones (Very basic, from 'tel:' links + text heuristic)
        phones = set()
        for a in soup.find_all('a', href=True):
            if a['href'].startswith('tel:'):
                phones.add(a['href'].replace('tel:', '').strip())
                
        # If no tel links, try regex on text (can be noisy, so we limit length)
        if not phones:
            potential_phones = re.findall(ContactExtractor.PHONE_REGEX, text)
            for p in potential_phones:
                p_clean = p.strip()
                if 8 <= len(re.sub(r'\D', '', p_clean)) <= 15:
                    phones.add(p_clean)
                    
        phone_dicts = [{"phone": p, "source": source_url} for p in phones]
        
        # 3. Extract Social Links from DOM
        socials = SocialLinks()
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if 'facebook.com' in href and not socials.facebook:
                socials.facebook = a['href']
            elif 'instagram.com' in href and not socials.instagram:
                socials.instagram = a['href']
            elif 'linkedin.com' in href and not socials.linkedin:
                socials.linkedin = a['href']
            elif ('twitter.com' in href or 'x.com' in href) and not socials.x:
                socials.x = a['href']
            elif 'youtube.com' in href and not socials.youtube:
                socials.youtube = a['href']
            elif 'tiktok.com' in href and not socials.tiktok:
                socials.tiktok = a['href']
                
        return ContactInfo(emails=email_dicts, phones=phone_dicts), socials

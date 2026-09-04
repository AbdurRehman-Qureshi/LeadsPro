import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

class Normalizer:
    @staticmethod
    def normalize_name(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        return re.sub(r'\s+', ' ', name).strip()

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        cleaned = re.sub(r'[^\d+]', '', phone)
        return cleaned if cleaned else None

    @staticmethod
    def normalize_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            parsed = urlparse(url)
            clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, '', parsed.fragment))
            return clean.rstrip('/')
        except Exception:
            return url

    @staticmethod
    def normalize_address(address: Optional[str]) -> Optional[str]:
        if not address:
            return None
        return re.sub(r'\s+', ' ', address).strip()
        
    @staticmethod
    def parse_address(address: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        # Returns (city, area, country)
        if not address:
            return None, None, None
            
        parts = [p.strip() for p in address.split('-') if p.strip()]
        if not parts:
            parts = [p.strip() for p in address.split(',') if p.strip()]
            
        country = parts[-1] if len(parts) > 0 else None
        city = parts[-2] if len(parts) > 1 else None
        area = parts[-3] if len(parts) > 2 else None
        
        return city, area, country

class Validator:
    @staticmethod
    def is_valid_record(data: dict) -> tuple[bool, str]:
        # Business name should not be empty
        if not data.get("raw_name") or not str(data.get("raw_name")).strip():
            return False, "Missing or empty business name"
            
        rating = data.get("google_rating")
        if rating is not None and (rating < 1.0 or rating > 5.0):
            return False, f"Invalid rating value: {rating}"
            
        lat = data.get("latitude")
        if lat is not None and (lat < -90 or lat > 90):
            return False, f"Invalid latitude: {lat}"
            
        lng = data.get("longitude")
        if lng is not None and (lng < -180 or lng > 180):
            return False, f"Invalid longitude: {lng}"
            
        website = data.get("website")
        if website:
            if not website.startswith("http") or len(website) < 5:
                return False, f"Invalid website format: {website}"
                
        return True, ""

class Deduplicator:
    @staticmethod
    def is_duplicate(existing_records: list, new_record: dict) -> bool:
        new_place_id = new_record.get("place_id")
        new_phone = new_record.get("raw_phone")
        new_name = new_record.get("raw_name")
        new_address = new_record.get("raw_address")
        
        for record in existing_records:
            if new_place_id and record.place_id == new_place_id:
                return True
            if new_phone and record.raw_phone == new_phone:
                return True
            if new_name and new_address and record.raw_name == new_name and record.raw_address == new_address:
                return True
                
        return False

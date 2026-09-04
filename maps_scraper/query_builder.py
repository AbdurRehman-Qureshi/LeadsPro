import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
# pyrefly: ignore [missing-import]
from loguru import logger
# pyrefly: ignore [missing-import]
from core_db.database import DBSearchConfiguration, DBSearchQuery

class SearchConfigurationInput(BaseModel):
    business_category: str
    category_variations: Optional[List[str]] = Field(default_factory=list)
    country: Optional[str] = None
    city: Optional[str] = None
    areas: Optional[List[str]] = Field(default_factory=list)
    target_results: Optional[int] = None
    max_queries: int = 20
    search_depth: int = 1

class QueryBuilder:
    def __init__(self, db_session):
        self.db = db_session

    def _normalize_query(self, query: str) -> str:
        # Normalize: leading/trailing whitespace, repeated spaces, lowercased
        normalized = re.sub(r'\s+', ' ', query).strip().lower()
        return normalized

    def build_queries(self, config_input: dict) -> DBSearchConfiguration:
        try:
            config = SearchConfigurationInput(**config_input)
        except Exception as e:
            logger.error(f"[CONFIG_VALIDATION_FAILED] Invalid configuration: {e}")
            raise ValueError(f"Invalid search configuration: {e}")

        # Create persistent configuration
        db_config = DBSearchConfiguration(
            business_category=config.business_category,
            category_variations=json.dumps(config.category_variations),
            country=config.country,
            city=config.city,
            areas=json.dumps(config.areas),
            target_results=config.target_results,
            max_queries=config.max_queries,
            search_depth=config.search_depth
        )
        self.db.add(db_config)
        self.db.flush() # flush to get db_config.id

        logger.info(f"[CONFIG_CREATED] Config ID: {db_config.id} - Target: {config.target_results}")

        generated_queries = []
        seen_normalized = set()
        
        def add_query(raw_query: str, q_type: str, priority: int, location: str = None):
            norm = self._normalize_query(raw_query)
            if norm not in seen_normalized:
                seen_normalized.add(norm)
                generated_queries.append({
                    "query": raw_query,
                    "normalized_query": norm,
                    "location": location,
                    "priority": priority,
                    "query_type": q_type
                })

        # Base Location String
        base_loc_parts = []
        if config.city:
            base_loc_parts.append(config.city)
        if config.country:
            base_loc_parts.append(config.country)
        base_location_str = " ".join(base_loc_parts)

        # Layer 1 - Primary Query
        if base_location_str:
            primary_q = f"{config.business_category} in {config.city}" if config.city else f"{config.business_category} in {config.country}"
        else:
            primary_q = config.business_category
            
        add_query(primary_q, "PRIMARY", priority=1, location=base_location_str)

        # Layer 2 - Basic Variations
        # e.g., "Gyms Dubai"
        if base_location_str:
            add_query(f"{config.business_category} {base_location_str}", "CATEGORY_VARIATION", priority=2, location=base_location_str)

        for var in config.category_variations:
            if base_location_str:
                add_query(f"{var} in {base_location_str}", "CATEGORY_VARIATION", priority=3, location=base_location_str)
                add_query(f"{var} {base_location_str}", "CATEGORY_VARIATION", priority=4, location=base_location_str)
            else:
                add_query(var, "CATEGORY_VARIATION", priority=3, location=None)

        # Layer 3 - Geographic Expansion (Areas)
        area_priority = 5
        for area in config.areas:
            # "Gyms in Downtown Dubai"
            loc_str = f"{area}, {base_location_str}" if base_location_str else area
            
            # Primary category in area
            add_query(f"{config.business_category} in {area}", "AREA", priority=area_priority, location=loc_str)
            area_priority += 1
            
            # Category variations in area
            for var in config.category_variations:
                add_query(f"{var} in {area}", "AREA_VARIATION", priority=area_priority, location=loc_str)
                area_priority += 1

        # Limit by max_queries
        # Sort by priority just in case, but they should already be ordered
        generated_queries.sort(key=lambda x: x["priority"])
        final_queries = generated_queries[:config.max_queries]

        logger.info(f"[QUERIES_GENERATED] Generated {len(final_queries)} unique queries for Config {db_config.id}")

        # Persist queries
        for q_data in final_queries:
            db_query = DBSearchQuery(
                search_configuration_id=db_config.id,
                query=q_data["query"],
                normalized_query=q_data["normalized_query"],
                location=q_data["location"],
                priority=q_data["priority"],
                query_type=q_data["query_type"]
            )
            self.db.add(db_query)

        self.db.commit()
        return db_config

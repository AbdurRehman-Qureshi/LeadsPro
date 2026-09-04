import asyncio
import datetime
import uuid
import sys
# pyrefly: ignore [missing-import]
from loguru import logger
from core_db.database import init_db, DBSearchJob, DBDiscoveryResult, DBBusiness, DBScrapeTask, DBScrapeAttempt
from maps_scraper.discovery import GoogleMapsDiscovery
from maps_scraper.extractor import ProfileExtractor
from maps_scraper.validation import Normalizer, Validator, Deduplicator

class SearchJobManager:
    def __init__(self, db_session):
        self.db = db_session
        self.discovery = GoogleMapsDiscovery(headless=True)
        self.extractor = ProfileExtractor(headless=True)
        
    def _create_job(self, query: str, location: str = None, search_query_id: int = None) -> DBSearchJob:
        job_id_string = f"job_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        job = DBSearchJob(
            search_query_id=search_query_id,
            job_id_string=job_id_string,
            query=query,
            location=location,
            status="PENDING",
            created_at=datetime.datetime.utcnow()
        )
        self.db.add(job)
        self.db.commit()
        logger.info(f"[JOB_CREATED] ID: {job.id} - Query: '{query}'")
        return job

    async def run_discovery_stage(self, job: DBSearchJob, max_results: int = 50):
        """Stage A: Discover profile URLs and create tasks."""
        job.status = "RUNNING"
        job.started_at = datetime.datetime.utcnow()
        self.db.commit()
        
        logger.info(f"[DISCOVERY_STARTED] Job ID: {job.id}")
        
        try:
            discovery_results = await self.discovery.discover(job.query, max_results=max_results)
            job.total_discovered = len(discovery_results)
            
            added_tasks = 0
            for res in discovery_results:
                url = res["url"]
                # Store Discovery Result
                dr = DBDiscoveryResult(
                    search_job_id=job.id,
                    business_name=res.get("business_name"),
                    google_maps_url=url,
                    place_id=res.get("place_id"),
                    rank=res.get("rank"),
                    discovery_timestamp=datetime.datetime.utcnow()
                )
                self.db.add(dr)
                
                # Check if task already exists globally or just add it
                existing_task = self.db.query(DBScrapeTask).filter(DBScrapeTask.url == url).first()
                if not existing_task:
                    new_task = DBScrapeTask(
                        search_job_id=job.id,
                        url=url,
                        query=job.query,
                        state="PENDING"
                    )
                    self.db.add(new_task)
                    added_tasks += 1
                    logger.info(f"[BUSINESS_DISCOVERED] Name: {res.get('business_name')} (Rank: {res.get('rank')})")
                else:
                    logger.info(f"[DUPLICATE_FOUND] Task already exists for URL: {url}")
                    
            job.total_tasks += added_tasks
            self.db.commit()
            logger.info(f"[DISCOVERY_COMPLETED] Added {added_tasks} new scrape tasks for Job {job.id}.")
            
        except Exception as e:
            logger.error(f"[DISCOVERY_FAILED] Job ID: {job.id}, Error: {e}")
            job.status = "FAILED"
            self.db.commit()

    def _determine_error_category(self, error_message: str) -> str:
        err_lower = error_message.lower()
        if "timeout" in err_lower:
            return "NETWORK_TIMEOUT"
        if "navigation" in err_lower or "net::" in err_lower:
            return "NAVIGATION_ERROR"
        return "UNKNOWN_ERROR"

    async def run_extraction_stage(self, job: DBSearchJob, prisma_client, max_tasks: int = 10, max_retries: int = 3):
        """Stage B: Process pending scrape tasks concurrently and sync to Supabase."""
        logger.info(f"Starting Extraction Stage for Job {job.id}")
        
        tasks = self.db.query(DBScrapeTask).filter(
            DBScrapeTask.search_job_id == job.id,
            (DBScrapeTask.state == 'PENDING') | (DBScrapeTask.state == 'RETRY')
        ).limit(max_tasks).all()
        
        if not tasks:
            logger.info("No pending tasks found for this job.")
            return

        attempts_dict = {}
        for task in tasks:
            task.state = 'RUNNING'
            task.attempts += 1
            task.last_attempt_time = datetime.datetime.utcnow()
            
            logger.info(f"[PROFILE_SCRAPE_STARTED] Task ID: {task.id} (Attempt {task.attempts})")
            
            attempt = DBScrapeAttempt(
                task_id=task.id,
                attempt_number=task.attempts,
                started_time=datetime.datetime.utcnow()
            )
            self.db.add(attempt)
            attempts_dict[task.id] = attempt
            
        self.db.commit()

        sem = asyncio.Semaphore(15)
        
        async def scrape_wrapper(task_id, url, query, location):
            try:
                async with sem:
                    raw_data = await self.extractor.extract_profile(url)
                raw_data['discovery_query'] = query
                raw_data['source'] = 'Google Maps'
                raw_data['search_location'] = location
                raw_data['raw_phone'] = raw_data.pop('phone', None)
                return task_id, raw_data, None
            except Exception as e:
                return task_id, None, str(e)

        logger.info(f"Processing {len(tasks)} Google Maps profiles concurrently (Limit: 5)...")
        coroutines = [scrape_wrapper(task.id, task.url, task.query, job.location) for task in tasks]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Unhandled concurrency exception: {res}")
                continue
                
            task_id, raw_data, error_msg = res
            task = next(t for t in tasks if t.id == task_id)
            attempt = attempts_dict[task.id]
            
            if error_msg:
                error_cat = self._determine_error_category(error_msg)
                
                attempt.status = 'FAILED'
                attempt.completed_time = datetime.datetime.utcnow()
                attempt.execution_duration = (attempt.completed_time - attempt.started_time).total_seconds()
                attempt.error_category = error_cat
                attempt.error_message = error_msg
                
                logger.error(f"[PROFILE_SCRAPE_FAILED] Task ID: {task.id}, Error: {error_msg}")
                
                task.last_error = error_msg
                if task.attempts >= max_retries:
                    task.state = 'FAILED'
                    job.total_failed += 1
                    job.total_processed += 1
                else:
                    task.state = 'RETRY'
                    job.total_retries += 1
                    logger.info(f"[PROFILE_RETRY] Task ID: {task.id} queued for retry.")
            else:
                try:
                    # Validation
                    is_valid, validation_msg = Validator.is_valid_record(raw_data)
                    if not is_valid:
                        raise ValueError(f"Validation failed: {validation_msg}")
                    
                    # Normalization
                    normalized_name = Normalizer.normalize_name(raw_data.get('raw_name'))
                    normalized_phone = Normalizer.normalize_phone(raw_data.get('raw_phone'))
                    normalized_website = Normalizer.normalize_url(raw_data.get('website'))
                    normalized_address = Normalizer.normalize_address(raw_data.get('raw_address'))
                    
                    raw_data['normalized_name'] = normalized_name
                    raw_data['phone'] = normalized_phone
                    raw_data['website'] = normalized_website
                    raw_data['normalized_address'] = normalized_address
                    logger.info(f"[NORMALIZATION_COMPLETED] Task ID: {task.id}")
                    
                    # Deduplication
                    existing_records = self.db.query(DBBusiness).all()
                    if Deduplicator.is_duplicate(existing_records, raw_data):
                        logger.info(f"[DUPLICATE_FOUND] Business already exists: {raw_data.get('raw_name')}")
                        job.total_duplicates += 1
                    else:
                        city, area, country = Normalizer.parse_address(normalized_address)
                        new_business = DBBusiness(
                            search_job_id=job.job_id_string,
                            place_id=raw_data.get('place_id'),
                            raw_name=raw_data.get('raw_name', ''),
                            normalized_name=normalized_name,
                            primary_category=raw_data.get('primary_category'),
                            raw_address=raw_data.get('raw_address'),
                            normalized_address=normalized_address,
                            city=city,
                            area=area,
                            country=country,
                            raw_phone=raw_data.get('raw_phone'),
                            normalized_phone=normalized_phone,
                            website=raw_data.get('website'),
                            social_facebook=raw_data.get('social_facebook'),
                            social_instagram=raw_data.get('social_instagram'),
                            social_linkedin=raw_data.get('social_linkedin'),
                            social_x=raw_data.get('social_x'),
                            google_rating=raw_data.get('google_rating'),
                            review_count=raw_data.get('review_count'),
                            google_maps_url=raw_data.get('google_maps_url'),
                            latitude=raw_data.get('latitude'),
                            longitude=raw_data.get('longitude'),
                            status=raw_data.get('status'),
                            discovery_query=raw_data['discovery_query'],
                            search_location=raw_data['search_location'],
                            source=raw_data['source']
                        )
                        self.db.add(new_business)
                        
                        # ----- SUPABASE SYNC -----
                        try:
                            business_data = {
                                "searchJobId": job.job_id_string,
                                "rawName": raw_data.get('raw_name', ''),
                                "normalizedName": normalized_name,
                                "primaryCategory": raw_data.get('primary_category'),
                                "rawAddress": raw_data.get('raw_address'),
                                "normalizedAddress": normalized_address,
                                "city": city,
                                "area": area,
                                "country": country,
                                "rawPhone": raw_data.get('raw_phone'),
                                "phone": normalized_phone,
                                "website": raw_data.get('website'),
                                "socialFacebook": raw_data.get('social_facebook'),
                                "socialInstagram": raw_data.get('social_instagram'),
                                "socialLinkedin": raw_data.get('social_linkedin'),
                                "socialX": raw_data.get('social_x'),
                                "googleRating": float(raw_data.get('google_rating')) if raw_data.get('google_rating') is not None else None,
                                "reviewCount": int(raw_data.get('review_count')) if raw_data.get('review_count') is not None else None,
                                "googleMapsUrl": raw_data.get('google_maps_url'),
                                "latitude": float(raw_data.get('latitude')) if raw_data.get('latitude') is not None else None,
                                "longitude": float(raw_data.get('longitude')) if raw_data.get('longitude') is not None else None,
                                "businessStatus": raw_data.get('status'),
                                "discoveryQuery": raw_data['discovery_query'],
                                "searchLocation": raw_data['search_location'],
                                "source": raw_data['source']
                            }
                            
                            if raw_data.get('place_id'):
                                await prisma_client.businesslead.upsert(
                                    where={"placeId": raw_data.get('place_id')},
                                    data={
                                        "create": {**business_data, "placeId": raw_data.get('place_id')},
                                        "update": {
                                            "googleRating": business_data["googleRating"],
                                            "reviewCount": business_data["reviewCount"]
                                        }
                                    }
                                )
                            else:
                                await prisma_client.businesslead.create(data=business_data)
                                
                            job.total_unique += 1
                            job.total_successful += 1
                            logger.info(f"[BUSINESS_CREATED & SYNCED] Name: {normalized_name}")
                        except Exception as sync_e:
                            logger.error(f"[SUPABASE_SYNC_FAILED] Could not sync {normalized_name}: {sync_e}")
                            raise ValueError(f"Supabase Sync Failed: {sync_e}")
                    
                    task.state = 'COMPLETED'
                    task.completed_time = datetime.datetime.utcnow()
                    
                    attempt.status = 'SUCCESS'
                    attempt.completed_time = datetime.datetime.utcnow()
                    attempt.execution_duration = (attempt.completed_time - attempt.started_time).total_seconds()
                    
                    job.total_processed += 1
                    logger.info(f"[PROFILE_SCRAPE_SUCCESS] Task ID: {task.id}")
                    
                except Exception as db_e:
                    error_msg = str(db_e)
                    error_cat = self._determine_error_category(error_msg)
                    
                    attempt.status = 'FAILED'
                    attempt.completed_time = datetime.datetime.utcnow()
                    attempt.execution_duration = (attempt.completed_time - attempt.started_time).total_seconds()
                    attempt.error_category = error_cat
                    attempt.error_message = error_msg
                    
                    logger.error(f"[PROFILE_PROCESS_FAILED] Task ID: {task.id}, Error: {error_msg}")
                    
                    task.last_error = error_msg
                    if task.attempts >= max_retries:
                        task.state = 'FAILED'
                        job.total_failed += 1
                        job.total_processed += 1
                    else:
                        task.state = 'RETRY'
                        job.total_retries += 1
                        logger.info(f"[PROFILE_RETRY] Task ID: {task.id} queued for retry.")

        self.db.commit()

    def _complete_job(self, job: DBSearchJob):
        job.completed_at = datetime.datetime.utcnow()
        if job.total_failed > 0 and job.total_successful > 0:
            job.status = "PARTIAL"
            logger.info(f"[JOB_PARTIAL] ID: {job.id}")
        elif job.total_failed > 0 and job.total_successful == 0:
            job.status = "FAILED"
            logger.info(f"[JOB_FAILED] ID: {job.id}")
        else:
            job.status = "COMPLETED"
            logger.info(f"[JOB_COMPLETED] ID: {job.id}")
        self.db.commit()

    async def run_full_pipeline(self, query: str, location: str = None, max_results: int = 50, search_query_id: int = None):
        from prisma import Prisma
        prisma_client = Prisma()
        await prisma_client.connect()
        
        job = self._create_job(query, location, search_query_id=search_query_id)
        
        await self.run_discovery_stage(job, max_results)
        
        # In a real system, you might loop extraction until all retries are exhausted.
        # We will loop enough times to process all generated tasks including retries.
        max_loops = 5
        for _ in range(max_loops):
            pending_count = self.db.query(DBScrapeTask).filter(
                DBScrapeTask.search_job_id == job.id,
                (DBScrapeTask.state == 'PENDING') | (DBScrapeTask.state == 'RETRY')
            ).count()
            
            if pending_count == 0:
                break
                
            await self.run_extraction_stage(job, prisma_client, max_tasks=max_results)
            
        self._complete_job(job)
        await prisma_client.disconnect()
        
        # Print stats
        logger.info(f"--- JOB STATISTICS ({job.job_id_string}) ---")
        logger.info(f"Status: {job.status}")
        logger.info(f"Discovered: {job.total_discovered}")
        logger.info(f"Unique: {job.total_unique}")
        logger.info(f"Duplicates: {job.total_duplicates}")
        logger.info(f"Tasks Created: {job.total_tasks}")
        logger.info(f"Processed: {job.total_processed}")
        logger.info(f"Successful: {job.total_successful}")
        logger.info(f"Failed: {job.total_failed}")
        logger.info(f"Retries: {job.total_retries}")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    db_session = init_db()
    manager = SearchJobManager(db_session)
    
    # Import QueryBuilder here to avoid circular imports if any
    from maps_scraper.query_builder import QueryBuilder, DBSearchQuery
    
    qb = QueryBuilder(db_session)
    
    # Define a test configuration bypassing Google pagination!
    config_input = {
        "business_category": "Dental Clinics",
        "category_variations": ["Dental Centers", "Dentist"],
        "country": "United Arab Emirates",
        "city": "Dubai",
        "areas": ["Downtown Dubai"],
        "target_results": 20,
        "max_queries": 1 # Limit to 1 query for quick generation
    }
    
    print("\n--- Building Query Plan ---")
    db_config = qb.build_queries(config_input)
    
    # Fetch generated queries
    queries_to_run = db_session.query(DBSearchQuery).filter(
        DBSearchQuery.search_configuration_id == db_config.id,
        DBSearchQuery.status == "PENDING"
    ).order_by(DBSearchQuery.priority).limit(1).all()
    
    print(f"\n--- Discovered {len(queries_to_run)} search queries to execute ---")
    for q in queries_to_run:
        print(f"[{q.priority}] {q.query}")
        
    for q in queries_to_run:
        q.status = "RUNNING"
        db_session.commit()
        
        print(f"\n--- Starting Pipeline for '{q.query}' ---\n")
        asyncio.run(manager.run_full_pipeline(q.query, location=q.location, max_results=20, search_query_id=q.id))
        
        q.status = "COMPLETED"
        db_session.commit()


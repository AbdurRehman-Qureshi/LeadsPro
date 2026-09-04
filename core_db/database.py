import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class DBSearchConfiguration(Base):
    __tablename__ = 'search_configurations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_category = Column(String, nullable=False)
    category_variations = Column(String, nullable=True) # Stored as JSON string or comma-separated
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    areas = Column(String, nullable=True) # Stored as JSON string or comma-separated
    target_results = Column(Integer, nullable=True)
    max_queries = Column(Integer, default=20)
    search_depth = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class DBSearchQuery(Base):
    __tablename__ = 'search_queries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    search_configuration_id = Column(Integer, ForeignKey('search_configurations.id'), nullable=False)
    query = Column(String, nullable=False)
    normalized_query = Column(String, nullable=False)
    location = Column(String, nullable=True)
    priority = Column(Integer, default=1)
    query_type = Column(String, nullable=False) # PRIMARY, CATEGORY_VARIATION, AREA, AREA_VARIATION
    status = Column(String, default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DBSearchJob(Base):
    __tablename__ = 'search_jobs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    search_query_id = Column(Integer, ForeignKey('search_queries.id'), nullable=True)
    job_id_string = Column(String, unique=True, nullable=False)
    query = Column(String, nullable=False)
    location = Column(String, nullable=True)
    status = Column(String, default="PENDING") # PENDING, RUNNING, PARTIAL, COMPLETED, FAILED
    
    # Statistics
    total_discovered = Column(Integer, default=0)
    total_unique = Column(Integer, default=0)
    total_duplicates = Column(Integer, default=0)
    total_tasks = Column(Integer, default=0)
    total_processed = Column(Integer, default=0)
    total_successful = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    total_retries = Column(Integer, default=0)
    

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class DBDiscoveryResult(Base):
    __tablename__ = 'discovery_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    search_job_id = Column(Integer, ForeignKey('search_jobs.id'))
    business_name = Column(String, nullable=True)
    google_maps_url = Column(String, nullable=False)
    place_id = Column(String, nullable=True)
    rank = Column(Integer, nullable=True)
    discovery_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class DBBusiness(Base):
    __tablename__ = 'businesses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    place_id = Column(String, unique=True, nullable=True) # Used for deduplication
    
    raw_name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=False)
    primary_category = Column(String)
    
    raw_address = Column(String)
    normalized_address = Column(String)
    city = Column(String)
    area = Column(String)
    country = Column(String)
    
    raw_phone = Column(String)
    normalized_phone = Column(String)
    
    website = Column(String)
    google_rating = Column(Float)
    review_count = Column(Integer)
    google_maps_url = Column(String, nullable=True)
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(String)
    
    # Social Links
    social_facebook = Column(String, nullable=True)
    social_instagram = Column(String, nullable=True)
    social_linkedin = Column(String, nullable=True)
    social_x = Column(String, nullable=True)
    
    # Discovery Metadata
    discovery_query = Column(String)
    search_location = Column(String)
    source = Column(String, default="Google Maps")
    discovery_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    scrape_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    search_job_id = Column(String)

class DBScrapeTask(Base):
    __tablename__ = 'scrape_tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    search_job_id = Column(Integer, ForeignKey('search_jobs.id'))
    url = Column(String, unique=True, nullable=False)
    query = Column(String, nullable=False)
    state = Column(String, default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED, RETRY
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_attempt_time = Column(DateTime, nullable=True)
    completed_time = Column(DateTime, nullable=True)

class DBScrapeAttempt(Base):
    __tablename__ = 'scrape_attempts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('scrape_tasks.id'))
    attempt_number = Column(Integer, nullable=False)
    started_time = Column(DateTime, default=datetime.datetime.utcnow)
    completed_time = Column(DateTime, nullable=True)
    status = Column(String) # SUCCESS, FAILED
    error_category = Column(String, nullable=True) # PAGE_LOAD_ERROR, NETWORK_TIMEOUT, etc.
    error_message = Column(Text, nullable=True)
    execution_duration = Column(Float, nullable=True) # Duration in seconds

def init_db(db_path="sqlite:///../discovery.db"):
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

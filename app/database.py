import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
from app.utils.logger import get_logger

DATABASE_URL = settings.database_url
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

logger = get_logger(__name__)


def _direct_url() -> str:
    url = DATABASE_URL
    url = url.replace("-pooler", "")
    if "?sslmode=require" in url and "pooler" not in url:
        url = url.replace("?sslmode=require&channel_binding=require", "?sslmode=require")
    return url


_MIGRATIONS = [
    "ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS embedding vector(384)",
    "CREATE INDEX IF NOT EXISTS idx_job_descriptions_embedding ON job_descriptions USING hnsw (embedding vector_cosine_ops)",
    "ALTER TABLE parsed_resumes ADD COLUMN IF NOT EXISTS embedding vector(384)",
    "CREATE INDEX IF NOT EXISTS idx_parsed_resumes_embedding ON parsed_resumes USING hnsw (embedding vector_cosine_ops)",
    # New columns for v2 schema
    "ALTER TABLE personal_info ADD COLUMN IF NOT EXISTS linkedin VARCHAR(255)",
    "ALTER TABLE personal_info ADD COLUMN IF NOT EXISTS social_links TEXT",
    "ALTER TABLE personal_info ADD COLUMN IF NOT EXISTS profile_summary TEXT",
    "ALTER TABLE education ADD COLUMN IF NOT EXISTS university VARCHAR(300)",
    "ALTER TABLE education ADD COLUMN IF NOT EXISTS gpa VARCHAR(20)",
    "ALTER TABLE education ADD COLUMN IF NOT EXISTS percentage VARCHAR(20)",
    "ALTER TABLE education ADD COLUMN IF NOT EXISTS board VARCHAR(50)",
    "ALTER TABLE education ADD COLUMN IF NOT EXISTS level VARCHAR(20)",
    "ALTER TABLE experience ADD COLUMN IF NOT EXISTS current_department VARCHAR(200)",
    "ALTER TABLE experience ADD COLUMN IF NOT EXISTS registration_council VARCHAR(200)",
    "ALTER TABLE experience ADD COLUMN IF NOT EXISTS registration_year INTEGER",
    "ALTER TABLE resume_skills ADD COLUMN IF NOT EXISTS category VARCHAR(20)",
    "ALTER TABLE resume_certifications ADD COLUMN IF NOT EXISTS abbreviation VARCHAR(50)",
    "ALTER TABLE resume_certifications ADD COLUMN IF NOT EXISTS issuer VARCHAR(300)",
    "ALTER TABLE resume_certifications ADD COLUMN IF NOT EXISTS year INTEGER",
    "ALTER TABLE resume_certifications ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE resume_certifications RENAME COLUMN certification TO name",
    "ALTER TABLE resume_languages ADD COLUMN IF NOT EXISTS proficiency VARCHAR(20)",
    "ALTER TABLE work_history ADD COLUMN IF NOT EXISTS employer_city VARCHAR(100)",
    "ALTER TABLE work_history ADD COLUMN IF NOT EXISTS department VARCHAR(200)",
    "ALTER TABLE work_history ADD COLUMN IF NOT EXISTS duration_months INTEGER",
    "ALTER TABLE work_history ADD COLUMN IF NOT EXISTS employment_type VARCHAR(50)",
]


def _run_migrations(engine):
    for stmt in _MIGRATIONS:
        try:
            with engine.connect() as conn:
                conn.execute(text(stmt))
                conn.commit()
        except Exception as e:
            logger.warning(f"Migration statement failed (non-fatal): {stmt[:60]}... -> {e}")


def init_db():
    direct_engine = create_engine(_direct_url())
    try:
        with direct_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(bind=direct_engine)
        _run_migrations(direct_engine)
    except Exception as e:
        logger.warning(f"Database initialization failed (non-fatal): {e}")
    finally:
        direct_engine.dispose()


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

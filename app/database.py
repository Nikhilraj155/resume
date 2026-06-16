import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.utils.logger import get_logger

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

# Pooled engine for runtime queries (works with Neon's PgBouncer)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def _direct_url() -> str:
    """Return a direct (non-pooled) connection URL for DDL operations.
    Neon's PgBouncer pooler ignores DDL statements like CREATE TABLE."""
    url = DATABASE_URL
    # Replace '-pooler' in hostname for a direct connection
    url = url.replace("-pooler", "")
    # Pooled connections use '?sslmode=require' — direct needs just the base
    if "?sslmode=require" in url and "pooler" not in url:
        url = url.replace("?sslmode=require&channel_binding=require", "?sslmode=require")
    return url


_MIGRATIONS = [
    "ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS embedding vector(384)",
    "CREATE INDEX IF NOT EXISTS idx_job_descriptions_embedding ON job_descriptions USING hnsw (embedding vector_cosine_ops)",
]


def _run_migrations(engine):
    for stmt in _MIGRATIONS:
        try:
            with engine.connect() as conn:
                conn.execute(text(stmt))
                conn.commit()
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Migration statement failed (non-fatal): {stmt[:60]}... -> {e}")


def init_db():
    """Create all tables using a direct (non-pooled) connection."""
    direct_engine = create_engine(_direct_url())
    try:
        with direct_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(bind=direct_engine)
        _run_migrations(direct_engine)
    finally:
        direct_engine.dispose()


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

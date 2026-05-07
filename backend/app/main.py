import os
import hashlib
import logging
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .routers import publications, users, scraping, authors
from .models.database import engine, SessionLocal
from .models.models import Base, Publication, Author, User
from .utils.sql_importer import initialize_database_from_sql


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables in the database (also creates publication_fingerprints on first run)
Base.metadata.create_all(bind=engine)


def _normalize_title(title: str) -> str:
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    return ' '.join(title.split())


def _title_hash(title: str) -> str | None:
    n = _normalize_title(title)
    if not n:
        return None
    return hashlib.sha256(n.encode()).hexdigest()


def _run_migrations():
    """Add columns that didn't exist in earlier schema versions."""
    col_migrations = [
        ("current_entries", "content_hash", "VARCHAR"),
        ("scraped_publications", "content_hash", "VARCHAR"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in col_migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
                logger.info("Migration: added %s.%s", table, column)
            except Exception:
                pass  # Column already exists


def _backfill_fingerprints():
    """Populate publication_fingerprints for any existing rows not yet covered."""
    from .models.models import PublicationFingerprint, ScrapedPublication
    db: Session = SessionLocal()
    try:
        # Helper: upsert a fingerprint row if not already present
        def _ensure(source_table: str, source_id: int, title: str | None, doi: str | None):
            exists = db.query(PublicationFingerprint).filter_by(
                source_table=source_table, source_id=source_id
            ).first()
            if exists:
                return
            th = _title_hash(title) if title else None
            clean_doi = doi.strip() if doi and doi.strip() else None
            db.add(PublicationFingerprint(
                source_table=source_table,
                source_id=source_id,
                doi=clean_doi,
                title_hash=th,
                title=title,
            ))

        for pub in db.query(Publication).all():
            _ensure("publications", pub.id, pub.title, pub.doi)

        for sp in db.query(ScrapedPublication).all():
            _ensure("scraped_publications", sp.id, sp.title, sp.doi)

        db.commit()
        logger.info("Fingerprint backfill complete.")
    except Exception as e:
        logger.error("Fingerprint backfill failed: %s", e)
        db.rollback()
    finally:
        db.close()


_run_migrations()
_backfill_fingerprints()

# ── Startup key check ────────────────────────────────────────────────────────
_nvidia_token = os.getenv("NVIDIA_TOKEN")
_hf_token = os.getenv("HF_TOKEN")
logger.info("NVIDIA_TOKEN: %s", f"set ({_nvidia_token[:8]}...)" if _nvidia_token else "NOT SET")
logger.info("HF_TOKEN:     %s", f"set ({_hf_token[:8]}...)" if _hf_token else "NOT SET")


app = FastAPI(
    title="Publications API",
    description="API for managing academic publications",
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Check if we're in production mode
is_production = os.getenv("SERVE_STATIC", "false").lower() == "true"


# Include routers
if is_production:
    # In production, prefix API routes with /api
    app.include_router(users.router, prefix="/api")
    app.include_router(publications.router, prefix="/api")
    app.include_router(authors.router, prefix="/api")
    app.include_router(scraping.router, prefix="/api")
    
    @app.get("/api")
    def read_root():
        return {"message": "Welcome to the Publications API"}
else:
    # In development, use original routes
    app.include_router(users.router)
    app.include_router(publications.router)
    app.include_router(scraping.router)
    app.include_router(authors.router)
    
    @app.get("/")
    def read_root():
        return {"message": "Welcome to the Publications API"}


# In production mode, we're using Nginx to serve static files now
# No need to mount static directories or handle SPA routing here
# as Nginx will handle all of that


# Initialize database with SQL data at startup
@app.on_event("startup")
async def startup_db_client():
    logger.info("Starting application and initializing SQLite database from SQL file...")
    try:
        initialize_database_from_sql(engine)
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")

    db = SessionLocal()
    try:
        pub_count = db.query(Publication).count()
        author_count = db.query(Author).count()
        user_count = db.query(User).count()
        logger.info("Database statistics:")
        logger.info(f"  Publications : {pub_count}")
        logger.info(f"  Authors      : {author_count}")
        logger.info(f"  Users        : {user_count}")
    finally:
        db.close()

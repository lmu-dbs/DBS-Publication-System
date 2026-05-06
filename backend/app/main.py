import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import publications, users, scraping, authors
from .models.database import engine, SessionLocal
from .models.models import Base, Publication, Author, User
from .utils.sql_importer import initialize_database_from_sql


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables in the database
Base.metadata.create_all(bind=engine)


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

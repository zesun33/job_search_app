"""
Database initialization and connection management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging
from contextlib import contextmanager
from typing import Generator

from .models import Base
from config import Config

logger = logging.getLogger(__name__)

# Database engine and session factory
engine = None
SessionLocal = None

# Initialize config instance
config = Config()


def init_database():
    """Initialize the database connection and create tables"""
    global engine, SessionLocal
    
    try:
        # Create engine with connection pooling
        try:
            engine = create_engine(
                config.DATABASE_URL,
                echo=config.DB_ECHO,
                pool_pre_ping=True,  # Validate connections before use
                pool_recycle=300,    # Recycle connections every 5 minutes
            )
            # attempt connect
            _ = engine.connect()
        except Exception as e:
            logger.warning(f"Primary DB connection failed ({e}), falling back to local SQLite.")
            fallback_url = "sqlite:///./data/jobsearch_local.db"
            engine = create_engine(fallback_url, echo=False)
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # For SQLite (used in tests), recreate schema each run to avoid stale columns and ensure latest schema
        if engine.url.drivername.startswith("sqlite"):
            Base.metadata.drop_all(bind=engine)
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions
    Ensures proper cleanup and error handling
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def get_session() -> Session:
    """Get a database session, initializing if necessary"""
    global SessionLocal
    if SessionLocal is None:
        init_database()
    return SessionLocal()


def close_database():
    """Close database connection and cleanup resources"""
    global engine
    if engine:
        engine.dispose()
        logger.info("Database connection closed")


__all__ = ["Base", "SessionLocal", "get_session", "init_database", "config"] 
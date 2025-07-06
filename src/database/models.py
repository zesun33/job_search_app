"""
Database models for the Job Search Application
Defines schemas for jobs, user preferences, rankings, and application tracking
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import json
import hashlib

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, 
    JSON, ForeignKey, UniqueConstraint, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session as _SqlSession
from sqlalchemy.dialects.postgresql import UUID
import uuid


Base = declarative_base()

Session = _SqlSession


class Job(Base):
    """Main job posting model with comprehensive fields for ranking and filtering"""
    
    __tablename__ = "jobs"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Unique identifier for deduplication
    job_hash = Column(String(64), unique=True, nullable=False, index=True)
    
    # Basic job information
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), index=True)
    description = Column(Text)
    requirements = Column(Text)
    
    # Salary information
    salary_min = Column(Integer)  # Annual salary in USD
    salary_max = Column(Integer)
    salary_currency = Column(String(3), default="USD")
    salary_type = Column(String(20))  # "annual", "hourly", "contract"
    
    # Job details
    job_type = Column(String(50), index=True)  # "full-time", "part-time", "contract", "internship"
    experience_level = Column(String(50), index=True)  # "entry", "mid", "senior", "lead"
    remote_option = Column(Boolean, default=False, index=True)
    
    # Company information
    company_size = Column(String(50))  # "startup", "mid-size", "enterprise"
    industry = Column(String(100))
    
    # Technology stack (stored as JSON array)
    technologies = Column(JSON)  # ["python", "javascript", "react"]
    
    # Source information
    source = Column(String(100), nullable=False, index=True)  # "indeed", "company_website", etc.
    source_url = Column(String(500), nullable=False)
    external_id = Column(String(255))  # ID from the source system
    
    # Timestamps
    posted_date = Column(DateTime)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Status tracking
    is_active = Column(Boolean, default=True, index=True)
    is_saved = Column(Boolean, default=False, index=True)
    application_status = Column(String(50))  # "not_applied", "applied", "interviewing", "rejected", "offered"
    
    # Relationships
    rankings = relationship("JobRanking", back_populates="job", cascade="all, delete-orphan")
    applications = relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_job_search', 'title', 'company', 'location'),
        Index('idx_job_meta', 'job_type', 'experience_level', 'remote_option'),
        Index('idx_job_time', 'posted_date', 'scraped_at'),
    )
    
    def __init__(self, **kwargs):
        # Map compatibility params
        if 'url' in kwargs and 'source_url' not in kwargs:
            kwargs['source_url'] = kwargs.pop('url')
        # Provide default source if missing
        if 'source' not in kwargs:
            kwargs['source'] = 'test'
        # Handle posting_date -> posted_date
        if 'posting_date' in kwargs and 'posted_date' not in kwargs:
            kwargs['posted_date'] = kwargs.pop('posting_date')
        super().__init__(**kwargs)
        # Auto-fill job_hash if not provided
        if not getattr(self, 'job_hash', None):
            self.job_hash = self.generate_hash()
    
    def generate_hash(self) -> str:
        """Generate a unique hash for deduplication based on key fields"""
        # Normalize fields for consistent hashing
        title_normalized = self.title.lower().strip() if self.title else ""
        company_normalized = self.company.lower().strip() if self.company else ""
        location_normalized = self.location.lower().strip() if self.location else ""
        
        # Include description snippet for better uniqueness
        description_snippet = ""
        if self.description:
            description_snippet = self.description[:200].lower().strip()
        
        hash_string = f"{title_normalized}|{company_normalized}|{location_normalized}|{description_snippet}"
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Convert job to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "requirements": self.requirements,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "salary_type": self.salary_type,
            "job_type": self.job_type,
            "experience_level": self.experience_level,
            "remote_option": self.remote_option,
            "company_size": self.company_size,
            "industry": self.industry,
            "technologies": self.technologies,
            "source": self.source,
            "source_url": self.source_url,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "is_saved": self.is_saved,
            "application_status": self.application_status
        }


class UserProfile(Base):
    """User profile and preferences storage"""
    
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), unique=True, nullable=False)  # Can be email or username
    
    # Contact information
    email = Column(String(255), nullable=False)
    phone = Column(String(20))
    phone_number = Column(String(20))
    
    # Preferences (stored as JSON for flexibility)
    name = Column(String(255))
    preferences = Column(JSON)  # legacy field
    search_preferences = Column(JSON, nullable=True)
    ranking_weights = Column(JSON, nullable=True)
    notification_preferences = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    rankings = relationship("JobRanking", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("JobApplication", back_populates="user", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        # Auto generate user_id if not provided
        if 'user_id' not in kwargs or kwargs['user_id'] is None:
            kwargs['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
        super().__init__(**kwargs)
    
    def get_preferences_dict(self) -> Dict:
        """Get all preferences as a combined dictionary"""
        return {
            "search": self.search_preferences or {},
            "ranking": self.ranking_weights or {},
            "notifications": self.notification_preferences or {}
        }


class JobRanking(Base):
    """Job ranking results for each user-job combination"""
    
    __tablename__ = "job_rankings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    user_id = Column(String(100), ForeignKey("user_profiles.user_id"), nullable=False)
    
    # Ranking scores (0.0 to 1.0)
    overall_score = Column(Float, nullable=False, index=True)
    keyword_score = Column(Float, default=0.0)
    location_score = Column(Float, default=0.0)
    salary_score = Column(Float, default=0.0)
    experience_score = Column(Float, default=0.0)
    company_score = Column(Float, default=0.0)
    freshness_score = Column(Float, default=0.0)
    
    # Metadata
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ranking_version = Column(String(20), default="1.0")  # For algorithm versioning
    
    # Relationships
    job = relationship("Job", back_populates="rankings")
    user = relationship("UserProfile", back_populates="rankings")
    
    # Ensure one ranking per user-job combination
    __table_args__ = (
        UniqueConstraint('job_id', 'user_id', name='uq_job_user_ranking'),
        Index('idx_ranking_score', 'overall_score', 'calculated_at'),
    )
    
    def to_dict(self) -> Dict:
        """Convert ranking to dictionary"""
        return {
            "job_id": self.job_id,
            "overall_score": self.overall_score,
            "keyword_score": self.keyword_score,
            "location_score": self.location_score,
            "salary_score": self.salary_score,
            "experience_score": self.experience_score,
            "company_score": self.company_score,
            "freshness_score": self.freshness_score,
            "calculated_at": self.calculated_at.isoformat()
        }


class JobApplication(Base):
    """Track job applications and their status"""
    
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    user_id = Column(String(100), ForeignKey("user_profiles.user_id"), nullable=False)
    
    # Application details
    status = Column(String(50), nullable=False, default="not_applied")  # "applied", "interviewing", "rejected", "offered"
    applied_date = Column(DateTime)
    response_date = Column(DateTime)
    interview_dates = Column(JSON)  # Array of interview dates
    
    # Notes and tracking
    cover_letter_path = Column(String(500))
    resume_path = Column(String(500))
    notes = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    job = relationship("Job", back_populates="applications")
    user = relationship("UserProfile", back_populates="applications")
    
    # Ensure one application per user-job combination
    __table_args__ = (
        UniqueConstraint('job_id', 'user_id', name='uq_job_user_application'),
    )


class ScrapingLog(Base):
    """Log scraping activities for monitoring and debugging"""
    
    __tablename__ = "scraping_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Scraping details
    source = Column(String(100), nullable=False, index=True)
    url = Column(String(500))
    status = Column(String(20), nullable=False)  # "success", "error", "blocked"
    
    # Results
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    jobs_updated = Column(Integer, default=0)
    
    # Error information
    error_message = Column(Text)
    response_code = Column(Integer)
    
    # Timing
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    
    # Metadata
    user_agent = Column(String(500))
    ip_address = Column(String(45))
    
    def __init__(self, source: str, url: str = None):
        self.source = source
        self.url = url
        self.started_at = datetime.now(timezone.utc)
    
    def complete(self, status: str, jobs_found: int = 0, jobs_new: int = 0, 
                jobs_updated: int = 0, error_message: str = None):
        """Mark the scraping session as complete"""
        self.completed_at = datetime.now(timezone.utc)
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.status = status
        self.jobs_found = jobs_found
        self.jobs_new = jobs_new
        self.jobs_updated = jobs_updated
        self.error_message = error_message


class NotificationLog(Base):
    """Track sent notifications to avoid spam and enable analytics"""
    
    __tablename__ = "notification_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User and job information
    user_id = Column(String(100), ForeignKey("user_profiles.user_id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # Nullable for summary notifications
    
    # Notification details
    notification_type = Column(String(50), nullable=False)  # "email", "sms", "push"
    notification_category = Column(String(50), nullable=False)  # "high_score", "daily_summary", "weekly_digest"
    
    # Content
    subject = Column(String(255))
    message = Column(Text)
    
    # Status
    status = Column(String(20), nullable=False)  # "sent", "failed", "queued"
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    error_message = Column(Text)
    
    # Prevent duplicate notifications
    __table_args__ = (
        Index('idx_notification_user_job', 'user_id', 'job_id', 'notification_category'),
    ) 

# Backward compatibility alias
JobData = Job 

# Helper to create tables programmatically
def create_tables(engine=None):
    """Create all tables using provided engine or default in-memory."""
    if engine is None:
        engine = create_engine('sqlite:///./data/jobsearch_test.db', echo=False)
    # Recreate tables to ensure schema up to date
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine) 

# Dataclass removed; use ORM Job for JobData compatibility 
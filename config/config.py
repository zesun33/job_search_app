"""
Configuration module for the Job Search Application
Handles environment variables, database settings, API keys, and user preferences
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
from dataclasses import dataclass


class Config(BaseSettings):
    """Main configuration class using Pydantic for validation"""
    
    # Application Settings
    APP_NAME: str = "Job Search Application"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/jobsearch"
    DB_ECHO: bool = False  # SQLAlchemy echo for debugging
    
    # Redis Configuration (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # API Keys
    INDEED_API_KEY: Optional[str] = None
    ZIPRECRUITER_API_KEY: Optional[str] = None
    MONSTER_API_KEY: Optional[str] = None
    PILOTERR_API_KEY: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None  # For GitHub API access to job repositories
    
    # Email Configuration
    EMAIL_BACKEND: str = "smtp"  # "smtp" or "sendgrid"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SENDGRID_API_KEY: Optional[str] = None
    FROM_EMAIL: str = "noreply@jobsearch.com"
    
    # SMS Configuration
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # Scraping Configuration
    SCRAPING_DELAY_MIN: float = 1.0
    SCRAPING_DELAY_MAX: float = 3.0
    MAX_CONCURRENT_REQUESTS: int = 5
    REQUEST_TIMEOUT: int = 30
    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    
    # Ranking Configuration
    DEFAULT_KEYWORD_WEIGHT: float = 0.3
    DEFAULT_LOCATION_WEIGHT: float = 0.2
    DEFAULT_SALARY_WEIGHT: float = 0.2
    DEFAULT_EXPERIENCE_WEIGHT: float = 0.15
    DEFAULT_COMPANY_WEIGHT: float = 0.1
    DEFAULT_FRESHNESS_WEIGHT: float = 0.05
    
    # Notification Thresholds
    HIGH_SCORE_THRESHOLD: float = 0.8
    MEDIUM_SCORE_THRESHOLD: float = 0.6
    
    # File Paths
    DATA_DIR: Path = Path(__file__).parent.parent / "data"
    LOGS_DIR: Path = Path(__file__).parent.parent / "logs"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @validator('DATA_DIR', 'LOGS_DIR', pre=True)
    def create_directories(cls, v):
        """Create directories if they don't exist"""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v


@dataclass
class UserPreferences:
    """User-specific preferences for job searching and ranking"""
    
    # Keywords and weights
    required_keywords: List[str]
    preferred_keywords: List[str]
    excluded_keywords: List[str]
    keyword_weights: Dict[str, float]
    
    # Location preferences
    preferred_locations: List[str]
    remote_acceptable: bool
    max_commute_distance: Optional[int]  # in miles
    
    # Salary preferences
    min_salary: Optional[int]
    max_salary: Optional[int]
    salary_importance: float  # 0-1 scale
    
    # Experience level
    experience_levels: List[str]  # ["entry", "mid", "senior", "lead"]
    
    # Company preferences
    preferred_company_types: List[str]  # ["startup", "mid-size", "enterprise", "nonprofit"]
    excluded_companies: List[str]
    
    # Technology stack
    required_technologies: List[str]
    preferred_technologies: List[str]
    
    # Job types
    job_types: List[str]  # ["full-time", "part-time", "contract", "internship"]
    
    # Notification preferences
    email_notifications: bool
    sms_notifications: bool
    notification_frequency: str  # "immediate", "daily", "weekly"
    
    # Ranking weights
    ranking_weights: Dict[str, float]


class DefaultPreferences:
    """Default user preferences for CS/IT positions"""
    
    @staticmethod
    def get_cs_internship_preferences() -> UserPreferences:
        return UserPreferences(
            required_keywords=["intern", "internship", "student"],
            preferred_keywords=["software", "developer", "engineer", "programming", "python", "java", "javascript"],
            excluded_keywords=["senior", "lead", "manager", "director"],
            keyword_weights={
                "python": 0.9,
                "java": 0.8,
                "javascript": 0.8,
                "react": 0.7,
                "sql": 0.6,
                "git": 0.5
            },
            preferred_locations=["Remote", "New York", "San Francisco", "Seattle", "Austin"],
            remote_acceptable=True,
            max_commute_distance=30,
            min_salary=15,  # per hour
            max_salary=40,  # per hour
            salary_importance=0.6,
            experience_levels=["entry"],
            preferred_company_types=["startup", "mid-size", "enterprise"],
            excluded_companies=[],
            required_technologies=["programming"],
            preferred_technologies=["python", "javascript", "sql", "git"],
            job_types=["internship", "part-time"],
            email_notifications=True,
            sms_notifications=False,
            notification_frequency="daily",
            ranking_weights={
                "keywords": 0.35,
                "location": 0.20,
                "salary": 0.15,
                "experience": 0.15,
                "company": 0.10,
                "freshness": 0.05
            }
        )
    
    @staticmethod
    def get_cs_fulltime_preferences() -> UserPreferences:
        return UserPreferences(
            required_keywords=["software", "developer", "engineer"],
            preferred_keywords=["python", "java", "javascript", "react", "sql", "aws", "docker"],
            excluded_keywords=["intern", "internship"],
            keyword_weights={
                "python": 1.0,
                "javascript": 0.9,
                "react": 0.8,
                "aws": 0.9,
                "docker": 0.7,
                "kubernetes": 0.8,
                "sql": 0.6
            },
            preferred_locations=["Remote", "San Francisco", "New York", "Seattle", "Austin", "Boston"],
            remote_acceptable=True,
            max_commute_distance=25,
            min_salary=70000,
            max_salary=180000,
            salary_importance=0.8,
            experience_levels=["entry", "mid"],
            preferred_company_types=["startup", "mid-size", "enterprise"],
            excluded_companies=[],
            required_technologies=["programming"],
            preferred_technologies=["python", "javascript", "sql", "aws", "docker", "git"],
            job_types=["full-time"],
            email_notifications=True,
            sms_notifications=True,
            notification_frequency="immediate",
            ranking_weights={
                "keywords": 0.30,
                "location": 0.20,
                "salary": 0.25,
                "experience": 0.15,
                "company": 0.05,
                "freshness": 0.05
            }
        )


# Global configuration instance
config = Config() 
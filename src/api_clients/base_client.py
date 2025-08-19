"""
Base API client with common functionality for job board integrations
Provides rate limiting, error handling, and standardized response parsing
"""

import time
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from datetime import datetime, timezone

from ..config.config import config

logger = logging.getLogger(__name__)


class JobData:
    """Standardized job data structure for all API clients"""
    
    def __init__(self, 
                 title: str,
                 company: str,
                 location: str = None,
                 description: str = None,
                 salary_min: int = None,
                 salary_max: int = None,
                 salary_currency: str = "USD",
                 salary_type: str = "annual",
                 job_type: str = None,
                 experience_level: str = None,
                 remote_option: bool = False,
                 company_size: str = None,
                 industry: str = None,
                 technologies: List[str] = None,
                 source: str = None,
                 source_url: str = None,
                 external_id: str = None,
                 posted_date: datetime = None):
        
        self.title = title
        self.company = company
        self.location = location
        self.description = description
        self.salary_min = salary_min
        self.salary_max = salary_max
        self.salary_currency = salary_currency
        self.salary_type = salary_type
        self.job_type = job_type
        self.experience_level = experience_level
        self.remote_option = remote_option
        self.company_size = company_size
        self.industry = industry
        self.technologies = technologies or []
        self.source = source
        self.source_url = source_url
        self.external_id = external_id
        self.posted_date = posted_date
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
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
            "external_id": self.external_id,
            "posted_date": self.posted_date
        }


class RateLimiter:
    """Simple rate limiter for API requests"""
    
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove old requests outside the time window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        # Check if we need to wait
        if len(self.requests) >= self.max_requests:
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
        
        # Add current request
        self.requests.append(now)


class BaseJobAPI(ABC):
    """
    Abstract base class for all job board API clients
    Provides common functionality like rate limiting, retries, and error handling
    """
    
    def __init__(self, api_key: str = None, rate_limit: int = 60):
        self.api_key = api_key
        self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=60)
        self.session = self._create_session()
        self.source_name = self.__class__.__name__.replace("API", "").lower()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Default headers
        session.headers.update({
            'User-Agent': random.choice(config.USER_AGENTS),
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        return session
    
    def _make_request(self, url: str, params: Dict = None, headers: Dict = None) -> requests.Response:
        """
        Make a rate-limited API request with error handling
        
        Args:
            url: API endpoint URL
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: For API errors
        """
        self.rate_limiter.wait_if_needed()
        
        try:
            # Add API key to headers if available
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            if self.api_key:
                request_headers.update(self._get_auth_headers())
            
            # Add random delay for politeness
            delay = random.uniform(config.SCRAPING_DELAY_MIN, config.SCRAPING_DELAY_MAX)
            time.sleep(delay)
            
            response = self.session.get(
                url,
                params=params,
                headers=request_headers,
                timeout=config.REQUEST_TIMEOUT
            )
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {e}")
            raise
    
    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers specific to each API"""
        pass
    
    @abstractmethod
    def search_jobs(self, 
                   keywords: str,
                   location: str = None,
                   job_type: str = None,
                   experience_level: str = None,
                   limit: int = 50) -> List[JobData]:
        """
        Search for jobs with given criteria
        
        Args:
            keywords: Search keywords
            location: Location filter
            job_type: Job type filter (full-time, part-time, etc.)
            experience_level: Experience level filter
            limit: Maximum number of results
            
        Returns:
            List of JobData objects
        """
        pass
    
    @abstractmethod
    def _parse_job(self, job_data: Dict) -> JobData:
        """Parse job data from API response to standardized JobData format"""
        pass
    
    def _parse_salary(self, salary_str: str) -> tuple:
        """
        Parse salary string to extract min/max values
        
        Returns:
            Tuple of (min_salary, max_salary, salary_type)
        """
        if not salary_str:
            return None, None, "annual"
        
        # Common salary patterns
        import re
        
        # Remove currency symbols and normalize
        salary_clean = re.sub(r'[$,]', '', salary_str.lower())
        
        # Look for ranges like "50000-70000" or "50k-70k"
        range_match = re.search(r'(\d+(?:\.\d+)?)\s*k?\s*[-–—]\s*(\d+(?:\.\d+)?)\s*k?', salary_clean)
        if range_match:
            min_sal = float(range_match.group(1))
            max_sal = float(range_match.group(2))
            
            # Convert 'k' notation
            if 'k' in salary_clean:
                min_sal *= 1000
                max_sal *= 1000
            
            # Determine if hourly or annual
            if any(word in salary_clean for word in ['hour', 'hourly', '/hr']):
                return int(min_sal), int(max_sal), "hourly"
            else:
                return int(min_sal), int(max_sal), "annual"
        
        # Single value like "50000" or "50k"
        single_match = re.search(r'(\d+(?:\.\d+)?)\s*k?', salary_clean)
        if single_match:
            salary = float(single_match.group(1))
            
            if 'k' in salary_clean:
                salary *= 1000
            
            salary_type = "hourly" if any(word in salary_clean for word in ['hour', 'hourly', '/hr']) else "annual"
            return int(salary), int(salary), salary_type
        
        return None, None, "annual"
    
    def _extract_technologies(self, text: str) -> List[str]:
        """Extract technology keywords from job description"""
        if not text:
            return []
        
        text_lower = text.lower()
        technologies = []
        
        # Common technology keywords
        tech_keywords = [
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'swift',
            'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring',
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'cassandra',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git', 'linux',
            'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'pandas', 'numpy'
        ]
        
        for tech in tech_keywords:
            if tech in text_lower:
                technologies.append(tech)
        
        return list(set(technologies))  # Remove duplicates
    
    def _classify_experience_level(self, text: str) -> str:
        """Classify experience level from job description"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Entry level indicators
        if any(term in text_lower for term in ['entry', 'junior', 'entry-level', 'new grad', 'recent graduate', '0-2 years']):
            return "entry"
        
        # Senior level indicators
        if any(term in text_lower for term in ['senior', 'sr.', 'lead', 'principal', '5+ years', '7+ years']):
            return "senior"
        
        # Mid level indicators
        if any(term in text_lower for term in ['mid', 'intermediate', '2-5 years', '3-7 years']):
            return "mid"
        
        # Lead level indicators
        if any(term in text_lower for term in ['lead', 'principal', 'architect', 'manager', 'director']):
            return "lead"
        
        return "mid"  # Default to mid level
    
    def _is_remote(self, location: str, description: str = "") -> bool:
        """Check if job offers remote work"""
        text = f"{location or ''} {description or ''}".lower()
        
        remote_keywords = [
            'remote', 'work from home', 'wfh', 'telecommute', 'distributed',
            'anywhere', 'location independent'
        ]
        
        return any(keyword in text for keyword in remote_keywords)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get API client statistics"""
        return {
            "source": self.source_name,
            "has_api_key": bool(self.api_key),
            "requests_made": len(self.rate_limiter.requests)
        } 
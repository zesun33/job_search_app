"""
Base web scraper with ethical scraping practices and robust error handling
Supports multiple scraping backends: requests/BeautifulSoup, Selenium, and Playwright
"""

import time
import random
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse, robots
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc
from playwright.sync_api import sync_playwright, Browser, Page
from urllib.robotparser import RobotFileParser

from ..api_clients.base_client import JobData
from ..config.config import config
from ..database.models import ScrapingLog

logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Custom exception for scraping errors"""
    pass


class RobotsChecker:
    """Check robots.txt compliance for ethical scraping"""
    
    def __init__(self):
        self.robots_cache = {}
    
    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """Check if we can fetch the given URL according to robots.txt"""
        try:
            domain = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            
            if domain not in self.robots_cache:
                robots_url = urljoin(domain, '/robots.txt')
                rp = RobotFileParser()
                rp.set_url(robots_url)
                try:
                    rp.read()
                    self.robots_cache[domain] = rp
                except Exception:
                    # If robots.txt can't be read, assume we can scrape
                    self.robots_cache[domain] = None
            
            robots_parser = self.robots_cache[domain]
            if robots_parser:
                return robots_parser.can_fetch(user_agent, url)
            return True
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {e}")
            return True  # Assume allowed if check fails


class BaseScraper(ABC):
    """
    Abstract base class for all web scrapers
    Provides ethical scraping practices and common functionality
    """
    
    def __init__(self, 
                 backend: str = "requests",  # "requests", "selenium", "playwright"
                 respect_robots: bool = True,
                 delay_range: tuple = None):
        
        self.backend = backend
        self.respect_robots = respect_robots
        self.delay_range = delay_range or (config.SCRAPING_DELAY_MIN, config.SCRAPING_DELAY_MAX)
        self.robots_checker = RobotsChecker() if respect_robots else None
        
        # Initialize the scraping backend
        self.session = None
        self.driver = None
        self.browser = None
        self.page = None
        
        self._init_backend()
    
    def _init_backend(self):
        """Initialize the chosen scraping backend"""
        if self.backend == "requests":
            self._init_requests()
        elif self.backend == "selenium":
            self._init_selenium()
        elif self.backend == "playwright":
            self._init_playwright()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")
    
    def _init_requests(self):
        """Initialize requests session with retry strategy"""
        self.session = requests.Session()
        
        # Set up retry strategy
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _init_selenium(self):
        """Initialize Selenium WebDriver with undetected Chrome"""
        try:
            # Use undetected-chromedriver for better bot detection evasion
            options = ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Headless mode for production
            if not config.DEBUG:
                options.add_argument('--headless')
            
            self.driver = uc.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
        except Exception as e:
            logger.error(f"Failed to initialize Selenium driver: {e}")
            raise ScrapingError(f"Selenium initialization failed: {e}")
    
    def _init_playwright(self):
        """Initialize Playwright browser"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=not config.DEBUG,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            # Create a new context with random user agent
            context = self.browser.new_context(
                user_agent=random.choice(config.USER_AGENTS)
            )
            self.page = context.new_page()
            
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise ScrapingError(f"Playwright initialization failed: {e}")
    
    def _get_random_headers(self) -> Dict[str, str]:
        """Get randomized headers for requests"""
        return {
            'User-Agent': random.choice(config.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def _wait_between_requests(self):
        """Wait between requests to be polite"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
    
    def _check_robots_txt(self, url: str) -> bool:
        """Check if URL can be scraped according to robots.txt"""
        if not self.respect_robots:
            return True
        
        return self.robots_checker.can_fetch(url)
    
    def fetch_page(self, url: str, **kwargs) -> Union[BeautifulSoup, str]:
        """
        Fetch a web page using the configured backend
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments for the backend
            
        Returns:
            BeautifulSoup object for requests backend, page source for others
        """
        # Check robots.txt
        if not self._check_robots_txt(url):
            raise ScrapingError(f"Scraping not allowed by robots.txt: {url}")
        
        # Wait between requests
        self._wait_between_requests()
        
        try:
            if self.backend == "requests":
                return self._fetch_with_requests(url, **kwargs)
            elif self.backend == "selenium":
                return self._fetch_with_selenium(url, **kwargs)
            elif self.backend == "playwright":
                return self._fetch_with_playwright(url, **kwargs)
        except Exception as e:
            logger.error(f"Error fetching {url} with {self.backend}: {e}")
            raise ScrapingError(f"Failed to fetch {url}: {e}")
    
    def _fetch_with_requests(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch page using requests and return BeautifulSoup object"""
        headers = self._get_random_headers()
        headers.update(kwargs.get('headers', {}))
        
        response = self.session.get(
            url,
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
            **kwargs
        )
        response.raise_for_status()
        
        return BeautifulSoup(response.content, 'html.parser')
    
    def _fetch_with_selenium(self, url: str, wait_for: str = None, timeout: int = 10) -> str:
        """Fetch page using Selenium and return page source"""
        self.driver.get(url)
        
        # Wait for specific element if specified
        if wait_for:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for element {wait_for} on {url}")
        
        return self.driver.page_source
    
    def _fetch_with_playwright(self, url: str, wait_for: str = None, timeout: int = 10000) -> str:
        """Fetch page using Playwright and return page source"""
        self.page.goto(url, wait_until='networkidle', timeout=timeout)
        
        # Wait for specific element if specified
        if wait_for:
            try:
                self.page.wait_for_selector(wait_for, timeout=timeout)
            except Exception:
                logger.warning(f"Timeout waiting for element {wait_for} on {url}")
        
        return self.page.content()
    
    @abstractmethod
    def scrape_jobs(self, search_params: Dict) -> List[JobData]:
        """
        Abstract method to scrape jobs from a specific source
        
        Args:
            search_params: Dictionary containing search parameters
            
        Returns:
            List of JobData objects
        """
        pass
    
    def close(self):
        """Clean up resources"""
        if self.session:
            self.session.close()
        
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
        
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
        
        if hasattr(self, 'playwright'):
            try:
                self.playwright.stop()
            except Exception:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ATSDetector:
    """
    Detect common Applicant Tracking Systems (ATS) to optimize scraping
    """
    
    ATS_SIGNATURES = {
        'workday': {
            'selectors': ['.wd-popup', '[data-automation-id]', '.workday'],
            'urls': ['myworkdayjobs.com', 'workday.com']
        },
        'greenhouse': {
            'selectors': ['.greenhouse-job', '.jobs-board'],
            'urls': ['greenhouse.io', 'boards.greenhouse.io']
        },
        'lever': {
            'selectors': ['.lever-job', '.posting'],
            'urls': ['lever.co', 'jobs.lever.co']
        },
        'jobvite': {
            'selectors': ['.jv-job', '.jobvite'],
            'urls': ['jobvite.com']
        },
        'bamboohr': {
            'selectors': ['.bamboo-job'],
            'urls': ['bamboohr.com']
        },
        'smartrecruiters': {
            'selectors': ['.smartrecruiters'],
            'urls': ['smartrecruiters.com']
        }
    }
    
    @classmethod
    def detect_ats(cls, url: str, page_content: str = None) -> Optional[str]:
        """
        Detect ATS system from URL or page content
        
        Args:
            url: Job board URL
            page_content: Optional page HTML content
            
        Returns:
            ATS name if detected, None otherwise
        """
        # Check URL patterns
        for ats_name, signatures in cls.ATS_SIGNATURES.items():
            for url_pattern in signatures['urls']:
                if url_pattern in url:
                    return ats_name
        
        # Check page content if provided
        if page_content:
            soup = BeautifulSoup(page_content, 'html.parser')
            for ats_name, signatures in cls.ATS_SIGNATURES.items():
                for selector in signatures['selectors']:
                    if soup.select(selector):
                        return ats_name
        
        return None


class CompanyWebsiteScraper(BaseScraper):
    """
    Generic scraper for company career pages
    Attempts to detect ATS and adapt scraping strategy accordingly
    """
    
    def __init__(self, company_name: str, career_url: str, **kwargs):
        super().__init__(**kwargs)
        self.company_name = company_name
        self.career_url = career_url
        self.ats_type = None
    
    def scrape_jobs(self, search_params: Dict = None) -> List[JobData]:
        """
        Scrape jobs from company career page
        
        Args:
            search_params: Optional search parameters (keywords, location, etc.)
            
        Returns:
            List of JobData objects
        """
        try:
            # Start scraping log
            scraping_log = ScrapingLog(source=f"{self.company_name}_website", url=self.career_url)
            
            logger.info(f"Scraping jobs from {self.company_name} at {self.career_url}")
            
            # Fetch the career page
            page_content = self.fetch_page(self.career_url)
            
            # Detect ATS if using requests backend
            if self.backend == "requests":
                self.ats_type = ATSDetector.detect_ats(self.career_url, str(page_content))
            else:
                self.ats_type = ATSDetector.detect_ats(self.career_url, page_content)
            
            if self.ats_type:
                logger.info(f"Detected ATS: {self.ats_type}")
                jobs = self._scrape_ats_jobs(page_content, search_params)
            else:
                logger.info("No specific ATS detected, using generic scraping")
                jobs = self._scrape_generic_jobs(page_content, search_params)
            
            # Complete scraping log
            scraping_log.complete("success", len(jobs), len(jobs), 0)
            
            logger.info(f"Successfully scraped {len(jobs)} jobs from {self.company_name}")
            return jobs
            
        except Exception as e:
            logger.error(f"Error scraping {self.company_name}: {e}")
            if 'scraping_log' in locals():
                scraping_log.complete("error", 0, 0, 0, str(e))
            return []
    
    def _scrape_ats_jobs(self, page_content: Union[str, BeautifulSoup], search_params: Dict = None) -> List[JobData]:
        """Scrape jobs using ATS-specific selectors"""
        if self.backend == "requests":
            soup = page_content if isinstance(page_content, BeautifulSoup) else BeautifulSoup(page_content, 'html.parser')
        else:
            soup = BeautifulSoup(page_content, 'html.parser')
        
        jobs = []
        
        if self.ats_type == 'workday':
            jobs = self._scrape_workday_jobs(soup)
        elif self.ats_type == 'greenhouse':
            jobs = self._scrape_greenhouse_jobs(soup)
        elif self.ats_type == 'lever':
            jobs = self._scrape_lever_jobs(soup)
        else:
            jobs = self._scrape_generic_jobs(soup, search_params)
        
        return jobs
    
    def _scrape_workday_jobs(self, soup: BeautifulSoup) -> List[JobData]:
        """Scrape Workday ATS jobs"""
        jobs = []
        
        # Common Workday selectors
        job_elements = soup.select('[data-automation-id="jobPostingItem"]') or soup.select('.css-1f4z7pj')
        
        for job_elem in job_elements:
            try:
                title_elem = job_elem.select_one('[data-automation-id="jobPostingTitle"]') or job_elem.select_one('h3')
                location_elem = job_elem.select_one('[data-automation-id="jobPostingLocation"]')
                
                if title_elem:
                    job = JobData(
                        title=title_elem.get_text(strip=True),
                        company=self.company_name,
                        location=location_elem.get_text(strip=True) if location_elem else None,
                        source=f"{self.company_name}_workday",
                        source_url=self.career_url
                    )
                    jobs.append(job)
                    
            except Exception as e:
                logger.warning(f"Error parsing Workday job element: {e}")
                continue
        
        return jobs
    
    def _scrape_greenhouse_jobs(self, soup: BeautifulSoup) -> List[JobData]:
        """Scrape Greenhouse ATS jobs"""
        jobs = []
        
        # Common Greenhouse selectors
        job_elements = soup.select('.opening') or soup.select('[data-mapped="true"]')
        
        for job_elem in job_elements:
            try:
                title_elem = job_elem.select_one('a') or job_elem.select_one('h3')
                location_elem = job_elem.select_one('.location')
                
                if title_elem:
                    job_url = title_elem.get('href', '')
                    if job_url and not job_url.startswith('http'):
                        job_url = urljoin(self.career_url, job_url)
                    
                    job = JobData(
                        title=title_elem.get_text(strip=True),
                        company=self.company_name,
                        location=location_elem.get_text(strip=True) if location_elem else None,
                        source=f"{self.company_name}_greenhouse",
                        source_url=job_url or self.career_url
                    )
                    jobs.append(job)
                    
            except Exception as e:
                logger.warning(f"Error parsing Greenhouse job element: {e}")
                continue
        
        return jobs
    
    def _scrape_lever_jobs(self, soup: BeautifulSoup) -> List[JobData]:
        """Scrape Lever ATS jobs"""
        jobs = []
        
        # Common Lever selectors
        job_elements = soup.select('.posting') or soup.select('[data-qa="posting"]')
        
        for job_elem in job_elements:
            try:
                title_elem = job_elem.select_one('.posting-title h5') or job_elem.select_one('h5')
                location_elem = job_elem.select_one('.posting-categories .sort-by-location')
                
                if title_elem:
                    job = JobData(
                        title=title_elem.get_text(strip=True),
                        company=self.company_name,
                        location=location_elem.get_text(strip=True) if location_elem else None,
                        source=f"{self.company_name}_lever",
                        source_url=self.career_url
                    )
                    jobs.append(job)
                    
            except Exception as e:
                logger.warning(f"Error parsing Lever job element: {e}")
                continue
        
        return jobs
    
    def _scrape_generic_jobs(self, page_content: Union[str, BeautifulSoup], search_params: Dict = None) -> List[JobData]:
        """Generic job scraping when no specific ATS is detected"""
        if self.backend == "requests":
            soup = page_content if isinstance(page_content, BeautifulSoup) else BeautifulSoup(page_content, 'html.parser')
        else:
            soup = BeautifulSoup(page_content, 'html.parser')
        
        jobs = []
        
        # Try common job listing patterns
        job_selectors = [
            '.job', '.job-listing', '.job-item', '.position', '.opening',
            '[class*="job"]', '[class*="position"]', '[class*="career"]',
            'li:has(a[href*="job"])', 'div:has(a[href*="career"])'
        ]
        
        for selector in job_selectors:
            job_elements = soup.select(selector)
            if job_elements and len(job_elements) > 2:  # Found a promising pattern
                for job_elem in job_elements[:20]:  # Limit to prevent false positives
                    try:
                        # Try to extract title
                        title_elem = (job_elem.select_one('h1, h2, h3, h4, h5, h6') or 
                                    job_elem.select_one('a') or 
                                    job_elem.select_one('[class*="title"]'))
                        
                        if title_elem and title_elem.get_text(strip=True):
                            title = title_elem.get_text(strip=True)
                            
                            # Skip if title looks like navigation or not a job
                            skip_keywords = ['home', 'about', 'contact', 'login', 'search', 'filter']
                            if any(keyword in title.lower() for keyword in skip_keywords):
                                continue
                            
                            # Try to extract location
                            location_elem = job_elem.select_one('[class*="location"]')
                            location = location_elem.get_text(strip=True) if location_elem else None
                            
                            job = JobData(
                                title=title,
                                company=self.company_name,
                                location=location,
                                source=f"{self.company_name}_website",
                                source_url=self.career_url
                            )
                            jobs.append(job)
                            
                    except Exception as e:
                        logger.debug(f"Error parsing generic job element: {e}")
                        continue
                
                if jobs:  # Found jobs with this selector, stop trying others
                    break
        
        return jobs 
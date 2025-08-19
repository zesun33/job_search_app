"""
ATS-specific scrapers for major Applicant Tracking Systems.
Handles Workday, Greenhouse, Lever, iCIMS, SmartRecruiters, and other common ATS platforms.
"""

import asyncio
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, urlparse, quote
import time

from ..database.models import JobData
from ..config.company_sources import ATSType, ATS_PATTERNS, CompanyJobSource
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class WorkdayATSScraper(BaseScraper):
    """Specialized scraper for Workday ATS systems."""
    
    def __init__(self, config):
        super().__init__(config)
        self.ats_type = ATSType.WORKDAY
        
    async def scrape_company_jobs(self, company_config: CompanyJobSource, focus_areas: List[str] = None) -> List[JobData]:
        """Scrape jobs from a Workday-powered company portal."""
        jobs = []
        
        try:
            for url in company_config.ats_specific_urls:
                logger.info(f"Scraping Workday jobs from {company_config.name}: {url}")
                
                # Workday often requires POST requests or has complex pagination
                jobs_batch = await self._scrape_workday_url(url, company_config, focus_areas)
                jobs.extend(jobs_batch)
                
                await asyncio.sleep(self.request_delay)
                
        except Exception as e:
            logger.error(f"Error scraping Workday jobs for {company_config.name}: {str(e)}")
        
        return jobs
    
    async def _scrape_workday_url(self, url: str, company_config: CompanyJobSource, focus_areas: List[str]) -> List[JobData]:
        """Scrape a specific Workday URL."""
        jobs = []
        
        try:
            # First, try to get the main page
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for Workday-specific job listings
            job_elements = soup.find_all(['div', 'tr'], class_=re.compile(r'job|position', re.I))
            
            for element in job_elements:
                try:
                    job = self._parse_workday_job_element(element, company_config)
                    if job and self._matches_focus_areas(job, focus_areas):
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Error parsing Workday job element: {str(e)}")
            
            # Try to handle pagination
            next_page = self._find_workday_next_page(soup, url)
            if next_page and len(jobs) < 50:  # Limit total pages
                await asyncio.sleep(self.request_delay)
                next_jobs = await self._scrape_workday_url(next_page, company_config, focus_areas)
                jobs.extend(next_jobs)
                
        except Exception as e:
            logger.warning(f"Error scraping Workday URL {url}: {str(e)}")
        
        return jobs
    
    def _parse_workday_job_element(self, element: BeautifulSoup, company_config: CompanyJobSource) -> Optional[JobData]:
        """Parse a Workday job element."""
        try:
            # Extract job title
            title_selectors = [
                'a[data-automation-id="jobTitle"]',
                '.jobTitle',
                'h3 a',
                '[data-automation-id*="title"]'
            ]
            
            title = ""
            job_url = ""
            for selector in title_selectors:
                title_elem = element.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title_elem.get('href'):
                        job_url = title_elem['href']
                    break
            
            if not title:
                return None
            
            # Extract location
            location_selectors = [
                '[data-automation-id*="location"]',
                '.jobLocation',
                '[class*="location"]'
            ]
            
            location = ""
            for selector in location_selectors:
                loc_elem = element.select_one(selector)
                if loc_elem:
                    location = loc_elem.get_text().strip()
                    break
            
            # Extract posting date
            date_selectors = [
                '[data-automation-id*="date"]',
                '.jobDate',
                '[class*="date"]'
            ]
            
            posting_date = datetime.now()
            for selector in date_selectors:
                date_elem = element.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text().strip()
                    posting_date = self._parse_date(date_text)
                    break
            
            # Extract job type/experience level
            level_selectors = [
                '[data-automation-id*="level"]',
                '[data-automation-id*="type"]',
                '.jobType'
            ]
            
            experience_level = "Entry-level"
            job_type = "Full-time"
            for selector in level_selectors:
                level_elem = element.select_one(selector)
                if level_elem:
                    level_text = level_elem.get_text().strip().lower()
                    if "intern" in level_text:
                        job_type = "Internship"
                        experience_level = "Entry-level"
                    elif "senior" in level_text:
                        experience_level = "Senior"
                    elif "principal" in level_text or "staff" in level_text:
                        experience_level = "Principal"
                    break
            
            return JobData(
                title=title,
                company=company_config.name,
                location=location or "Not specified",
                job_type=job_type,
                experience_level=experience_level,
                salary_min=None,
                salary_max=None,
                description="",
                requirements="",
                benefits="",
                url=urljoin(company_config.careers_url, job_url) if job_url else company_config.careers_url,
                posting_date=posting_date,
                technologies=self._extract_technologies_from_title(title),
                source=f"Workday:{company_config.name}",
                remote_eligible="remote" in (title + location).lower(),
                visa_sponsorship=False  # Would need job description to determine
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Workday job element: {str(e)}")
            return None
    
    def _find_workday_next_page(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Find next page URL in Workday pagination."""
        next_selectors = [
            'a[data-automation-id="nextBtn"]',
            'a[aria-label="next"]',
            '.paginationNext a',
            'a:contains("Next")'
        ]
        
        for selector in next_selectors:
            next_elem = soup.select_one(selector)
            if next_elem and next_elem.get('href'):
                return urljoin(current_url, next_elem['href'])
        
        return None

class GreenhouseATSScraper(BaseScraper):
    """Specialized scraper for Greenhouse ATS systems."""
    
    def __init__(self, config):
        super().__init__(config)
        self.ats_type = ATSType.GREENHOUSE
        
    async def scrape_company_jobs(self, company_config: CompanyJobSource, focus_areas: List[str] = None) -> List[JobData]:
        """Scrape jobs from a Greenhouse-powered company portal."""
        jobs = []
        
        try:
            for url in company_config.ats_specific_urls:
                logger.info(f"Scraping Greenhouse jobs from {company_config.name}: {url}")
                
                jobs_batch = await self._scrape_greenhouse_url(url, company_config, focus_areas)
                jobs.extend(jobs_batch)
                
                await asyncio.sleep(self.request_delay)
                
        except Exception as e:
            logger.error(f"Error scraping Greenhouse jobs for {company_config.name}: {str(e)}")
        
        return jobs
    
    async def _scrape_greenhouse_url(self, url: str, company_config: CompanyJobSource, focus_areas: List[str]) -> List[JobData]:
        """Scrape a specific Greenhouse URL."""
        jobs = []
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Greenhouse typically uses specific class names
            job_selectors = [
                '.job',
                '.opening',
                '[data-mapped-job]',
                '.job-post'
            ]
            
            job_elements = []
            for selector in job_selectors:
                elements = soup.select(selector)
                if elements:
                    job_elements = elements
                    break
            
            for element in job_elements:
                try:
                    job = self._parse_greenhouse_job_element(element, company_config)
                    if job and self._matches_focus_areas(job, focus_areas):
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Error parsing Greenhouse job element: {str(e)}")
                    
        except Exception as e:
            logger.warning(f"Error scraping Greenhouse URL {url}: {str(e)}")
        
        return jobs
    
    def _parse_greenhouse_job_element(self, element: BeautifulSoup, company_config: CompanyJobSource) -> Optional[JobData]:
        """Parse a Greenhouse job element."""
        try:
            # Extract title and URL
            title_elem = element.select_one('a') or element.select_one('h3') or element.select_one('h4')
            if not title_elem:
                return None
                
            title = title_elem.get_text().strip()
            job_url = title_elem.get('href', '') if title_elem.name == 'a' else ''
            
            # Extract location
            location_elem = element.select_one('.location') or element.select_one('[class*="location"]')
            location = location_elem.get_text().strip() if location_elem else "Not specified"
            
            # Extract department/team
            dept_elem = element.select_one('.department') or element.select_one('[class*="department"]')
            department = dept_elem.get_text().strip() if dept_elem else ""
            
            # Determine job type and experience level
            title_lower = title.lower()
            experience_level = "Entry-level"
            job_type = "Full-time"
            
            if "intern" in title_lower:
                job_type = "Internship"
            elif "senior" in title_lower:
                experience_level = "Senior"
            elif "principal" in title_lower or "staff" in title_lower:
                experience_level = "Principal"
            elif "lead" in title_lower:
                experience_level = "Senior"
            
            return JobData(
                title=title,
                company=company_config.name,
                location=location,
                job_type=job_type,
                experience_level=experience_level,
                salary_min=None,
                salary_max=None,
                description=department,
                requirements="",
                benefits="",
                url=urljoin(company_config.careers_url, job_url) if job_url else company_config.careers_url,
                posting_date=datetime.now(),
                technologies=self._extract_technologies_from_title(title),
                source=f"Greenhouse:{company_config.name}",
                remote_eligible="remote" in (title + location).lower(),
                visa_sponsorship=False
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Greenhouse job element: {str(e)}")
            return None

class LeverATSScraper(BaseScraper):
    """Specialized scraper for Lever ATS systems."""
    
    def __init__(self, config):
        super().__init__(config)
        self.ats_type = ATSType.LEVER
        
    async def scrape_company_jobs(self, company_config: CompanyJobSource, focus_areas: List[str] = None) -> List[JobData]:
        """Scrape jobs from a Lever-powered company portal."""
        jobs = []
        
        try:
            # Lever often has API endpoints we can use
            api_jobs = await self._try_lever_api(company_config)
            if api_jobs:
                jobs.extend(api_jobs)
            else:
                # Fallback to web scraping
                for url in company_config.ats_specific_urls:
                    logger.info(f"Scraping Lever jobs from {company_config.name}: {url}")
                    
                    jobs_batch = await self._scrape_lever_url(url, company_config, focus_areas)
                    jobs.extend(jobs_batch)
                    
                    await asyncio.sleep(self.request_delay)
                    
        except Exception as e:
            logger.error(f"Error scraping Lever jobs for {company_config.name}: {str(e)}")
        
        return jobs
    
    async def _try_lever_api(self, company_config: CompanyJobSource) -> List[JobData]:
        """Try to use Lever's API if available."""
        jobs = []
        
        try:
            # Extract company identifier from URL
            parsed_url = urlparse(company_config.careers_url)
            if 'lever.co' in parsed_url.netloc:
                # Lever API format: https://api.lever.co/v0/postings/{company}
                company_id = parsed_url.path.split('/')[1] if '/' in parsed_url.path else None
                
                if company_id:
                    api_url = f"https://api.lever.co/v0/postings/{company_id}"
                    response = requests.get(api_url, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        for job_data in data:
                            job = self._parse_lever_api_job(job_data, company_config)
                            if job:
                                jobs.append(job)
                                
        except Exception as e:
            logger.warning(f"Lever API scraping failed: {str(e)}")
        
        return jobs
    
    def _parse_lever_api_job(self, job_data: Dict, company_config: CompanyJobSource) -> Optional[JobData]:
        """Parse job data from Lever API response."""
        try:
            title = job_data.get('text', '')
            location = ', '.join([loc.get('name', '') for loc in job_data.get('categories', {}).get('location', [])])
            team = ', '.join([team.get('text', '') for team in job_data.get('categories', {}).get('team', [])])
            commitment = ', '.join([comm.get('text', '') for comm in job_data.get('categories', {}).get('commitment', [])])
            
            # Determine job type and experience level
            title_lower = title.lower()
            commitment_lower = commitment.lower()
            
            job_type = "Full-time"
            if "intern" in title_lower or "intern" in commitment_lower:
                job_type = "Internship"
            elif "part" in commitment_lower:
                job_type = "Part-time"
            elif "contract" in commitment_lower:
                job_type = "Contract"
            
            experience_level = "Entry-level"
            if "senior" in title_lower:
                experience_level = "Senior"
            elif "principal" in title_lower or "staff" in title_lower:
                experience_level = "Principal"
            
            posting_date = datetime.now()
            if job_data.get('createdAt'):
                try:
                    posting_date = datetime.fromtimestamp(job_data['createdAt'] / 1000)
                except:
                    pass
            
            return JobData(
                title=title,
                company=company_config.name,
                location=location or "Not specified",
                job_type=job_type,
                experience_level=experience_level,
                salary_min=None,
                salary_max=None,
                description=team,
                requirements="",
                benefits="",
                url=job_data.get('hostedUrl', company_config.careers_url),
                posting_date=posting_date,
                technologies=self._extract_technologies_from_title(title),
                source=f"Lever:{company_config.name}",
                remote_eligible="remote" in (title + location).lower(),
                visa_sponsorship=False
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Lever API job: {str(e)}")
            return None
    
    async def _scrape_lever_url(self, url: str, company_config: CompanyJobSource, focus_areas: List[str]) -> List[JobData]:
        """Scrape Lever jobs from web interface."""
        jobs = []
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Lever typically uses these selectors
            job_elements = soup.select('.posting') or soup.select('.job-posting') or soup.select('[data-qa="posting"]')
            
            for element in job_elements:
                try:
                    job = self._parse_lever_web_job_element(element, company_config)
                    if job and self._matches_focus_areas(job, focus_areas):
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Error parsing Lever web job element: {str(e)}")
                    
        except Exception as e:
            logger.warning(f"Error scraping Lever URL {url}: {str(e)}")
        
        return jobs
    
    def _parse_lever_web_job_element(self, element: BeautifulSoup, company_config: CompanyJobSource) -> Optional[JobData]:
        """Parse a Lever job element from web interface."""
        try:
            # Extract title
            title_elem = element.select_one('h5 a') or element.select_one('.posting-title a') or element.select_one('a')
            if not title_elem:
                return None
                
            title = title_elem.get_text().strip()
            job_url = title_elem.get('href', '')
            
            # Extract categories (location, team, etc.)
            categories = element.select('.posting-categories .sort-by-time') or element.select('.posting-categories span')
            
            location = ""
            team = ""
            for cat in categories:
                cat_text = cat.get_text().strip()
                if any(word in cat_text.lower() for word in ['office', 'remote', 'san francisco', 'new york', 'austin']):
                    location = cat_text
                else:
                    team = cat_text
            
            # Determine job characteristics
            title_lower = title.lower()
            job_type = "Internship" if "intern" in title_lower else "Full-time"
            
            experience_level = "Entry-level"
            if "senior" in title_lower:
                experience_level = "Senior"
            elif "principal" in title_lower or "staff" in title_lower:
                experience_level = "Principal"
            
            return JobData(
                title=title,
                company=company_config.name,
                location=location or "Not specified",
                job_type=job_type,
                experience_level=experience_level,
                salary_min=None,
                salary_max=None,
                description=team,
                requirements="",
                benefits="",
                url=urljoin(company_config.careers_url, job_url) if job_url else company_config.careers_url,
                posting_date=datetime.now(),
                technologies=self._extract_technologies_from_title(title),
                source=f"Lever:{company_config.name}",
                remote_eligible="remote" in (title + location).lower(),
                visa_sponsorship=False
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Lever web job element: {str(e)}")
            return None

class ATSScraperFactory:
    """Factory class to create appropriate ATS scrapers."""
    
    @staticmethod
    def create_scraper(ats_type: ATSType, config) -> BaseScraper:
        """Create appropriate scraper based on ATS type."""
        scraper_map = {
            ATSType.WORKDAY: WorkdayATSScraper,
            ATSType.GREENHOUSE: GreenhouseATSScraper,
            ATSType.LEVER: LeverATSScraper,
            # Add more ATS scrapers as needed
        }
        
        scraper_class = scraper_map.get(ats_type, BaseScraper)
        return scraper_class(config)
    
    @staticmethod
    def get_supported_ats_types() -> List[ATSType]:
        """Get list of supported ATS types."""
        return [ATSType.WORKDAY, ATSType.GREENHOUSE, ATSType.LEVER]

# Utility functions for all ATS scrapers
class ATSUtils:
    """Utility functions shared across ATS scrapers."""
    
    @staticmethod
    def extract_technologies_from_title(title: str) -> List[str]:
        """Extract technology keywords from job title."""
        if not title:
            return []
        
        title_lower = title.lower()
        technologies = []
        
        tech_keywords = [
            'python', 'java', 'javascript', 'react', 'node.js', 'angular', 'vue',
            'c++', 'c#', 'go', 'rust', 'swift', 'kotlin', 'scala',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes',
            'tensorflow', 'pytorch', 'machine learning', 'ai',
            'sql', 'mongodb', 'postgresql', 'redis',
            'git', 'jenkins', 'ci/cd'
        ]
        
        for tech in tech_keywords:
            if tech in title_lower:
                technologies.append(tech.title())
        
        return technologies
    
    @staticmethod
    def parse_date(date_string: str) -> datetime:
        """Parse various date formats commonly used by ATS systems."""
        if not date_string:
            return datetime.now()
        
        try:
            # Common patterns
            patterns = [
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
                r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
                r'(\d{1,2})\s+days?\s+ago',      # X days ago
                r'(\d{1,2})\s+hours?\s+ago',     # X hours ago
            ]
            
            for pattern in patterns:
                match = re.search(pattern, date_string, re.IGNORECASE)
                if match:
                    if 'days ago' in date_string.lower():
                        days = int(match.group(1))
                        return datetime.now() - timedelta(days=days)
                    elif 'hours ago' in date_string.lower():
                        hours = int(match.group(1))
                        return datetime.now() - timedelta(hours=hours)
                    else:
                        # Handle MM/DD/YYYY or YYYY-MM-DD
                        try:
                            if '/' in date_string:
                                return datetime.strptime(date_string, '%m/%d/%Y')
                            else:
                                return datetime.strptime(date_string, '%Y-%m-%d')
                        except ValueError:
                            continue
            
        except Exception as e:
            logger.warning(f"Error parsing date '{date_string}': {str(e)}")
        
        return datetime.now()
    
    @staticmethod
    def matches_focus_areas(job: JobData, focus_areas: List[str]) -> bool:
        """Check if job matches specified focus areas."""
        if not focus_areas or "all" in focus_areas:
            return True
        
        job_text = (job.title + " " + job.description).lower()
        
        if "internships" in focus_areas and "intern" in job_text:
            return True
        if "new_grad" in focus_areas and any(term in job_text for term in ["new grad", "entry level", "junior"]):
            return True
        if "remote" in focus_areas and "remote" in job_text:
            return True
        if "h1b" in focus_areas and any(term in job_text for term in ["visa", "h1b", "sponsorship"]):
            return True
        
        return False

# Extend BaseScraper with ATS utility methods
BaseScraper._extract_technologies_from_title = ATSUtils.extract_technologies_from_title
BaseScraper._parse_date = ATSUtils.parse_date
BaseScraper._matches_focus_areas = ATSUtils.matches_focus_areas 
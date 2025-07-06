"""
Scraper for intern-list.com website.
Extracts internship listings from the comprehensive intern list website.
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

import config

from ..database.models import JobData
from config.company_sources import EXTERNAL_SOURCES
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class InternListScraper(BaseScraper):
    """Scraper for intern-list.com internship listings."""
    
    def __init__(self, config_obj=None, backend: str = "requests"):
        self.config = config_obj or config
        super().__init__(backend=backend)
        self.base_url = EXTERNAL_SOURCES["intern_list"]["base_url"]
        self.engineering_url = EXTERNAL_SOURCES["intern_list"]["engineering_url"]
        self.software_url = EXTERNAL_SOURCES["intern_list"]["software_url"]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    async def scrape_all_categories(self) -> List[JobData]:
        """Scrape all relevant internship categories."""
        all_jobs = []
        
        categories = [
            ("engineering", self.engineering_url),
            ("software", self.software_url)
        ]
        
        for category, url in categories:
            try:
                logger.info(f"Scraping intern-list.com category: {category}")
                jobs = await self.scrape_category(url, category)
                all_jobs.extend(jobs)
                
                # Rate limiting
                await asyncio.sleep(self.request_delay)
                
            except Exception as e:
                logger.error(f"Error scraping category {category}: {str(e)}")
        
        logger.info(f"Total jobs scraped from intern-list.com: {len(all_jobs)}")
        return all_jobs

    async def scrape_category(self, url: str, category: str) -> List[JobData]:
        """Scrape a specific category page."""
        try:
            await asyncio.sleep(self.request_delay)
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try different extraction methods
            jobs = []
            
            # Method 1: Look for structured job data in scripts
            script_jobs = self._extract_from_scripts(soup, category)
            jobs.extend(script_jobs)
            
            # Method 2: Parse HTML structure
            if not jobs:
                html_jobs = self._extract_from_html(soup, category)
                jobs.extend(html_jobs)
            
            # Method 3: Try to find table/list structures
            if not jobs:
                table_jobs = self._extract_from_tables(soup, category)
                jobs.extend(table_jobs)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return []

    def _extract_from_scripts(self, soup: BeautifulSoup, category: str) -> List[JobData]:
        """Extract job data from JavaScript variables or JSON in scripts."""
        jobs = []
        
        try:
            # Look for script tags that might contain job data
            scripts = soup.find_all('script')
            
            for script in scripts:
                if script.string:
                    script_content = script.string
                    
                    # Look for JSON data patterns
                    json_matches = re.finditer(r'({[^{}]*"company"[^{}]*})', script_content, re.IGNORECASE)
                    for match in json_matches:
                        try:
                            job_data = json.loads(match.group(1))
                            job = self._parse_json_job(job_data, category)
                            if job:
                                jobs.append(job)
                        except (json.JSONDecodeError, Exception):
                            continue
                    
                    # Look for array patterns
                    array_matches = re.finditer(r'\[([^[\]]*"company"[^[\]]*)\]', script_content, re.IGNORECASE)
                    for match in array_matches:
                        try:
                            array_content = '[' + match.group(1) + ']'
                            job_array = json.loads(array_content)
                            for job_data in job_array:
                                if isinstance(job_data, dict):
                                    job = self._parse_json_job(job_data, category)
                                    if job:
                                        jobs.append(job)
                        except (json.JSONDecodeError, Exception):
                            continue
            
        except Exception as e:
            logger.warning(f"Error extracting from scripts: {str(e)}")
        
        return jobs

    def _extract_from_html(self, soup: BeautifulSoup, category: str) -> List[JobData]:
        """Extract job data from HTML structure."""
        jobs = []
        
        try:
            # Common selectors for job listings
            selectors = [
                'div[class*="job"]',
                'div[class*="position"]',
                'div[class*="listing"]',
                'div[class*="item"]',
                'tr[class*="job"]',
                'li[class*="job"]',
                '.job-item',
                '.job-listing',
                '.position-item',
                '[data-company]',
                '[data-position]'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        job = self._parse_html_job_element(element, category)
                        if job:
                            jobs.append(job)
                    break  # Use first successful selector
            
        except Exception as e:
            logger.warning(f"Error extracting from HTML: {str(e)}")
        
        return jobs

    def _extract_from_tables(self, soup: BeautifulSoup, category: str) -> List[JobData]:
        """Extract job data from table structures."""
        jobs = []
        
        try:
            tables = soup.find_all('table')
            
            for table in tables:
                # Look for header row to identify column structure
                headers = []
                header_row = table.find('tr')
                if header_row:
                    header_cells = header_row.find_all(['th', 'td'])
                    headers = [cell.get_text().strip().lower() for cell in header_cells]
                
                # Process data rows
                rows = table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:  # At least company and position
                        job = self._parse_table_row(cells, headers, category)
                        if job:
                            jobs.append(job)
            
        except Exception as e:
            logger.warning(f"Error extracting from tables: {str(e)}")
        
        return jobs

    def _parse_json_job(self, job_data: Dict, category: str) -> Optional[JobData]:
        """Parse job data from JSON object."""
        try:
            # Extract fields with various possible key names
            company = self._get_field(job_data, ['company', 'companyName', 'employer'])
            title = self._get_field(job_data, ['title', 'position', 'role', 'jobTitle'])
            location = self._get_field(job_data, ['location', 'city', 'state', 'place'])
            url = self._get_field(job_data, ['url', 'link', 'apply', 'applicationUrl'])
            description = self._get_field(job_data, ['description', 'details', 'summary'])
            requirements = self._get_field(job_data, ['requirements', 'qualifications'])
            
            if not company or not title:
                return None
            
            return JobData(
                title=title,
                company=company,
                location=location or "Remote",
                job_type="Internship",
                experience_level="Entry-level",
                salary_min=None,
                salary_max=None,
                description=description or "",
                requirements=requirements or "",
                benefits="",
                url=url or "",
                posting_date=datetime.now(),
                technologies=self._extract_technologies(title + " " + (description or "")),
                source="intern-list.com",
                remote_eligible="remote" in (location or "").lower(),
                visa_sponsorship=False
            )
            
        except Exception as e:
            logger.warning(f"Error parsing JSON job: {str(e)}")
            return None

    def _parse_html_job_element(self, element: BeautifulSoup, category: str) -> Optional[JobData]:
        """Parse job data from HTML element."""
        try:
            # Try to extract company name
            company_selectors = [
                '[class*="company"]',
                '[data-company]',
                '.company-name',
                'h3', 'h4', 'h5',
                'strong', 'b'
            ]
            
            company = ""
            for selector in company_selectors:
                comp_elem = element.select_one(selector)
                if comp_elem:
                    company = comp_elem.get_text().strip()
                    if company:
                        break
            
            # Try to extract position title
            title_selectors = [
                '[class*="title"]',
                '[class*="position"]',
                '[data-position]',
                '.job-title',
                'h1', 'h2', 'h3',
                'a[href*="job"]'
            ]
            
            title = ""
            for selector in title_selectors:
                title_elem = element.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title and title != company:
                        break
            
            # Try to extract location
            location_selectors = [
                '[class*="location"]',
                '[data-location]',
                '.location',
                'span:contains("Remote")',
                'span:contains("CA")',
                'span:contains("NY")'
            ]
            
            location = ""
            for selector in location_selectors:
                loc_elem = element.select_one(selector)
                if loc_elem:
                    location = loc_elem.get_text().strip()
                    if location:
                        break
            
            # Try to find application link
            url = ""
            link_elem = element.find('a', href=True)
            if link_elem:
                url = link_elem['href']
                if not url.startswith('http'):
                    url = urljoin(self.base_url, url)
            
            if company and title:
                return JobData(
                    title=title,
                    company=company,
                    location=location or "Remote",
                    job_type="Internship",
                    experience_level="Entry-level",
                    salary_min=None,
                    salary_max=None,
                    description="",
                    requirements="",
                    benefits="",
                    url=url,
                    posting_date=datetime.now(),
                    technologies=self._extract_technologies(title),
                    source="intern-list.com",
                    remote_eligible="remote" in (location or "").lower(),
                    visa_sponsorship=False
                )
            
        except Exception as e:
            logger.warning(f"Error parsing HTML job element: {str(e)}")
        
        return None

    def _parse_table_row(self, cells: List, headers: List[str], category: str) -> Optional[JobData]:
        """Parse job data from table row."""
        try:
            if len(cells) < 2:
                return None
            
            # Map cells to data based on headers or position
            company = ""
            title = ""
            location = ""
            url = ""
            
            if headers:
                # Use headers to map data
                for i, header in enumerate(headers):
                    if i < len(cells):
                        cell_text = cells[i].get_text().strip()
                        
                        if 'company' in header:
                            company = cell_text
                        elif any(word in header for word in ['title', 'position', 'role']):
                            title = cell_text
                        elif 'location' in header:
                            location = cell_text
                        elif 'link' in header or 'url' in header:
                            link_elem = cells[i].find('a', href=True)
                            if link_elem:
                                url = link_elem['href']
            else:
                # Assume standard order: company, title, location
                company = cells[0].get_text().strip()
                if len(cells) > 1:
                    title = cells[1].get_text().strip()
                if len(cells) > 2:
                    location = cells[2].get_text().strip()
                
                # Look for link in any cell
                for cell in cells:
                    link_elem = cell.find('a', href=True)
                    if link_elem:
                        url = link_elem['href']
                        break
            
            if company and title:
                return JobData(
                    title=title,
                    company=company,
                    location=location or "Remote",
                    job_type="Internship",
                    experience_level="Entry-level",
                    salary_min=None,
                    salary_max=None,
                    description="",
                    requirements="",
                    benefits="",
                    url=url if url.startswith('http') else urljoin(self.base_url, url) if url else "",
                    posting_date=datetime.now(),
                    technologies=self._extract_technologies(title),
                    source="intern-list.com",
                    remote_eligible="remote" in (location or "").lower(),
                    visa_sponsorship=False
                )
            
        except Exception as e:
            logger.warning(f"Error parsing table row: {str(e)}")
        
        return None

    def _get_field(self, data: Dict, possible_keys: List[str]) -> str:
        """Get field value from dict using multiple possible keys."""
        for key in possible_keys:
            if key in data and data[key]:
                return str(data[key]).strip()
        return ""

    def _extract_technologies(self, text: str) -> List[str]:
        """Extract technology keywords from text."""
        if not text:
            return []
        
        text_lower = text.lower()
        technologies = []
        
        # Common technology keywords
        tech_keywords = [
            'python', 'java', 'javascript', 'react', 'node.js', 'angular', 'vue',
            'c++', 'c#', 'go', 'rust', 'swift', 'kotlin', 'scala',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes',
            'tensorflow', 'pytorch', 'machine learning', 'ai',
            'sql', 'mongodb', 'postgresql', 'redis',
            'git', 'jenkins', 'ci/cd'
        ]
        
        for tech in tech_keywords:
            if tech in text_lower:
                technologies.append(tech.title())
        
        return technologies

    async def test_scraping(self) -> Dict[str, Any]:
        """Test the scraping functionality and return status."""
        results = {
            "accessible": False,
            "categories_tested": [],
            "total_jobs_found": 0,
            "errors": []
        }
        
        try:
            # Test base URL accessibility
            response = requests.get(self.base_url, headers=self.headers, timeout=10)
            results["accessible"] = response.status_code == 200
            
            if results["accessible"]:
                # Test each category
                categories = [
                    ("engineering", self.engineering_url),
                    ("software", self.software_url)
                ]
                
                for category, url in categories:
                    try:
                        jobs = await self.scrape_category(url, category)
                        results["categories_tested"].append({
                            "category": category,
                            "jobs_found": len(jobs),
                            "success": True
                        })
                        results["total_jobs_found"] += len(jobs)
                    except Exception as e:
                        results["categories_tested"].append({
                            "category": category,
                            "jobs_found": 0,
                            "success": False,
                            "error": str(e)
                        })
                        results["errors"].append(f"{category}: {str(e)}")
            
        except Exception as e:
            results["errors"].append(f"Base URL test failed: {str(e)}")
        
        return results 

    async def scrape_jobs(self, *args, **kwargs):
        """Fallback method for abstract base class compliance (calls scrape_all_categories)."""
        return await self.scrape_all_categories() 
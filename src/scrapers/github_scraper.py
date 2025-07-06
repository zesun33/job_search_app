"""
GitHub repository scraper for job listings.
Scrapes job data from GitHub repositories that maintain job listing collections.
"""

import asyncio
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin, urlparse
import time

from ..database.models import JobData
from ..config.company_sources import GITHUB_JOB_SOURCES
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class GitHubJobScraper(BaseScraper):
    """Scraper for GitHub repositories containing job listings."""
    
    def __init__(self, config):
        super().__init__(config)
        self.github_token = config.github_token  # Optional GitHub API token
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; JobSearchBot/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        if self.github_token:
            self.api_headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }

    async def scrape_repository(self, repo_key: str) -> List[JobData]:
        """Scrape jobs from a specific GitHub repository."""
        if repo_key not in GITHUB_JOB_SOURCES:
            logger.error(f"Unknown repository key: {repo_key}")
            return []
        
        repo_config = GITHUB_JOB_SOURCES[repo_key]
        repo_name = repo_config["repo"]
        
        logger.info(f"Scraping GitHub repository: {repo_name}")
        
        try:
            # Try API approach first, fallback to web scraping
            jobs = await self._scrape_via_api(repo_name, repo_config)
            if not jobs:
                jobs = await self._scrape_via_web(repo_name, repo_config)
            
            logger.info(f"Found {len(jobs)} jobs in {repo_name}")
            return jobs
            
        except Exception as e:
            logger.error(f"Error scraping {repo_name}: {str(e)}")
            return []

    async def _scrape_via_api(self, repo_name: str, repo_config: Dict) -> List[JobData]:
        """Scrape using GitHub API (if token available)."""
        if not self.github_token:
            return []
        
        try:
            # Get repository contents
            api_url = f"https://api.github.com/repos/{repo_name}/contents"
            response = requests.get(api_url, headers=self.api_headers, timeout=30)
            response.raise_for_status()
            
            contents = response.json()
            
            # Look for README.md or main content file
            readme_content = None
            for item in contents:
                if item['name'].lower() == 'readme.md':
                    readme_url = item['download_url']
                    readme_response = requests.get(readme_url, timeout=30)
                    readme_response.raise_for_status()
                    readme_content = readme_response.text
                    break
            
            if readme_content:
                return self._parse_markdown_jobs(readme_content, repo_name, repo_config)
            
        except Exception as e:
            logger.warning(f"API scraping failed for {repo_name}: {str(e)}")
        
        return []

    async def _scrape_via_web(self, repo_name: str, repo_config: Dict) -> List[JobData]:
        """Scrape using web interface."""
        try:
            # GitHub repository URL
            repo_url = f"https://github.com/{repo_name}"
            
            await asyncio.sleep(self.request_delay)
            response = requests.get(repo_url, headers=self.base_headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to find the README content
            readme_content = self._extract_readme_content(soup)
            if readme_content:
                return self._parse_markdown_jobs(readme_content, repo_name, repo_config)
            
        except Exception as e:
            logger.error(f"Web scraping failed for {repo_name}: {str(e)}")
        
        return []

    def _extract_readme_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract README content from GitHub page."""
        try:
            # Look for README content in various possible containers
            readme_selectors = [
                'article.markdown-body',
                'div.markdown-body',
                '[data-target="readme-toc.content"]',
                'div.Box-body.px-5.pb-5'
            ]
            
            for selector in readme_selectors:
                readme_elem = soup.select_one(selector)
                if readme_elem:
                    return readme_elem.get_text()
            
        except Exception as e:
            logger.warning(f"Error extracting README: {str(e)}")
        
        return None

    def _parse_markdown_jobs(self, content: str, repo_name: str, repo_config: Dict) -> List[JobData]:
        """Parse job data from markdown content."""
        jobs = []
        
        try:
            # Different parsing strategies based on repository
            if "Daily-H1B-Jobs" in repo_name:
                jobs = self._parse_h1b_jobs(content, repo_name)
            elif "SimplifyJobs" in repo_name:
                jobs = self._parse_simplify_jobs(content, repo_name)
            elif "jobright-ai" in repo_name:
                jobs = self._parse_jobright_jobs(content, repo_name)
            else:
                jobs = self._parse_generic_jobs(content, repo_name)
                
        except Exception as e:
            logger.error(f"Error parsing jobs from {repo_name}: {str(e)}")
        
        return jobs

    def _parse_h1b_jobs(self, content: str, repo_name: str) -> List[JobData]:
        """Parse Daily H1B Jobs format."""
        jobs = []
        
        # Look for job tables in markdown
        lines = content.split('\n')
        in_table = False
        headers = []
        
        for line in lines:
            line = line.strip()
            
            # Detect table headers
            if '|' in line and ('Company' in line or 'Job Title' in line):
                headers = [h.strip() for h in line.split('|') if h.strip()]
                in_table = True
                continue
            
            # Skip separator line
            if in_table and line.startswith('|') and all(c in '|-: ' for c in line):
                continue
            
            # Parse job rows
            if in_table and line.startswith('|'):
                try:
                    job = self._parse_h1b_job_row(line, headers, repo_name)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Error parsing job row: {str(e)}")
                    continue
            elif in_table and not line.startswith('|'):
                in_table = False
        
        return jobs

    def _parse_h1b_job_row(self, line: str, headers: List[str], repo_name: str) -> Optional[JobData]:
        """Parse a single H1B job row."""
        try:
            # Split by | and clean up
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
            
            if len(cells) < len(headers):
                return None
            
            # Create mapping
            job_data = dict(zip(headers, cells))
            
            # Extract information
            company = self._clean_markdown(job_data.get('Company', ''))
            title = self._clean_markdown(job_data.get('Job Title', ''))
            location = self._clean_markdown(job_data.get('Location', ''))
            level = self._clean_markdown(job_data.get('Level', ''))
            h1b_status = job_data.get('H1B status', '')
            link = self._extract_link(job_data.get('Link', ''))
            date_posted = job_data.get('Date Posted', '')
            
            if not company or not title:
                return None
            
            # Determine experience level
            experience_level = self._map_experience_level(level)
            
            # Parse date
            posting_date = self._parse_date(date_posted)
            
            # Create JobData object
            return JobData(
                title=title,
                company=company,
                location=location,
                job_type="Full-time",  # Default assumption
                experience_level=experience_level,
                salary_min=None,
                salary_max=None,
                description=f"H1B Status: {h1b_status}",
                requirements="",
                benefits="H1B sponsorship available" if '🏅' in h1b_status else "Company has H1B history",
                url=link,
                posting_date=posting_date,
                technologies=[],
                source=f"GitHub: {repo_name}",
                remote_eligible=False,
                visa_sponsorship=True
            )
            
        except Exception as e:
            logger.warning(f"Error parsing H1B job row: {str(e)}")
            return None

    def _parse_simplify_jobs(self, content: str, repo_name: str) -> List[JobData]:
        """Parse SimplifyJobs format."""
        jobs = []
        
        # SimplifyJobs typically uses different markdown formats
        # Look for job listings in various patterns
        
        # Pattern 1: Table format
        table_jobs = self._parse_table_format(content, repo_name)
        jobs.extend(table_jobs)
        
        # Pattern 2: List format
        list_jobs = self._parse_list_format(content, repo_name)
        jobs.extend(list_jobs)
        
        return jobs

    def _parse_table_format(self, content: str, repo_name: str) -> List[JobData]:
        """Parse table format job listings."""
        jobs = []
        lines = content.split('\n')
        in_table = False
        headers = []
        
        for line in lines:
            line = line.strip()
            
            if '|' in line and any(keyword in line.lower() for keyword in ['company', 'position', 'location']):
                headers = [h.strip() for h in line.split('|') if h.strip()]
                in_table = True
                continue
            
            if in_table and line.startswith('|') and all(c in '|-: ' for c in line):
                continue
            
            if in_table and line.startswith('|'):
                try:
                    job = self._parse_generic_job_row(line, headers, repo_name)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Error parsing table job: {str(e)}")
            elif in_table and not line.startswith('|'):
                in_table = False
        
        return jobs

    def _parse_list_format(self, content: str, repo_name: str) -> List[JobData]:
        """Parse list format job listings."""
        jobs = []
        
        # Look for patterns like "- [Company] - [Position] - [Location]"
        pattern = r'[-*]\s*\[(.*?)\]\s*-\s*(.*?)\s*-\s*(.*?)(?:\s*-\s*(.*?))?'
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        for match in matches:
            try:
                company = match.group(1).strip()
                title = match.group(2).strip()
                location = match.group(3).strip()
                extra = match.group(4).strip() if match.group(4) else ""
                
                if company and title:
                    job = JobData(
                        title=title,
                        company=company,
                        location=location,
                        job_type="Internship" if "intern" in repo_name.lower() else "Full-time",
                        experience_level="Entry-level",
                        salary_min=None,
                        salary_max=None,
                        description=extra,
                        requirements="",
                        benefits="",
                        url="",
                        posting_date=datetime.now(),
                        technologies=[],
                        source=f"GitHub: {repo_name}",
                        remote_eligible=False,
                        visa_sponsorship=False
                    )
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Error parsing list job: {str(e)}")
        
        return jobs

    def _parse_jobright_jobs(self, content: str, repo_name: str) -> List[JobData]:
        """Parse jobright-ai repository format."""
        # Similar to H1B jobs but may have different structure
        return self._parse_h1b_jobs(content, repo_name)

    def _parse_generic_jobs(self, content: str, repo_name: str) -> List[JobData]:
        """Generic job parsing for unknown formats."""
        jobs = []
        
        # Try table format first
        jobs.extend(self._parse_table_format(content, repo_name))
        
        # Try list format
        jobs.extend(self._parse_list_format(content, repo_name))
        
        return jobs

    def _parse_generic_job_row(self, line: str, headers: List[str], repo_name: str) -> Optional[JobData]:
        """Parse a generic job table row."""
        try:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            
            if len(cells) < len(headers):
                return None
            
            job_data = dict(zip(headers, cells))
            
            # Try to map common column names
            company = ""
            title = ""
            location = ""
            
            for key, value in job_data.items():
                key_lower = key.lower()
                clean_value = self._clean_markdown(value)
                
                if 'company' in key_lower:
                    company = clean_value
                elif any(word in key_lower for word in ['position', 'title', 'job', 'role']):
                    title = clean_value
                elif 'location' in key_lower:
                    location = clean_value
            
            if company and title:
                return JobData(
                    title=title,
                    company=company,
                    location=location,
                    job_type="Internship" if "intern" in repo_name.lower() else "Full-time",
                    experience_level="Entry-level",
                    salary_min=None,
                    salary_max=None,
                    description="",
                    requirements="",
                    benefits="",
                    url="",
                    posting_date=datetime.now(),
                    technologies=[],
                    source=f"GitHub: {repo_name}",
                    remote_eligible=False,
                    visa_sponsorship=False
                )
        except Exception as e:
            logger.warning(f"Error parsing generic job row: {str(e)}")
        
        return None

    def _clean_markdown(self, text: str) -> str:
        """Clean markdown formatting from text."""
        if not text:
            return ""
        
        # Remove markdown links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        # Remove other markdown
        text = re.sub(r'[`#]', '', text)
        
        return text.strip()

    def _extract_link(self, cell: str) -> str:
        """Extract URL from markdown link."""
        match = re.search(r'\]\(([^)]+)\)', cell)
        return match.group(1) if match else ""

    def _map_experience_level(self, level: str) -> str:
        """Map level text to standard experience levels."""
        if not level:
            return "Entry-level"
        
        level_lower = level.lower()
        if any(word in level_lower for word in ['intern', 'entry', 'junior', 'new grad']):
            return "Entry-level"
        elif any(word in level_lower for word in ['mid', 'intermediate']):
            return "Mid-level"
        elif any(word in level_lower for word in ['senior', 'lead']):
            return "Senior"
        elif any(word in level_lower for word in ['principal', 'staff']):
            return "Principal"
        else:
            return "Entry-level"

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        if not date_str:
            return datetime.now()
        
        try:
            # Try various date formats
            formats = [
                '%Y-%m-%d',
                '%m/%d/%Y',
                '%d/%m/%Y',
                '%Y-%m-%d %H:%M:%S',
                '%B %d, %Y'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # If no format works, return current time
            return datetime.now()
            
        except Exception:
            return datetime.now()

    async def scrape_all_repositories(self) -> List[JobData]:
        """Scrape all configured GitHub repositories."""
        all_jobs = []
        
        for repo_key in GITHUB_JOB_SOURCES.keys():
            try:
                jobs = await self.scrape_repository(repo_key)
                all_jobs.extend(jobs)
                
                # Rate limiting
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scraping repository {repo_key}: {str(e)}")
        
        logger.info(f"Total jobs scraped from GitHub repositories: {len(all_jobs)}")
        return all_jobs

    def get_repository_status(self) -> Dict[str, Any]:
        """Get status of all repositories."""
        status = {}
        
        for repo_key, repo_config in GITHUB_JOB_SOURCES.items():
            try:
                repo_url = f"https://api.github.com/repos/{repo_config['repo']}"
                headers = self.api_headers if self.github_token else {}
                
                response = requests.get(repo_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    status[repo_key] = {
                        "name": repo_config["repo"],
                        "description": repo_config["description"],
                        "last_updated": data.get("updated_at", ""),
                        "stars": data.get("stargazers_count", 0),
                        "accessible": True
                    }
                else:
                    status[repo_key] = {
                        "name": repo_config["repo"],
                        "description": repo_config["description"],
                        "accessible": False,
                        "error": f"HTTP {response.status_code}"
                    }
                    
            except Exception as e:
                status[repo_key] = {
                    "name": repo_config["repo"],
                    "description": repo_config["description"],
                    "accessible": False,
                    "error": str(e)
                }
        
        return status 
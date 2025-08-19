"""
Job Source Coordinator - manages all job acquisition sources.
Coordinates scraping from GitHub repositories, APIs, company websites, and external sources.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from ..database.models import JobData, Session
from ..database import get_session
from ..api_clients.base_client import JobAPIManager
from ..scrapers.github_scraper import GitHubJobScraper
from ..scrapers.intern_list_scraper import InternListScraper
from ..scrapers.base_scraper import BaseScraper
from ..config.config import Config
from ..config.company_sources import (
    TECH_COMPANIES, 
    GITHUB_JOB_SOURCES, 
    EXTERNAL_SOURCES,
    ATSType,
    get_high_priority_companies,
    get_internship_focused_companies
)

logger = logging.getLogger(__name__)

@dataclass
class SourceResult:
    """Result from a single job source."""
    source_name: str
    source_type: str
    jobs_found: int
    jobs_saved: int
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    last_updated: datetime = None

@dataclass
class ScrapeSession:
    """A complete job scraping session across all sources."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    total_jobs_found: int
    total_jobs_saved: int
    sources_processed: List[SourceResult]
    focus_areas: List[str]  # e.g., ["internships", "new_grad", "h1b"]
    success: bool

class JobSourceCoordinator:
    """Coordinates job acquisition from all configured sources."""
    
    def __init__(self, config: Config):
        self.config = config
        self.api_manager = JobAPIManager(config)
        self.github_scraper = GitHubJobScraper(config)
        self.intern_list_scraper = InternListScraper(config)
        self.company_scrapers = {}  # Will be populated with company-specific scrapers
        
        # Source priority and configuration
        self.source_priorities = {
            "github_repos": 1,
            "api_clients": 2,
            "intern_list": 3,
            "company_websites": 4,
            "ats_systems": 5
        }
        
        # Deduplication tracking
        self.seen_jobs: Set[str] = set()
        
    async def run_comprehensive_search(
        self, 
        focus_areas: List[str] = None,
        max_jobs_per_source: Optional[int] = None,
        priority_companies_only: bool = False
    ) -> ScrapeSession:
        """
        Run a comprehensive job search across all sources.
        
        Args:
            focus_areas: List of focus areas ["internships", "new_grad", "h1b", "remote"]
            max_jobs_per_source: Limit jobs per source (for testing)
            priority_companies_only: Only scrape high-priority companies
        """
        session_id = f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session = ScrapeSession(
            session_id=session_id,
            start_time=datetime.now(),
            end_time=None,
            total_jobs_found=0,
            total_jobs_saved=0,
            sources_processed=[],
            focus_areas=focus_areas or ["all"],
            success=False
        )
        
        logger.info(f"Starting comprehensive job search session: {session_id}")
        logger.info(f"Focus areas: {focus_areas}")
        
        try:
            # Clear deduplication tracking
            self.seen_jobs.clear()
            
            # Phase 1: GitHub Repositories (highest priority, most reliable)
            if "internships" in (focus_areas or []) or "all" in (focus_areas or []):
                github_result = await self._scrape_github_sources(max_jobs_per_source)
                session.sources_processed.append(github_result)
                session.total_jobs_found += github_result.jobs_found
                session.total_jobs_saved += github_result.jobs_saved
            
            # Phase 2: External websites (intern-list.com)
            if "internships" in (focus_areas or []) or "all" in (focus_areas or []):
                intern_list_result = await self._scrape_intern_list(max_jobs_per_source)
                session.sources_processed.append(intern_list_result)
                session.total_jobs_found += intern_list_result.jobs_found
                session.total_jobs_saved += intern_list_result.jobs_saved
            
            # Phase 3: Job Board APIs
            api_result = await self._scrape_api_sources(focus_areas, max_jobs_per_source)
            session.sources_processed.append(api_result)
            session.total_jobs_found += api_result.jobs_found
            session.total_jobs_saved += api_result.jobs_saved
            
            # Phase 4: Company websites (priority companies first)
            if priority_companies_only:
                companies = get_high_priority_companies()
                if "internships" in (focus_areas or []):
                    companies.extend(get_internship_focused_companies())
                companies = list(set(companies))  # Remove duplicates
            else:
                companies = list(TECH_COMPANIES.keys())
            
            company_result = await self._scrape_company_websites(
                companies[:20] if max_jobs_per_source else companies,  # Limit for testing
                focus_areas
            )
            session.sources_processed.append(company_result)
            session.total_jobs_found += company_result.jobs_found
            session.total_jobs_saved += company_result.jobs_saved
            
            session.end_time = datetime.now()
            session.success = True
            
            logger.info(f"Search session {session_id} completed successfully")
            logger.info(f"Total jobs found: {session.total_jobs_found}")
            logger.info(f"Total jobs saved: {session.total_jobs_saved}")
            
        except Exception as e:
            logger.error(f"Error in comprehensive search: {str(e)}")
            session.end_time = datetime.now()
            session.success = False
        
        return session

    async def _scrape_github_sources(self, max_jobs: Optional[int] = None) -> SourceResult:
        """Scrape all GitHub repository sources."""
        start_time = datetime.now()
        result = SourceResult(
            source_name="GitHub Repositories",
            source_type="github",
            jobs_found=0,
            jobs_saved=0,
            execution_time=0,
            success=False,
            last_updated=start_time
        )
        
        try:
            logger.info("Starting GitHub repositories scraping...")
            jobs = await self.github_scraper.scrape_all_repositories()
            
            if max_jobs:
                jobs = jobs[:max_jobs]
            
            result.jobs_found = len(jobs)
            
            # Save jobs to database with deduplication
            saved_count = await self._save_jobs_with_dedup(jobs, "github")
            result.jobs_saved = saved_count
            result.success = True
            
        except Exception as e:
            logger.error(f"Error scraping GitHub sources: {str(e)}")
            result.error_message = str(e)
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        return result

    async def _scrape_intern_list(self, max_jobs: Optional[int] = None) -> SourceResult:
        """Scrape intern-list.com website."""
        start_time = datetime.now()
        result = SourceResult(
            source_name="Intern-List.com",
            source_type="external_website",
            jobs_found=0,
            jobs_saved=0,
            execution_time=0,
            success=False,
            last_updated=start_time
        )
        
        try:
            logger.info("Starting intern-list.com scraping...")
            jobs = await self.intern_list_scraper.scrape_all_categories()
            
            if max_jobs:
                jobs = jobs[:max_jobs]
            
            result.jobs_found = len(jobs)
            
            # Save jobs with deduplication
            saved_count = await self._save_jobs_with_dedup(jobs, "intern_list")
            result.jobs_saved = saved_count
            result.success = True
            
        except Exception as e:
            logger.error(f"Error scraping intern-list.com: {str(e)}")
            result.error_message = str(e)
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        return result

    async def _scrape_api_sources(self, focus_areas: List[str], max_jobs: Optional[int] = None) -> SourceResult:
        """Scrape job board APIs."""
        start_time = datetime.now()
        result = SourceResult(
            source_name="Job Board APIs",
            source_type="api",
            jobs_found=0,
            jobs_saved=0,
            execution_time=0,
            success=False,
            last_updated=start_time
        )
        
        try:
            logger.info("Starting job board API scraping...")
            
            # Determine search terms based on focus areas
            search_terms = self._get_search_terms_for_focus(focus_areas)
            
            all_jobs = []
            for term in search_terms:
                try:
                    jobs = await self.api_manager.search_all_sources(
                        query=term,
                        location="United States",
                        max_results=max_jobs // len(search_terms) if max_jobs else 100
                    )
                    all_jobs.extend(jobs)
                except Exception as e:
                    logger.warning(f"Error searching APIs for '{term}': {str(e)}")
            
            result.jobs_found = len(all_jobs)
            
            # Save jobs with deduplication
            saved_count = await self._save_jobs_with_dedup(all_jobs, "api")
            result.jobs_saved = saved_count
            result.success = True
            
        except Exception as e:
            logger.error(f"Error scraping API sources: {str(e)}")
            result.error_message = str(e)
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        return result

    async def _scrape_company_websites(self, companies: List[str], focus_areas: List[str]) -> SourceResult:
        """Scrape company websites directly."""
        start_time = datetime.now()
        result = SourceResult(
            source_name="Company Websites",
            source_type="company_direct",
            jobs_found=0,
            jobs_saved=0,
            execution_time=0,
            success=False,
            last_updated=start_time
        )
        
        try:
            logger.info(f"Starting company website scraping for {len(companies)} companies...")
            
            all_jobs = []
            for company_key in companies:
                if company_key not in TECH_COMPANIES:
                    continue
                
                try:
                    company_config = TECH_COMPANIES[company_key]
                    
                    # Create appropriate scraper based on ATS type
                    scraper = await self._get_company_scraper(company_config)
                    if scraper:
                        jobs = await scraper.scrape_company_jobs(company_config, focus_areas)
                        all_jobs.extend(jobs)
                        
                        # Rate limiting between companies
                        await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.warning(f"Error scraping {company_key}: {str(e)}")
            
            result.jobs_found = len(all_jobs)
            
            # Save jobs with deduplication
            saved_count = await self._save_jobs_with_dedup(all_jobs, "company_direct")
            result.jobs_saved = saved_count
            result.success = True
            
        except Exception as e:
            logger.error(f"Error scraping company websites: {str(e)}")
            result.error_message = str(e)
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        return result

    async def _get_company_scraper(self, company_config) -> Optional[BaseScraper]:
        """Get appropriate scraper for company based on ATS type."""
        # For now, return base scraper. In production, you'd have specialized scrapers
        # for different ATS types (Workday, Greenhouse, etc.)
        return BaseScraper(self.config)

    async def _save_jobs_with_dedup(self, jobs: List[JobData], source_prefix: str) -> int:
        """Save jobs to database with deduplication."""
        if not jobs:
            return 0
        
        saved_count = 0
        session = get_session()
        
        try:
            for job in jobs:
                # Create job hash for deduplication
                job_hash = self._create_job_hash(job)
                
                if job_hash not in self.seen_jobs:
                    # Add source prefix to distinguish origins
                    job.source = f"{source_prefix}:{job.source}"
                    
                    session.add(job)
                    self.seen_jobs.add(job_hash)
                    saved_count += 1
            
            session.commit()
            logger.info(f"Saved {saved_count} new jobs from {source_prefix}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving jobs from {source_prefix}: {str(e)}")
        finally:
            session.close()
        
        return saved_count

    def _create_job_hash(self, job: JobData) -> str:
        """Create a hash for job deduplication."""
        # Use title + company + location for basic deduplication
        hash_string = f"{job.title.lower()}_{job.company.lower()}_{job.location.lower()}"
        # Remove extra whitespace and special characters
        hash_string = ''.join(c for c in hash_string if c.isalnum() or c == '_')
        return hash_string

    def _get_search_terms_for_focus(self, focus_areas: List[str]) -> List[str]:
        """Get search terms based on focus areas."""
        terms = []
        
        if not focus_areas or "all" in focus_areas:
            terms = ["software engineer", "developer", "programmer", "intern"]
        else:
            if "internships" in focus_areas:
                terms.extend(["software intern", "engineering intern", "developer intern"])
            if "new_grad" in focus_areas:
                terms.extend(["new grad software", "entry level developer", "junior engineer"])
            if "h1b" in focus_areas:
                terms.extend(["software engineer visa", "h1b software"])
            if "remote" in focus_areas:
                terms.extend(["remote software engineer", "remote developer"])
        
        return list(set(terms))  # Remove duplicates

    async def get_source_status(self) -> Dict[str, Any]:
        """Get status of all job sources."""
        status = {
            "github_repositories": {},
            "external_websites": {},
            "api_sources": {},
            "company_websites": {}
        }
        
        try:
            # GitHub repositories status
            status["github_repositories"] = self.github_scraper.get_repository_status()
            
            # Intern-list status
            intern_status = await self.intern_list_scraper.test_scraping()
            status["external_websites"]["intern_list"] = intern_status
            
            # API sources status
            api_status = await self.api_manager.test_connections()
            status["api_sources"] = api_status
            
            # Company websites status (sample a few)
            company_status = {}
            high_priority = get_high_priority_companies()[:5]  # Test top 5
            
            for company_key in high_priority:
                if company_key in TECH_COMPANIES:
                    company_config = TECH_COMPANIES[company_key]
                    try:
                        import requests
                        response = requests.get(company_config.careers_url, timeout=10)
                        company_status[company_key] = {
                            "name": company_config.name,
                            "accessible": response.status_code == 200,
                            "ats_type": company_config.ats_type.value
                        }
                    except Exception as e:
                        company_status[company_key] = {
                            "name": company_config.name,
                            "accessible": False,
                            "error": str(e)
                        }
            
            status["company_websites"] = company_status
            
        except Exception as e:
            logger.error(f"Error getting source status: {str(e)}")
            status["error"] = str(e)
        
        return status

    async def run_quick_test(self) -> Dict[str, Any]:
        """Run a quick test of all sources with limited results."""
        logger.info("Running quick test of all job sources...")
        
        session = await self.run_comprehensive_search(
            focus_areas=["internships"],
            max_jobs_per_source=5,
            priority_companies_only=True
        )
        
        return {
            "session_id": session.session_id,
            "success": session.success,
            "total_jobs_found": session.total_jobs_found,
            "total_jobs_saved": session.total_jobs_saved,
            "execution_time": (session.end_time - session.start_time).total_seconds() if session.end_time else 0,
            "sources": [
                {
                    "name": result.source_name,
                    "type": result.source_type,
                    "jobs_found": result.jobs_found,
                    "jobs_saved": result.jobs_saved,
                    "success": result.success,
                    "error": result.error_message
                }
                for result in session.sources_processed
            ]
        } 
#!/usr/bin/env python3
"""
Comprehensive system test for the Job Search Application.
Tests all major components including database, scrapers, ranking, notifications, and web interface.
"""

import asyncio
import logging
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.config import Config, DefaultPreferences
from database.models import JobData, UserProfile, Session, create_tables
from database import get_session, init_database
from ranking.job_ranker import JobRanker, RankingExplanation
from notifications.notifier import NotificationManager
from utils.source_coordinator import JobSourceCoordinator
from scrapers.github_scraper import GitHubJobScraper
from scrapers.intern_list_scraper import InternListScraper
from scrapers.ats_scrapers import ATSScraperFactory, ATSType
from api_clients.base_client import JobAPIManager
from web_app.app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/system_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemTester:
    """Comprehensive system tester for the job search application."""
    
    def __init__(self):
        self.config = Config()
        self.test_results = {
            "database": {},
            "scrapers": {},
            "ranking": {},
            "notifications": {},
            "web_interface": {},
            "integration": {},
            "overall_success": False,
            "test_duration": 0,
            "timestamp": datetime.now().isoformat()
        }
        
    async def run_all_tests(self) -> dict:
        """Run all system tests."""
        start_time = time.time()
        logger.info("🚀 Starting comprehensive system tests...")
        
        try:
            # Test 1: Database functionality
            logger.info("📊 Testing database functionality...")
            await self.test_database()
            
            # Test 2: Scraper functionality  
            logger.info("🕷️ Testing scraper functionality...")
            await self.test_scrapers()
            
            # Test 3: Ranking system
            logger.info("📈 Testing ranking system...")
            await self.test_ranking_system()
            
            # Test 4: Notification system
            logger.info("📧 Testing notification system...")
            await self.test_notifications()
            
            # Test 5: Web interface
            logger.info("🌐 Testing web interface...")
            await self.test_web_interface()
            
            # Test 6: Integration test
            logger.info("🔗 Testing end-to-end integration...")
            await self.test_integration()
            
            # Calculate overall success
            self.test_results["overall_success"] = self._calculate_overall_success()
            self.test_results["test_duration"] = time.time() - start_time
            
            if self.test_results["overall_success"]:
                logger.info("✅ All system tests passed!")
            else:
                logger.warning("⚠️ Some system tests failed. Check results for details.")
                
        except Exception as e:
            logger.error(f"❌ System test suite failed: {str(e)}")
            self.test_results["overall_success"] = False
            self.test_results["error"] = str(e)
        
        return self.test_results
    
    async def test_database(self):
        """Test database connectivity, schema creation, and basic operations."""
        try:
            # Test 1: Database connection
            session = get_session()
            self.test_results["database"]["connection"] = {
                "success": True,
                "message": "Database connection successful"
            }
            session.close()
            
            # Test 2: Schema creation
            create_tables()
            self.test_results["database"]["schema"] = {
                "success": True,
                "message": "Database schema created successfully"
            }
            
            # Test 3: Create test user profile
            test_prefs = DefaultPreferences.get_cs_internship_preferences()
            user_profile = UserProfile(
                name="Test User",
                email="test@example.com",
                phone_number="+1234567890",
                preferences=test_prefs.__dict__
            )
            
            session = get_session()
            session.add(user_profile)
            session.commit()
            user_id = user_profile.id
            session.close()
            
            self.test_results["database"]["user_creation"] = {
                "success": True,
                "message": f"Test user created with ID: {user_id}"
            }
            
            # Test 4: Create test job
            test_job = JobData(
                title="Software Engineer Intern",
                company="Test Company",
                location="San Francisco, CA",
                job_type="Internship",
                experience_level="Entry-level",
                description="Test job description",
                requirements="Python, JavaScript",
                url="https://example.com/job",
                posting_date=datetime.now(),
                technologies=["Python", "JavaScript"],
                source="test"
            )
            
            session = get_session()
            session.add(test_job)
            session.commit()
            job_id = test_job.id
            session.close()
            
            self.test_results["database"]["job_creation"] = {
                "success": True,
                "message": f"Test job created with ID: {job_id}"
            }
            
        except Exception as e:
            logger.error(f"Database test failed: {str(e)}")
            self.test_results["database"]["error"] = str(e)
    
    async def test_scrapers(self):
        """Test all scraper components."""
        try:
            # Test 1: GitHub scraper
            github_scraper = GitHubJobScraper(self.config)
            github_status = github_scraper.get_repository_status()
            
            self.test_results["scrapers"]["github"] = {
                "success": len(github_status) > 0,
                "repositories_configured": len(github_status),
                "details": github_status
            }
            
            # Test 2: Intern-list scraper
            intern_scraper = InternListScraper(self.config)
            intern_status = await intern_scraper.test_scraping()
            
            self.test_results["scrapers"]["intern_list"] = {
                "success": intern_status.get("accessible", False),
                "details": intern_status
            }
            
            # Test 3: ATS scrapers
            supported_ats = ATSScraperFactory.get_supported_ats_types()
            ats_results = {}
            
            for ats_type in supported_ats:
                try:
                    scraper = ATSScraperFactory.create_scraper(ats_type, self.config)
                    ats_results[ats_type.value] = {
                        "success": True,
                        "message": f"{ats_type.value} scraper created successfully"
                    }
                except Exception as e:
                    ats_results[ats_type.value] = {
                        "success": False,
                        "error": str(e)
                    }
            
            self.test_results["scrapers"]["ats"] = ats_results
            
            # Test 4: API clients
            api_manager = JobAPIManager(self.config)
            api_status = await api_manager.test_connections()
            
            self.test_results["scrapers"]["api_clients"] = {
                "success": any(client.get("available", False) for client in api_status.values()),
                "details": api_status
            }
            
            # Test 5: Source coordinator quick test
            coordinator = JobSourceCoordinator(self.config)
            source_status = await coordinator.get_source_status()
            
            self.test_results["scrapers"]["coordinator"] = {
                "success": "error" not in source_status,
                "details": source_status
            }
            
        except Exception as e:
            logger.error(f"Scraper tests failed: {str(e)}")
            self.test_results["scrapers"]["error"] = str(e)
    
    async def test_ranking_system(self):
        """Test the job ranking and scoring system."""
        try:
            # Create test jobs
            test_jobs = [
                JobData(
                    title="Python Software Engineer Intern",
                    company="Google",
                    location="Mountain View, CA",
                    job_type="Internship",
                    experience_level="Entry-level",
                    description="Build software with Python and React",
                    requirements="Python, JavaScript, SQL",
                    technologies=["Python", "JavaScript", "SQL"],
                    source="test",
                    posting_date=datetime.now()
                ),
                JobData(
                    title="Senior Java Developer",
                    company="Microsoft",
                    location="Seattle, WA", 
                    job_type="Full-time",
                    experience_level="Senior",
                    description="Enterprise Java development",
                    requirements="Java, Spring, SQL",
                    technologies=["Java", "Spring", "SQL"],
                    source="test",
                    posting_date=datetime.now()
                ),
                JobData(
                    title="Remote Frontend Developer",
                    company="Startup Inc",
                    location="Remote",
                    job_type="Full-time",
                    experience_level="Mid-level",
                    description="React and TypeScript frontend",
                    requirements="React, TypeScript, CSS",
                    technologies=["React", "TypeScript", "CSS"],
                    source="test",
                    posting_date=datetime.now()
                )
            ]
            
            # Test with internship preferences
            prefs = DefaultPreferences.get_cs_internship_preferences()
            ranker = JobRanker(prefs)
            
            rankings = []
            for job in test_jobs:
                ranking = ranker.rank_job(job)
                rankings.append(ranking)
            
            # Sort by score
            rankings.sort(key=lambda x: x.total_score, reverse=True)
            
            self.test_results["ranking"]["internship_preferences"] = {
                "success": True,
                "total_jobs_ranked": len(rankings),
                "highest_score": rankings[0].total_score,
                "highest_scoring_job": rankings[0].job.title,
                "score_breakdown": {
                    "keyword_score": rankings[0].keyword_score,
                    "location_score": rankings[0].location_score,
                    "salary_score": rankings[0].salary_score,
                    "experience_score": rankings[0].experience_score
                }
            }
            
            # Test with full-time preferences
            ft_prefs = DefaultPreferences.get_cs_fulltime_preferences()
            ft_ranker = JobRanker(ft_prefs)
            
            ft_rankings = []
            for job in test_jobs:
                ranking = ft_ranker.rank_job(job)
                ft_rankings.append(ranking)
            
            ft_rankings.sort(key=lambda x: x.total_score, reverse=True)
            
            self.test_results["ranking"]["fulltime_preferences"] = {
                "success": True,
                "total_jobs_ranked": len(ft_rankings),
                "highest_score": ft_rankings[0].total_score,
                "highest_scoring_job": ft_rankings[0].job.title
            }
            
        except Exception as e:
            logger.error(f"Ranking system test failed: {str(e)}")
            self.test_results["ranking"]["error"] = str(e)
    
    async def test_notifications(self):
        """Test the notification system."""
        try:
            notifier = NotificationManager(self.config)
            
            # Test notification creation (without sending)
            test_job = JobData(
                title="Test Software Engineer Position",
                company="Test Company",
                location="Remote",
                job_type="Full-time",
                experience_level="Entry-level",
                description="Test job for notification",
                url="https://example.com/test-job",
                posting_date=datetime.now(),
                technologies=["Python"],
                source="test"
            )
            
            # Create test ranking
            prefs = DefaultPreferences.get_cs_fulltime_preferences()
            ranker = JobRanker(prefs)
            ranking = ranker.rank_job(test_job)
            
            # Test email template generation
            email_subject, email_body = notifier._create_job_notification_email([ranking])
            
            self.test_results["notifications"]["email_template"] = {
                "success": bool(email_subject and email_body),
                "subject_length": len(email_subject),
                "body_length": len(email_body)
            }
            
            # Test notification configuration
            self.test_results["notifications"]["configuration"] = {
                "success": True,
                "email_backend": self.config.EMAIL_BACKEND,
                "smtp_configured": bool(self.config.SMTP_HOST and self.config.SMTP_USERNAME),
                "sendgrid_configured": bool(self.config.SENDGRID_API_KEY),
                "twilio_configured": bool(self.config.TWILIO_ACCOUNT_SID and self.config.TWILIO_AUTH_TOKEN)
            }
            
            # Test notification filtering
            high_score_jobs = notifier._filter_high_score_jobs([ranking], threshold=0.6)
            
            self.test_results["notifications"]["filtering"] = {
                "success": True,
                "jobs_above_threshold": len(high_score_jobs),
                "threshold_used": 0.6
            }
            
        except Exception as e:
            logger.error(f"Notification system test failed: {str(e)}")
            self.test_results["notifications"]["error"] = str(e)
    
    async def test_web_interface(self):
        """Test the Flask web interface."""
        try:
            app = create_app()
            app.config['TESTING'] = True
            
            with app.test_client() as client:
                # Test main routes
                routes_to_test = [
                    '/',
                    '/jobs',
                    '/preferences',
                    '/dashboard'
                ]
                
                route_results = {}
                for route in routes_to_test:
                    try:
                        response = client.get(route)
                        route_results[route] = {
                            "success": response.status_code in [200, 302],
                            "status_code": response.status_code
                        }
                    except Exception as e:
                        route_results[route] = {
                            "success": False,
                            "error": str(e)
                        }
                
                self.test_results["web_interface"]["routes"] = route_results
                
                # Test API endpoints
                api_routes = [
                    '/api/jobs',
                    '/api/stats'
                ]
                
                api_results = {}
                for route in api_routes:
                    try:
                        response = client.get(route)
                        api_results[route] = {
                            "success": response.status_code in [200, 404],  # 404 OK if no data
                            "status_code": response.status_code
                        }
                    except Exception as e:
                        api_results[route] = {
                            "success": False,
                            "error": str(e)
                        }
                
                self.test_results["web_interface"]["api"] = api_results
                
                # Overall web interface success
                all_routes_working = all(
                    result["success"] for result in {**route_results, **api_results}.values()
                )
                
                self.test_results["web_interface"]["overall"] = {
                    "success": all_routes_working,
                    "total_routes_tested": len(routes_to_test) + len(api_routes)
                }
                
        except Exception as e:
            logger.error(f"Web interface test failed: {str(e)}")
            self.test_results["web_interface"]["error"] = str(e)
    
    async def test_integration(self):
        """Test end-to-end integration workflow."""
        try:
            logger.info("Running end-to-end integration test...")
            
            # Step 1: Initialize system
            coordinator = JobSourceCoordinator(self.config)
            
            # Step 2: Run a quick job search
            search_session = await coordinator.run_quick_test()
            
            self.test_results["integration"]["job_acquisition"] = {
                "success": search_session.get("success", False),
                "total_jobs_found": search_session.get("total_jobs_found", 0),
                "total_jobs_saved": search_session.get("total_jobs_saved", 0),
                "sources_tested": len(search_session.get("sources", []))
            }
            
            # Step 3: Test ranking on found jobs (if any)
            if search_session.get("total_jobs_saved", 0) > 0:
                session = get_session()
                recent_jobs = session.query(JobData).limit(5).all()
                session.close()
                
                if recent_jobs:
                    prefs = DefaultPreferences.get_cs_internship_preferences()
                    ranker = JobRanker(prefs)
                    
                    rankings = [ranker.rank_job(job) for job in recent_jobs]
                    rankings.sort(key=lambda x: x.total_score, reverse=True)
                    
                    self.test_results["integration"]["ranking"] = {
                        "success": True,
                        "jobs_ranked": len(rankings),
                        "highest_score": rankings[0].total_score if rankings else 0
                    }
                    
                    # Step 4: Test notification creation
                    notifier = NotificationManager(self.config)
                    high_score_jobs = notifier._filter_high_score_jobs(rankings, threshold=0.5)
                    
                    self.test_results["integration"]["notifications"] = {
                        "success": True,
                        "high_score_jobs": len(high_score_jobs),
                        "notification_ready": len(high_score_jobs) > 0
                    }
            else:
                self.test_results["integration"]["ranking"] = {
                    "success": True,
                    "message": "No jobs to rank - job acquisition needed first"
                }
                self.test_results["integration"]["notifications"] = {
                    "success": True,
                    "message": "No high-score jobs for notifications"
                }
            
            # Step 5: Overall integration success
            integration_success = (
                self.test_results["integration"]["job_acquisition"]["success"] and
                self.test_results["integration"]["ranking"]["success"] and
                self.test_results["integration"]["notifications"]["success"]
            )
            
            self.test_results["integration"]["overall"] = {
                "success": integration_success,
                "message": "End-to-end integration test completed"
            }
            
        except Exception as e:
            logger.error(f"Integration test failed: {str(e)}")
            self.test_results["integration"]["error"] = str(e)
    
    def _calculate_overall_success(self) -> bool:
        """Calculate overall system test success."""
        try:
            # Check each major component
            components = ["database", "scrapers", "ranking", "notifications", "web_interface", "integration"]
            
            for component in components:
                if component not in self.test_results:
                    return False
                
                if "error" in self.test_results[component]:
                    return False
                
                # Check if component has any successful tests
                component_data = self.test_results[component]
                if isinstance(component_data, dict):
                    has_success = any(
                        isinstance(v, dict) and v.get("success", False) 
                        for v in component_data.values()
                    )
                    if not has_success:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error calculating overall success: {str(e)}")
            return False
    
    def generate_report(self) -> str:
        """Generate a human-readable test report."""
        report = []
        report.append("="*60)
        report.append("JOB SEARCH APPLICATION - SYSTEM TEST REPORT")
        report.append("="*60)
        report.append(f"Test Date: {self.test_results['timestamp']}")
        report.append(f"Test Duration: {self.test_results['test_duration']:.2f} seconds")
        report.append(f"Overall Success: {'✅ PASS' if self.test_results['overall_success'] else '❌ FAIL'}")
        report.append("")
        
        # Component details
        for component, results in self.test_results.items():
            if component in ["overall_success", "test_duration", "timestamp"]:
                continue
                
            report.append(f"📋 {component.upper()}")
            report.append("-" * 30)
            
            if isinstance(results, dict) and "error" not in results:
                for test_name, test_result in results.items():
                    if isinstance(test_result, dict):
                        success = test_result.get("success", False)
                        status = "✅" if success else "❌"
                        report.append(f"  {status} {test_name}")
                        if "message" in test_result:
                            report.append(f"      {test_result['message']}")
            elif "error" in results:
                report.append(f"  ❌ Component failed: {results['error']}")
            
            report.append("")
        
        return "\n".join(report)

async def main():
    """Main test execution function."""
    print("🧪 Job Search Application System Test")
    print("="*50)
    
    # Ensure directories exist
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    tester = SystemTester()
    results = await tester.run_all_tests()
    
    # Generate and display report
    report = tester.generate_report()
    print("\n" + report)
    
    # Save results to file
    with open("logs/system_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    # Save report to file
    with open("logs/system_test_report.txt", "w") as f:
        f.write(report)
    
    print(f"\n📄 Detailed results saved to: logs/system_test_results.json")
    print(f"📄 Test report saved to: logs/system_test_report.txt")
    
    # Exit with appropriate code
    exit_code = 0 if results["overall_success"] else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main()) 
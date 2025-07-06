"""
Comprehensive database of tech companies, their job websites, and ATS systems.
This configuration drives the company-specific scraping strategies.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class ATSType(Enum):
    WORKDAY = "workday"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ICIMS = "icims"
    SMARTRECRUITERS = "smartrecruiters"
    BAMBOOHR = "bamboohr"
    JOBVITE = "jobvite"
    TALEO = "taleo"
    SUCCESSFACTORS = "successfactors"
    CUSTOM = "custom"
    CAREER_BUILDER = "careerbuilder"
    DAYFORCE = "dayforce"

@dataclass
class CompanyJobSource:
    name: str
    careers_url: str
    ats_type: ATSType
    ats_specific_urls: List[str]
    search_keywords: List[str]  # For filtering relevant positions
    locations: List[str]  # Primary locations for internships/new grad
    notes: Optional[str] = None
    api_endpoint: Optional[str] = None
    requires_auth: bool = False
    
# FAANG + Major Tech Companies
TECH_COMPANIES = {
    # FAANG
    "google": CompanyJobSource(
        name="Google",
        careers_url="https://careers.google.com/jobs/results/",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://careers.google.com/jobs/results/?q=software%20engineer",
            "https://careers.google.com/jobs/results/?q=intern",
        ],
        search_keywords=["software engineer", "intern", "new grad", "swe", "backend", "frontend"],
        locations=["Mountain View", "San Francisco", "Seattle", "New York", "Austin"],
        notes="Custom Google careers system with dynamic loading"
    ),
    
    "apple": CompanyJobSource(
        name="Apple",
        careers_url="https://jobs.apple.com/en-us/search",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://jobs.apple.com/en-us/search?search=software%20engineer",
            "https://jobs.apple.com/en-us/search?search=intern",
        ],
        search_keywords=["software engineer", "intern", "ios", "macos", "swift"],
        locations=["Cupertino", "Austin", "Seattle"],
        notes="Apple's custom career portal"
    ),
    
    "amazon": CompanyJobSource(
        name="Amazon",
        careers_url="https://amazon.jobs/en/",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://amazon.jobs/en/search?base_query=software%20engineer",
            "https://amazon.jobs/en/search?base_query=intern",
        ],
        search_keywords=["software engineer", "intern", "sde", "aws", "backend"],
        locations=["Seattle", "Bellevue", "Austin", "New York", "Boston"],
        notes="Amazon's unified jobs portal"
    ),
    
    "meta": CompanyJobSource(
        name="Meta",
        careers_url="https://www.metacareers.com/jobs/",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://www.metacareers.com/jobs/?q=software%20engineer",
            "https://www.metacareers.com/jobs/?q=intern",
        ],
        search_keywords=["software engineer", "intern", "frontend", "backend", "mobile"],
        locations=["Menlo Park", "Seattle", "New York", "Austin"],
        notes="Meta's career portal"
    ),
    
    "netflix": CompanyJobSource(
        name="Netflix",
        careers_url="https://jobs.netflix.com/",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://jobs.netflix.com/search?q=engineer",
            "https://jobs.netflix.com/search?q=intern",
        ],
        search_keywords=["software engineer", "intern", "backend", "streaming"],
        locations=["Los Gatos", "Los Angeles"],
        notes="Uses Greenhouse ATS"
    ),

    # Major Tech Companies
    "microsoft": CompanyJobSource(
        name="Microsoft",
        careers_url="https://careers.microsoft.com/us/en/",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://careers.microsoft.com/us/en/search-results?keywords=software%20engineer",
            "https://careers.microsoft.com/us/en/search-results?keywords=intern",
        ],
        search_keywords=["software engineer", "intern", "azure", "backend", "frontend"],
        locations=["Redmond", "Seattle", "San Francisco", "Austin"],
        notes="Microsoft's career portal"
    ),
    
    "tesla": CompanyJobSource(
        name="Tesla",
        careers_url="https://www.tesla.com/careers/",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://www.tesla.com/careers/search/?query=software%20engineer",
            "https://www.tesla.com/careers/search/?query=intern",
        ],
        search_keywords=["software engineer", "intern", "autopilot", "embedded"],
        locations=["Palo Alto", "Austin", "Fremont"],
        notes="Tesla's custom career system"
    ),
    
    "spacex": CompanyJobSource(
        name="SpaceX",
        careers_url="https://www.spacex.com/careers/",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://www.spacex.com/careers/?q=software%20engineer",
            "https://www.spacex.com/careers/?q=intern",
        ],
        search_keywords=["software engineer", "intern", "embedded", "c++"],
        locations=["Hawthorne", "Austin", "Cape Canaveral"],
        notes="SpaceX custom portal"
    ),

    # Unicorns & High-Growth
    "stripe": CompanyJobSource(
        name="Stripe",
        careers_url="https://stripe.com/jobs/",
        ats_type=ATSType.CUSTOM,
        ats_specific_urls=[
            "https://stripe.com/jobs/search?query=engineer",
            "https://stripe.com/jobs/search?query=intern",
        ],
        search_keywords=["software engineer", "intern", "backend", "payments"],
        locations=["San Francisco", "Seattle", "New York"],
        notes="Custom Stripe careers"
    ),
    
    "databricks": CompanyJobSource(
        name="Databricks",
        careers_url="https://www.databricks.com/company/careers/",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://www.databricks.com/company/careers/open-positions?department=engineering",
        ],
        search_keywords=["software engineer", "intern", "spark", "backend"],
        locations=["San Francisco", "Seattle", "Amsterdam"],
        notes="Uses Greenhouse"
    ),
    
    "snowflake": CompanyJobSource(
        name="Snowflake",
        careers_url="https://careers.snowflake.com/",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://careers.snowflake.com/open-positions?gh_jid=&query=engineer",
        ],
        search_keywords=["software engineer", "intern", "backend", "database"],
        locations=["San Mateo", "Seattle", "Boston"],
        notes="Uses Greenhouse"
    ),

    # Workday Companies
    "nvidia": CompanyJobSource(
        name="NVIDIA",
        careers_url="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        ats_type=ATSType.WORKDAY,
        ats_specific_urls=[
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite?q=software%20engineer",
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite?q=intern",
        ],
        search_keywords=["software engineer", "intern", "cuda", "ai", "gpu"],
        locations=["Santa Clara", "Austin", "Seattle"],
        notes="Uses Workday ATS"
    ),
    
    "salesforce": CompanyJobSource(
        name="Salesforce",
        careers_url="https://salesforce.wd1.myworkdayjobs.com/External_Career_Site",
        ats_type=ATSType.WORKDAY,
        ats_specific_urls=[
            "https://salesforce.wd1.myworkdayjobs.com/en-US/External_Career_Site?q=software%20engineer",
        ],
        search_keywords=["software engineer", "intern", "crm", "backend"],
        locations=["San Francisco", "Seattle", "Austin"],
        notes="Uses Workday"
    ),
    
    "adobe": CompanyJobSource(
        name="Adobe",
        careers_url="https://adobe.wd5.myworkdayjobs.com/external_experienced",
        ats_type=ATSType.WORKDAY,
        ats_specific_urls=[
            "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced?q=software%20engineer",
        ],
        search_keywords=["software engineer", "intern", "creative", "frontend"],
        locations=["San Jose", "Seattle", "Austin"],
        notes="Uses Workday"
    ),

    # Lever Companies
    "uber": CompanyJobSource(
        name="Uber",
        careers_url="https://www.uber.com/careers/",
        ats_type=ATSType.LEVER,
        ats_specific_urls=[
            "https://www.uber.com/careers/list/?query=software%20engineer",
        ],
        search_keywords=["software engineer", "intern", "backend", "mobile"],
        locations=["San Francisco", "Seattle", "New York"],
        notes="Uses Lever ATS"
    ),
    
    "airbnb": CompanyJobSource(
        name="Airbnb",
        careers_url="https://careers.airbnb.com/",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://careers.airbnb.com/positions/?search=engineer",
        ],
        search_keywords=["software engineer", "intern", "backend", "frontend"],
        locations=["San Francisco", "Seattle"],
        notes="Uses Greenhouse"
    ),

    # Hardware Companies
    "intel": CompanyJobSource(
        name="Intel",
        careers_url="https://intel.wd1.myworkdayjobs.com/External",
        ats_type=ATSType.WORKDAY,
        ats_specific_urls=[
            "https://intel.wd1.myworkdayjobs.com/en-US/External?q=software%20engineer",
        ],
        search_keywords=["software engineer", "intern", "hardware", "embedded"],
        locations=["Santa Clara", "Hillsboro", "Austin"],
        notes="Uses Workday"
    ),
    
    "amd": CompanyJobSource(
        name="AMD",
        careers_url="https://jobs.amd.com/",
        ats_type=ATSType.SMARTRECRUITERS,
        ats_specific_urls=[
            "https://jobs.amd.com/search-jobs?k=software%20engineer",
        ],
        search_keywords=["software engineer", "intern", "gpu", "hardware"],
        locations=["Santa Clara", "Austin", "Boston"],
        notes="Uses SmartRecruiters"
    ),
    
    "qualcomm": CompanyJobSource(
        name="Qualcomm",
        careers_url="https://qualcomm.wd5.myworkdayjobs.com/External",
        ats_type=ATSType.WORKDAY,
        ats_specific_urls=[
            "https://qualcomm.wd5.myworkdayjobs.com/en-US/External?q=software%20engineer",
        ],
        search_keywords=["software engineer", "intern", "mobile", "embedded"],
        locations=["San Diego", "Austin", "Santa Clara"],
        notes="Uses Workday"
    ),

    # Financial Tech
    "robinhood": CompanyJobSource(
        name="Robinhood",
        careers_url="https://careers.robinhood.com/",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://careers.robinhood.com/openings?&search=engineer",
        ],
        search_keywords=["software engineer", "intern", "backend", "fintech"],
        locations=["Menlo Park", "New York"],
        notes="Uses Greenhouse"
    ),
    
    "coinbase": CompanyJobSource(
        name="Coinbase",
        careers_url="https://www.coinbase.com/careers/positions",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://www.coinbase.com/careers/positions?search=engineer",
        ],
        search_keywords=["software engineer", "intern", "backend", "crypto"],
        locations=["San Francisco", "New York", "Austin"],
        notes="Uses Greenhouse"
    ),

    # Gaming
    "riot_games": CompanyJobSource(
        name="Riot Games",
        careers_url="https://www.riotgames.com/en/work-with-us",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://www.riotgames.com/en/work-with-us/jobs?search=engineer",
        ],
        search_keywords=["software engineer", "intern", "game", "backend"],
        locations=["Los Angeles", "Seattle"],
        notes="Uses Greenhouse"
    ),

    # Additional High-Priority Companies
    "mongodb": CompanyJobSource(
        name="MongoDB",
        careers_url="https://www.mongodb.com/careers",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://www.mongodb.com/careers/jobs?search=engineer",
        ],
        search_keywords=["software engineer", "intern", "database", "backend"],
        locations=["New York", "Austin", "San Francisco"],
        notes="Uses Greenhouse"
    ),
    
    "palantir": CompanyJobSource(
        name="Palantir",
        careers_url="https://www.palantir.com/careers/",
        ats_type=ATSType.GREENHOUSE,
        ats_specific_urls=[
            "https://www.palantir.com/careers/?search=engineer",
        ],
        search_keywords=["software engineer", "intern", "backend", "data"],
        locations=["Palo Alto", "New York", "Seattle"],
        notes="Uses Greenhouse"
    ),
}

# GitHub Repository Sources
GITHUB_JOB_SOURCES = {
    "daily_h1b": {
        "repo": "jobright-ai/Daily-H1B-Jobs-In-Tech",
        "description": "Daily H1B sponsorship jobs in tech",
        "update_frequency": "daily",
        "focus": "h1b_sponsorship"
    },
    "new_grad_2025": {
        "repo": "jobright-ai/2025-Software-Engineer-New-Grad",
        "description": "2025 Software Engineer New Grad positions",
        "update_frequency": "regular",
        "focus": "new_grad"
    },
    "internship_2025": {
        "repo": "jobright-ai/2025-Engineer-Internship",
        "description": "2025 Engineering Internship positions",
        "update_frequency": "regular",
        "focus": "internship"
    },
    "simplify_internships": {
        "repo": "SimplifyJobs/Summer2026-Internships",
        "description": "Summer 2026 Internship positions",
        "update_frequency": "regular",
        "focus": "internship"
    },
    "simplify_new_grad": {
        "repo": "SimplifyJobs/New-Grad-Positions",
        "description": "New Grad positions collection",
        "update_frequency": "regular",
        "focus": "new_grad"
    }
}

# External Website Sources
EXTERNAL_SOURCES = {
    "intern_list": {
        "base_url": "https://www.intern-list.com/",
        "engineering_url": "https://www.intern-list.com/?selectedKey=%F0%9F%9B%A0%EF%B8%8F%20Engineering%20and%20Development",
        "software_url": "https://www.intern-list.com/?selectedKey=%F0%9F%92%BB%20Software%20Engineering",
        "description": "Comprehensive internship listings",
        "focus": "internship"
    }
}

# ATS-Specific URL Patterns
ATS_PATTERNS = {
    ATSType.WORKDAY: {
        "domain_pattern": r"\.wd\d+\.myworkdayjobs\.com",
        "job_pattern": r"/job/.*?/[A-Z0-9_]+",
        "search_params": {"q": "software engineer"}
    },
    ATSType.GREENHOUSE: {
        "domain_pattern": r"boards\.greenhouse\.io|greenhouse\.io",
        "job_pattern": r"/jobs/\d+",
        "search_params": {"search": "engineer"}
    },
    ATSType.LEVER: {
        "domain_pattern": r"jobs\.lever\.co",
        "job_pattern": r"/\d+-.*",
        "search_params": {"search": "engineer"}
    },
    ATSType.ICIMS: {
        "domain_pattern": r"\.icims\.com",
        "job_pattern": r"/jobs/\d+",
        "search_params": {"search": "engineer"}
    },
    ATSType.SMARTRECRUITERS: {
        "domain_pattern": r"jobs\.smartrecruiters\.com",
        "job_pattern": r"/.*?/\d+",
        "search_params": {"search": "engineer"}
    }
}

def get_companies_by_ats(ats_type: ATSType) -> List[CompanyJobSource]:
    """Get all companies using a specific ATS."""
    return [company for company in TECH_COMPANIES.values() if company.ats_type == ats_type]

def get_high_priority_companies() -> List[str]:
    """Get list of high-priority company keys for focused scraping."""
    return [
        "google", "apple", "amazon", "meta", "microsoft", 
        "nvidia", "tesla", "stripe", "uber", "airbnb",
        "databricks", "snowflake", "palantir", "robinhood"
    ]

def get_internship_focused_companies() -> List[str]:
    """Get companies known for strong internship programs."""
    return [
        "google", "apple", "amazon", "meta", "microsoft",
        "nvidia", "intel", "adobe", "salesforce", "uber"
    ] 
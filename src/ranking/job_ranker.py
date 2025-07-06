"""
Comprehensive Job Ranking Algorithm
Scores jobs based on multiple criteria with user-specific weights and preferences
"""

import re
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from fuzzywuzzy import fuzz
import numpy as np

from ..database.models import Job, UserProfile, JobRanking
from config import UserPreferences


@dataclass
class RankingResult:
    """Container for detailed ranking results"""
    job: Any
    overall_score: float
    keyword_score: float
    location_score: float
    salary_score: float
    experience_score: float
    company_score: float
    freshness_score: float
    explanation: Dict[str, str]
    job_type: Optional[str] = None
    total_score: float = 0.0  # alias for overall_score used in tests

    def __post_init__(self):
        # Maintain backward-compat property name used in tests
        self.total_score = self.overall_score


class JobRanker:
    """
    Advanced job ranking system with multiple scoring algorithms
    """
    
    def __init__(self, user_preferences: Optional["UserPreferences"] = None, *args, **kwargs):
        # Store default preferences for convenience
        self.default_preferences = user_preferences
        # Common technology synonyms for better matching
        self.tech_synonyms = {
            "javascript": ["js", "node.js", "nodejs", "react", "vue", "angular"],
            "python": ["django", "flask", "fastapi", "pandas", "numpy"],
            "java": ["spring", "springboot", "maven", "gradle"],
            "database": ["sql", "mysql", "postgresql", "mongodb", "redis"],
            "cloud": ["aws", "azure", "gcp", "docker", "kubernetes"],
            "frontend": ["html", "css", "react", "vue", "angular", "typescript"],
            "backend": ["api", "rest", "microservices", "server"],
        }
        
        # Location similarity mappings
        self.location_mappings = {
            "remote": ["work from home", "wfh", "telecommute", "distributed"],
            "san francisco": ["sf", "bay area", "silicon valley"],
            "new york": ["nyc", "manhattan", "brooklyn"],
            "los angeles": ["la", "hollywood", "santa monica"],
        }
        
        # Experience level mappings
        self.experience_mappings = {
            "entry": ["junior", "entry-level", "new grad", "graduate", "associate", "0-2 years"],
            "mid": ["mid-level", "intermediate", "2-5 years", "3-7 years"],
            "senior": ["senior", "sr", "lead", "5+ years", "7+ years"],
            "lead": ["lead", "principal", "architect", "manager", "director"]
        }
    
    def rank_job(self, job: Job, user_preferences: Optional["UserPreferences"] = None) -> RankingResult:
        """
        Calculate comprehensive ranking score for a job based on user preferences
        
        Args:
            job: Job object to rank
            user_preferences: User's preferences and weights
            
        Returns:
            RankingResult with detailed scores and explanations
        """
        # Resolve preferences
        if user_preferences is None:
            if self.default_preferences is None:
                raise ValueError("user_preferences must be provided")
            user_preferences = self.default_preferences

        # Calculate individual scores
        keyword_score = self._calculate_keyword_score(job, user_preferences)
        location_score = self._calculate_location_score(job, user_preferences)
        salary_score = self._calculate_salary_score(job, user_preferences)
        experience_score = self._calculate_experience_score(job, user_preferences)
        company_score = self._calculate_company_score(job, user_preferences)
        freshness_score = self._calculate_freshness_score(job)
        
        # Apply user-defined weights
        weights = user_preferences.ranking_weights
        overall_score = (
            keyword_score * weights.get("keywords", 0.3) +
            location_score * weights.get("location", 0.2) +
            salary_score * weights.get("salary", 0.2) +
            experience_score * weights.get("experience", 0.15) +
            company_score * weights.get("company", 0.1) +
            freshness_score * weights.get("freshness", 0.05)
        )
        
        # Ensure score is between 0 and 1
        overall_score = max(0.0, min(1.0, overall_score))
        
        # Generate explanations
        explanation = self._generate_explanation(
            job, user_preferences, keyword_score, location_score, 
            salary_score, experience_score, company_score, freshness_score
        )
        
        return RankingResult(
            job=job,
            overall_score=overall_score,
            keyword_score=keyword_score,
            location_score=location_score,
            salary_score=salary_score,
            experience_score=experience_score,
            company_score=company_score,
            freshness_score=freshness_score,
            explanation=explanation,
            job_type=job.job_type if hasattr(job, "job_type") else None
        )
    
    def _calculate_keyword_score(self, job: Job, preferences: UserPreferences) -> float:
        """
        Score based on keyword matching in title and description
        Uses fuzzy matching and synonym expansion
        """
        text_to_analyze = f"{job.title} {job.description or ''}".lower()
        
        # Required keywords (must have at least one)
        required_score = 0.0
        if preferences.required_keywords:
            required_matches = sum(
                1 for keyword in preferences.required_keywords
                if self._keyword_matches(keyword.lower(), text_to_analyze)
            )
            required_score = min(1.0, required_matches / len(preferences.required_keywords))
        else:
            required_score = 1.0  # No requirements = perfect score
        
        # Preferred keywords (weighted scoring)
        preferred_score = 0.0
        total_weight = 0.0
        
        for keyword in preferences.preferred_keywords:
            weight = preferences.keyword_weights.get(keyword.lower(), 1.0)
            total_weight += weight
            
            if self._keyword_matches(keyword.lower(), text_to_analyze):
                preferred_score += weight
        
        if total_weight > 0:
            preferred_score = preferred_score / total_weight
        
        # Excluded keywords (penalty)
        excluded_penalty = 0.0
        for keyword in preferences.excluded_keywords:
            if self._keyword_matches(keyword.lower(), text_to_analyze):
                excluded_penalty += 0.2  # 20% penalty per excluded keyword
        
        # Technology stack bonus
        tech_bonus = 0.0
        job_technologies = job.technologies or []
        for tech in preferences.preferred_technologies:
            if any(self._keyword_matches(tech.lower(), t.lower()) for t in job_technologies):
                tech_bonus += 0.1
        
        # Combine scores
        final_score = (required_score * 0.4 + preferred_score * 0.6) + tech_bonus - excluded_penalty
        return max(0.0, min(1.0, final_score))
    
    def _calculate_location_score(self, job: Job, preferences: UserPreferences) -> float:
        """Score based on location preferences and remote work options"""
        if not job.location:
            return 0.5  # Neutral score for missing location
        
        job_location = job.location.lower().strip()
        
        # Perfect score for remote if acceptable
        if preferences.remote_acceptable and job.remote_option:
            return 1.0
        
        # Check preferred locations
        max_location_score = 0.0
        for pref_location in preferences.preferred_locations:
            pref_location = pref_location.lower().strip()
            
            # Exact match
            if pref_location == job_location:
                max_location_score = 1.0
                break
            
            # Fuzzy matching
            similarity = fuzz.partial_ratio(pref_location, job_location) / 100.0
            if similarity > 0.8:
                max_location_score = max(max_location_score, similarity)
            
            # Check location mappings
            if pref_location in self.location_mappings:
                for synonym in self.location_mappings[pref_location]:
                    if synonym in job_location:
                        max_location_score = max(max_location_score, 0.9)
        
        return max_location_score
    
    def _calculate_salary_score(self, job: Job, preferences: UserPreferences) -> float:
        """Score based on salary requirements and preferences"""
        if not preferences.min_salary and not preferences.max_salary:
            return 1.0  # No salary preferences = perfect score
        
        # Handle missing salary data
        if not job.salary_min and not job.salary_max:
            return 0.3  # Neutral-low score for missing salary
        
        # Get job salary range
        job_min = job.salary_min or 0
        job_max = job.salary_max or job_min
        
        # Convert hourly to annual if needed
        if job.salary_type == "hourly":
            job_min *= 2080  # 40 hours * 52 weeks
            job_max *= 2080
        
        # Calculate overlap with preferred range
        user_min = preferences.min_salary or 0
        user_max = preferences.max_salary or float('inf')
        
        # Check if there's any overlap
        overlap_start = max(job_min, user_min)
        overlap_end = min(job_max, user_max)
        
        if overlap_start <= overlap_end:
            # Calculate percentage of job range that overlaps with user preference
            job_range = max(1, job_max - job_min)
            user_range = max(1, user_max - user_min)
            overlap_size = overlap_end - overlap_start
            
            score = overlap_size / min(job_range, user_range)
            
            # Bonus for job salary being above user minimum
            if job_min >= user_min:
                score += 0.2
            
            return min(1.0, score)
        else:
            # No overlap - check how close we are
            if job_max < user_min:
                # Job pays too little
                gap = user_min - job_max
                relative_gap = gap / user_min if user_min > 0 else 1.0
                return max(0.0, 1.0 - relative_gap)
            else:
                # Job pays too much (less common penalty)
                return 0.7
    
    def _calculate_experience_score(self, job: Job, preferences: UserPreferences) -> float:
        """Score based on experience level requirements"""
        if not job.experience_level or not preferences.experience_levels:
            return 0.7  # Neutral score for missing data
        
        job_exp = job.experience_level.lower()
        
        # Direct match
        for user_exp in preferences.experience_levels:
            if user_exp.lower() == job_exp:
                return 1.0
        
        # Check experience mappings
        for user_exp in preferences.experience_levels:
            if user_exp.lower() in self.experience_mappings:
                synonyms = self.experience_mappings[user_exp.lower()]
                for synonym in synonyms:
                    if synonym in job_exp or fuzz.partial_ratio(synonym, job_exp) > 80:
                        return 0.9
        
        # Partial match based on experience progression
        experience_hierarchy = ["entry", "mid", "senior", "lead"]
        
        user_levels = [exp.lower() for exp in preferences.experience_levels]
        job_level_idx = None
        
        for i, level in enumerate(experience_hierarchy):
            if level in job_exp:
                job_level_idx = i
                break
        
        if job_level_idx is not None:
            for user_exp in user_levels:
                if user_exp in experience_hierarchy:
                    user_idx = experience_hierarchy.index(user_exp)
                    distance = abs(job_level_idx - user_idx)
                    if distance <= 1:
                        return max(0.5, 1.0 - (distance * 0.3))
        
        return 0.3  # Low score for significant mismatch
    
    def _calculate_company_score(self, job: Job, preferences: UserPreferences) -> float:
        """Score based on company preferences and exclusions"""
        score = 0.7  # Base score
        
        # Check exclusions first
        if job.company and preferences.excluded_companies:
            for excluded in preferences.excluded_companies:
                if excluded.lower() in job.company.lower():
                    return 0.0  # Zero score for excluded companies
        
        # Check company size preferences
        if job.company_size and preferences.preferred_company_types:
            if job.company_size.lower() in [t.lower() for t in preferences.preferred_company_types]:
                score += 0.3
        
        return min(1.0, score)
    
    def _calculate_freshness_score(self, job: Job) -> float:
        """Score based on how recently the job was posted"""
        if not job.posted_date:
            return 0.5  # Neutral score for missing date
        
        now = datetime.now(timezone.utc)
        if job.posted_date.tzinfo is None:
            job_posted = job.posted_date.replace(tzinfo=timezone.utc)
        else:
            job_posted = job.posted_date
        
        days_old = (now - job_posted).days
        
        # Scoring based on age
        if days_old <= 1:
            return 1.0  # Posted today or yesterday
        elif days_old <= 7:
            return 0.9  # Posted within a week
        elif days_old <= 30:
            return 0.7  # Posted within a month
        elif days_old <= 60:
            return 0.5  # Posted within two months
        else:
            return 0.2  # Older posts
    
    def _keyword_matches(self, keyword: str, text: str) -> bool:
        """
        Check if a keyword matches text using multiple strategies
        """
        # Direct substring match
        if keyword in text:
            return True
        
        # Word boundary match
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
        
        # Check synonyms
        for category, synonyms in self.tech_synonyms.items():
            if keyword in synonyms or keyword == category:
                for synonym in synonyms + [category]:
                    if synonym in text or re.search(r'\b' + re.escape(synonym) + r'\b', text, re.IGNORECASE):
                        return True
        
        # Fuzzy matching for longer keywords
        if len(keyword) > 3:
            words = text.split()
            for word in words:
                if fuzz.ratio(keyword, word) > 85:
                    return True
        
        return False
    
    def _generate_explanation(self, job: Job, preferences: UserPreferences, 
                            keyword_score: float, location_score: float, 
                            salary_score: float, experience_score: float, 
                            company_score: float, freshness_score: float) -> Dict[str, str]:
        """Generate human-readable explanations for the ranking scores"""
        
        explanations = {}
        
        # Keyword explanation
        if keyword_score > 0.8:
            explanations["keywords"] = "Excellent match for required and preferred keywords"
        elif keyword_score > 0.6:
            explanations["keywords"] = "Good keyword match with some preferred technologies"
        elif keyword_score > 0.4:
            explanations["keywords"] = "Moderate keyword match, missing some preferred skills"
        else:
            explanations["keywords"] = "Poor keyword match or contains excluded terms"
        
        # Location explanation
        if location_score > 0.9:
            explanations["location"] = "Perfect location match or remote work available"
        elif location_score > 0.6:
            explanations["location"] = "Good location match in preferred area"
        elif location_score > 0.3:
            explanations["location"] = "Acceptable location but not ideal"
        else:
            explanations["location"] = "Location doesn't match preferences"
        
        # Salary explanation
        if salary_score > 0.8:
            explanations["salary"] = "Salary range aligns well with expectations"
        elif salary_score > 0.6:
            explanations["salary"] = "Salary partially meets requirements"
        elif salary_score > 0.3:
            explanations["salary"] = "Salary information missing or below expectations"
        else:
            explanations["salary"] = "Salary significantly below requirements"
        
        # Experience explanation
        if experience_score > 0.8:
            explanations["experience"] = "Experience requirements match your level perfectly"
        elif experience_score > 0.6:
            explanations["experience"] = "Experience requirements are close to your level"
        else:
            explanations["experience"] = "Experience requirements don't align well"
        
        # Company explanation
        if company_score == 0.0:
            explanations["company"] = "Company is in your exclusion list"
        elif company_score > 0.8:
            explanations["company"] = "Company type matches your preferences"
        else:
            explanations["company"] = "Neutral company rating"
        
        # Freshness explanation
        if freshness_score > 0.8:
            explanations["freshness"] = "Recently posted job (within a week)"
        elif freshness_score > 0.5:
            explanations["freshness"] = "Moderately fresh posting"
        else:
            explanations["freshness"] = "Older job posting"
        
        return explanations
    
    def batch_rank_jobs(self, jobs: List[Job], user_preferences: UserPreferences) -> List[Tuple[Job, RankingResult]]:
        """
        Rank multiple jobs efficiently
        
        Returns:
            List of (job, ranking_result) tuples sorted by overall score descending
        """
        results = []
        for job in jobs:
            ranking = self.rank_job(job, user_preferences)
            results.append((job, ranking))
        
        # Sort by overall score (highest first)
        results.sort(key=lambda x: x[1].overall_score, reverse=True)
        return results


# Utility functions for easy access
def rank_single_job(job: Job, user_preferences: UserPreferences) -> RankingResult:
    """Convenience function to rank a single job"""
    ranker = JobRanker()
    return ranker.rank_job(job, user_preferences)


def get_top_jobs(jobs: List[Job], user_preferences: UserPreferences, limit: int = 10) -> List[Tuple[Job, RankingResult]]:
    """Get top N ranked jobs"""
    ranker = JobRanker()
    ranked_jobs = ranker.batch_rank_jobs(jobs, user_preferences)
    return ranked_jobs[:limit]


# Backwards compatibility alias
RankingExplanation = RankingResult 
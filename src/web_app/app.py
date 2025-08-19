"""
Flask Web Application for Job Search Tool
Provides web interface for viewing jobs, managing preferences, and tracking applications
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_cors import CORS
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json

from ..database import init_database, get_db_session
from ..database.models import Job, UserProfile, JobRanking, JobApplication
from ..config.config import config, UserPreferences, DefaultPreferences
from ..ranking.job_ranker import JobRanker, get_top_jobs
from ..api_clients.indeed_client import JobAPIManager
from ..scrapers.base_scraper import CompanyWebsiteScraper
from ..notifications.notifier import NotificationManager

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['DEBUG'] = config.DEBUG

# Enable CORS for API endpoints
CORS(app)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
notification_manager = NotificationManager()
job_api_manager = JobAPIManager()
job_ranker = JobRanker()


@app.before_first_request
def initialize():
    """Initialize database and components"""
    init_database()
    logger.info("Job Search Web App initialized")


@app.route('/')
def index():
    """Home page with job search overview"""
    return render_template('index.html')


@app.route('/jobs')
def view_jobs():
    """View all jobs with filtering and ranking"""
    # Get query parameters
    user_id = request.args.get('user_id', 'default_user')
    keywords = request.args.get('keywords', '')
    location = request.args.get('location', '')
    job_type = request.args.get('job_type', '')
    min_score = float(request.args.get('min_score', 0.0))
    limit = int(request.args.get('limit', 50))
    
    try:
        with get_db_session() as session:
            # Get user preferences
            user_profile = session.query(UserProfile).filter_by(user_id=user_id).first()
            if not user_profile:
                # Create default user profile
                user_preferences = DefaultPreferences.get_cs_fulltime_preferences()
                user_profile = UserProfile(
                    user_id=user_id,
                    email=f"{user_id}@example.com",
                    search_preferences=user_preferences.__dict__,
                    ranking_weights=user_preferences.ranking_weights,
                    notification_preferences={
                        "email_notifications": user_preferences.email_notifications,
                        "sms_notifications": user_preferences.sms_notifications,
                        "notification_frequency": user_preferences.notification_frequency
                    }
                )
                session.add(user_profile)
                session.commit()
            
            # Build query
            query = session.query(Job).filter(Job.is_active == True)
            
            if keywords:
                query = query.filter(
                    Job.title.ilike(f'%{keywords}%') |
                    Job.description.ilike(f'%{keywords}%')
                )
            
            if location:
                query = query.filter(Job.location.ilike(f'%{location}%'))
            
            if job_type:
                query = query.filter(Job.job_type == job_type)
            
            # Get jobs and their rankings
            jobs = query.limit(limit).all()
            
            # Get rankings for these jobs
            job_rankings = {}
            for job in jobs:
                ranking = session.query(JobRanking).filter_by(
                    job_id=job.id, user_id=user_id
                ).first()
                if ranking:
                    job_rankings[job.id] = ranking.overall_score
            
            # Filter by minimum score
            filtered_jobs = [
                job for job in jobs 
                if job_rankings.get(job.id, 0) >= min_score
            ]
            
            # Sort by ranking score
            filtered_jobs.sort(
                key=lambda j: job_rankings.get(j.id, 0), 
                reverse=True
            )
            
            # Prepare job data for template
            jobs_data = []
            for job in filtered_jobs:
                job_dict = job.to_dict()
                job_dict['ranking_score'] = job_rankings.get(job.id, 0)
                jobs_data.append(job_dict)
            
            return render_template('jobs.html', 
                                 jobs=jobs_data,
                                 filters={
                                     'keywords': keywords,
                                     'location': location,
                                     'job_type': job_type,
                                     'min_score': min_score
                                 })
    
    except Exception as e:
        logger.error(f"Error viewing jobs: {e}")
        flash(f"Error loading jobs: {str(e)}", 'error')
        return render_template('jobs.html', jobs=[])


@app.route('/preferences')
def view_preferences():
    """View and edit user preferences"""
    user_id = request.args.get('user_id', 'default_user')
    
    try:
        with get_db_session() as session:
            user_profile = session.query(UserProfile).filter_by(user_id=user_id).first()
            
            if not user_profile:
                # Create with default preferences
                default_prefs = DefaultPreferences.get_cs_fulltime_preferences()
                preferences = default_prefs.__dict__
            else:
                preferences = user_profile.search_preferences
            
            return render_template('preferences.html', 
                                 user_id=user_id,
                                 preferences=preferences)
    
    except Exception as e:
        logger.error(f"Error loading preferences: {e}")
        flash(f"Error loading preferences: {str(e)}", 'error')
        return render_template('preferences.html', user_id=user_id, preferences={})


@app.route('/preferences', methods=['POST'])
def update_preferences():
    """Update user preferences"""
    user_id = request.form.get('user_id')
    
    try:
        # Parse form data
        preferences_data = {
            'required_keywords': request.form.get('required_keywords', '').split(','),
            'preferred_keywords': request.form.get('preferred_keywords', '').split(','),
            'excluded_keywords': request.form.get('excluded_keywords', '').split(','),
            'preferred_locations': request.form.get('preferred_locations', '').split(','),
            'remote_acceptable': bool(request.form.get('remote_acceptable')),
            'min_salary': int(request.form.get('min_salary', 0)) or None,
            'max_salary': int(request.form.get('max_salary', 0)) or None,
            'experience_levels': request.form.getlist('experience_levels'),
            'job_types': request.form.getlist('job_types'),
            'email_notifications': bool(request.form.get('email_notifications')),
            'sms_notifications': bool(request.form.get('sms_notifications')),
        }
        
        # Clean up empty strings
        for key, value in preferences_data.items():
            if isinstance(value, list):
                preferences_data[key] = [item.strip() for item in value if item.strip()]
        
        with get_db_session() as session:
            user_profile = session.query(UserProfile).filter_by(user_id=user_id).first()
            
            if not user_profile:
                user_profile = UserProfile(
                    user_id=user_id,
                    email=f"{user_id}@example.com",
                    search_preferences=preferences_data,
                    ranking_weights={
                        "keywords": 0.30,
                        "location": 0.20,
                        "salary": 0.25,
                        "experience": 0.15,
                        "company": 0.05,
                        "freshness": 0.05
                    },
                    notification_preferences={
                        "email_notifications": preferences_data.get('email_notifications', False),
                        "sms_notifications": preferences_data.get('sms_notifications', False),
                        "notification_frequency": "daily"
                    }
                )
                session.add(user_profile)
            else:
                user_profile.search_preferences = preferences_data
                user_profile.notification_preferences.update({
                    "email_notifications": preferences_data.get('email_notifications', False),
                    "sms_notifications": preferences_data.get('sms_notifications', False)
                })
            
            session.commit()
            flash('Preferences updated successfully!', 'success')
    
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        flash(f"Error updating preferences: {str(e)}", 'error')
    
    return redirect(url_for('view_preferences', user_id=user_id))


@app.route('/search', methods=['POST'])
def search_jobs():
    """Search for new jobs using APIs and scrapers"""
    user_id = request.form.get('user_id', 'default_user')
    keywords = request.form.get('keywords', '')
    location = request.form.get('location', '')
    
    if not keywords:
        flash('Keywords are required for job search', 'error')
        return redirect(url_for('index'))
    
    try:
        # Search using API clients
        new_jobs = job_api_manager.search_all_sources(
            keywords=keywords,
            location=location,
            limit_per_source=25
        )
        
        # Save jobs to database
        jobs_saved = 0
        with get_db_session() as session:
            for job_data in new_jobs:
                # Check for duplicates
                job_hash = Job().generate_hash()  # Would need the actual data
                existing = session.query(Job).filter_by(job_hash=job_hash).first()
                
                if not existing:
                    job = Job(**job_data.to_dict())
                    job.job_hash = job.generate_hash()
                    session.add(job)
                    jobs_saved += 1
            
            session.commit()
        
        flash(f'Found {len(new_jobs)} jobs, saved {jobs_saved} new ones!', 'success')
        
    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        flash(f"Error searching jobs: {str(e)}", 'error')
    
    return redirect(url_for('view_jobs', user_id=user_id))


@app.route('/rank_jobs', methods=['POST'])
def rank_jobs():
    """Rank all jobs for a user"""
    user_id = request.form.get('user_id', 'default_user')
    
    try:
        with get_db_session() as session:
            # Get user preferences
            user_profile = session.query(UserProfile).filter_by(user_id=user_id).first()
            if not user_profile:
                flash('User profile not found', 'error')
                return redirect(url_for('index'))
            
            # Convert to UserPreferences object
            prefs_dict = user_profile.search_preferences
            user_preferences = UserPreferences(
                required_keywords=prefs_dict.get('required_keywords', []),
                preferred_keywords=prefs_dict.get('preferred_keywords', []),
                excluded_keywords=prefs_dict.get('excluded_keywords', []),
                keyword_weights=prefs_dict.get('keyword_weights', {}),
                preferred_locations=prefs_dict.get('preferred_locations', []),
                remote_acceptable=prefs_dict.get('remote_acceptable', True),
                max_commute_distance=prefs_dict.get('max_commute_distance', 30),
                min_salary=prefs_dict.get('min_salary'),
                max_salary=prefs_dict.get('max_salary'),
                salary_importance=prefs_dict.get('salary_importance', 0.8),
                experience_levels=prefs_dict.get('experience_levels', ['entry']),
                preferred_company_types=prefs_dict.get('preferred_company_types', []),
                excluded_companies=prefs_dict.get('excluded_companies', []),
                required_technologies=prefs_dict.get('required_technologies', []),
                preferred_technologies=prefs_dict.get('preferred_technologies', []),
                job_types=prefs_dict.get('job_types', ['full-time']),
                email_notifications=user_profile.notification_preferences.get('email_notifications', True),
                sms_notifications=user_profile.notification_preferences.get('sms_notifications', False),
                notification_frequency=user_profile.notification_preferences.get('notification_frequency', 'daily'),
                ranking_weights=user_profile.ranking_weights
            )
            
            # Get all active jobs
            jobs = session.query(Job).filter(Job.is_active == True).all()
            
            # Rank jobs
            rankings_updated = 0
            for job in jobs:
                ranking_result = job_ranker.rank_job(job, user_preferences)
                
                # Update or create ranking
                existing_ranking = session.query(JobRanking).filter_by(
                    job_id=job.id, user_id=user_id
                ).first()
                
                if existing_ranking:
                    existing_ranking.overall_score = ranking_result.overall_score
                    existing_ranking.keyword_score = ranking_result.keyword_score
                    existing_ranking.location_score = ranking_result.location_score
                    existing_ranking.salary_score = ranking_result.salary_score
                    existing_ranking.experience_score = ranking_result.experience_score
                    existing_ranking.company_score = ranking_result.company_score
                    existing_ranking.freshness_score = ranking_result.freshness_score
                    existing_ranking.calculated_at = datetime.now(timezone.utc)
                else:
                    new_ranking = JobRanking(
                        job_id=job.id,
                        user_id=user_id,
                        overall_score=ranking_result.overall_score,
                        keyword_score=ranking_result.keyword_score,
                        location_score=ranking_result.location_score,
                        salary_score=ranking_result.salary_score,
                        experience_score=ranking_result.experience_score,
                        company_score=ranking_result.company_score,
                        freshness_score=ranking_result.freshness_score
                    )
                    session.add(new_ranking)
                
                rankings_updated += 1
            
            session.commit()
            flash(f'Updated rankings for {rankings_updated} jobs!', 'success')
    
    except Exception as e:
        logger.error(f"Error ranking jobs: {e}")
        flash(f"Error ranking jobs: {str(e)}", 'error')
    
    return redirect(url_for('view_jobs', user_id=user_id))


@app.route('/job/<int:job_id>')
def view_job_detail(job_id: int):
    """View detailed information about a specific job"""
    user_id = request.args.get('user_id', 'default_user')
    
    try:
        with get_db_session() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            
            if not job:
                flash('Job not found', 'error')
                return redirect(url_for('view_jobs'))
            
            # Get ranking for this job
            ranking = session.query(JobRanking).filter_by(
                job_id=job_id, user_id=user_id
            ).first()
            
            # Get application status
            application = session.query(JobApplication).filter_by(
                job_id=job_id, user_id=user_id
            ).first()
            
            return render_template('job_detail.html',
                                 job=job,
                                 ranking=ranking,
                                 application=application,
                                 user_id=user_id)
    
    except Exception as e:
        logger.error(f"Error viewing job detail: {e}")
        flash(f"Error loading job details: {str(e)}", 'error')
        return redirect(url_for('view_jobs'))


@app.route('/save_job/<int:job_id>', methods=['POST'])
def save_job(job_id: int):
    """Save a job for later review"""
    user_id = request.form.get('user_id', 'default_user')
    
    try:
        with get_db_session() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            
            if job:
                job.is_saved = True
                session.commit()
                flash('Job saved successfully!', 'success')
            else:
                flash('Job not found', 'error')
    
    except Exception as e:
        logger.error(f"Error saving job: {e}")
        flash(f"Error saving job: {str(e)}", 'error')
    
    return redirect(url_for('view_job_detail', job_id=job_id, user_id=user_id))


@app.route('/apply_job/<int:job_id>', methods=['POST'])
def apply_job(job_id: int):
    """Mark a job as applied"""
    user_id = request.form.get('user_id', 'default_user')
    notes = request.form.get('notes', '')
    
    try:
        with get_db_session() as session:
            # Check if application already exists
            existing_app = session.query(JobApplication).filter_by(
                job_id=job_id, user_id=user_id
            ).first()
            
            if existing_app:
                existing_app.status = 'applied'
                existing_app.applied_date = datetime.now(timezone.utc)
                existing_app.notes = notes
            else:
                application = JobApplication(
                    job_id=job_id,
                    user_id=user_id,
                    status='applied',
                    applied_date=datetime.now(timezone.utc),
                    notes=notes
                )
                session.add(application)
            
            session.commit()
            flash('Application status updated!', 'success')
    
    except Exception as e:
        logger.error(f"Error updating application: {e}")
        flash(f"Error updating application: {str(e)}", 'error')
    
    return redirect(url_for('view_job_detail', job_id=job_id, user_id=user_id))


@app.route('/applications')
def view_applications():
    """View all job applications for a user"""
    user_id = request.args.get('user_id', 'default_user')
    status_filter = request.args.get('status', '')
    
    try:
        with get_db_session() as session:
            query = session.query(JobApplication, Job).join(Job).filter(
                JobApplication.user_id == user_id
            )
            
            if status_filter:
                query = query.filter(JobApplication.status == status_filter)
            
            applications = query.order_by(JobApplication.created_at.desc()).all()
            
            return render_template('applications.html',
                                 applications=applications,
                                 status_filter=status_filter,
                                 user_id=user_id)
    
    except Exception as e:
        logger.error(f"Error viewing applications: {e}")
        flash(f"Error loading applications: {str(e)}", 'error')
        return render_template('applications.html', applications=[], user_id=user_id)


@app.route('/dashboard')
def dashboard():
    """User dashboard with statistics and quick actions"""
    user_id = request.args.get('user_id', 'default_user')
    
    try:
        with get_db_session() as session:
            # Get statistics
            total_jobs = session.query(Job).filter(Job.is_active == True).count()
            saved_jobs = session.query(Job).filter(
                Job.is_active == True, Job.is_saved == True
            ).count()
            
            applications_count = session.query(JobApplication).filter(
                JobApplication.user_id == user_id
            ).count()
            
            # Get top ranked jobs
            top_rankings = session.query(JobRanking, Job).join(Job).filter(
                JobRanking.user_id == user_id,
                Job.is_active == True
            ).order_by(JobRanking.overall_score.desc()).limit(5).all()
            
            # Get notification stats
            notification_stats = notification_manager.get_notification_stats(user_id)
            
            return render_template('dashboard.html',
                                 user_id=user_id,
                                 stats={
                                     'total_jobs': total_jobs,
                                     'saved_jobs': saved_jobs,
                                     'applications': applications_count
                                 },
                                 top_jobs=top_rankings,
                                 notification_stats=notification_stats)
    
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash(f"Error loading dashboard: {str(e)}", 'error')
        return render_template('dashboard.html', user_id=user_id, stats={}, top_jobs=[])


# API Endpoints for AJAX requests
@app.route('/api/search_status')
def api_search_status():
    """Get status of ongoing job searches"""
    return jsonify({
        "available_sources": job_api_manager.get_available_sources(),
        "source_stats": job_api_manager.get_source_stats(),
        "notification_available": notification_manager.is_available()
    })


@app.route('/api/quick_rank/<int:job_id>')
def api_quick_rank(job_id: int):
    """Get quick ranking for a specific job"""
    user_id = request.args.get('user_id', 'default_user')
    
    try:
        with get_db_session() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            user_profile = session.query(UserProfile).filter_by(user_id=user_id).first()
            
            if not job or not user_profile:
                return jsonify({"error": "Job or user not found"}), 404
            
            # Quick ranking calculation would go here
            # For now, return existing ranking if available
            ranking = session.query(JobRanking).filter_by(
                job_id=job_id, user_id=user_id
            ).first()
            
            if ranking:
                return jsonify(ranking.to_dict())
            else:
                return jsonify({"error": "No ranking available"}), 404
    
    except Exception as e:
        logger.error(f"Error getting quick rank: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=config.DEBUG, host='0.0.0.0', port=5000) 
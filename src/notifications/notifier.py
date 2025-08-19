"""
Comprehensive notification system for job alerts
Supports email (SMTP/SendGrid) and SMS (Twilio) with templates and delivery tracking
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Union
from datetime import datetime, timezone
from abc import ABC, abstractmethod
import json

import sendgrid
from sendgrid.helpers.mail import Mail
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioException

from ..config.config import config, UserPreferences
from ..database.models import Job, JobRanking, NotificationLog
from ..database import get_db_session
from ..ranking.job_ranker import RankingResult

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Custom exception for notification errors"""
    pass


class BaseNotifier(ABC):
    """Abstract base class for all notification providers"""
    
    @abstractmethod
    def send(self, recipient: str, subject: str, message: str, **kwargs) -> bool:
        """Send notification to recipient"""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the notifier is properly configured"""
        pass


class EmailNotifier(BaseNotifier):
    """Email notification using SMTP or SendGrid"""
    
    def __init__(self, backend: str = None):
        self.backend = backend or config.EMAIL_BACKEND
        
        if self.backend == "sendgrid":
            self._init_sendgrid()
        elif self.backend == "smtp":
            self._init_smtp()
        else:
            raise ValueError(f"Unsupported email backend: {self.backend}")
    
    def _init_sendgrid(self):
        """Initialize SendGrid client"""
        if not config.SENDGRID_API_KEY:
            raise NotificationError("SendGrid API key not configured")
        self.sendgrid_client = sendgrid.SendGridAPIClient(api_key=config.SENDGRID_API_KEY)
    
    def _init_smtp(self):
        """Initialize SMTP configuration"""
        required_configs = [config.SMTP_HOST, config.SMTP_USERNAME, config.SMTP_PASSWORD]
        if not all(required_configs):
            raise NotificationError("SMTP configuration incomplete")
    
    def send(self, recipient: str, subject: str, message: str, 
             html_message: str = None, attachments: List = None) -> bool:
        """
        Send email notification
        
        Args:
            recipient: Email address
            subject: Email subject
            message: Plain text message
            html_message: HTML version of message
            attachments: List of file paths to attach
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if self.backend == "sendgrid":
                return self._send_sendgrid(recipient, subject, message, html_message)
            else:
                return self._send_smtp(recipient, subject, message, html_message, attachments)
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return False
    
    def _send_sendgrid(self, recipient: str, subject: str, message: str, html_message: str = None) -> bool:
        """Send email using SendGrid"""
        try:
            mail = Mail(
                from_email=config.FROM_EMAIL,
                to_emails=recipient,
                subject=subject,
                plain_text_content=message,
                html_content=html_message
            )
            
            response = self.sendgrid_client.send(mail)
            return response.status_code < 400
            
        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return False
    
    def _send_smtp(self, recipient: str, subject: str, message: str, 
                   html_message: str = None, attachments: List = None) -> bool:
        """Send email using SMTP"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = config.FROM_EMAIL
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Add plain text part
            msg.attach(MIMEText(message, 'plain'))
            
            # Add HTML part if provided
            if html_message:
                msg.attach(MIMEText(html_message, 'html'))
            
            # Add attachments if provided
            if attachments:
                for file_path in attachments:
                    try:
                        with open(file_path, "rb") as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {file_path.split("/")[-1]}'
                        )
                        msg.attach(part)
                    except Exception as e:
                        logger.warning(f"Failed to attach file {file_path}: {e}")
            
            # Send email
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return False
    
    def is_configured(self) -> bool:
        """Check if email notification is properly configured"""
        if self.backend == "sendgrid":
            return bool(config.SENDGRID_API_KEY)
        else:
            return all([config.SMTP_HOST, config.SMTP_USERNAME, config.SMTP_PASSWORD])


class SMSNotifier(BaseNotifier):
    """SMS notification using Twilio"""
    
    def __init__(self):
        if not self.is_configured():
            raise NotificationError("Twilio SMS configuration incomplete")
        
        self.client = TwilioClient(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        self.from_phone = config.TWILIO_PHONE_NUMBER
    
    def send(self, recipient: str, subject: str, message: str, **kwargs) -> bool:
        """
        Send SMS notification
        
        Args:
            recipient: Phone number in E.164 format
            subject: Not used for SMS (included for interface compatibility)
            message: SMS message text
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Truncate message if too long for SMS
            if len(message) > 1600:
                message = message[:1590] + "... [truncated]"
            
            message_obj = self.client.messages.create(
                body=message,
                from_=self.from_phone,
                to=recipient
            )
            
            logger.info(f"SMS sent to {recipient}: {message_obj.sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Twilio SMS error: {e}")
            return False
        except Exception as e:
            logger.error(f"SMS error: {e}")
            return False
    
    def is_configured(self) -> bool:
        """Check if SMS notification is properly configured"""
        return all([
            config.TWILIO_ACCOUNT_SID,
            config.TWILIO_AUTH_TOKEN,
            config.TWILIO_PHONE_NUMBER
        ])


class NotificationTemplates:
    """Email and SMS templates for different notification types"""
    
    @staticmethod
    def format_job_alert_email(jobs: List[tuple], user_preferences: UserPreferences) -> tuple:
        """
        Format job alert email
        
        Args:
            jobs: List of (Job, RankingResult) tuples
            user_preferences: User preferences
            
        Returns:
            Tuple of (subject, plain_text, html_text)
        """
        if not jobs:
            return "No new jobs found", "No new jobs match your criteria.", "<p>No new jobs match your criteria.</p>"
        
        subject = f"🚀 {len(jobs)} New Job Alert{'s' if len(jobs) > 1 else ''} - Job Search App"
        
        # Plain text version
        plain_text = f"""
Hello!

We found {len(jobs)} new job{'s' if len(jobs) > 1 else ''} that match your preferences:

"""
        
        # HTML version
        html_text = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
        .job {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; }}
        .job-title {{ font-size: 18px; font-weight: bold; color: #2196F3; }}
        .company {{ font-size: 16px; color: #666; }}
        .location {{ color: #888; }}
        .score {{ background-color: #4CAF50; color: white; padding: 3px 8px; border-radius: 3px; font-size: 12px; }}
        .salary {{ color: #4CAF50; font-weight: bold; }}
        .technologies {{ margin: 10px 0; }}
        .tech-tag {{ background-color: #e1f5fe; color: #0277bd; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-right: 5px; }}
        .footer {{ text-align: center; margin-top: 30px; padding: 20px; background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 New Job Alert{'s' if len(jobs) > 1 else ''}</h1>
        <p>We found {len(jobs)} job{'s' if len(jobs) > 1 else ''} that match your preferences!</p>
    </div>
"""
        
        for i, (job, ranking) in enumerate(jobs[:10], 1):  # Limit to top 10
            # Plain text
            plain_text += f"""
{i}. {job.title} at {job.company}
   Location: {job.location or 'Not specified'}
   Score: {ranking.overall_score:.1%}
   URL: {job.source_url}
   
"""
            
            # Salary information
            salary_text = ""
            if job.salary_min or job.salary_max:
                if job.salary_min and job.salary_max:
                    salary_text = f"${job.salary_min:,} - ${job.salary_max:,}"
                elif job.salary_min:
                    salary_text = f"${job.salary_min:,}+"
                else:
                    salary_text = f"Up to ${job.salary_max:,}"
                
                if job.salary_type == "hourly":
                    salary_text += "/hour"
                else:
                    salary_text += "/year"
            
            # Technologies
            tech_tags = ""
            if job.technologies:
                tech_tags = "".join([f'<span class="tech-tag">{tech}</span>' for tech in job.technologies[:5]])
            
            # HTML
            html_text += f"""
    <div class="job">
        <div class="job-title">{job.title}</div>
        <div class="company">{job.company}</div>
        <div class="location">📍 {job.location or 'Location not specified'}</div>
        {f'<div class="salary">💰 {salary_text}</div>' if salary_text else ''}
        <div style="margin: 10px 0;">
            <span class="score">Match Score: {ranking.overall_score:.1%}</span>
            {f'<span style="margin-left: 10px;">🏠 Remote Available</span>' if job.remote_option else ''}
        </div>
        {f'<div class="technologies">{tech_tags}</div>' if tech_tags else ''}
        <div style="margin-top: 10px;">
            <a href="{job.source_url}" style="color: #2196F3; text-decoration: none;">View Job Details →</a>
        </div>
    </div>
"""
        
        # Footer
        plain_text += f"""
---
Job Search App
Configure your preferences or unsubscribe at: [Your App URL]
"""
        
        html_text += f"""
    <div class="footer">
        <p>Happy job hunting! 🎯</p>
        <p><small>Job Search App | <a href="#">Configure Preferences</a> | <a href="#">Unsubscribe</a></small></p>
    </div>
</body>
</html>
"""
        
        return subject, plain_text, html_text
    
    @staticmethod
    def format_job_alert_sms(jobs: List[tuple], user_preferences: UserPreferences) -> str:
        """
        Format job alert SMS
        
        Args:
            jobs: List of (Job, RankingResult) tuples
            user_preferences: User preferences
            
        Returns:
            SMS message text
        """
        if not jobs:
            return "Job Search App: No new jobs match your criteria today."
        
        if len(jobs) == 1:
            job, ranking = jobs[0]
            message = f"🚀 New Job Match ({ranking.overall_score:.0%})!\n\n"
            message += f"{job.title} at {job.company}\n"
            message += f"📍 {job.location or 'Remote'}\n"
            
            if job.salary_min:
                message += f"💰 ${job.salary_min:,}+\n"
            
            message += f"\nView: {job.source_url}"
        else:
            message = f"🚀 {len(jobs)} New Job Matches!\n\n"
            for i, (job, ranking) in enumerate(jobs[:3], 1):  # Top 3 for SMS
                message += f"{i}. {job.title} at {job.company} ({ranking.overall_score:.0%})\n"
            
            if len(jobs) > 3:
                message += f"\n+{len(jobs) - 3} more jobs. Check your email for details!"
        
        return message
    
    @staticmethod
    def format_daily_summary_email(jobs_found: int, top_jobs: List[tuple]) -> tuple:
        """Format daily summary email"""
        subject = f"📊 Daily Job Search Summary - {jobs_found} jobs found"
        
        plain_text = f"""
Daily Job Search Summary

Total jobs found today: {jobs_found}
Top matches:

"""
        
        html_text = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .summary {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; }}
        .stat {{ font-size: 24px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="summary">
        <h1>📊 Daily Summary</h1>
        <div class="stat">{jobs_found} jobs found today</div>
    </div>
"""
        
        if top_jobs:
            plain_text += "Top matches:\n\n"
            html_text += "<h2>Top Matches:</h2>"
            
            for i, (job, ranking) in enumerate(top_jobs[:5], 1):
                plain_text += f"{i}. {job.title} at {job.company} ({ranking.overall_score:.1%})\n"
                html_text += f"<p>{i}. <strong>{job.title}</strong> at {job.company} ({ranking.overall_score:.1%})</p>"
        
        html_text += "</body></html>"
        
        return subject, plain_text, html_text


class NotificationManager:
    """
    Central notification management system
    Handles different notification types and delivery tracking
    """
    
    def __init__(self):
        self.email_notifier = None
        self.sms_notifier = None
        
        # Initialize available notifiers
        try:
            self.email_notifier = EmailNotifier()
        except NotificationError as e:
            logger.warning(f"Email notifications not available: {e}")
        
        try:
            self.sms_notifier = SMSNotifier()
        except NotificationError as e:
            logger.warning(f"SMS notifications not available: {e}")
    
    def send_job_alerts(self, user_id: str, jobs_with_rankings: List[tuple], 
                       user_preferences: UserPreferences) -> Dict[str, bool]:
        """
        Send job alerts to user via configured notification methods
        
        Args:
            user_id: User identifier
            jobs_with_rankings: List of (Job, RankingResult) tuples
            user_preferences: User preferences including notification settings
            
        Returns:
            Dictionary with notification results
        """
        results = {"email": False, "sms": False}
        
        # Filter high-scoring jobs
        high_score_jobs = [
            (job, ranking) for job, ranking in jobs_with_rankings
            if ranking.overall_score >= config.HIGH_SCORE_THRESHOLD
        ]
        
        if not high_score_jobs:
            logger.info(f"No high-scoring jobs for user {user_id}")
            return results
        
        # Get user contact info
        with get_db_session() as session:
            from ..database.models import UserProfile
            user_profile = session.query(UserProfile).filter_by(user_id=user_id).first()
            
            if not user_profile:
                logger.error(f"User profile not found for {user_id}")
                return results
            
            # Send email notification
            if (user_preferences.email_notifications and 
                self.email_notifier and 
                user_profile.email):
                
                try:
                    subject, plain_text, html_text = NotificationTemplates.format_job_alert_email(
                        high_score_jobs, user_preferences
                    )
                    
                    success = self.email_notifier.send(
                        user_profile.email, subject, plain_text, html_text
                    )
                    
                    results["email"] = success
                    
                    # Log notification
                    for job, ranking in high_score_jobs:
                        self._log_notification(
                            user_id, job.id, "email", "high_score", 
                            subject, "sent" if success else "failed"
                        )
                    
                    if success:
                        logger.info(f"Email alert sent to {user_profile.email} for {len(high_score_jobs)} jobs")
                    
                except Exception as e:
                    logger.error(f"Failed to send email to {user_profile.email}: {e}")
            
            # Send SMS notification
            if (user_preferences.sms_notifications and 
                self.sms_notifier and 
                user_profile.phone):
                
                try:
                    message = NotificationTemplates.format_job_alert_sms(
                        high_score_jobs, user_preferences
                    )
                    
                    success = self.sms_notifier.send(
                        user_profile.phone, "Job Alert", message
                    )
                    
                    results["sms"] = success
                    
                    # Log notification
                    self._log_notification(
                        user_id, high_score_jobs[0][0].id if high_score_jobs else None,
                        "sms", "high_score", message, "sent" if success else "failed"
                    )
                    
                    if success:
                        logger.info(f"SMS alert sent to {user_profile.phone} for {len(high_score_jobs)} jobs")
                    
                except Exception as e:
                    logger.error(f"Failed to send SMS to {user_profile.phone}: {e}")
        
        return results
    
    def send_daily_summary(self, user_id: str, jobs_found: int, top_jobs: List[tuple]) -> bool:
        """Send daily summary email"""
        if not self.email_notifier:
            return False
        
        with get_db_session() as session:
            from ..database.models import UserProfile
            user_profile = session.query(UserProfile).filter_by(user_id=user_id).first()
            
            if not user_profile or not user_profile.email:
                return False
            
            subject, plain_text, html_text = NotificationTemplates.format_daily_summary_email(
                jobs_found, top_jobs
            )
            
            success = self.email_notifier.send(
                user_profile.email, subject, plain_text, html_text
            )
            
            # Log notification
            self._log_notification(
                user_id, None, "email", "daily_summary", 
                subject, "sent" if success else "failed"
            )
            
            return success
    
    def _log_notification(self, user_id: str, job_id: Optional[int], 
                         notification_type: str, category: str, 
                         message: str, status: str):
        """Log notification to database"""
        with get_db_session() as session:
            log_entry = NotificationLog(
                user_id=user_id,
                job_id=job_id,
                notification_type=notification_type,
                notification_category=category,
                message=message[:1000],  # Truncate if too long
                status=status
            )
            session.add(log_entry)
    
    def get_notification_stats(self, user_id: str, days: int = 30) -> Dict:
        """Get notification statistics for a user"""
        with get_db_session() as session:
            from sqlalchemy import func
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            stats = session.query(
                NotificationLog.notification_type,
                NotificationLog.status,
                func.count(NotificationLog.id).label('count')
            ).filter(
                NotificationLog.user_id == user_id,
                NotificationLog.sent_at >= cutoff_date
            ).group_by(
                NotificationLog.notification_type,
                NotificationLog.status
            ).all()
            
            return {
                f"{stat.notification_type}_{stat.status}": stat.count
                for stat in stats
            }
    
    def is_available(self) -> Dict[str, bool]:
        """Check which notification methods are available"""
        return {
            "email": self.email_notifier is not None and self.email_notifier.is_configured(),
            "sms": self.sms_notifier is not None and self.sms_notifier.is_configured()
        } 
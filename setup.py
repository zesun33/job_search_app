#!/usr/bin/env python3
"""
Setup script for the Job Search Application.
Initializes database, creates necessary directories, and sets up the environment.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from database.models import create_tables
    from database import init_database
    from config.config import Config, DefaultPreferences
    from database.models import UserProfile
    from database import get_session
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)

def create_directories():
    """Create necessary directories for the application."""
    directories = [
        "data",
        "logs", 
        "config",
        "tests",
        "static/css",
        "static/js",
        "templates"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")

def create_env_template():
    """Create a template .env file with configuration options."""
    env_template = """# Job Search Application Environment Configuration

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/jobsearch
# For SQLite (development): DATABASE_URL=sqlite:///./data/jobsearch.db

# Redis Configuration (for background tasks)
REDIS_URL=redis://localhost:6379/0

# API Keys for Job Boards
INDEED_API_KEY=your_indeed_api_key_here
ZIPRECRUITER_API_KEY=your_ziprecruiter_api_key_here
MONSTER_API_KEY=your_monster_api_key_here
GITHUB_TOKEN=your_github_token_here

# Email Configuration
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=noreply@jobsearch.com

# Alternative: SendGrid
# EMAIL_BACKEND=sendgrid
# SENDGRID_API_KEY=your_sendgrid_api_key

# SMS Configuration (Twilio)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Application Settings
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=True

# Scraping Configuration
SCRAPING_DELAY_MIN=1.0
SCRAPING_DELAY_MAX=3.0
MAX_CONCURRENT_REQUESTS=5

# Notification Thresholds
HIGH_SCORE_THRESHOLD=0.8
MEDIUM_SCORE_THRESHOLD=0.6
"""
    
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write(env_template)
        print(f"✅ Created environment template: {env_path}")
        print("📝 Please edit .env file with your actual configuration values")
    else:
        print(f"⚠️ Environment file already exists: {env_path}")

def setup_database():
    """Initialize the database and create tables."""
    try:
        print("🔄 Setting up database...")
        
        # Initialize database connection
        init_database()
        
        # Create all tables
        create_tables()
        print("✅ Database tables created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def create_default_user():
    """Create a default user profile for testing."""
    try:
        config = Config()
        session = get_session()
        
        # Check if any users exist
        existing_user = session.query(UserProfile).first()
        if existing_user:
            print("⚠️ User profiles already exist, skipping default user creation")
            session.close()
            return
        
        # Create default user with internship preferences
        prefs = DefaultPreferences.get_cs_internship_preferences()
        
        default_user = UserProfile(
            name="Default User",
            email="user@example.com",
            phone_number="+1234567890",
            preferences=prefs.__dict__
        )
        
        session.add(default_user)
        session.commit()
        user_id = default_user.id
        session.close()
        
        print(f"✅ Created default user profile (ID: {user_id})")
        print("📝 You can modify user preferences through the web interface")
        
    except Exception as e:
        print(f"❌ Failed to create default user: {e}")

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "sqlalchemy",
        "psycopg2-binary",
        "requests",
        "beautifulsoup4",
        "flask",
        "pydantic",
        "asyncio",
        "aiohttp"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install with: pip install -r requirements.txt")
        return False
    
    print("✅ All required dependencies are installed")
    return True

def create_sample_config():
    """Create sample configuration files."""
    # Create a sample cron job for automated job scraping
    cron_sample = """# Sample cron job for automated job scraping
# Run job search every 6 hours
0 */6 * * * cd /path/to/job_search_app && python run_search.py

# Send daily notifications at 9 AM
0 9 * * * cd /path/to/job_search_app && python send_notifications.py
"""
    
    with open("config/cron_sample.txt", "w") as f:
        f.write(cron_sample)
    
    # Create a sample systemd service file
    systemd_sample = """[Unit]
Description=Job Search Application
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/job_search_app
Environment=PATH=/path/to/job_search_app/venv/bin
ExecStart=/path/to/job_search_app/venv/bin/python web_app/app.py
Restart=always

[Install]
WantedBy=multi-user.target
"""
    
    with open("config/jobsearch.service", "w") as f:
        f.write(systemd_sample)
    
    print("✅ Created sample configuration files in config/")

def main():
    """Main setup function."""
    print("🚀 Job Search Application Setup")
    print("=" * 40)
    
    # Step 1: Check dependencies
    print("\n1. Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    
    # Step 2: Create directories
    print("\n2. Creating directories...")
    create_directories()
    
    # Step 3: Create environment template
    print("\n3. Setting up environment configuration...")
    create_env_template()
    
    # Step 4: Setup database
    print("\n4. Setting up database...")
    if not setup_database():
        print("⚠️ Database setup failed. Please check your DATABASE_URL in .env")
        print("   For development, you can use SQLite: DATABASE_URL=sqlite:///./data/jobsearch.db")
    
    # Step 5: Create default user
    print("\n5. Creating default user profile...")
    create_default_user()
    
    # Step 6: Create sample configurations
    print("\n6. Creating sample configuration files...")
    create_sample_config()
    
    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your API keys and configuration")
    print("2. Run system test: python test_system.py")
    print("3. Start web application: python src/web_app/app.py")
    print("4. Access web interface at: http://localhost:5000")
    print("\n📚 Documentation:")
    print("- Check docs/ directory for detailed setup instructions")
    print("- See config/ directory for sample configuration files")
    print("- Review logs/ directory for application logs")

if __name__ == "__main__":
    main() 
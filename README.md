# Job Search Application

A comprehensive job search application for CS/IT positions that aggregates opportunities from multiple sources, ranks them using custom criteria, and sends notifications for high-scoring matches.

## 🌟 Features

### **Multi-Source Job Acquisition**
- **GitHub Repositories**: Daily-H1B-Jobs, SimplifyJobs, Engineer-Internship repos
- **External Websites**: intern-list.com and other specialized job boards
- **Company Websites**: Direct scraping of 100+ tech company career pages
- **ATS Systems**: Specialized scrapers for Workday, Greenhouse, Lever
- **Job Board APIs**: Indeed, ZipRecruiter, Monster integration

### **Advanced Ranking System**
- **Multi-criteria scoring**: Keywords, location, salary, experience, company type
- **Fuzzy keyword matching**: Handles variations and synonyms
- **Location preferences**: Remote-first with geographic preferences
- **Technology stack matching**: AI/ML-powered tech stack recognition
- **Company preferences**: Startup vs enterprise, inclusion/exclusion lists

### **Smart Notifications**
- **Email & SMS alerts**: High-scoring job notifications
- **Rich HTML templates**: Detailed job information and ranking explanations
- **Configurable thresholds**: Custom score thresholds for notifications
- **Daily summaries**: Digest of all new opportunities

### **Web Interface**
- **Job browsing**: Filter, sort, and search saved opportunities
- **Preference management**: Customize ranking weights and criteria
- **Application tracking**: Track application status and outcomes
- **Analytics dashboard**: Job market insights and personal statistics

## 🏗️ Architecture

```
job_search_app/
├── src/
│   ├── api_clients/           # Job board API integrations
│   ├── database/              # Database models and management
│   ├── notifications/         # Email/SMS notification system
│   ├── ranking/               # Job ranking and scoring algorithms
│   ├── scrapers/              # Web scrapers for various sources
│   ├── utils/                 # Utilities and source coordination
│   └── web_app/               # Flask web interface
├── config/                    # Configuration management
├── data/                      # Data storage directory
├── logs/                      # Application logs
├── tests/                     # Test suite
├── requirements.txt           # Python dependencies
├── setup.py                   # Environment setup script
└── test_system.py            # Comprehensive system test
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the application
cd job_search_app

# Install dependencies
pip install -r requirements.txt

# Run setup script
python setup.py
```

### 2. Configuration

Edit the `.env` file created by setup:

```bash
# Database (SQLite for development, PostgreSQL for production)
DATABASE_URL=sqlite:///./data/jobsearch.db

# API Keys (optional but recommended)
GITHUB_TOKEN=your_github_token_here
INDEED_API_KEY=your_indeed_api_key_here

# Email configuration for notifications
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

### 3. Run System Test

```bash
python test_system.py
```

### 4. Start the Application

```bash
# Start web interface
python src/web_app/app.py

# Access at http://localhost:5000
```

## 📊 Usage Examples

### Running a Job Search

```python
from src.utils.source_coordinator import JobSourceCoordinator
from config.config import Config

# Initialize coordinator
config = Config()
coordinator = JobSourceCoordinator(config)

# Run comprehensive search
session = await coordinator.run_comprehensive_search(
    focus_areas=["internships", "new_grad"],
    priority_companies_only=True
)

print(f"Found {session.total_jobs_found} jobs")
print(f"Saved {session.total_jobs_saved} new jobs")
```

### Custom Ranking

```python
from src.ranking.job_ranker import JobRanker
from config.config import DefaultPreferences

# Get user preferences
prefs = DefaultPreferences.get_cs_internship_preferences()

# Customize weights
prefs.ranking_weights = {
    "keywords": 0.4,      # Prioritize keyword matching
    "location": 0.3,      # Strong location preference
    "salary": 0.1,        # Less emphasis on salary
    "experience": 0.1,
    "company": 0.05,
    "freshness": 0.05
}

# Rank jobs
ranker = JobRanker(prefs)
ranking = ranker.rank_job(job)
print(f"Score: {ranking.total_score:.2f}")
```

### Automated Notifications

```python
from src.notifications.notifier import NotificationManager

notifier = NotificationManager(config)

# Send notifications for high-scoring jobs
await notifier.send_high_score_notifications(
    user_profile=user,
    threshold=0.8
)
```

## 🔧 Configuration Options

### User Preferences
- **Keywords**: Required, preferred, and excluded terms
- **Location**: Geographic preferences and remote work options
- **Salary**: Min/max ranges and importance weighting
- **Experience**: Target experience levels
- **Company**: Preferred company types and exclusions
- **Technology**: Required and preferred tech stacks

### Ranking Weights
- **Keywords (30%)**: Keyword matching and relevance
- **Location (20%)**: Geographic and remote work preferences
- **Salary (25%)**: Salary range compatibility
- **Experience (15%)**: Experience level matching
- **Company (5%)**: Company type and preferences
- **Freshness (5%)**: Job posting recency

### Notification Settings
- **Thresholds**: High (0.8), Medium (0.6) score thresholds
- **Frequency**: Immediate, daily, or weekly notifications
- **Channels**: Email, SMS, or both
- **Templates**: Customizable HTML email templates

## 🔍 Job Sources

### GitHub Repositories
- [Daily-H1B-Jobs-In-Tech](https://github.com/jobright-ai/Daily-H1B-Jobs-In-Tech)
- [2025-Software-Engineer-New-Grad](https://github.com/jobright-ai/2025-Software-Engineer-New-Grad)
- [2025-Engineer-Internship](https://github.com/jobright-ai/2025-Engineer-Internship)
- [Summer2026-Internships](https://github.com/SimplifyJobs/Summer2026-Internships)
- [New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions)

### External Websites
- [intern-list.com](https://www.intern-list.com/) - Engineering & Software internships
- Additional curated job boards

### Company Websites (100+ Companies)
- **FAANG**: Google, Apple, Facebook, Amazon, Netflix
- **Big Tech**: Microsoft, Oracle, IBM, Salesforce, Adobe
- **Unicorns**: Stripe, Airbnb, Uber, Lyft, Slack
- **Startups**: YC companies, well-funded startups
- **Hardware**: Intel, AMD, NVIDIA, Qualcomm

### ATS Systems
- **Workday**: Enterprise-level ATS scraping
- **Greenhouse**: Startup-focused ATS integration
- **Lever**: Modern ATS platform support
- **iCIMS**: Traditional ATS system
- **SmartRecruiters**: Global ATS platform

## 🧪 Testing

### System Test
```bash
python test_system.py
```

Tests all major components:
- Database connectivity and operations
- Scraper functionality across all sources
- Ranking algorithm accuracy
- Notification system reliability
- Web interface responsiveness
- End-to-end integration workflow

### Individual Component Tests
```bash
# Test specific scrapers
python -m pytest tests/test_scrapers.py

# Test ranking system
python -m pytest tests/test_ranking.py

# Test notifications
python -m pytest tests/test_notifications.py
```

## 📈 Performance & Scalability

### Optimizations
- **Deduplication**: Hash-based job deduplication across sources
- **Rate Limiting**: Respectful scraping with configurable delays
- **Concurrent Processing**: Parallel scraping with connection pooling
- **Caching**: Intelligent caching of API responses and web pages
- **Database Indexing**: Optimized queries for job search and ranking

### Scalability Features
- **Horizontal Scaling**: Multi-instance deployment support
- **Background Processing**: Celery integration for async job processing
- **Database Options**: SQLite for development, PostgreSQL for production
- **Cloud Integration**: AWS/GCP deployment ready

## 🔒 Ethical Considerations

### Responsible Scraping
- **Robots.txt Compliance**: Respects website scraping policies
- **Rate Limiting**: Configurable delays between requests
- **User Agent Rotation**: Mimics human browsing patterns
- **Error Handling**: Graceful failure and retry mechanisms

### Data Privacy
- **Local Storage**: All data stored locally by default
- **Encryption**: Sensitive data encryption at rest
- **GDPR Compliance**: Data deletion and export capabilities
- **Minimal Data**: Only collects necessary job information

## 🛠️ Development

### Adding New Job Sources

1. **Create Scraper Class**:
```python
class NewSourceScraper(BaseScraper):
    async def scrape_jobs(self) -> List[JobData]:
        # Implement scraping logic
        pass
```

2. **Register in Source Coordinator**:
```python
# Add to source_coordinator.py
self.new_scraper = NewSourceScraper(config)
```

3. **Add Configuration**:
```python
# Add to company_sources.py
NEW_SOURCE_CONFIG = {
    "name": "New Source",
    "url": "https://example.com/jobs"
}
```

### Customizing Ranking Algorithm

```python
# Extend JobRanker class
class CustomJobRanker(JobRanker):
    def _calculate_custom_score(self, job: JobData) -> float:
        # Implement custom scoring logic
        return score
```

## 📝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

- **Documentation**: Check the `docs/` directory
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Join community discussions for usage questions

## 🎯 Roadmap

### Upcoming Features
- [ ] LinkedIn API integration (when available)
- [ ] Machine learning job matching
- [ ] Mobile app development
- [ ] Chrome extension for job tracking
- [ ] Salary prediction modeling
- [ ] Interview preparation integration

### Enhancements
- [ ] Advanced NLP for job description analysis
- [ ] Company culture scoring
- [ ] Referral network integration
- [ ] Interview scheduling automation
- [ ] Career progression tracking

---

**Built with ❤️ for job seekers in CS/IT**

*Streamline your job search, maximize your opportunities, land your dream job.* 
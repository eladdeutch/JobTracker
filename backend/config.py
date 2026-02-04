"""Application configuration."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    
    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-me')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '127.0.0.1')
    PORT = int(os.getenv('FLASK_PORT', 5000))
    
    # Database (using psycopg3 driver)
    DATABASE_URL = os.getenv(
        'DATABASE_URL', 
        'postgresql+psycopg://postgres:postgres@localhost:5432/job_tracker'
    )
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/callback')
    
    # Google API Scopes (Gmail + Calendar)
    GMAIL_SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    # Job search keywords for email scanning
    JOB_KEYWORDS = [
        # Application confirmations
        'application received',
        'thank you for applying',
        'thanks for applying',
        'application status',
        'application submitted',
        'successfully applied',
        'your application',
        'application for',
        'regarding your application',
        'confirm your application',
        'application confirmation',
        
        # Interview related
        'interview invitation',
        'phone screen',
        'phone interview',
        'video interview',
        'interview scheduled',
        'schedule an interview',
        'schedule a call',
        'interview request',
        'technical interview',
        'coding interview',
        'onsite interview',
        'on-site interview',
        'virtual onsite',
        'final round',
        'next round',
        'assessment',
        'take-home',
        'coding challenge',
        'technical assessment',
        
        # Status updates
        'moved forward',
        'moving forward',
        'move forward',
        'next steps',
        'update on your',
        'status update',
        'candidacy',
        'your candidacy',
        'under review',
        'being reviewed',
        'shortlisted',
        
        # Rejection phrases
        'we regret to inform',
        'unfortunately',
        'not moving forward',
        'decided not to proceed',
        'other candidates',
        'not selected',
        'position has been filled',
        'filled the position',
        'went with another',
        'pursue other candidates',
        
        # Offer related
        'offer letter',
        'job offer',
        'offer of employment',
        'congratulations',
        'pleased to offer',
        'extend an offer',
        
        # Position mentions
        'position at',
        'role at',
        'opportunity at',
        'position of',
        'role of',
        'job at',
        'career at',
        'opening at',
        'vacancy',
        
        # Recruiter/HR terms
        'hiring manager',
        'recruiter',
        'recruiting',
        'recruitment',
        'talent acquisition',
        'talent team',
        'people team',
        'HR team',
        'human resources',
        'career',
        'careers',
        
        # Company communication
        'we reviewed',
        'reviewed your',
        'your profile',
        'your resume',
        'your cv',
        'your background',
        'your experience',
        'your qualifications',
        'impressed by',
        'excited to',
        'like to connect',
        'reach out',
        
        # Job titles (common)
        'software engineer',
        'software developer',
        'backend engineer',
        'frontend engineer',
        'full stack',
        'fullstack',
        'senior engineer',
        'staff engineer',
        'engineering manager',
        'tech lead',
        'developer',
        'programmer',
        
        # ATS systems
        'workday',
        'greenhouse',
        'lever',
        'ashby',
        'bamboohr',
        'icims',
        'taleo',
        'smartrecruiters',
        'jobvite',
        'breezy',
        'comeet',
        
        # Common phrases
        'join our team',
        'join the team',
        'great fit',
        'good fit',
        'right fit',
        'team would love',
        'speak with you',
        'chat with you',
        'learn more about you',
        'discuss the opportunity',
        'discuss the role',
        'discuss the position'
    ]
    
    # Company domain patterns to ignore (non-company emails)
    IGNORE_DOMAINS = [
        'linkedin.com',
        'indeed.com', 
        'glassdoor.com',
        'ziprecruiter.com',
        'monster.com',
        'careerbuilder.com',
        'dice.com',
        'noreply',
        'no-reply',
        'mailer-daemon'
    ]


config = Config()

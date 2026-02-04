"""Database models for job application tracker."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
import enum
from backend.models.database import Base


class ApplicationStatus(enum.Enum):
    """Status stages for job applications."""
    APPLIED = "applied"
    PHONE_SCREEN = "phone_screen"
    FIRST_INTERVIEW = "first_interview"
    SECOND_INTERVIEW = "second_interview"
    THIRD_INTERVIEW = "third_interview"
    OFFER_RECEIVED = "offer_received"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    NO_RESPONSE = "no_response"


class Application(Base):
    """Job application record."""
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    position_title = Column(String(255), nullable=False)
    job_url = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    
    status = Column(
        Enum(ApplicationStatus), 
        default=ApplicationStatus.APPLIED, 
        nullable=False,
        index=True
    )
    
    # Track at which stage rejection happened
    rejected_at_stage = Column(String(100), nullable=True)
    
    applied_date = Column(DateTime, default=datetime.utcnow)
    last_contact_date = Column(DateTime, nullable=True)
    next_action_date = Column(DateTime, nullable=True)
    
    recruiter_name = Column(String(255), nullable=True)
    recruiter_email = Column(String(255), nullable=True)
    
    job_description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    emails = relationship("Email", back_populates="application", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="application", cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="application", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "company_name": self.company_name,
            "position_title": self.position_title,
            "job_url": self.job_url,
            "location": self.location,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "status": self.status.value if self.status else None,
            "rejected_at_stage": self.rejected_at_stage,
            "applied_date": self.applied_date.isoformat() if self.applied_date else None,
            "last_contact_date": self.last_contact_date.isoformat() if self.last_contact_date else None,
            "next_action_date": self.next_action_date.isoformat() if self.next_action_date else None,
            "recruiter_name": self.recruiter_name,
            "recruiter_email": self.recruiter_email,
            "job_description": self.job_description,
            "notes": self.notes,
            "created_at": (self.created_at.isoformat() + 'Z') if self.created_at else None,
            "updated_at": (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
            "email_count": len(self.emails) if self.emails else 0
        }


class Email(Base):
    """Email records linked to applications."""
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    gmail_id = Column(String(255), unique=True, nullable=False, index=True)
    thread_id = Column(String(255), nullable=True, index=True)
    
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    
    sender = Column(String(255), nullable=False)
    sender_email = Column(String(255), nullable=True)
    subject = Column(Text, nullable=False)
    snippet = Column(Text, nullable=True)
    body_preview = Column(Text, nullable=True)
    
    received_date = Column(DateTime, nullable=False)
    
    # Extracted data
    detected_company = Column(String(255), nullable=True)
    detected_position = Column(String(255), nullable=True)
    detected_status = Column(String(50), nullable=True)
    rejected_at_stage = Column(String(100), nullable=True)
    confidence_score = Column(Float, default=0.0)
    
    is_processed = Column(Boolean, default=False)
    is_job_related = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    application = relationship("Application", back_populates="emails")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "gmail_id": self.gmail_id,
            "thread_id": self.thread_id,
            "application_id": self.application_id,
            "sender": self.sender,
            "sender_email": self.sender_email,
            "subject": self.subject,
            "snippet": self.snippet,
            "received_date": self.received_date.isoformat() if self.received_date else None,
            "detected_company": self.detected_company,
            "detected_position": self.detected_position,
            "detected_status": self.detected_status,
            "confidence_score": self.confidence_score,
            "is_processed": self.is_processed,
            "is_job_related": self.is_job_related
        }


class Reminder(Base):
    """Follow-up reminders for applications."""
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    
    reminder_date = Column(DateTime, nullable=False)
    message = Column(Text, nullable=False)
    
    is_completed = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    application = relationship("Application", back_populates="reminders")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "reminder_date": self.reminder_date.isoformat() if self.reminder_date else None,
            "message": self.message,
            "is_completed": self.is_completed,
            "is_dismissed": self.is_dismissed,
            "company_name": self.application.company_name if self.application else None,
            "position_title": self.application.position_title if self.application else None
        }


class InterviewType(enum.Enum):
    """Types of interviews."""
    PHONE_SCREEN = "phone_screen"
    VIDEO_CALL = "video_call"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    ONSITE = "onsite"
    PANEL = "panel"
    FINAL = "final"
    OTHER = "other"


class Interview(Base):
    """Scheduled interviews linked to applications."""
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    
    # Interview details
    interview_type = Column(Enum(InterviewType), default=InterviewType.VIDEO_CALL)
    title = Column(String(255), nullable=True)  # Custom title if provided
    
    # Scheduling
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    timezone = Column(String(50), default='UTC')
    
    # Location/Meeting details
    location = Column(Text, nullable=True)  # Physical address or video link
    meeting_link = Column(Text, nullable=True)  # Zoom/Meet/Teams link
    
    # Interviewer info
    interviewer_name = Column(String(255), nullable=True)
    interviewer_email = Column(String(255), nullable=True)
    interviewer_title = Column(String(255), nullable=True)
    
    # Google Calendar integration
    calendar_event_id = Column(String(255), nullable=True, index=True)
    calendar_event_link = Column(Text, nullable=True)
    
    # Notes
    preparation_notes = Column(Text, nullable=True)  # Pre-interview notes
    interview_notes = Column(Text, nullable=True)  # Post-interview notes/feedback
    questions_asked = Column(Text, nullable=True)  # Questions they asked
    your_questions = Column(Text, nullable=True)  # Questions you asked
    went_well = Column(Text, nullable=True)  # What went well
    to_improve = Column(Text, nullable=True)  # Areas to improve
    follow_up_items = Column(Text, nullable=True)  # Follow-up tasks
    
    # Status
    is_completed = Column(Boolean, default=False)
    is_cancelled = Column(Boolean, default=False)
    outcome = Column(String(50), nullable=True)  # passed, failed, pending
    confidence_rating = Column(Integer, nullable=True)  # 1-5 self-assessment
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    application = relationship("Application", back_populates="interviews")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "interview_type": self.interview_type.value if self.interview_type else None,
            "title": self.title,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_minutes": self.duration_minutes,
            "timezone": self.timezone,
            "location": self.location,
            "meeting_link": self.meeting_link,
            "interviewer_name": self.interviewer_name,
            "interviewer_email": self.interviewer_email,
            "interviewer_title": self.interviewer_title,
            "calendar_event_id": self.calendar_event_id,
            "calendar_event_link": self.calendar_event_link,
            "preparation_notes": self.preparation_notes,
            "interview_notes": self.interview_notes,
            "questions_asked": self.questions_asked,
            "your_questions": self.your_questions,
            "went_well": self.went_well,
            "to_improve": self.to_improve,
            "follow_up_items": self.follow_up_items,
            "is_completed": self.is_completed,
            "is_cancelled": self.is_cancelled,
            "outcome": self.outcome,
            "confidence_rating": self.confidence_rating,
            "created_at": (self.created_at.isoformat() + 'Z') if self.created_at else None,
            "updated_at": (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
            "company_name": self.application.company_name if self.application else None,
            "position_title": self.application.position_title if self.application else None
        }


class UserSettings(Base):
    """User settings and OAuth tokens."""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # OAuth tokens (encrypted in production)
    gmail_access_token = Column(Text, nullable=True)
    gmail_refresh_token = Column(Text, nullable=True)
    gmail_token_expiry = Column(DateTime, nullable=True)
    
    # Email sync settings
    last_sync_date = Column(DateTime, nullable=True)
    sync_from_date = Column(DateTime, nullable=True)
    auto_sync_enabled = Column(Boolean, default=True)
    sync_interval_minutes = Column(Integer, default=30)
    
    # Reminder settings
    default_followup_days = Column(Integer, default=7)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary (excluding sensitive data)."""
        return {
            "id": self.id,
            "is_gmail_connected": bool(self.gmail_refresh_token),
            "last_sync_date": self.last_sync_date.isoformat() if self.last_sync_date else None,
            "auto_sync_enabled": self.auto_sync_enabled,
            "sync_interval_minutes": self.sync_interval_minutes,
            "default_followup_days": self.default_followup_days
        }

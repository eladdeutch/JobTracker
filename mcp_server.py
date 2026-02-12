"""
MCP Server for Job Application Tracker

This server exposes tools for:
- Scanning Gmail for job-related emails
- Managing job applications
- Getting statistics and insights
- Setting reminders
"""

import sys
import os
import json
from datetime import datetime, timedelta, timezone
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("Job Application Tracker")

# Import our services after path setup
from backend.config import config
from backend.models import SessionLocal, Application, Email, Reminder, UserSettings, ApplicationStatus, init_db
from backend.services import gmail_service, email_parser, stats_service

# Initialize database on startup
init_db()


def get_db():
    """Get database session."""
    return SessionLocal()


@mcp.tool()
def get_gmail_status() -> dict:
    """Check if Gmail is connected and get sync status."""
    db = get_db()
    try:
        settings = db.query(UserSettings).first()
        return {
            "connected": bool(settings and settings.gmail_refresh_token),
            "last_sync": settings.last_sync_date.isoformat() if settings and settings.last_sync_date else None
        }
    finally:
        db.close()


@mcp.tool()
def scan_gmail_for_jobs(days_back: int = 30, max_results: int = 100) -> dict:
    """
    Scan Gmail for job-related emails.
    
    Args:
        days_back: Number of days to look back (default 30)
        max_results: Maximum emails to scan (default 100)
    
    Returns:
        Summary of scanned and new emails found
    """
    db = get_db()
    try:
        # Get OAuth tokens
        settings = db.query(UserSettings).first()
        if not settings or not settings.gmail_refresh_token:
            return {"error": "Gmail not connected. Please connect via the web dashboard at http://localhost:5000"}
        
        # Initialize Gmail service
        gmail_service.set_credentials(
            access_token=settings.gmail_access_token or '',
            refresh_token=settings.gmail_refresh_token,
            expiry=settings.gmail_token_expiry
        )
        
        # Update tokens if refreshed
        updated_tokens = gmail_service.get_updated_tokens()
        if updated_tokens:
            settings.gmail_access_token = updated_tokens['access_token']
            if updated_tokens.get('expiry'):
                settings.gmail_token_expiry = datetime.fromisoformat(updated_tokens['expiry'])
        
        # Calculate search date
        after_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        # Fetch emails
        raw_emails = gmail_service.search_emails(
            max_results=max_results,
            after_date=after_date
        )
        
        # Parse and store emails
        new_count = 0
        for raw_email in raw_emails:
            existing = db.query(Email).filter(Email.gmail_id == raw_email['gmail_id']).first()
            if existing:
                continue
            
            parsed = email_parser.parse_email(raw_email)
            
            email = Email(
                gmail_id=parsed['gmail_id'],
                thread_id=parsed.get('thread_id'),
                sender=parsed['sender'],
                sender_email=parsed.get('sender_email'),
                subject=parsed['subject'],
                snippet=parsed.get('snippet'),
                body_preview=parsed.get('body_preview'),
                received_date=parsed['received_date'],
                detected_company=parsed.get('detected_company'),
                detected_position=parsed.get('detected_position'),
                detected_status=parsed.get('detected_status'),
                rejected_at_stage=parsed.get('rejected_at_stage'),
                confidence_score=parsed.get('confidence_score', 0),
                is_job_related=parsed.get('is_job_related', True),
                is_processed=False
            )
            db.add(email)
            new_count += 1
        
        settings.last_sync_date = datetime.now(timezone.utc)
        db.commit()
        
        return {
            "scanned": len(raw_emails),
            "new_emails": new_count,
            "message": f"Found {new_count} new job-related emails out of {len(raw_emails)} scanned"
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def auto_process_emails(min_confidence: float = 0.4) -> dict:
    """
    Automatically create applications from high-confidence emails.
    
    Args:
        min_confidence: Minimum confidence score (0.0-1.0, default 0.4)
    
    Returns:
        Number of applications created
    """
    db = get_db()
    try:
        emails = db.query(Email).filter(
            Email.is_job_related == True,
            Email.is_processed == False,
            Email.application_id.is_(None),
            Email.confidence_score >= min_confidence,
            Email.detected_company.isnot(None)
        ).all()
        
        created = []
        for email in emails:
            existing = db.query(Application).filter(
                Application.company_name.ilike(f"%{email.detected_company}%")
            ).first()
            
            if existing:
                email.application_id = existing.id
                email.is_processed = True
                if email.received_date > (existing.last_contact_date or existing.applied_date):
                    existing.last_contact_date = email.received_date
                if email.detected_status == 'rejected':
                    existing.status = ApplicationStatus.REJECTED
                    if email.rejected_at_stage:
                        existing.rejected_at_stage = email.rejected_at_stage
            else:
                if email.detected_status == 'rejected':
                    status = ApplicationStatus.REJECTED
                elif email.detected_status == 'offer_received':
                    status = ApplicationStatus.OFFER_RECEIVED
                elif email.detected_status in ['interview_scheduled', 'phone_screen']:
                    status = ApplicationStatus.PHONE_SCREEN
                else:
                    status = ApplicationStatus.APPLIED
                
                application = Application(
                    company_name=email.detected_company,
                    position_title=email.detected_position or 'Unknown Position',
                    status=status,
                    rejected_at_stage=email.rejected_at_stage if email.detected_status == 'rejected' else None,
                    applied_date=email.received_date,
                    recruiter_email=email.sender_email,
                    notes=f"Auto-created from email: {email.subject}"
                )
                db.add(application)
                db.flush()
                
                email.application_id = application.id
                email.is_processed = True
                created.append({
                    "company": email.detected_company,
                    "position": email.detected_position or 'Unknown',
                    "status": status.value
                })
        
        db.commit()
        
        return {
            "processed": len(emails),
            "created": len(created),
            "applications": created
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def list_applications(
    status: str = None,
    search: str = None,
    limit: int = 50
) -> list:
    """
    List job applications with optional filtering.
    
    Args:
        status: Filter by status (applied, phone_screen, rejected, offer_received, etc.)
        search: Search in company name or position
        limit: Maximum results (default 50)
    
    Returns:
        List of applications
    """
    db = get_db()
    try:
        query = db.query(Application)
        
        if status:
            try:
                status_enum = ApplicationStatus(status)
                query = query.filter(Application.status == status_enum)
            except ValueError:
                pass
        
        if search:
            search_term = f"%{search}%"
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    Application.company_name.ilike(search_term),
                    Application.position_title.ilike(search_term)
                )
            )
        
        applications = query.order_by(Application.applied_date.desc()).limit(limit).all()
        
        return [app.to_dict() for app in applications]
    finally:
        db.close()


@mcp.tool()
def get_application(application_id: int) -> dict:
    """
    Get detailed information about a specific application.
    
    Args:
        application_id: The application ID
    
    Returns:
        Application details including related emails
    """
    db = get_db()
    try:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return {"error": "Application not found"}
        
        result = application.to_dict()
        result['emails'] = [email.to_dict() for email in application.emails]
        result['reminders'] = [rem.to_dict() for rem in application.reminders]
        
        return result
    finally:
        db.close()


@mcp.tool()
def update_application_status(application_id: int, new_status: str, rejected_at_stage: str = None) -> dict:
    """
    Update the status of an application.
    
    Args:
        application_id: The application ID
        new_status: New status (applied, phone_screen, technical_interview, onsite_interview, 
                   final_interview, offer_received, offer_accepted, offer_declined, rejected, withdrawn)
        rejected_at_stage: Optional - stage where rejection happened (e.g., "After Phone Screen")
    
    Returns:
        Updated application
    """
    db = get_db()
    try:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return {"error": "Application not found"}
        
        try:
            application.status = ApplicationStatus(new_status)
            application.last_contact_date = datetime.now(timezone.utc)
            
            if new_status == 'rejected' and rejected_at_stage:
                application.rejected_at_stage = rejected_at_stage
            
            db.commit()
            return application.to_dict()
        except ValueError:
            return {"error": f"Invalid status: {new_status}"}
    finally:
        db.close()


@mcp.tool()
def add_application(
    company_name: str,
    position_title: str,
    status: str = "applied",
    job_url: str = None,
    location: str = None,
    notes: str = None
) -> dict:
    """
    Manually add a new job application.
    
    Args:
        company_name: Company name
        position_title: Job title/position
        status: Initial status (default "applied")
        job_url: Link to job posting
        location: Job location
        notes: Any notes about the application
    
    Returns:
        Created application
    """
    db = get_db()
    try:
        application = Application(
            company_name=company_name,
            position_title=position_title,
            status=ApplicationStatus(status),
            job_url=job_url,
            location=location,
            notes=notes,
            applied_date=datetime.now(timezone.utc)
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        
        return application.to_dict()
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def get_dashboard_stats() -> dict:
    """
    Get comprehensive job search statistics.
    
    Returns:
        Overview stats, status breakdown, response rates, and recent activity
    """
    db = get_db()
    try:
        return stats_service.get_dashboard_stats(db)
    finally:
        db.close()


@mcp.tool()
def get_job_search_summary() -> str:
    """
    Get a natural language summary of your job search progress.
    
    Returns:
        A formatted summary of your job search
    """
    db = get_db()
    try:
        stats = stats_service.get_dashboard_stats(db)
        
        overview = stats['overview']
        rates = stats['response_rates']
        
        # Build summary
        lines = [
            f"## Job Search Summary",
            f"",
            f"**Total Applications:** {overview['total_applications']}",
            f"**Active Applications:** {overview['active_applications']}",
            f"**Interviews:** {overview['interviews']}",
            f"**Offers:** {overview['offers']}",
            f"",
            f"### Response Rates",
            f"- Response Rate: {rates['response_rate']}%",
            f"- Interview Rate: {rates['interview_rate']}%",
            f"- Offer Rate: {rates['offer_rate']}%",
        ]
        
        if rates['avg_response_days']:
            lines.append(f"- Average Response Time: {rates['avg_response_days']} days")
        
        # Add status breakdown
        breakdown = stats['status_breakdown']
        active_statuses = [s for s in breakdown if s['count'] > 0]
        
        if active_statuses:
            lines.extend(["", "### Status Breakdown"])
            for status in active_statuses:
                lines.append(f"- {status['label']}: {status['count']}")
        
        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def create_followup_reminder(
    application_id: int,
    days_from_now: int = 7,
    message: str = None
) -> dict:
    """
    Create a follow-up reminder for an application.
    
    Args:
        application_id: The application ID
        days_from_now: Days until reminder (default 7)
        message: Custom reminder message
    
    Returns:
        Created reminder
    """
    db = get_db()
    try:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return {"error": "Application not found"}
        
        reminder = Reminder(
            application_id=application_id,
            reminder_date=datetime.now(timezone.utc) + timedelta(days=days_from_now),
            message=message or f"Follow up with {application.company_name}"
        )
        db.add(reminder)
        application.next_action_date = reminder.reminder_date
        
        db.commit()
        db.refresh(reminder)
        
        return reminder.to_dict()
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def get_due_reminders() -> list:
    """
    Get all reminders that are due today or overdue.
    
    Returns:
        List of due reminders
    """
    db = get_db()
    try:
        today_end = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
        
        reminders = db.query(Reminder).join(Application).filter(
            Reminder.is_completed == False,
            Reminder.is_dismissed == False,
            Reminder.reminder_date <= today_end
        ).order_by(Reminder.reminder_date.asc()).all()
        
        return [r.to_dict() for r in reminders]
    finally:
        db.close()


@mcp.tool()
def get_unprocessed_emails() -> dict:
    """
    Get emails that haven't been processed into applications yet.
    
    Returns:
        List of unprocessed job-related emails
    """
    db = get_db()
    try:
        emails = db.query(Email).filter(
            Email.is_job_related == True,
            Email.is_processed == False,
            Email.application_id.is_(None)
        ).order_by(Email.received_date.desc()).limit(50).all()
        
        return {
            "count": len(emails),
            "emails": [e.to_dict() for e in emails]
        }
    finally:
        db.close()


@mcp.tool()
def get_applications_needing_followup(days_inactive: int = 7) -> list:
    """
    Get applications that haven't had activity in a while and may need follow-up.
    
    Args:
        days_inactive: Days of inactivity to consider (default 7)
    
    Returns:
        List of applications needing follow-up
    """
    db = get_db()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)
        
        # Active statuses that might need follow-up
        active_statuses = [
            ApplicationStatus.APPLIED,
            ApplicationStatus.PHONE_SCREEN,
            ApplicationStatus.TECHNICAL_INTERVIEW,
            ApplicationStatus.ONSITE_INTERVIEW,
            ApplicationStatus.FINAL_INTERVIEW
        ]
        
        applications = db.query(Application).filter(
            Application.status.in_(active_statuses),
            Application.updated_at < cutoff_date
        ).order_by(Application.updated_at.asc()).all()
        
        return [app.to_dict() for app in applications]
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()

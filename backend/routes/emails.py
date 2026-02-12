"""Email scanning and management routes."""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone

from backend.models import SessionLocal, Email, Application, UserSettings, ApplicationStatus
from backend.services import gmail_service, email_parser
from backend.services.encryption import encrypt_token, decrypt_token

emails_bp = Blueprint('emails', __name__, url_prefix='/api/emails')


@emails_bp.route('/scan', methods=['POST'])
def scan_emails():
    """Scan Gmail for job-related emails."""
    data = request.json or {}
    days_back = data.get('days_back', 30)
    max_results = data.get('max_results', 100)
    
    db = SessionLocal()
    try:
        # Get OAuth tokens
        settings = db.query(UserSettings).first()
        if not settings or not settings.gmail_refresh_token:
            return jsonify({"error": "Gmail not connected"}), 401
        
        # Initialize Gmail service (decrypt tokens from DB)
        gmail_service.set_credentials(
            access_token=decrypt_token(settings.gmail_access_token or ''),
            refresh_token=decrypt_token(settings.gmail_refresh_token),
            expiry=settings.gmail_token_expiry
        )

        # Update tokens if refreshed (encrypt before saving)
        updated_tokens = gmail_service.get_updated_tokens()
        if updated_tokens:
            settings.gmail_access_token = encrypt_token(updated_tokens['access_token'])
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
        processed = []
        skipped_existing = 0
        skipped_dismissed = 0
        skipped_already_processed = 0
        
        for raw_email in raw_emails:
            # Check if already exists
            existing = db.query(Email).filter(
                Email.gmail_id == raw_email['gmail_id']
            ).first()
            
            if existing:
                # Track why it was skipped
                if existing.is_job_related == False:
                    skipped_dismissed += 1
                elif existing.is_processed:
                    skipped_already_processed += 1
                else:
                    skipped_existing += 1
                continue
            
            # Parse email
            parsed = email_parser.parse_email(raw_email)
            
            # Create email record
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
            processed.append(email)
        
        # Update last sync time
        settings.last_sync_date = datetime.now(timezone.utc)
        db.commit()
        
        return jsonify({
            "scanned": len(raw_emails),
            "new_emails": len(processed),
            "skipped": {
                "dismissed": skipped_dismissed,
                "already_processed": skipped_already_processed,
                "pending": skipped_existing
            },
            "emails": [e.to_dict() for e in processed[:20]]  # Return first 20
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@emails_bp.route('/unprocessed', methods=['GET'])
def get_unprocessed():
    """Get unprocessed job-related emails."""
    db = SessionLocal()
    try:
        emails = db.query(Email).filter(
            Email.is_job_related == True,
            Email.is_processed == False,
            Email.application_id.is_(None)
        ).order_by(Email.received_date.desc()).all()
        
        return jsonify({
            "count": len(emails),
            "emails": [e.to_dict() for e in emails]
        })
    finally:
        db.close()


@emails_bp.route('/<int:email_id>/link', methods=['POST'])
def link_to_application(email_id):
    """Link email to an application."""
    data = request.json
    application_id = data.get('application_id')
    
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        if application_id:
            application = db.query(Application).filter(
                Application.id == application_id
            ).first()
            if not application:
                return jsonify({"error": "Application not found"}), 404
            
            email.application_id = application_id
        
        email.is_processed = True
        db.commit()
        
        return jsonify(email.to_dict())
    finally:
        db.close()


@emails_bp.route('/<int:email_id>/create-application', methods=['POST'])
def create_from_email(email_id):
    """Create application from email data."""
    data = request.json or {}
    
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        company_name = data.get('company_name') or email.detected_company or 'Unknown Company'
        position_title = data.get('position_title') or email.detected_position or 'Unknown Position'
        applied_date = email.received_date
        
        # Determine status from email
        new_status = _get_status_from_email(email.detected_status)
        
        # Check for existing application (same company)
        existing = _find_duplicate_application(db, company_name, position_title, applied_date)
        
        if existing:
            # Link email to existing application
            email.application_id = existing.id
            email.is_processed = True
            
            # Check if this email indicates a status advancement
            update_info = _update_application_status(existing, new_status, email)
            
            db.commit()
            
            if update_info["updated"]:
                return jsonify({
                    "duplicate": True,
                    "status_updated": True,
                    "message": f"Updated existing application: {update_info['message']}",
                    "existing_application": existing.to_dict()
                }), 200
            else:
                return jsonify({
                    "duplicate": True,
                    "status_updated": False,
                    "message": f"Linked to existing application for {existing.company_name} - {existing.position_title}",
                    "existing_application": existing.to_dict()
                }), 200
        
        # Create new application
        application = Application(
            company_name=company_name,
            position_title=position_title,
            status=new_status,
            rejected_at_stage=email.rejected_at_stage if new_status == ApplicationStatus.REJECTED else None,
            applied_date=applied_date,
            recruiter_email=email.sender_email,
            notes=f"Created from email: {email.subject}"
        )
        
        db.add(application)
        db.flush()  # Get ID
        
        # Link email
        email.application_id = application.id
        email.is_processed = True
        
        db.commit()
        db.refresh(application)
        
        return jsonify(application.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


def _find_duplicate_application(db, company_name: str, position_title: str, applied_date) -> Application:
    """Find duplicate application by company+date or position+date."""
    from sqlalchemy import func, and_, or_
    
    # Normalize the date to just the date part (ignore time)
    if applied_date:
        date_only = applied_date.date() if hasattr(applied_date, 'date') else applied_date
        
        # Check for duplicates: same company name AND same date
        duplicate = db.query(Application).filter(
            and_(
                func.lower(Application.company_name) == company_name.lower(),
                func.date(Application.applied_date) == date_only
            )
        ).first()
        
        if duplicate:
            return duplicate
        
        # Also check: same position title AND same company (even if different date)
        if position_title and position_title != 'Unknown Position':
            duplicate = db.query(Application).filter(
                and_(
                    func.lower(Application.company_name) == company_name.lower(),
                    func.lower(Application.position_title) == position_title.lower()
                )
            ).first()
            
            if duplicate:
                return duplicate
        
        # Also check: just same company name (for status updates from same company)
        duplicate = db.query(Application).filter(
            func.lower(Application.company_name) == company_name.lower()
        ).order_by(Application.applied_date.desc()).first()
        
        if duplicate:
            return duplicate
    
    return None


# Status progression order (lower index = earlier stage)
STATUS_PROGRESSION = [
    ApplicationStatus.APPLIED,
    ApplicationStatus.NO_RESPONSE,
    ApplicationStatus.PHONE_SCREEN,
    ApplicationStatus.FIRST_INTERVIEW,
    ApplicationStatus.SECOND_INTERVIEW,
    ApplicationStatus.THIRD_INTERVIEW,
    ApplicationStatus.OFFER_RECEIVED,
    ApplicationStatus.OFFER_ACCEPTED,
]

# Terminal statuses (no progression from these)
TERMINAL_STATUSES = [
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.OFFER_DECLINED,
]


def _get_next_interview_status(current_status: ApplicationStatus) -> ApplicationStatus:
    """Get the next interview status in progression."""
    progression_map = {
        ApplicationStatus.APPLIED: ApplicationStatus.PHONE_SCREEN,
        ApplicationStatus.PROFILE_VIEWED: ApplicationStatus.PHONE_SCREEN,
        ApplicationStatus.NO_RESPONSE: ApplicationStatus.PHONE_SCREEN,
        ApplicationStatus.PHONE_SCREEN: ApplicationStatus.FIRST_INTERVIEW,
        ApplicationStatus.FIRST_INTERVIEW: ApplicationStatus.SECOND_INTERVIEW,
        ApplicationStatus.SECOND_INTERVIEW: ApplicationStatus.THIRD_INTERVIEW,
        ApplicationStatus.THIRD_INTERVIEW: ApplicationStatus.OFFER_RECEIVED,
    }
    return progression_map.get(current_status, current_status)


def _get_status_from_email(detected_status: str) -> ApplicationStatus:
    """Convert detected status string to ApplicationStatus enum."""
    status_map = {
        'rejected': ApplicationStatus.REJECTED,
        'offer_received': ApplicationStatus.OFFER_RECEIVED,
        'interview_scheduled': ApplicationStatus.FIRST_INTERVIEW,
        'phone_screen': ApplicationStatus.PHONE_SCREEN,
        'application_received': ApplicationStatus.APPLIED,
    }
    return status_map.get(detected_status, ApplicationStatus.APPLIED)


def _is_status_advancement(current_status: ApplicationStatus, new_status: ApplicationStatus) -> bool:
    """Check if new_status is an advancement from current_status."""
    # If current status is terminal, no advancement possible (except rejection can happen anytime)
    if current_status in TERMINAL_STATUSES:
        return False
    
    # Rejection is always a valid update (can happen at any stage)
    if new_status == ApplicationStatus.REJECTED:
        return True
    
    # Check if new status is further in the progression
    try:
        current_index = STATUS_PROGRESSION.index(current_status)
        new_index = STATUS_PROGRESSION.index(new_status)
        return new_index > current_index
    except ValueError:
        return False


def _update_application_status(application: Application, new_status: ApplicationStatus, email: Email) -> dict:
    """Update application status and return info about the update.
    
    Auto-advancement logic:
    - If email is NOT a rejection, auto-advance to next interview stage
    - If email IS a rejection, set status to rejected and record the stage
    """
    old_status = application.status
    
    update_info = {
        "updated": False,
        "old_status": old_status.value,
        "new_status": new_status.value,
        "message": ""
    }
    
    # If current status is terminal, no changes
    if old_status in TERMINAL_STATUSES:
        return update_info
    
    # Handle rejection
    if new_status == ApplicationStatus.REJECTED:
        application.status = ApplicationStatus.REJECTED
        application.last_contact_date = email.received_date
        
        # Set rejection stage based on current status
        if email.rejected_at_stage:
            application.rejected_at_stage = email.rejected_at_stage
        else:
            # Auto-determine rejection stage from current status
            rejection_stage_map = {
                ApplicationStatus.APPLIED: "Application/Resume Stage",
                ApplicationStatus.PROFILE_VIEWED: "Application/Resume Stage",
                ApplicationStatus.NO_RESPONSE: "Application/Resume Stage",
                ApplicationStatus.PHONE_SCREEN: "After Phone Screen",
                ApplicationStatus.FIRST_INTERVIEW: "After First Interview",
                ApplicationStatus.SECOND_INTERVIEW: "After Second Interview",
                ApplicationStatus.THIRD_INTERVIEW: "After Third Interview",
            }
            application.rejected_at_stage = rejection_stage_map.get(old_status, "Application/Resume Stage")
        
        update_info["updated"] = True
        update_info["new_status"] = ApplicationStatus.REJECTED.value
        update_info["message"] = f"Rejected at {application.rejected_at_stage}"
        return update_info
    
    # Handle offer
    if new_status == ApplicationStatus.OFFER_RECEIVED:
        if _is_status_advancement(old_status, new_status):
            application.status = new_status
            application.last_contact_date = email.received_date
            update_info["updated"] = True
            update_info["message"] = f"Advanced from {old_status.value.replace('_', ' ').title()} → Offer Received"
        return update_info
    
    # Auto-advance to next interview stage for non-rejection emails
    # Only advance if the email indicates interview activity (not just application received)
    if new_status in [ApplicationStatus.FIRST_INTERVIEW, ApplicationStatus.APPLIED]:
        # Get next status in progression
        next_status = _get_next_interview_status(old_status)
        
        if next_status != old_status:
            application.status = next_status
            application.last_contact_date = email.received_date
            update_info["updated"] = True
            update_info["new_status"] = next_status.value
            update_info["message"] = f"Auto-advanced from {old_status.value.replace('_', ' ').title()} → {next_status.value.replace('_', ' ').title()}"
    
    return update_info


@emails_bp.route('/<int:email_id>/dismiss', methods=['POST'])
def dismiss_email(email_id):
    """Mark email as not job-related."""
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return jsonify({"error": "Email not found"}), 404
        
        email.is_job_related = False
        email.is_processed = True
        db.commit()
        
        return jsonify({"success": True})
    finally:
        db.close()


@emails_bp.route('/auto-process', methods=['POST'])
def auto_process():
    """Automatically create applications from high-confidence emails."""
    data = request.json or {}
    min_confidence = data.get('min_confidence', 0.7)
    
    db = SessionLocal()
    try:
        # Get high-confidence unprocessed emails
        emails = db.query(Email).filter(
            Email.is_job_related == True,
            Email.is_processed == False,
            Email.application_id.is_(None),
            Email.confidence_score >= min_confidence,
            Email.detected_company.isnot(None)
        ).all()
        
        created = []
        linked_to_existing = []
        status_updated = []
        
        for email in emails:
            company_name = email.detected_company
            position_title = email.detected_position or 'Unknown Position'
            
            # Determine status from email
            new_status = _get_status_from_email(email.detected_status)
            
            # Check for existing application
            existing = _find_duplicate_application(db, company_name, position_title, email.received_date)
            
            if existing:
                # Link to existing application
                email.application_id = existing.id
                email.is_processed = True
                
                # Check if this email indicates a status advancement
                update_info = _update_application_status(existing, new_status, email)
                
                if update_info["updated"]:
                    status_updated.append({
                        "company": existing.company_name,
                        "position": existing.position_title,
                        "change": update_info["message"]
                    })
                else:
                    linked_to_existing.append({
                        "email_subject": email.subject,
                        "linked_to": f"{existing.company_name} - {existing.position_title}"
                    })
            else:
                # Create new application
                application = Application(
                    company_name=company_name,
                    position_title=position_title,
                    status=new_status,
                    rejected_at_stage=email.rejected_at_stage if new_status == ApplicationStatus.REJECTED else None,
                    applied_date=email.received_date,
                    recruiter_email=email.sender_email,
                    notes=f"Auto-created from email: {email.subject}"
                )
                db.add(application)
                db.flush()
                
                email.application_id = application.id
                email.is_processed = True
                created.append(application)
        
        db.commit()
        
        return jsonify({
            "processed": len(emails),
            "created": len(created),
            "linked_to_existing": len(linked_to_existing),
            "status_updated": len(status_updated),
            "updates_info": status_updated,
            "duplicates_info": linked_to_existing,
            "applications": [app.to_dict() for app in created]
        })
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

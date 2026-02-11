"""Interview management routes with Google Calendar integration."""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from backend.models import SessionLocal, Application, Interview, InterviewType, UserSettings
from backend.services.calendar_service import calendar_service
from backend.services.encryption import encrypt_token, decrypt_token

interviews_bp = Blueprint('interviews', __name__, url_prefix='/api/interviews')


def _get_calendar_credentials(db):
    """Get calendar credentials from user settings."""
    settings = db.query(UserSettings).first()
    if not settings or not settings.gmail_refresh_token:
        return None
    
    calendar_service.set_credentials(
        access_token=decrypt_token(settings.gmail_access_token),
        refresh_token=decrypt_token(settings.gmail_refresh_token),
        expiry=settings.gmail_token_expiry
    )

    # Update tokens if refreshed (encrypt before saving)
    updated_tokens = calendar_service.get_updated_tokens()
    if updated_tokens:
        settings.gmail_access_token = encrypt_token(updated_tokens['access_token'])
        if updated_tokens.get('expiry'):
            settings.gmail_token_expiry = datetime.fromisoformat(updated_tokens['expiry'])
        db.commit()
    
    return calendar_service


@interviews_bp.route('', methods=['GET'])
def get_interviews():
    """Get all interviews, optionally filtered by application."""
    application_id = request.args.get('application_id')
    upcoming_only = request.args.get('upcoming', 'false').lower() == 'true'
    
    db = SessionLocal()
    try:
        query = db.query(Interview)
        
        if application_id:
            query = query.filter(Interview.application_id == int(application_id))
        
        if upcoming_only:
            query = query.filter(
                Interview.scheduled_at >= datetime.utcnow(),
                Interview.is_cancelled == False
            )
        
        query = query.order_by(Interview.scheduled_at.asc())
        interviews = query.all()
        
        return jsonify({
            "interviews": [i.to_dict() for i in interviews]
        })
    finally:
        db.close()


@interviews_bp.route('/<int:interview_id>', methods=['GET'])
def get_interview(interview_id):
    """Get single interview details."""
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return jsonify({"error": "Interview not found"}), 404
        
        return jsonify(interview.to_dict())
    finally:
        db.close()


@interviews_bp.route('', methods=['POST'])
def create_interview():
    """Create new interview and optionally sync to Google Calendar."""
    data = request.json
    sync_to_calendar = data.get('sync_to_calendar', True)
    
    db = SessionLocal()
    try:
        # Validate application exists
        application = db.query(Application).filter(
            Application.id == data.get('application_id')
        ).first()
        
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        # Parse interview type
        interview_type = InterviewType.VIDEO_CALL
        if data.get('interview_type'):
            try:
                interview_type = InterviewType(data['interview_type'])
            except ValueError:
                pass
        
        # Parse scheduled time
        scheduled_at = datetime.fromisoformat(data['scheduled_at'].replace('Z', '+00:00'))
        duration = data.get('duration_minutes', 60)
        
        # Create interview record
        interview = Interview(
            application_id=application.id,
            interview_type=interview_type,
            title=data.get('title'),
            scheduled_at=scheduled_at,
            duration_minutes=duration,
            timezone=data.get('timezone', 'UTC'),
            location=data.get('location'),
            meeting_link=data.get('meeting_link'),
            interviewer_name=data.get('interviewer_name'),
            interviewer_email=data.get('interviewer_email'),
            interviewer_title=data.get('interviewer_title'),
            preparation_notes=data.get('preparation_notes')
        )
        
        db.add(interview)
        db.flush()  # Get the ID
        
        # Sync to Google Calendar if requested
        calendar_synced = False
        calendar_error = None
        
        if sync_to_calendar:
            try:
                cal_service = _get_calendar_credentials(db)
                if cal_service:
                    # Build event details
                    event_title = interview.title or f"Interview - {application.company_name} - {application.position_title}"
                    
                    interview_type_label = interview_type.value.replace('_', ' ').title()
                    description = f"""
Interview Type: {interview_type_label}
Company: {application.company_name}
Position: {application.position_title}
                    """.strip()
                    
                    if interview.interviewer_name:
                        description += f"\nInterviewer: {interview.interviewer_name}"
                    if interview.interviewer_title:
                        description += f" ({interview.interviewer_title})"
                    if interview.preparation_notes:
                        description += f"\n\nPreparation Notes:\n{interview.preparation_notes}"
                    
                    end_time = scheduled_at + timedelta(minutes=duration)
                    
                    # Create calendar event
                    event_result = cal_service.create_interview_event(
                        summary=event_title,
                        description=description,
                        start_time=scheduled_at,
                        end_time=end_time,
                        location=interview.meeting_link or interview.location,
                        attendees=[interview.interviewer_email] if interview.interviewer_email else None
                    )
                    
                    interview.calendar_event_id = event_result['id']
                    interview.calendar_event_link = event_result['html_link']
                    calendar_synced = True
                else:
                    calendar_error = "Google Calendar not connected"
                    
            except Exception as e:
                calendar_error = str(e)
        
        db.commit()
        db.refresh(interview)
        
        response = {
            "interview": interview.to_dict(),
            "calendar_synced": calendar_synced
        }
        
        if calendar_error:
            response["calendar_error"] = calendar_error
        
        return jsonify(response), 201
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@interviews_bp.route('/<int:interview_id>', methods=['PUT'])
def update_interview(interview_id):
    """Update interview details."""
    data = request.json
    sync_changes = data.get('sync_to_calendar', True)
    
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return jsonify({"error": "Interview not found"}), 404
        
        # Update fields
        if 'interview_type' in data:
            try:
                interview.interview_type = InterviewType(data['interview_type'])
            except ValueError:
                pass
        
        if 'title' in data:
            interview.title = data['title']
        if 'scheduled_at' in data:
            interview.scheduled_at = datetime.fromisoformat(data['scheduled_at'].replace('Z', '+00:00'))
        if 'duration_minutes' in data:
            interview.duration_minutes = data['duration_minutes']
        if 'timezone' in data:
            interview.timezone = data['timezone']
        if 'location' in data:
            interview.location = data['location']
        if 'meeting_link' in data:
            interview.meeting_link = data['meeting_link']
        if 'interviewer_name' in data:
            interview.interviewer_name = data['interviewer_name']
        if 'interviewer_email' in data:
            interview.interviewer_email = data['interviewer_email']
        if 'interviewer_title' in data:
            interview.interviewer_title = data['interviewer_title']
        if 'preparation_notes' in data:
            interview.preparation_notes = data['preparation_notes']
        if 'interview_notes' in data:
            interview.interview_notes = data['interview_notes']
        if 'is_completed' in data:
            interview.is_completed = data['is_completed']
        if 'outcome' in data:
            interview.outcome = data['outcome']
        
        # Sync changes to calendar if event exists
        calendar_synced = False
        if sync_changes and interview.calendar_event_id:
            try:
                cal_service = _get_calendar_credentials(db)
                if cal_service:
                    application = interview.application
                    event_title = interview.title or f"Interview - {application.company_name} - {application.position_title}"
                    end_time = interview.scheduled_at + timedelta(minutes=interview.duration_minutes)
                    
                    cal_service.update_event(
                        event_id=interview.calendar_event_id,
                        summary=event_title,
                        start_time=interview.scheduled_at,
                        end_time=end_time,
                        location=interview.meeting_link or interview.location
                    )
                    calendar_synced = True
            except Exception as e:
                print(f"Failed to update calendar event: {e}")
        
        db.commit()
        db.refresh(interview)
        
        return jsonify({
            "interview": interview.to_dict(),
            "calendar_synced": calendar_synced
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@interviews_bp.route('/<int:interview_id>', methods=['DELETE'])
def delete_interview(interview_id):
    """Delete interview and remove from Google Calendar."""
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return jsonify({"error": "Interview not found"}), 404
        
        # Delete from calendar if event exists
        if interview.calendar_event_id:
            try:
                cal_service = _get_calendar_credentials(db)
                if cal_service:
                    cal_service.delete_event(interview.calendar_event_id)
            except Exception as e:
                print(f"Failed to delete calendar event: {e}")
        
        db.delete(interview)
        db.commit()
        
        return jsonify({"success": True})
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@interviews_bp.route('/<int:interview_id>/cancel', methods=['POST'])
def cancel_interview(interview_id):
    """Cancel interview and update Google Calendar."""
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return jsonify({"error": "Interview not found"}), 404
        
        interview.is_cancelled = True
        
        # Delete from calendar if event exists
        if interview.calendar_event_id:
            try:
                cal_service = _get_calendar_credentials(db)
                if cal_service:
                    cal_service.delete_event(interview.calendar_event_id)
                    interview.calendar_event_id = None
                    interview.calendar_event_link = None
            except Exception as e:
                print(f"Failed to delete calendar event: {e}")
        
        db.commit()
        
        return jsonify({"interview": interview.to_dict()})
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@interviews_bp.route('/upcoming', methods=['GET'])
def get_upcoming_interviews():
    """Get all upcoming interviews across all applications."""
    limit = int(request.args.get('limit', 10))
    
    db = SessionLocal()
    try:
        interviews = db.query(Interview).filter(
            Interview.scheduled_at >= datetime.utcnow(),
            Interview.is_cancelled == False
        ).order_by(Interview.scheduled_at.asc()).limit(limit).all()
        
        return jsonify({
            "interviews": [i.to_dict() for i in interviews]
        })
    finally:
        db.close()


@interviews_bp.route('/<int:interview_id>/notes', methods=['PUT'])
def update_interview_notes(interview_id):
    """Update interview notes (preparation or post-interview)."""
    data = request.json
    
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return jsonify({"error": "Interview not found"}), 404
        
        # Basic notes
        if 'preparation_notes' in data:
            interview.preparation_notes = data['preparation_notes']
        if 'interview_notes' in data:
            interview.interview_notes = data['interview_notes']
        
        # Structured notes
        if 'questions_asked' in data:
            interview.questions_asked = data['questions_asked']
        if 'your_questions' in data:
            interview.your_questions = data['your_questions']
        if 'went_well' in data:
            interview.went_well = data['went_well']
        if 'to_improve' in data:
            interview.to_improve = data['to_improve']
        if 'follow_up_items' in data:
            interview.follow_up_items = data['follow_up_items']
        
        # Status
        if 'outcome' in data:
            interview.outcome = data['outcome']
        if 'is_completed' in data:
            interview.is_completed = data['is_completed']
        if 'confidence_rating' in data:
            interview.confidence_rating = int(data['confidence_rating']) if data['confidence_rating'] else None
        
        db.commit()
        db.refresh(interview)
        
        return jsonify({"interview": interview.to_dict()})
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

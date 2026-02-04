"""Application management routes."""
from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy import or_

from backend.models import SessionLocal, Application, Email, Reminder, ApplicationStatus

applications_bp = Blueprint('applications', __name__, url_prefix='/api/applications')


@applications_bp.route('', methods=['GET'])
def get_applications():
    """Get all applications with filtering and sorting."""
    # Query parameters
    status = request.args.get('status')
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'applied_date')
    sort_order = request.args.get('order', 'desc')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    db = SessionLocal()
    try:
        query = db.query(Application)
        
        # Filter by status
        if status:
            try:
                status_enum = ApplicationStatus(status)
                query = query.filter(Application.status == status_enum)
            except ValueError:
                pass
        
        # Search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Application.company_name.ilike(search_term),
                    Application.position_title.ilike(search_term),
                    Application.notes.ilike(search_term)
                )
            )
        
        # Sorting
        sort_column = getattr(Application, sort_by, Application.applied_date)
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Pagination
        total = query.count()
        applications = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return jsonify({
            "applications": [app.to_dict() for app in applications],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page
        })
    finally:
        db.close()


@applications_bp.route('/<int:app_id>', methods=['GET'])
def get_application(app_id):
    """Get single application with details."""
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == app_id).first()
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        result = application.to_dict()
        result['emails'] = [email.to_dict() for email in application.emails]
        result['reminders'] = [rem.to_dict() for rem in application.reminders]
        
        return jsonify(result)
    finally:
        db.close()


@applications_bp.route('', methods=['POST'])
def create_application():
    """Create new application."""
    data = request.json
    
    db = SessionLocal()
    try:
        status = ApplicationStatus(data.get('status', 'applied'))
        application = Application(
            company_name=data.get('company_name'),
            position_title=data.get('position_title'),
            job_url=data.get('job_url'),
            location=data.get('location'),
            salary_min=data.get('salary_min'),
            salary_max=data.get('salary_max'),
            status=status,
            rejected_at_stage=data.get('rejected_at_stage') if status == ApplicationStatus.REJECTED else None,
            applied_date=datetime.fromisoformat(data['applied_date']) if data.get('applied_date') else datetime.utcnow(),
            recruiter_name=data.get('recruiter_name'),
            recruiter_email=data.get('recruiter_email'),
            job_description=data.get('job_description'),
            notes=data.get('notes')
        )
        
        db.add(application)
        db.commit()
        db.refresh(application)
        
        return jsonify(application.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@applications_bp.route('/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    """Update existing application."""
    data = request.json
    
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == app_id).first()
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        # Get the new company name and position (for duplicate check)
        new_company = data.get('company_name', application.company_name)
        new_position = data.get('position_title', application.position_title)
        
        # Check for duplicate (another application with same company + position)
        from sqlalchemy import func, and_
        duplicate = db.query(Application).filter(
            and_(
                Application.id != app_id,  # Not the current application
                func.lower(Application.company_name) == new_company.lower(),
                func.lower(Application.position_title) == new_position.lower()
            )
        ).first()
        
        if duplicate:
            # Merge applications - keep the one with later updated_at
            merged_info = _merge_applications(db, application, duplicate, data)
            db.commit()
            
            return jsonify({
                "merged": True,
                "message": merged_info["message"],
                "application": merged_info["kept_application"].to_dict(),
                "deleted_id": merged_info["deleted_id"]
            })
        
        # No duplicate - normal update
        # Update fields
        updatable_fields = [
            'company_name', 'position_title', 'job_url', 'location',
            'salary_min', 'salary_max', 'recruiter_name', 'recruiter_email', 
            'job_description', 'notes'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(application, field, data[field])
        
        # Handle status separately
        if 'status' in data:
            try:
                application.status = ApplicationStatus(data['status'])
            except ValueError:
                pass
        
        # Handle rejected_at_stage - only set if status is rejected
        if 'rejected_at_stage' in data:
            if application.status == ApplicationStatus.REJECTED:
                application.rejected_at_stage = data['rejected_at_stage']
            else:
                application.rejected_at_stage = None
        
        # Handle dates
        date_fields = ['applied_date', 'last_contact_date', 'next_action_date']
        for field in date_fields:
            if field in data:
                value = data[field]
                if value:
                    setattr(application, field, datetime.fromisoformat(value))
                else:
                    setattr(application, field, None)
        
        db.commit()
        db.refresh(application)
        
        return jsonify(application.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


def _merge_applications(db, app1: Application, app2: Application, new_data: dict) -> dict:
    """Merge two applications into one, keeping the most recently updated."""
    # Determine which one to keep (the one with later updated_at)
    if app1.updated_at >= app2.updated_at:
        keep = app1
        delete = app2
    else:
        keep = app2
        delete = app1
    
    # Apply new data to the kept application
    updatable_fields = [
        'company_name', 'position_title', 'job_url', 'location',
        'salary_min', 'salary_max', 'recruiter_name', 'recruiter_email',
        'job_description', 'notes'
    ]
    
    for field in updatable_fields:
        if field in new_data:
            setattr(keep, field, new_data[field])
        elif getattr(delete, field) and not getattr(keep, field):
            # Copy non-empty fields from deleted app if kept app is empty
            setattr(keep, field, getattr(delete, field))
    
    # Handle status - keep the more advanced status
    if 'status' in new_data:
        try:
            keep.status = ApplicationStatus(new_data['status'])
        except ValueError:
            pass
    
    # Handle rejected_at_stage
    if 'rejected_at_stage' in new_data:
        if keep.status == ApplicationStatus.REJECTED:
            keep.rejected_at_stage = new_data['rejected_at_stage']
        else:
            keep.rejected_at_stage = None
    elif delete.rejected_at_stage and not keep.rejected_at_stage:
        keep.rejected_at_stage = delete.rejected_at_stage
    
    # Keep the earlier applied_date (always use the earliest, ignore form data for this field)
    all_applied_dates = [d for d in [delete.applied_date, keep.applied_date] if d]
    if all_applied_dates:
        keep.applied_date = min(all_applied_dates)
    
    # Handle other dates from new_data (but NOT applied_date - that's always the earliest)
    date_fields = ['last_contact_date', 'next_action_date']
    for field in date_fields:
        if field in new_data:
            value = new_data[field]
            if value:
                setattr(keep, field, datetime.fromisoformat(value))
    
    # Merge notes if both have them
    if delete.notes and keep.notes and delete.notes != keep.notes:
        keep.notes = f"{keep.notes}\n\n--- Merged from duplicate ---\n{delete.notes}"
    elif delete.notes and not keep.notes:
        keep.notes = delete.notes
    
    # Transfer emails from deleted application to kept one
    for email in delete.emails:
        email.application_id = keep.id
    
    # Transfer reminders from deleted application to kept one
    for reminder in delete.reminders:
        reminder.application_id = keep.id
    
    deleted_id = delete.id
    db.delete(delete)
    
    return {
        "kept_application": keep,
        "deleted_id": deleted_id,
        "message": f"Merged duplicate applications for {keep.company_name} - {keep.position_title}"
    }


@applications_bp.route('/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    """Delete application."""
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == app_id).first()
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        db.delete(application)
        db.commit()
        
        return jsonify({"success": True})
    finally:
        db.close()


@applications_bp.route('/<int:app_id>/status', methods=['PATCH'])
def update_status(app_id):
    """Quick status update."""
    data = request.json
    new_status = data.get('status')
    
    if not new_status:
        return jsonify({"error": "Status required"}), 400
    
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == app_id).first()
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        try:
            application.status = ApplicationStatus(new_status)
            application.last_contact_date = datetime.utcnow()
            db.commit()
            db.refresh(application)
            
            return jsonify(application.to_dict())
        except ValueError:
            return jsonify({"error": "Invalid status"}), 400
    finally:
        db.close()


@applications_bp.route('/bulk', methods=['POST'])
def bulk_create():
    """Bulk create applications from parsed emails."""
    data = request.json
    applications_data = data.get('applications', [])
    
    db = SessionLocal()
    try:
        created = []
        for app_data in applications_data:
            application = Application(
                company_name=app_data.get('company_name', 'Unknown Company'),
                position_title=app_data.get('position_title', 'Unknown Position'),
                status=ApplicationStatus.APPLIED,
                applied_date=datetime.fromisoformat(app_data['applied_date']) if app_data.get('applied_date') else datetime.utcnow(),
                notes=app_data.get('notes')
            )
            db.add(application)
            created.append(application)
        
        db.commit()
        
        return jsonify({
            "created": len(created),
            "applications": [app.to_dict() for app in created]
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@applications_bp.route('/scrape-job', methods=['POST'])
def scrape_job_description():
    """Scrape job description from a URL."""
    from backend.services.scraper_service import scraper_service
    
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    result = scraper_service.scrape_job_description(url)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

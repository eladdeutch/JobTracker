"""Reminder management routes."""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from backend.models import SessionLocal, Reminder, Application

reminders_bp = Blueprint('reminders', __name__, url_prefix='/api/reminders')


@reminders_bp.route('', methods=['GET'])
def get_reminders():
    """Get all reminders with filtering."""
    show_completed = request.args.get('completed', 'false').lower() == 'true'
    upcoming_only = request.args.get('upcoming', 'false').lower() == 'true'
    
    db = SessionLocal()
    try:
        query = db.query(Reminder).join(Application)
        
        if not show_completed:
            query = query.filter(
                Reminder.is_completed == False,
                Reminder.is_dismissed == False
            )
        
        if upcoming_only:
            query = query.filter(Reminder.reminder_date >= datetime.utcnow())
        
        reminders = query.order_by(Reminder.reminder_date.asc()).all()
        
        return jsonify({
            "reminders": [r.to_dict() for r in reminders]
        })
    finally:
        db.close()


@reminders_bp.route('/due', methods=['GET'])
def get_due_reminders():
    """Get reminders that are due today or overdue."""
    db = SessionLocal()
    try:
        # End of today
        today_end = datetime.utcnow().replace(hour=23, minute=59, second=59)
        
        reminders = db.query(Reminder).join(Application).filter(
            Reminder.is_completed == False,
            Reminder.is_dismissed == False,
            Reminder.reminder_date <= today_end
        ).order_by(Reminder.reminder_date.asc()).all()
        
        return jsonify({
            "count": len(reminders),
            "reminders": [r.to_dict() for r in reminders]
        })
    finally:
        db.close()


@reminders_bp.route('', methods=['POST'])
def create_reminder():
    """Create a new reminder."""
    data = request.json
    
    if not data.get('application_id') or not data.get('reminder_date'):
        return jsonify({"error": "application_id and reminder_date required"}), 400
    
    db = SessionLocal()
    try:
        # Verify application exists
        application = db.query(Application).filter(
            Application.id == data['application_id']
        ).first()
        
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        reminder = Reminder(
            application_id=data['application_id'],
            reminder_date=datetime.fromisoformat(data['reminder_date']),
            message=data.get('message', f'Follow up with {application.company_name}')
        )
        
        db.add(reminder)
        
        # Also update application's next action date
        application.next_action_date = reminder.reminder_date
        
        db.commit()
        db.refresh(reminder)
        
        return jsonify(reminder.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@reminders_bp.route('/<int:reminder_id>/complete', methods=['POST'])
def complete_reminder(reminder_id):
    """Mark reminder as completed."""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            return jsonify({"error": "Reminder not found"}), 404
        
        reminder.is_completed = True
        db.commit()
        
        return jsonify(reminder.to_dict())
    finally:
        db.close()


@reminders_bp.route('/<int:reminder_id>/dismiss', methods=['POST'])
def dismiss_reminder(reminder_id):
    """Dismiss reminder without completing."""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            return jsonify({"error": "Reminder not found"}), 404
        
        reminder.is_dismissed = True
        db.commit()
        
        return jsonify(reminder.to_dict())
    finally:
        db.close()


@reminders_bp.route('/<int:reminder_id>/snooze', methods=['POST'])
def snooze_reminder(reminder_id):
    """Snooze reminder to a later date."""
    data = request.json or {}
    days = data.get('days', 1)
    
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            return jsonify({"error": "Reminder not found"}), 404
        
        # Push reminder date forward
        new_date = datetime.utcnow() + timedelta(days=days)
        reminder.reminder_date = new_date
        
        # Update application's next action date
        if reminder.application:
            reminder.application.next_action_date = new_date
        
        db.commit()
        db.refresh(reminder)
        
        return jsonify(reminder.to_dict())
    finally:
        db.close()


@reminders_bp.route('/<int:reminder_id>', methods=['DELETE'])
def delete_reminder(reminder_id):
    """Delete a reminder."""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            return jsonify({"error": "Reminder not found"}), 404
        
        db.delete(reminder)
        db.commit()
        
        return jsonify({"success": True})
    finally:
        db.close()


@reminders_bp.route('/auto-create', methods=['POST'])
def auto_create_reminders():
    """Auto-create follow-up reminders for applications without recent activity."""
    data = request.json or {}
    days_inactive = data.get('days_inactive', 7)
    
    db = SessionLocal()
    try:
        # Find applications without recent activity and no pending reminders
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
        
        # Get application IDs with pending reminders
        apps_with_reminders = db.query(Reminder.application_id).filter(
            Reminder.is_completed == False,
            Reminder.is_dismissed == False
        ).subquery()
        
        # Get inactive applications without pending reminders
        applications = db.query(Application).filter(
            Application.status.in_([
                'applied', 'phone_screen', 'technical_interview', 
                'onsite_interview', 'final_interview'
            ]),
            Application.updated_at < cutoff_date,
            ~Application.id.in_(apps_with_reminders)
        ).all()
        
        created = []
        for app in applications:
            reminder = Reminder(
                application_id=app.id,
                reminder_date=datetime.utcnow() + timedelta(days=1),
                message=f"Follow up with {app.company_name} - no response in {days_inactive}+ days"
            )
            db.add(reminder)
            created.append(reminder)
            
            app.next_action_date = reminder.reminder_date
        
        db.commit()
        
        return jsonify({
            "created": len(created),
            "reminders": [r.to_dict() for r in created]
        })
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

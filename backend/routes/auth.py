"""Authentication routes for Gmail OAuth."""
from flask import Blueprint, request, jsonify, redirect, session
from datetime import datetime

from backend.services import gmail_service
from backend.models import SessionLocal, UserSettings

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/gmail/login', methods=['GET'])
def gmail_login():
    """Redirect to Gmail OAuth."""
    try:
        auth_url = gmail_service.get_auth_url()
        return jsonify({"auth_url": auth_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """Handle OAuth callback from Google."""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return redirect(f'/?auth_error={error}')
    
    if not code:
        return redirect('/?auth_error=no_code')
    
    try:
        # Exchange code for tokens
        tokens = gmail_service.exchange_code(code)
        
        # Store tokens in database
        db = SessionLocal()
        try:
            settings = db.query(UserSettings).first()
            if not settings:
                settings = UserSettings()
                db.add(settings)
            
            settings.gmail_access_token = tokens['access_token']
            settings.gmail_refresh_token = tokens['refresh_token']
            if tokens.get('expiry'):
                settings.gmail_token_expiry = datetime.fromisoformat(tokens['expiry'])
            
            db.commit()
        finally:
            db.close()
        
        return redirect('/?auth_success=true')
        
    except Exception as e:
        return redirect(f'/?auth_error={str(e)}')


@auth_bp.route('/gmail/status', methods=['GET'])
def gmail_status():
    """Check Gmail authentication status."""
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).first()
        is_connected = bool(settings and settings.gmail_refresh_token)
        
        return jsonify({
            "connected": is_connected,
            "last_sync": settings.last_sync_date.isoformat() if settings and settings.last_sync_date else None
        })
    finally:
        db.close()


@auth_bp.route('/gmail/disconnect', methods=['POST'])
def gmail_disconnect():
    """Disconnect Gmail account."""
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).first()
        if settings:
            settings.gmail_access_token = None
            settings.gmail_refresh_token = None
            settings.gmail_token_expiry = None
            db.commit()
        
        return jsonify({"success": True})
    finally:
        db.close()

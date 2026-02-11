"""Authentication routes for Gmail OAuth and app-level login."""
from flask import Blueprint, request, jsonify, redirect, session
from datetime import datetime

from backend.config import config
from backend.services import gmail_service
from backend.services.encryption import encrypt_token, decrypt_token
from backend.models import SessionLocal, UserSettings

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ------------------------------------------------------------------
# App-level authentication (session-based password)
# ------------------------------------------------------------------

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate with the application password."""
    if not config.APP_PASSWORD:
        # No password configured – auth is disabled
        return jsonify({"success": True, "auth_disabled": True})

    data = request.json or {}
    password = data.get('password', '')

    if password == config.APP_PASSWORD:
        session['authenticated'] = True
        return jsonify({"success": True})

    return jsonify({"error": "Invalid password"}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear the session."""
    session.clear()
    return jsonify({"success": True})


@auth_bp.route('/status', methods=['GET'])
def auth_status():
    """Return whether the user is currently authenticated."""
    if not config.APP_PASSWORD:
        return jsonify({"authenticated": True, "auth_required": False})
    return jsonify({
        "authenticated": session.get('authenticated', False),
        "auth_required": True,
    })


# ------------------------------------------------------------------
# Gmail OAuth
# ------------------------------------------------------------------

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
        tokens = gmail_service.exchange_code(code)

        db = SessionLocal()
        try:
            settings = db.query(UserSettings).first()
            if not settings:
                settings = UserSettings()
                db.add(settings)

            settings.gmail_access_token = encrypt_token(tokens['access_token'])
            settings.gmail_refresh_token = encrypt_token(tokens['refresh_token'])
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

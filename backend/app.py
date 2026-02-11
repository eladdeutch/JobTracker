"""Main Flask application."""
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, send_from_directory, jsonify, request, session
from flask_cors import CORS

from backend.config import config
from backend.models import init_db
from backend.routes import auth_bp, applications_bp, emails_bp, reminders_bp, stats_bp, interviews_bp


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__,
                static_folder='../frontend',
                static_url_path='')

    # Configuration
    app.secret_key = config.SECRET_KEY

    # CORS
    CORS(app, origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

    # Initialize database
    with app.app_context():
        init_db()

    # ------------------------------------------------------------------
    # Authentication middleware – protects /api/* routes when APP_PASSWORD
    # is configured. Auth endpoints and static files are always allowed.
    # ------------------------------------------------------------------
    PUBLIC_PREFIXES = ('/auth/', '/api/health')

    @app.before_request
    def require_auth():
        # Skip auth check when no password is configured
        if not config.APP_PASSWORD:
            return None

        path = request.path

        # Always allow: static files, auth endpoints, health check, OAuth callback
        if not path.startswith('/api/') and not path.startswith('/auth/'):
            return None
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        # Check session
        if not session.get('authenticated'):
            return jsonify({"error": "Authentication required"}), 401

        return None

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(emails_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(interviews_bp)

    # Serve frontend
    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        if os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')

    # Health check
    @app.route('/api/health')
    def health_check():
        return jsonify({"status": "ok", "version": "1.0.0"})

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    print(f"\n{'='*50}")
    print(f"Job Application Tracker running at http://{config.HOST}:{config.PORT}")
    if config.APP_PASSWORD:
        print("Authentication: ENABLED")
    else:
        print("Authentication: DISABLED (set APP_PASSWORD in .env)")
    if config.FERNET:
        print("Token encryption: ENABLED")
    else:
        print("Token encryption: DISABLED (set TOKEN_ENCRYPTION_KEY in .env)")
    print(f"{'='*50}\n")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )

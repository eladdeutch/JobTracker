"""Main Flask application."""
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, send_from_directory, jsonify
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
    print(f"\n🚀 Job Application Tracker running at http://{config.HOST}:{config.PORT}\n")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )

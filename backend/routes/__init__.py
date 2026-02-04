"""Routes package."""
from backend.routes.auth import auth_bp
from backend.routes.applications import applications_bp
from backend.routes.emails import emails_bp
from backend.routes.reminders import reminders_bp
from backend.routes.stats import stats_bp
from backend.routes.interviews import interviews_bp

__all__ = ['auth_bp', 'applications_bp', 'emails_bp', 'reminders_bp', 'stats_bp', 'interviews_bp']

"""Statistics and analytics routes."""
from flask import Blueprint, jsonify, request

from backend.models import SessionLocal
from backend.services import stats_service

stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')


@stats_bp.route('/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Get comprehensive dashboard statistics."""
    db = SessionLocal()
    try:
        stats = stats_service.get_dashboard_stats(db)
        return jsonify(stats)
    finally:
        db.close()


@stats_bp.route('/overview', methods=['GET'])
def get_overview():
    """Get overview statistics only."""
    db = SessionLocal()
    try:
        stats = stats_service._get_overview_stats(db)
        return jsonify(stats)
    finally:
        db.close()


@stats_bp.route('/status-breakdown', methods=['GET'])
def get_status_breakdown():
    """Get application count by status."""
    db = SessionLocal()
    try:
        breakdown = stats_service._get_status_breakdown(db)
        return jsonify({"breakdown": breakdown})
    finally:
        db.close()


@stats_bp.route('/timeline', methods=['GET'])
def get_timeline():
    """Get application timeline."""
    days = int(request.args.get('days', 30))
    
    db = SessionLocal()
    try:
        timeline = stats_service._get_timeline_stats(db, days=days)
        return jsonify({"timeline": timeline})
    finally:
        db.close()


@stats_bp.route('/response-rates', methods=['GET'])
def get_response_rates():
    """Get response rate statistics."""
    db = SessionLocal()
    try:
        rates = stats_service._get_response_rates(db)
        return jsonify(rates)
    finally:
        db.close()

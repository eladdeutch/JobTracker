"""Statistics and analytics service."""
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from backend.models import Application, Email, ApplicationStatus


class StatsService:
    """Service for calculating application statistics."""
    
    def get_dashboard_stats(self, db: Session) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics."""
        return {
            "overview": self._get_overview_stats(db),
            "status_breakdown": self._get_status_breakdown(db),
            "rejection_breakdown": self._get_rejection_breakdown(db),
            "interview_funnel": self._get_interview_funnel(db),
            "timeline": self._get_timeline_stats(db),
            "response_rates": self._get_response_rates(db),
            "recent_activity": self._get_recent_activity(db)
        }
    
    def _get_overview_stats(self, db: Session) -> Dict[str, Any]:
        """Get high-level overview statistics."""
        total = db.query(func.count(Application.id)).scalar() or 0
        
        # Active applications (not rejected, withdrawn, or offer_declined)
        inactive_statuses = [
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.OFFER_DECLINED,
            ApplicationStatus.OFFER_ACCEPTED
        ]
        active = db.query(func.count(Application.id)).filter(
            ~Application.status.in_(inactive_statuses)
        ).scalar() or 0
        
        # This week's applications
        week_ago = datetime.utcnow() - timedelta(days=7)
        this_week = db.query(func.count(Application.id)).filter(
            Application.applied_date >= week_ago
        ).scalar() or 0
        
        # Interviews scheduled
        interview_statuses = [
            ApplicationStatus.PHONE_SCREEN,
            ApplicationStatus.FIRST_INTERVIEW,
            ApplicationStatus.SECOND_INTERVIEW,
            ApplicationStatus.THIRD_INTERVIEW,
        ]
        interviews = db.query(func.count(Application.id)).filter(
            Application.status.in_(interview_statuses)
        ).scalar() or 0
        
        # Offers
        offers = db.query(func.count(Application.id)).filter(
            Application.status.in_([
                ApplicationStatus.OFFER_RECEIVED,
                ApplicationStatus.OFFER_ACCEPTED,
                ApplicationStatus.OFFER_DECLINED
            ])
        ).scalar() or 0
        
        # Rejected count
        rejected = db.query(func.count(Application.id)).filter(
            Application.status == ApplicationStatus.REJECTED
        ).scalar() or 0
        
        # Withdrawn count
        withdrawn = db.query(func.count(Application.id)).filter(
            Application.status == ApplicationStatus.WITHDRAWN
        ).scalar() or 0
        
        return {
            "total_applications": total,
            "active_applications": active,
            "this_week": this_week,
            "interviews": interviews,
            "offers": offers,
            "rejected": rejected,
            "withdrawn": withdrawn
        }
    
    def _get_status_breakdown(self, db: Session) -> List[Dict[str, Any]]:
        """Get application count by status."""
        results = db.query(
            Application.status,
            func.count(Application.id).label('count')
        ).group_by(Application.status).all()
        
        # Create full breakdown with all statuses
        status_counts = {status: 0 for status in ApplicationStatus}
        for status, count in results:
            if status:
                status_counts[status] = count
        
        return [
            {
                "status": status.value,
                "label": self._format_status_label(status),
                "count": count,
                "color": self._get_status_color(status)
            }
            for status, count in status_counts.items()
        ]
    
    def _get_rejection_breakdown(self, db: Session) -> Dict[str, Any]:
        """Get breakdown of rejections by stage."""
        # Total rejected applications
        total_rejected = db.query(func.count(Application.id)).filter(
            Application.status == ApplicationStatus.REJECTED
        ).scalar() or 0
        
        # Breakdown by rejected_at_stage
        results = db.query(
            Application.rejected_at_stage,
            func.count(Application.id).label('count')
        ).filter(
            Application.status == ApplicationStatus.REJECTED
        ).group_by(Application.rejected_at_stage).all()
        
        stages = []
        for stage, count in results:
            stage_name = stage if stage else "Not specified"
            stages.append({
                "stage": stage_name,
                "count": count,
                "percentage": round((count / total_rejected) * 100, 1) if total_rejected > 0 else 0
            })
        
        # Sort by count descending
        stages.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            "total_rejected": total_rejected,
            "by_stage": stages
        }
    
    def _get_interview_funnel(self, db: Session) -> List[Dict[str, Any]]:
        """Get interview funnel showing drop-off at each stage."""
        total = db.query(func.count(Application.id)).scalar() or 0
        
        if total == 0:
            return []
        
        # Define the funnel stages in order
        funnel_stages = [
            ("Applied", [ApplicationStatus.APPLIED, ApplicationStatus.PROFILE_VIEWED, ApplicationStatus.NO_RESPONSE]),
            ("Phone Screen", [ApplicationStatus.PHONE_SCREEN]),
            ("First Interview", [ApplicationStatus.FIRST_INTERVIEW]),
            ("Second Interview", [ApplicationStatus.SECOND_INTERVIEW]),
            ("Third Interview", [ApplicationStatus.THIRD_INTERVIEW]),
            ("Offer", [ApplicationStatus.OFFER_RECEIVED, ApplicationStatus.OFFER_ACCEPTED, ApplicationStatus.OFFER_DECLINED])
        ]
        
        # Count rejections at each stage
        rejection_stages_map = {
            "Application/Resume Stage": "Applied",
            "After Phone Screen": "Phone Screen",
            "After First Interview": "First Interview",
            "After Second Interview": "Second Interview",
            "After Third Interview": "Third Interview",
            "After Offer Negotiation": "Offer"
        }
        
        # Get rejection counts by stage
        rejection_results = db.query(
            Application.rejected_at_stage,
            func.count(Application.id).label('count')
        ).filter(
            Application.status == ApplicationStatus.REJECTED,
            Application.rejected_at_stage.isnot(None)
        ).group_by(Application.rejected_at_stage).all()
        
        rejection_by_stage = {}
        for stage, count in rejection_results:
            mapped_stage = rejection_stages_map.get(stage, "Applied")
            rejection_by_stage[mapped_stage] = rejection_by_stage.get(mapped_stage, 0) + count
        
        # Count withdrawn
        withdrawn = db.query(func.count(Application.id)).filter(
            Application.status == ApplicationStatus.WITHDRAWN
        ).scalar() or 0
        
        # Calculate funnel data
        funnel = []
        cumulative_reached = total
        
        for stage_name, statuses in funnel_stages:
            # Count currently at this stage
            at_stage = db.query(func.count(Application.id)).filter(
                Application.status.in_(statuses)
            ).scalar() or 0
            
            # Rejections at this stage
            rejected_at = rejection_by_stage.get(stage_name, 0)
            
            # Count applications that reached this stage or beyond
            # (current at stage + those who moved past + rejected at this stage)
            stage_index = [s[0] for s in funnel_stages].index(stage_name)
            later_stages = funnel_stages[stage_index + 1:] if stage_index < len(funnel_stages) - 1 else []
            
            reached_count = at_stage + rejected_at
            for later_name, later_statuses in later_stages:
                reached_count += db.query(func.count(Application.id)).filter(
                    Application.status.in_(later_statuses)
                ).scalar() or 0
                reached_count += rejection_by_stage.get(later_name, 0)
            
            funnel.append({
                "stage": stage_name,
                "reached": reached_count,
                "current": at_stage,
                "rejected_here": rejected_at,
                "percentage_of_total": round((reached_count / total) * 100, 1) if total > 0 else 0
            })
        
        return funnel

    def _get_timeline_stats(self, db: Session, days: int = 30) -> List[Dict[str, Any]]:
        """Get application timeline for the past N days."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        results = db.query(
            func.date(Application.applied_date).label('date'),
            func.count(Application.id).label('count')
        ).filter(
            Application.applied_date >= start_date
        ).group_by(
            func.date(Application.applied_date)
        ).order_by('date').all()
        
        # Fill in missing dates
        date_counts = {r.date: r.count for r in results}
        timeline = []
        current_date = start_date.date()
        
        while current_date <= datetime.utcnow().date():
            timeline.append({
                "date": current_date.isoformat(),
                "count": date_counts.get(current_date, 0)
            })
            current_date += timedelta(days=1)
        
        return timeline
    
    def _get_response_rates(self, db: Session) -> Dict[str, Any]:
        """Calculate response rate statistics."""
        total = db.query(func.count(Application.id)).scalar() or 0
        
        if total == 0:
            return {
                "response_rate": 0,
                "interview_rate": 0,
                "offer_rate": 0,
                "avg_response_days": None
            }
        
        # Applications with any response (not just applied/no_response)
        responded = db.query(func.count(Application.id)).filter(
            ~Application.status.in_([
                ApplicationStatus.APPLIED,
                ApplicationStatus.NO_RESPONSE
            ])
        ).scalar() or 0
        
        # Interview rate
        interview_statuses = [
            ApplicationStatus.PHONE_SCREEN,
            ApplicationStatus.FIRST_INTERVIEW,
            ApplicationStatus.SECOND_INTERVIEW,
            ApplicationStatus.THIRD_INTERVIEW,
            ApplicationStatus.OFFER_RECEIVED,
            ApplicationStatus.OFFER_ACCEPTED,
            ApplicationStatus.OFFER_DECLINED
        ]
        interviews = db.query(func.count(Application.id)).filter(
            Application.status.in_(interview_statuses)
        ).scalar() or 0
        
        # Offer rate
        offers = db.query(func.count(Application.id)).filter(
            Application.status.in_([
                ApplicationStatus.OFFER_RECEIVED,
                ApplicationStatus.OFFER_ACCEPTED,
                ApplicationStatus.OFFER_DECLINED
            ])
        ).scalar() or 0
        
        # Average days to response
        apps_with_response = db.query(Application).filter(
            Application.last_contact_date.isnot(None),
            Application.applied_date.isnot(None)
        ).all()
        
        avg_days = None
        if apps_with_response:
            total_days = sum(
                (app.last_contact_date - app.applied_date).days 
                for app in apps_with_response
            )
            avg_days = round(total_days / len(apps_with_response), 1)
        
        return {
            "response_rate": round((responded / total) * 100, 1),
            "interview_rate": round((interviews / total) * 100, 1),
            "offer_rate": round((offers / total) * 100, 1),
            "avg_response_days": avg_days
        }
    
    def _get_recent_activity(self, db: Session, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent application activity."""
        applications = db.query(Application).order_by(
            Application.updated_at.desc()
        ).limit(limit).all()
        
        return [app.to_dict() for app in applications]
    
    def _format_status_label(self, status: ApplicationStatus) -> str:
        """Format status enum to readable label."""
        labels = {
            ApplicationStatus.APPLIED: "Applied",
            ApplicationStatus.PROFILE_VIEWED: "Profile Viewed",
            ApplicationStatus.PHONE_SCREEN: "Phone Screen",
            ApplicationStatus.FIRST_INTERVIEW: "1st Interview",
            ApplicationStatus.SECOND_INTERVIEW: "2nd Interview",
            ApplicationStatus.THIRD_INTERVIEW: "3rd Interview",
            ApplicationStatus.OFFER_RECEIVED: "Offer Received",
            ApplicationStatus.OFFER_ACCEPTED: "Offer Accepted",
            ApplicationStatus.OFFER_DECLINED: "Offer Declined",
            ApplicationStatus.REJECTED: "Rejected",
            ApplicationStatus.WITHDRAWN: "Withdrawn",
            ApplicationStatus.NO_RESPONSE: "No Response"
        }
        return labels.get(status, status.value.replace('_', ' ').title())
    
    def _get_status_color(self, status: ApplicationStatus) -> str:
        """Get color for status visualization."""
        colors = {
            ApplicationStatus.APPLIED: "#3B82F6",  # Blue
            ApplicationStatus.PROFILE_VIEWED: "#0EA5E9",  # Sky blue
            ApplicationStatus.PHONE_SCREEN: "#6366F1",  # Indigo
            ApplicationStatus.FIRST_INTERVIEW: "#8B5CF6",  # Purple
            ApplicationStatus.SECOND_INTERVIEW: "#A855F7",  # Light purple
            ApplicationStatus.THIRD_INTERVIEW: "#EC4899",  # Pink
            ApplicationStatus.OFFER_RECEIVED: "#22C55E",  # Green
            ApplicationStatus.OFFER_ACCEPTED: "#10B981",  # Emerald
            ApplicationStatus.OFFER_DECLINED: "#6B7280",  # Gray
            ApplicationStatus.REJECTED: "#EF4444",  # Red
            ApplicationStatus.WITHDRAWN: "#9CA3AF",  # Light gray
            ApplicationStatus.NO_RESPONSE: "#F59E0B"  # Amber
        }
        return colors.get(status, "#6B7280")


stats_service = StatsService()

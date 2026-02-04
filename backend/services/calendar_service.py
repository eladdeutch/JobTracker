"""Google Calendar API integration service."""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import config


class CalendarService:
    """Service for interacting with Google Calendar API."""
    
    def __init__(self):
        self.credentials: Optional[Credentials] = None
        self.service = None
    
    def set_credentials(self, access_token: str, refresh_token: str, expiry: Optional[datetime] = None):
        """Set credentials from stored tokens."""
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=config.GOOGLE_CLIENT_ID,
            client_secret=config.GOOGLE_CLIENT_SECRET,
            expiry=expiry
        )
        
        # Refresh if expired
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
        
        self.service = build('calendar', 'v3', credentials=self.credentials)
    
    def get_updated_tokens(self) -> Optional[Dict[str, Any]]:
        """Get updated tokens after refresh."""
        if self.credentials:
            return {
                "access_token": self.credentials.token,
                "refresh_token": self.credentials.refresh_token,
                "expiry": self.credentials.expiry.isoformat() if self.credentials.expiry else None
            }
        return None
    
    def create_interview_event(
        self,
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        reminders_minutes: List[int] = [30, 10]
    ) -> Dict[str, Any]:
        """
        Create a calendar event for an interview.
        
        Args:
            summary: Event title (e.g., "Interview - Google - Software Engineer")
            description: Event description with details
            start_time: Interview start time
            end_time: Interview end time
            location: Meeting location or video link
            attendees: List of attendee email addresses
            reminders_minutes: List of reminder times in minutes before event
            
        Returns:
            Created event details including event ID
        """
        if not self.service:
            raise ValueError("Calendar service not initialized. Call set_credentials first.")
        
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': minutes}
                    for minutes in reminders_minutes
                ],
            },
        }
        
        if location:
            event['location'] = location
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        try:
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event,
                sendUpdates='all' if attendees else 'none'
            ).execute()
            
            return {
                'id': created_event.get('id'),
                'html_link': created_event.get('htmlLink'),
                'summary': created_event.get('summary'),
                'start': created_event.get('start'),
                'end': created_event.get('end'),
                'status': 'created'
            }
            
        except HttpError as error:
            raise Exception(f"Failed to create calendar event: {error}")
    
    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing calendar event."""
        if not self.service:
            raise ValueError("Calendar service not initialized.")
        
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            # Update fields
            if summary:
                event['summary'] = summary
            if description:
                event['description'] = description
            if start_time:
                event['start'] = {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'}
            if end_time:
                event['end'] = {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'}
            if location:
                event['location'] = location
            
            updated_event = self.service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event
            ).execute()
            
            return {
                'id': updated_event.get('id'),
                'html_link': updated_event.get('htmlLink'),
                'status': 'updated'
            }
            
        except HttpError as error:
            raise Exception(f"Failed to update calendar event: {error}")
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        if not self.service:
            raise ValueError("Calendar service not initialized.")
        
        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            return True
            
        except HttpError as error:
            if error.resp.status == 404:
                return True  # Already deleted
            raise Exception(f"Failed to delete calendar event: {error}")
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a calendar event by ID."""
        if not self.service:
            raise ValueError("Calendar service not initialized.")
        
        try:
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            return {
                'id': event.get('id'),
                'summary': event.get('summary'),
                'description': event.get('description'),
                'start': event.get('start'),
                'end': event.get('end'),
                'location': event.get('location'),
                'html_link': event.get('htmlLink'),
                'status': event.get('status')
            }
            
        except HttpError as error:
            if error.resp.status == 404:
                return None
            raise Exception(f"Failed to get calendar event: {error}")
    
    def list_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """List upcoming calendar events."""
        if not self.service:
            raise ValueError("Calendar service not initialized.")
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            return [
                {
                    'id': event.get('id'),
                    'summary': event.get('summary'),
                    'start': event.get('start'),
                    'end': event.get('end'),
                    'location': event.get('location'),
                    'html_link': event.get('htmlLink')
                }
                for event in events
            ]
            
        except HttpError as error:
            raise Exception(f"Failed to list calendar events: {error}")


# Singleton instance
calendar_service = CalendarService()

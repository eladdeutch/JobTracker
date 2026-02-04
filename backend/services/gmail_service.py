"""Gmail API integration service."""
import base64
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from email.utils import parsedate_to_datetime

# Allow OAuth scope changes (Google may return additional granted scopes)
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import config


class GmailService:
    """Service for interacting with Gmail API."""
    
    def __init__(self):
        self.scopes = config.GMAIL_SCOPES
        self.credentials: Optional[Credentials] = None
        self.service = None
    
    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL."""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [config.GOOGLE_REDIRECT_URI]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = config.GOOGLE_REDIRECT_URI
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return auth_url
    
    def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [config.GOOGLE_REDIRECT_URI]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = config.GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
    
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
        
        self.service = build('gmail', 'v1', credentials=self.credentials)
    
    def get_updated_tokens(self) -> Optional[Dict[str, Any]]:
        """Get updated tokens after refresh."""
        if self.credentials:
            return {
                "access_token": self.credentials.token,
                "refresh_token": self.credentials.refresh_token,
                "expiry": self.credentials.expiry.isoformat() if self.credentials.expiry else None
            }
        return None
    
    def search_emails(
        self, 
        query: str = "", 
        max_results: int = 100,
        after_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Search for emails matching query."""
        if not self.service:
            raise ValueError("Gmail service not initialized. Call set_credentials first.")
        
        # Build search query
        search_query = query
        if after_date:
            date_str = after_date.strftime("%Y/%m/%d")
            search_query = f"{search_query} after:{date_str}".strip()
        
        # Add job-related keywords if no query specified
        if not query:
            keyword_query = " OR ".join([f'"{kw}"' for kw in config.JOB_KEYWORDS[:10]])
            search_query = f"({keyword_query}) {search_query}".strip()
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=search_query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages:
                email_data = self.get_email_details(msg['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            print(f"Gmail API error: {error}")
            return []
    
    def get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed email information."""
        if not self.service:
            return None
        
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message.get('payload', {}).get('headers', [])
            
            # Extract header values
            subject = ""
            sender = ""
            date_str = ""
            
            for header in headers:
                name = header.get('name', '').lower()
                if name == 'subject':
                    subject = header.get('value', '')
                elif name == 'from':
                    sender = header.get('value', '')
                elif name == 'date':
                    date_str = header.get('value', '')
            
            # Parse sender email
            sender_email = ""
            email_match = re.search(r'<(.+?)>', sender)
            if email_match:
                sender_email = email_match.group(1)
            elif '@' in sender:
                sender_email = sender.strip()
            
            # Parse date
            received_date = None
            if date_str:
                try:
                    received_date = parsedate_to_datetime(date_str)
                except Exception:
                    received_date = datetime.utcnow()
            
            # Get snippet and body preview
            snippet = message.get('snippet', '')
            body_preview = self._extract_body_preview(message.get('payload', {}))
            
            return {
                "gmail_id": message_id,
                "thread_id": message.get('threadId'),
                "subject": subject,
                "sender": sender,
                "sender_email": sender_email,
                "received_date": received_date,
                "snippet": snippet,
                "body_preview": body_preview
            }
            
        except HttpError as error:
            print(f"Error fetching email {message_id}: {error}")
            return None
    
    def _extract_body_preview(self, payload: Dict, max_length: int = 1000) -> str:
        """Extract text body preview from email payload."""
        body = ""
        
        # Check for direct body
        if 'body' in payload and payload['body'].get('data'):
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        
        # Check parts
        elif 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain' and part.get('body', {}).get('data'):
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
                elif 'parts' in part:
                    # Nested parts
                    body = self._extract_body_preview(part, max_length)
                    if body:
                        break
        
        # Clean and truncate
        body = re.sub(r'\s+', ' ', body).strip()
        return body[:max_length] if body else ""


gmail_service = GmailService()

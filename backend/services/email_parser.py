"""Email parsing service for extracting job application data."""
import re
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from backend.config import config


class EmailParser:
    """Parse emails to extract job application information."""
    
    # Common job title patterns
    JOB_TITLE_PATTERNS = [
        r'(?:position|role|job|opening)\s*(?:of|for|as|:)?\s*["\']?([A-Z][A-Za-z\s\-\/]+(?:Engineer|Developer|Manager|Designer|Analyst|Director|Lead|Architect|Specialist|Coordinator|Associate|Intern))',
        r'(?:Software|Senior|Junior|Staff|Principal|Lead|Full[\s-]?Stack|Front[\s-]?End|Back[\s-]?End|Data|ML|Machine Learning|AI|DevOps|Cloud|Platform|Product|Project|Program|QA|Test|Security|Network|Systems?|IT|Web|Mobile|iOS|Android|UX|UI)\s*[A-Za-z\s\-]*(?:Engineer|Developer|Manager|Designer|Analyst|Architect|Specialist|Lead)',
        r'(?:applying|applied|application)\s+(?:for|to)\s+(?:the\s+)?(?:position\s+(?:of\s+)?)?["\']?([A-Z][A-Za-z\s\-\/]+)',
    ]
    
    # Status detection patterns
    STATUS_PATTERNS = {
        'rejected': [
            r'unfortunately',
            r'regret\s+to\s+inform',
            r'not\s+(?:be\s+)?mov(?:ing|ed)\s+forward',
            r'decided\s+(?:to\s+)?(?:not\s+)?(?:proceed|continue)',
            r'we\s+have\s+decided\s+not\s+to\s+proceed',
            r'not\s+to\s+proceed\s+with\s+your\s+application',
            r'position\s+has\s+been\s+filled',
            r'other\s+candidates',
            r'not\s+selected',
            r'will\s+not\s+be\s+(?:proceeding|continuing)',
            r'we\s+(?:will\s+)?not\s+be\s+(?:moving|going)\s+forward',
            r'after\s+careful\s+(?:review|consideration)',
            r'(?:has|have)\s+been\s+filled',
            r'pursue\s+other\s+candidates',
            r'won\'?t\s+be\s+(?:moving|proceeding)',
            r'no\s+longer\s+(?:being\s+)?consider',
            r'not\s+a\s+(?:good\s+)?(?:fit|match)',
            r'decided\s+to\s+go\s+(?:in\s+)?a(?:nother)?\s+(?:different\s+)?direction',
            r'your\s+application\s+(?:was|has\s+been)\s+(?:unsuccessful|rejected)',
            r'unable\s+to\s+offer\s+you',
            r'not\s+be\s+able\s+to\s+offer',
        ],
        'interview_scheduled': [
            r'schedule\s+(?:a|an|your)?\s*(?:phone|video|virtual|in-person|onsite|on-site)?\s*(?:screen|interview|call)',
            r'interview\s+(?:is\s+)?(?:scheduled|confirmed)',
            r'invite\s+you\s+(?:to|for)\s+(?:a|an)?\s*interview',
            r'like\s+to\s+(?:schedule|set\s+up)\s+(?:a|an)?\s*(?:time|call|interview)',
            r'next\s+(?:step|round|stage)',
            r'move\s+(?:you\s+)?forward',
            r'proceed\s+(?:with|to)',
        ],
        'phone_screen': [
            r'phone\s+(?:screen|call|interview)',
            r'initial\s+(?:screen|call|conversation)',
            r'recruiter\s+(?:screen|call)',
            r'15|20|30\s*(?:-|–)?\s*minute\s+(?:call|chat|conversation)',
        ],
        'offer_received': [
            r'pleased\s+to\s+(?:offer|extend)',
            r'offer\s+(?:letter|of\s+employment)',
            r'job\s+offer',
            r'would\s+like\s+to\s+offer\s+you',
            r'congratulations.*(?:offer|position)',
            r'we(?:\'d|\s+would)\s+like\s+(?:to\s+)?(?:have|bring)\s+you',
        ],
        'application_received': [
            r'application\s+(?:has\s+been\s+)?received',
            r'thank\s+you\s+for\s+(?:your\s+)?(?:interest|applying|application)',
            r'confirm(?:ing|ation)?\s+(?:that\s+)?(?:we\s+)?(?:have\s+)?received',
            r'successfully\s+(?:submitted|received)',
        ],
    }
    
    # Rejection stage detection patterns
    REJECTION_STAGE_PATTERNS = {
        'After Application Review': [
            r'after\s+(?:reviewing|review\s+of)\s+your\s+(?:application|resume|cv)',
            r'initial\s+(?:review|screening)',
            r'application\s+(?:review|screening)',
            r'resume\s+(?:review|screening)',
            r'reviewed\s+your\s+(?:application|resume|background)',
        ],
        'After Phone Screen': [
            r'after\s+(?:your|the|our)\s+(?:phone|initial)\s+(?:screen|call|interview|conversation)',
            r'following\s+(?:your|the|our)\s+(?:phone|initial)\s+(?:screen|call|interview)',
            r'phone\s+(?:screen|interview)',
            r'initial\s+(?:call|conversation|chat)',
            r'recruiter\s+(?:call|screen|conversation)',
        ],
        'After Technical Interview': [
            r'after\s+(?:your|the)\s+technical\s+(?:interview|assessment|screen)',
            r'following\s+(?:your|the)\s+technical',
            r'technical\s+(?:interview|round|assessment)',
            r'coding\s+(?:interview|challenge|assessment)',
            r'take[\s-]?home\s+(?:assignment|test|project)',
        ],
        'After Onsite Interview': [
            r'after\s+(?:your|the)\s+(?:onsite|on-site|in-person|virtual\s+onsite)',
            r'following\s+(?:your|the)\s+(?:onsite|on-site|in-person)',
            r'onsite\s+(?:interview|round)',
            r'on-site\s+(?:interview|round)',
            r'final\s+round',
            r'team\s+interview',
        ],
        'After Final Interview': [
            r'after\s+(?:your|the)\s+final\s+(?:interview|round)',
            r'following\s+(?:your|the)\s+final',
            r'final\s+(?:interview|round|stage)',
            r'(?:executive|leadership|hiring\s+manager)\s+interview',
        ],
    }
    
    # Company extraction patterns
    COMPANY_PATTERNS = [
        r'(?:at|from|with)\s+([A-Z][A-Za-z0-9\s\&\.\,]+?)(?:\s+(?:Inc|LLC|Ltd|Corp|Corporation|Company|Co|Group|Technologies|Tech|Labs|Solutions|Services|Systems|Software|Digital|Media|Health|Healthcare|Finance|Financial|Bank|Insurance|Consulting|Partners|Ventures|Capital|Entertainment|Studios|Games|Interactive|Analytics|Networks|Communications|Therapeutics|Pharmaceuticals|Biotech|Bio|Robotics|Automotive|Motors|Energy|Power|Electric|Aerospace|Defense|Security|Global|International|Worldwide|Americas|USA|US|NA|EMEA|APAC)\.?)?(?:\s|$|,|\.)',
        r'(?:^|\s)([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,3})\s+(?:is\s+)?(?:hiring|recruiting|looking)',
        r'(?:team|company|organization)\s+at\s+([A-Z][A-Za-z0-9\s\&]+)',
        r'(?:careers?|jobs?|talent)\s*@\s*([A-Za-z0-9]+)',
    ]
    
    def __init__(self):
        self.compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, Any]:
        """Pre-compile regex patterns for efficiency."""
        compiled = {
            'job_titles': [re.compile(p, re.IGNORECASE) for p in self.JOB_TITLE_PATTERNS],
            'companies': [re.compile(p, re.IGNORECASE) for p in self.COMPANY_PATTERNS],
            'statuses': {
                status: [re.compile(p, re.IGNORECASE) for p in patterns]
                for status, patterns in self.STATUS_PATTERNS.items()
            },
            'rejection_stages': {
                stage: [re.compile(p, re.IGNORECASE) for p in patterns]
                for stage, patterns in self.REJECTION_STAGE_PATTERNS.items()
            }
        }
        return compiled
    
    def parse_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse email and extract job application information."""
        subject = email_data.get('subject', '')
        sender = email_data.get('sender', '')
        sender_email = email_data.get('sender_email', '')
        snippet = email_data.get('snippet', '')
        body = email_data.get('body_preview', '')
        
        # Combine text for analysis
        full_text = f"{subject} {snippet} {body}"
        
        # Check if job-related
        is_job_related = self._is_job_related(full_text, sender_email)
        
        if not is_job_related:
            return {
                **email_data,
                'is_job_related': False,
                'detected_company': None,
                'detected_position': None,
                'detected_status': None,
                'confidence_score': 0.0
            }
        
        # Extract information
        company = self._extract_company(full_text, sender, sender_email)
        position = self._extract_position(full_text)
        status = self._detect_status(full_text)
        
        # Detect rejection stage if status is rejected
        rejection_stage = None
        if status == 'rejected':
            rejection_stage = self._detect_rejection_stage(full_text)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(company, position, status, full_text)
        
        return {
            **email_data,
            'is_job_related': True,
            'detected_company': company,
            'detected_position': position,
            'detected_status': status,
            'rejected_at_stage': rejection_stage,
            'confidence_score': confidence
        }
    
    def _is_job_related(self, text: str, sender_email: str) -> bool:
        """Check if email is job-related."""
        text_lower = text.lower()
        
        # Check for ignore domains
        for domain in config.IGNORE_DOMAINS:
            if domain in sender_email.lower():
                # Still could be job-related if from job board
                if any(kw in text_lower for kw in ['application', 'interview', 'position']):
                    return True
                return False
        
        # Check for job keywords
        job_keyword_count = sum(1 for kw in config.JOB_KEYWORDS if kw.lower() in text_lower)
        
        return job_keyword_count >= 2
    
    def _extract_company(self, text: str, sender: str, sender_email: str) -> Optional[str]:
        """Extract company name from email."""
        # Try to extract from sender name first
        if sender:
            # Pattern: "Name from Company" or "Company Recruiting"
            sender_match = re.search(r'(?:from|at|@)\s+([A-Z][A-Za-z0-9\s\&]+?)(?:\s+(?:Recruiting|HR|Careers|Talent|Team))?(?:\s*<|$)', sender)
            if sender_match:
                return self._clean_company_name(sender_match.group(1))
        
        # Try email domain
        if sender_email:
            domain_match = re.search(r'@([A-Za-z0-9\-]+)\.[a-z]+', sender_email)
            if domain_match:
                domain_name = domain_match.group(1)
                if domain_name.lower() not in ['gmail', 'yahoo', 'outlook', 'hotmail', 'aol', 'icloud', 'mail', 'email']:
                    return self._clean_company_name(domain_name.replace('-', ' ').title())
        
        # Try patterns on text
        for pattern in self.compiled_patterns['companies']:
            match = pattern.search(text)
            if match:
                company = match.group(1).strip()
                if len(company) >= 2 and not self._is_common_word(company):
                    return self._clean_company_name(company)
        
        return None
    
    def _extract_position(self, text: str) -> Optional[str]:
        """Extract job position/title from email."""
        for pattern in self.compiled_patterns['job_titles']:
            match = pattern.search(text)
            if match:
                position = match.group(1) if match.lastindex else match.group(0)
                position = position.strip()
                if len(position) >= 5 and len(position) <= 100:
                    return self._clean_position_title(position)
        
        return None
    
    def _detect_status(self, text: str) -> Optional[str]:
        """Detect application status from email content."""
        text_lower = text.lower()
        
        # Check each status type
        scores = {}
        for status, patterns in self.compiled_patterns['statuses'].items():
            score = sum(1 for p in patterns if p.search(text_lower))
            if score > 0:
                scores[status] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return 'applied'  # Default to "in progress" state
    
    def _detect_rejection_stage(self, text: str) -> Optional[str]:
        """Detect at which stage the rejection happened."""
        text_lower = text.lower()
        
        # Check each rejection stage
        scores = {}
        for stage, patterns in self.compiled_patterns['rejection_stages'].items():
            score = sum(1 for p in patterns if p.search(text_lower))
            if score > 0:
                scores[stage] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return None  # Could not determine stage
    
    def _calculate_confidence(
        self, 
        company: Optional[str], 
        position: Optional[str], 
        status: Optional[str],
        text: str
    ) -> float:
        """Calculate confidence score for extracted data."""
        score = 0.0
        
        # Company found
        if company:
            score += 0.35
        
        # Position found
        if position:
            score += 0.30
        
        # Status detected
        if status:
            score += 0.20
        
        # Job-related keywords density
        text_lower = text.lower()
        keyword_count = sum(1 for kw in config.JOB_KEYWORDS if kw.lower() in text_lower)
        keyword_score = min(keyword_count * 0.03, 0.15)
        score += keyword_score
        
        return min(score, 1.0)
    
    def _clean_company_name(self, name: str) -> str:
        """Clean and normalize company name."""
        # Remove common suffixes
        name = re.sub(r'\s*(?:Inc|LLC|Ltd|Corp|Corporation|Company|Co)\.?\s*$', '', name, flags=re.IGNORECASE)
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Capitalize properly
        return name.strip().title()
    
    def _clean_position_title(self, title: str) -> str:
        """Clean and normalize position title."""
        # Remove extra whitespace
        title = ' '.join(title.split())
        return title.strip()
    
    def _is_common_word(self, word: str) -> bool:
        """Check if word is too common to be a company name."""
        common_words = {
            'the', 'team', 'company', 'position', 'role', 'job', 'opportunity',
            'application', 'interview', 'regarding', 'update', 'status', 'your',
            'our', 'this', 'that', 'with', 'from', 'for', 'about', 'thank',
            'thanks', 'hello', 'hi', 'dear', 'please', 'kindly'
        }
        return word.lower() in common_words


email_parser = EmailParser()

"""Service for scraping job descriptions from URLs."""
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
from urllib.parse import urlparse


class JobScraperService:
    """Service for extracting job descriptions from job posting URLs."""
    
    # Common user agent to avoid blocking
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    # Site-specific selectors for job descriptions
    SITE_SELECTORS = {
        'linkedin.com': [
            '.description__text',
            '.show-more-less-html__markup',
            '[class*="description"]',
        ],
        'indeed.com': [
            '#jobDescriptionText',
            '.jobsearch-jobDescriptionText',
            '[class*="jobDescription"]',
        ],
        'greenhouse.io': [
            '#content',
            '.content',
            '[class*="job-description"]',
        ],
        'lever.co': [
            '.content',
            '[class*="description"]',
            '.posting-page',
        ],
        'workday.com': [
            '[data-automation-id="jobPostingDescription"]',
            '.job-description',
        ],
        'glassdoor.com': [
            '.desc',
            '[class*="JobDesc"]',
            '.jobDescriptionContent',
        ],
        'monster.com': [
            '#JobDescription',
            '.job-description',
        ],
        'ziprecruiter.com': [
            '.job_description',
            '[class*="description"]',
        ],
    }
    
    # Generic selectors to try for unknown sites
    GENERIC_SELECTORS = [
        '[class*="job-description"]',
        '[class*="jobDescription"]',
        '[class*="job_description"]',
        '[id*="job-description"]',
        '[id*="jobDescription"]',
        '[class*="description"]',
        '[class*="posting-description"]',
        '[class*="content"]',
        'article',
        'main',
        '.job-details',
        '.posting-content',
    ]
    
    def scrape_job_description(self, url: str) -> Dict[str, Any]:
        """
        Scrape job description from a URL.
        
        Returns:
            Dict with 'success', 'description', 'title', 'company', 'error' keys
        """
        result = {
            'success': False,
            'description': None,
            'title': None,
            'company': None,
            'error': None
        }
        
        if not url:
            result['error'] = 'No URL provided'
            return result
        
        try:
            # Fetch the page
            response = requests.get(url, headers=self.HEADERS, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Get domain for site-specific selectors
            domain = self._get_domain(url)
            
            # Try to extract job description
            description = self._extract_description(soup, domain)
            
            if description:
                result['success'] = True
                result['description'] = description
                
                # Try to extract title and company
                result['title'] = self._extract_title(soup)
                result['company'] = self._extract_company(soup)
            else:
                result['error'] = 'Could not find job description on this page. You can paste it manually.'
                
        except requests.exceptions.Timeout:
            result['error'] = 'Request timed out. The website took too long to respond.'
        except requests.exceptions.TooManyRedirects:
            result['error'] = 'Too many redirects. The URL may be invalid.'
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                result['error'] = 'Access denied. This website blocks automated access.'
            elif e.response.status_code == 404:
                result['error'] = 'Page not found. The job posting may have been removed.'
            else:
                result['error'] = f'HTTP error: {e.response.status_code}'
        except requests.exceptions.ConnectionError:
            result['error'] = 'Could not connect to the website.'
        except Exception as e:
            result['error'] = f'Failed to fetch job description: {str(e)}'
        
        return result
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ''
    
    def _extract_description(self, soup: BeautifulSoup, domain: str) -> Optional[str]:
        """Extract job description using site-specific or generic selectors."""
        # Try site-specific selectors first
        for site, selectors in self.SITE_SELECTORS.items():
            if site in domain:
                for selector in selectors:
                    element = soup.select_one(selector)
                    if element:
                        text = self._clean_text(element.get_text())
                        if len(text) > 200:  # Minimum length for valid description
                            return text
        
        # Try generic selectors
        for selector in self.GENERIC_SELECTORS:
            elements = soup.select(selector)
            for element in elements:
                text = self._clean_text(element.get_text())
                if len(text) > 500:  # Higher threshold for generic selectors
                    return text
        
        # Fallback: try to find the largest text block
        return self._find_largest_text_block(soup)
    
    def _find_largest_text_block(self, soup: BeautifulSoup) -> Optional[str]:
        """Find the largest coherent text block as a fallback."""
        candidates = []
        
        for tag in ['div', 'section', 'article']:
            for element in soup.find_all(tag):
                text = self._clean_text(element.get_text())
                if 500 < len(text) < 50000:  # Reasonable size range
                    candidates.append((len(text), text))
        
        if candidates:
            # Return the largest one that's not too large
            candidates.sort(reverse=True)
            return candidates[0][1]
        
        return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Try to extract job title from the page."""
        # Try common title selectors
        title_selectors = [
            'h1',
            '[class*="job-title"]',
            '[class*="jobTitle"]',
            '[class*="posting-title"]',
            'title',
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if text and len(text) < 200:
                    # Clean up common suffixes
                    text = re.sub(r'\s*[-|]\s*(LinkedIn|Indeed|Glassdoor|Careers).*$', '', text, flags=re.IGNORECASE)
                    return text.strip()
        
        return None
    
    def _extract_company(self, soup: BeautifulSoup) -> Optional[str]:
        """Try to extract company name from the page."""
        company_selectors = [
            '[class*="company-name"]',
            '[class*="companyName"]',
            '[class*="employer"]',
            '[class*="organization"]',
        ]
        
        for selector in company_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if text and len(text) < 100:
                    return text
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ''
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines but preserve paragraph structure
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text


# Singleton instance
scraper_service = JobScraperService()

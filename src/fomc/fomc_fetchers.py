import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, Dict
import re

class FOMCDataFetcher:
    """Base class for fetching FOMC data"""

    BASE_URL = "https://www.federalreserve.gov"

    @staticmethod
    def get_today() -> str:
        """Get today's date in YYYYMMDD format"""
        return datetime.now().strftime("%Y%m%d")
    
    @staticmethod
    def normalize_date(date_str: Optional[str]) -> str:
        """
        Ensures date is in YYYYMMDD format for URLs.
        Converts '2025-10-29' -> '20251029'.
        """
        if not date_str:
            return FOMCDataFetcher.get_today()
        return date_str.replace("-", "")
    
    @staticmethod
    def extract_date_from_url(url: str) -> Optional[str]:
        """
        Extract date from Federal Reserve URL (YYYY-MM-DD)
        """
        match = re.search(r'(\d{4})(\d{2})(\d{2})', url)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"
        return None
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean up extracted text"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    

class StatementFetcher(FOMCDataFetcher):
    """Fetch FOMC Statement"""
    def fetch(self, date_str: Optional[str] = None) -> Dict:
        if date_str is None:
            date_str = self.normalize_date(date_str)
        
        url = f"{self.BASE_URL}/newsevents/pressreleases/monetary{date_str}a.htm"

        try:
            response = requests.get(url, timeout=30)
            # Handle 404 (Expected if no meeting today)
            if response.status_code == 404:
                return {"statement": "", "url": url, "new_release_date": None}
            
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            article = soup.select_one('div#article')
            if article: 
                for ul in article.select('ul.list-unstyled'):
                    ul.decompose()
                statement = self.clean_text(article.get_text())
            else:
                statement = ""

            meta_url = soup.select_one('meta[property="og:url"]')
            release_url = meta_url['content'] if meta_url else url
            
            # Rule: Date comes from URL
            new_release_date = self.extract_date_from_url(release_url)

            return {
                "statement": statement,
                "url": release_url,
                "new_release_date": new_release_date
            }
        except Exception as e:
            print(f"Error fetching statement: {e}")
            return {"statement": "", "url": url, "new_release_date": None}
        

class MinutesFetcher(FOMCDataFetcher):
    """Fetch FOMC Minutes"""
    def fetch(self, date_str: Optional[str] = None) -> Dict:
        if date_str is None:
            date_str = self.normalize_date(date_str)
        
        url = f"{self.BASE_URL}/monetarypolicy/fomcminutes{date_str}.htm"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                return {"minutes": "", "url": url, "new_release_date": None}

            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            article = soup.select_one('div#article')
            if article:
                html_content = str(article)
                html_content = re.sub(r'<a\b[^>]*href=["\']#fn\d+["\'][^>]*>[\s\S]*?</a>', '', html_content, flags=re.IGNORECASE)
                html_content = re.sub(r'<a\b[^>]*>\s*Return to text\s*</a>', '', html_content, flags=re.IGNORECASE)
                soup_clean = BeautifulSoup(html_content, 'html.parser')
                minutes = self.clean_text(soup_clean.get_text())
            else:
                minutes = ""
            
            meta_url = soup.select_one('meta[property="og:url"]')
            release_url = meta_url['content'] if meta_url else url
            new_release_date = self.extract_date_from_url(release_url)
            
            return {
                "minutes": minutes,
                "meeting_content": minutes,
                "url": release_url,
                "new_release_date": new_release_date
            }
        except Exception as e:
            print(f"Error fetching minutes: {e}")
            return {"minutes": "", "url": url, "new_release_date": None}


class ProjectionNoteFetcher(FOMCDataFetcher):
    """Fetch FOMC Projection Materials"""
    def fetch(self, date_str: Optional[str] = None) -> Dict:
        if date_str is None:
            date_str = self.normalize_date(date_str)
        
        url = f"{self.BASE_URL}/monetarypolicy/fomcprojtabl{date_str}.htm"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                return {"projection_note": "", "url": url, "new_release_date": None}

            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            content = soup.select_one('div#content > .row:nth-of-type(2) .col-xs-12.col-sm-8.col-md-8')
            projection_materials = self.clean_text(content.get_text()) if content else ""
            
            meta_url = soup.select_one('meta[property="og:url"]')
            release_url = meta_url['content'] if meta_url else url
            new_release_date = self.extract_date_from_url(release_url)
            
            return {
                "projection_note": projection_materials,
                "url": release_url,
                "new_release_date": new_release_date
            }
        except Exception as e:
            print(f"Error fetching projection note: {e}")
            return {"projection_note": "", "url": url, "new_release_date": None}


class ImplementationNoteFetcher(FOMCDataFetcher):
    """Fetch FOMC Implementation Note"""
    def fetch(self, date_str: Optional[str] = None) -> Dict:
        if date_str is None:
            date_str = self.normalize_date(date_str)
        
        url = f"{self.BASE_URL}/newsevents/pressreleases/monetary{date_str}a1.htm"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                return {"implementation_note": "", "url": url, "new_release_date": None}

            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            content = soup.select_one('div#content > .row:nth-of-type(3) .col-xs-12')
            implementation_note = self.clean_text(content.get_text()) if content else ""
            
            meta_url = soup.select_one('meta[property="og:url"]')
            release_url = meta_url['content'] if meta_url else url
            new_release_date = self.extract_date_from_url(release_url)
            
            return {
                "implementation_note": implementation_note,
                "url": release_url,
                "new_release_date": new_release_date
            }
        except Exception as e:
            print(f"Error fetching implementation note: {e}")
            return {"implementation_note": "", "url": url, "new_release_date": None}

def fetch_all_fomc_data(date_str: Optional[str] = None) -> Dict:
    """Fetch all FOMC communication types"""
    return {
        "statement": StatementFetcher().fetch(date_str),
        "minutes": MinutesFetcher().fetch(date_str),
        "projection_note": ProjectionNoteFetcher().fetch(date_str),
        "implementation_note": ImplementationNoteFetcher().fetch(date_str)
    }
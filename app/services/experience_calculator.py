import re
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
}

class ExperienceCalculatorService:
    @staticmethod
    def _parse_month_year(date_str: str, default_month: int) -> tuple[int, int]:
        """
        Parses a date string (e.g. 'Jan 2018', '05/2014', '2015') into (month, year).
        Returns the current month and year if it represents the present.
        """
        cleaned = date_str.strip().lower()
        now = datetime.now()
        
        # Check for present indicators
        if cleaned in ['present', 'current', 'now', 'till date', 'ongoing']:
            return now.month, now.year
            
        # Extract 4-digit year
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', cleaned)
        if not year_match:
            return default_month, now.year  # Fallback to current year if no year found
        year = int(year_match.group(1))
        
        # Remove the year from string to avoid matching year digits as month digits
        text_without_year = cleaned.replace(str(year), "").strip()
        
        # Check for word month (e.g. 'jan', 'january')
        for month_name, month_num in MONTH_MAP.items():
            if month_name in text_without_year:
                return month_num, year
                
        # Check for numerical month (e.g. '05/2014' -> 5, or '12-2018' -> 12)
        month_match = re.search(r'\b(0?[1-9]|1[0-2])\b', text_without_year)
        if month_match:
            return int(month_match.group(1)), year
            
        return default_month, year

    @classmethod
    def calculate_experience(cls, text: str) -> float:
        """
        Scans text for date ranges and calculates the total experience in years.
        Avoids overcounting overlapping intervals by tracking month-level uniqueness.
        """
        # Define month and year regex components
        months_regex = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|\d{1,2})"
        year_regex = r"\b(?:19\d{2}|20\d{2})\b"
        
        # Date items can be 'Month Year', 'Month/Year', 'Year'
        date_item_regex = rf"(?:{months_regex}\s*[-/.,]?\s*{year_regex}|{year_regex})"
        separator_regex = r"\s*(?:-|–|—|to)\s*"
        end_date_regex = rf"(?:{date_item_regex}|present|current|now|till date|ongoing)"
        
        # Final Date Range Regex
        range_pattern = rf"({date_item_regex}){separator_regex}({end_date_regex})"
        
        matches = re.findall(range_pattern, text, re.IGNORECASE)
        
        if not matches:
            logger.info("No date ranges matching experience pattern found in text.")
            return 0.0
            
        unique_months = set()
        
        for start_str, end_str in matches:
            try:
                start_month, start_year = cls._parse_month_year(start_str, default_month=1)
                end_month, end_year = cls._parse_month_year(end_str, default_month=12)
                
                # Convert start and end to total months since year 0
                start_total_months = start_year * 12 + start_month
                end_total_months = end_year * 12 + end_month
                
                if start_total_months > end_total_months:
                    continue  # Invalid range
                    
                # Limit unreasonable durations
                current_total_months = datetime.now().year * 12 + datetime.now().month
                if end_total_months > current_total_months + 12: # Allowing 1 year in future
                    continue
                    
                # Add all months in this interval to the set of unique months worked
                for m in range(start_total_months, end_total_months + 1):
                    unique_months.add(m)
                    
            except Exception as e:
                logger.warning(f"Error parsing date range '{start_str} - {end_str}': {str(e)}")
                continue
                
        total_years = len(unique_months) / 12.0
        # Round to 1 decimal place
        return round(total_years, 1)

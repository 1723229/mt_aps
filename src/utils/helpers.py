"""Helper utility functions."""

from datetime import datetime
from typing import Dict


WEEK_DAYS_CN = {
    0: 'Monday',
    1: 'Tuesday', 
    2: 'Wednesday',
    3: 'Thursday',
    4: 'Friday',
    5: 'Saturday',
    6: 'Sunday',
}


def get_week_number(date_str: str, work_week: Dict[str, int]) -> int:
    """Get week number for a date from work_week mapping."""
    return work_week.get(date_str, 1)


def get_day_of_week(date_str: str) -> str:
    """Get day of week name for a date string."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return WEEK_DAYS_CN[date_obj.weekday()]


def calculate_bottles_from_tons(tons: float, spec: int) -> int:
    """Convert tons to bottles.
    
    Formula: bottles = tons × 500 × 2124 ÷ spec
    
    Args:
        tons: Amount in tons
        spec: Specification in ml (e.g., 500, 1000, 200)
    
    Returns:
        Number of bottles
    """
    return int(tons * 500 * 2124 / spec)


def calculate_tons_from_bottles(bottles: int, spec: int) -> float:
    """Convert bottles to tons.
    
    Formula: tons = bottles × spec ÷ (500 × 2124)
    
    Args:
        bottles: Number of bottles
        spec: Specification in ml
    
    Returns:
        Amount in tons
    """
    return bottles * spec / (500 * 2124)


def format_date(date_str: str) -> str:
    """Ensure date is in YYYY-MM-DD format."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # Try other formats if needed
        return date_str


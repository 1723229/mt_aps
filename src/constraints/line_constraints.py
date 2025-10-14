"""Line forbidden time constraint handler."""

from typing import Dict, List, Set
from ..models.input_models import ConstraintSetting


class LineForbidTimeConstraint:
    """Handles line_forbid_time constraints."""
    
    def __init__(self, constraints: List[ConstraintSetting]):
        """Initialize from constraint settings.
        
        Args:
            constraints: List of line_forbid_time constraint settings
        """
        self.forbidden_dates: Dict[str, Set[str]] = {}
        
        for constraint in constraints:
            if constraint.constraintType == 'line_forbid_time' and constraint.enable:
                self._parse_constraint(constraint)
    
    def _parse_constraint(self, constraint: ConstraintSetting):
        """Parse a line_forbid_time constraint.
        
        Expected format:
        {
            "constraintValue": [
                {"lineCode": "030207", "forbidTime": "2025-10-10"},
                ...
            ]
        }
        """
        if not isinstance(constraint.constraintValue, list):
            return
        
        for item in constraint.constraintValue:
            if not isinstance(item, dict):
                continue
            
            line_code = item.get('lineCode')
            forbid_time = item.get('forbidTime')
            
            if line_code and forbid_time:
                if line_code not in self.forbidden_dates:
                    self.forbidden_dates[line_code] = set()
                self.forbidden_dates[line_code].add(forbid_time)
    
    def is_line_forbidden(self, line_code: str, date: str) -> bool:
        """Check if a line is forbidden on a date.
        
        Args:
            line_code: Line code
            date: Date string in YYYY-MM-DD format
        
        Returns:
            True if line is forbidden on this date
        """
        return date in self.forbidden_dates.get(line_code, set())
    
    def get_forbidden_dates(self, line_code: str) -> Set[str]:
        """Get all forbidden dates for a line.
        
        Args:
            line_code: Line code
        
        Returns:
            Set of forbidden date strings
        """
        return self.forbidden_dates.get(line_code, set()).copy()
    
    def get_forbidden_lines(self, date: str) -> Set[str]:
        """Get all forbidden lines on a date.
        
        Args:
            date: Date string
        
        Returns:
            Set of forbidden line codes
        """
        forbidden = set()
        for line_code, dates in self.forbidden_dates.items():
            if date in dates:
                forbidden.add(line_code)
        return forbidden


"""Base class for regional constraint handlers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Set, Optional
from dataclasses import dataclass


@dataclass
class CrewAllocation:
    """Suggested crew allocation for a line."""
    
    line_code: str
    crew_code: str
    priority_score: float  # Lower is better


class BaseRegion(ABC):
    """Abstract base class for regional constraint handlers."""
    
    def __init__(self, line_codes: Set[str], crew_codes: Set[str]):
        """Initialize region.
        
        Args:
            line_codes: Set of line codes in this region
            crew_codes: Set of crew codes that can work in this region
        """
        self.line_codes = line_codes
        self.crew_codes = crew_codes
    
    @abstractmethod
    def validate_shift_allocation(
        self,
        date: str,
        shift: str,
        line_assignments: Dict[str, List[str]],  # line_code -> [crew_codes]
    ) -> tuple[bool, Optional[str]]:
        """Validate that a shift allocation satisfies regional constraints.
        
        Args:
            date: Date string
            shift: 'early' or 'middle'
            line_assignments: Current crew assignments per line
        
        Returns:
            (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def get_max_idle_lines(self) -> int:
        """Get maximum number of idle lines allowed per shift.
        
        Returns:
            Maximum number of idle lines (0 = no idle allowed)
        """
        pass
    
    @abstractmethod
    def get_constraints_description(self) -> str:
        """Get human-readable description of constraints.
        
        Returns:
            Description string
        """
        pass
    
    def is_in_region(self, line_code: str) -> bool:
        """Check if a line is in this region.
        
        Args:
            line_code: Line code
        
        Returns:
            True if line is in this region
        """
        return line_code in self.line_codes
    
    def get_crew_in_region(self, crew_code: str) -> bool:
        """Check if a crew works in this region.
        
        Args:
            crew_code: Crew code
        
        Returns:
            True if crew works in this region
        """
        return crew_code in self.crew_codes


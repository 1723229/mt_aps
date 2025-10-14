"""Manages all regional constraints."""

from typing import Dict, List, Optional
from .base_region import BaseRegion
from .old_packaging import OldPackagingRegion
from .new_packaging_a import NewPackagingARegion
from .new_packaging_b import NewPackagingBRegion
from .new_packaging_cd import NewPackagingCDRegion


class RegionManager:
    """Centralized management of all regional constraints."""
    
    def __init__(self):
        """Initialize all regions."""
        self.regions: List[BaseRegion] = [
            OldPackagingRegion(),
            NewPackagingARegion(),
            NewPackagingBRegion(),
            NewPackagingCDRegion(),
        ]
        
        # Build line-to-region mapping
        self.line_to_region: Dict[str, BaseRegion] = {}
        for region in self.regions:
            for line_code in region.line_codes:
                self.line_to_region[line_code] = region
    
    def get_region_for_line(self, line_code: str) -> Optional[BaseRegion]:
        """Get the region for a line.
        
        Args:
            line_code: Line code
        
        Returns:
            BaseRegion or None if not found
        """
        return self.line_to_region.get(line_code)
    
    def validate_shift(
        self,
        date: str,
        shift: str,
        line_assignments: Dict[str, List[str]],
    ) -> tuple[bool, Dict[str, str]]:
        """Validate shift allocation across all regions.
        
        Args:
            date: Date string
            shift: 'early' or 'middle'
            line_assignments: line_code -> [crew_codes]
        
        Returns:
            (all_valid, errors_by_region)
        """
        errors = {}
        
        for region in self.regions:
            valid, error = region.validate_shift_allocation(date, shift, line_assignments)
            if not valid:
                region_name = region.__class__.__name__
                errors[region_name] = error
        
        return len(errors) == 0, errors
    
    def get_all_constraints_description(self) -> List[str]:
        """Get descriptions of all regional constraints.
        
        Returns:
            List of constraint descriptions
        """
        return [region.get_constraints_description() for region in self.regions]


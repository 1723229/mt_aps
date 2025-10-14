"""New Packaging B Region (Region C) constraint handler.

Lines: 030205 (5号线), 030206 (6号线)
Crews: 
  - 030205: pack05, pack11
  - 030206: pack06, pack13

Constraints:
- Strict crew-line binding
- Both lines must run double shifts
- No idle lines allowed
"""

from typing import Dict, List, Optional
from .base_region import BaseRegion


class NewPackagingBRegion(BaseRegion):
    """New packaging B region with strict crew-line binding."""
    
    def __init__(self):
        line_codes = {'030205', '030206'}
        crew_codes = {'pack05', 'pack11', 'pack06', 'pack13'}
        super().__init__(line_codes, crew_codes)
        
        # Strict bindings
        self.line_crews = {
            '030205': {'pack05', 'pack11'},
            '030206': {'pack06', 'pack13'},
        }
        
        # Reverse lookup
        self.crew_line = {
            'pack05': '030205',
            'pack11': '030205',
            'pack06': '030206',
            'pack13': '030206',
        }
    
    def validate_shift_allocation(
        self,
        date: str,
        shift: str,
        line_assignments: Dict[str, List[str]],
    ) -> tuple[bool, Optional[str]]:
        """Validate new packaging B region constraints.
        
        Requirements:
        1. No idle lines (both lines must be active)
        2. Each line must have exactly 2 crews (double shift)
        3. Crews must match their designated line
        """
        # Filter to this region's lines
        region_assignments = {
            line: crews for line, crews in line_assignments.items()
            if line in self.line_codes
        }
        
        # Both lines must be active
        if len(region_assignments) != 2:
            return False, f"New packaging B requires both lines active, got {len(region_assignments)}"
        
        # Check each line
        for line_code in self.line_codes:
            if line_code not in region_assignments:
                return False, f"Line {line_code} must be active (no idle allowed)"
            
            crews = region_assignments[line_code]
            
            # Must have exactly 2 crews (double shift)
            if len(crews) != 2:
                return False, f"Line {line_code} must have 2 crews (double shift), got {len(crews)}"
            
            # Crews must be from the designated set
            allowed_crews = self.line_crews[line_code]
            for crew in crews:
                if crew not in allowed_crews:
                    return False, f"Crew {crew} not allowed on line {line_code}, allowed: {allowed_crews}"
        
        return True, None
    
    def get_max_idle_lines(self) -> int:
        """New packaging B allows no idle lines."""
        return 0
    
    def get_constraints_description(self) -> str:
        return (
            "New Packaging B Region (Lines 030205, 030206): "
            "Strict crew binding (030205: pack05/pack11, 030206: pack06/pack13), "
            "both lines must run double shifts, no idle allowed"
        )
    
    def get_line_for_crew(self, crew_code: str) -> Optional[str]:
        """Get the designated line for a crew.
        
        Args:
            crew_code: Crew code
        
        Returns:
            Line code or None if crew not in region
        """
        return self.crew_line.get(crew_code)
    
    def is_crew_allowed_on_line(self, crew_code: str, line_code: str) -> bool:
        """Check if crew is allowed on line.
        
        Args:
            crew_code: Crew code
            line_code: Line code
        
        Returns:
            True if crew can work on this line
        """
        return self.crew_line.get(crew_code) == line_code


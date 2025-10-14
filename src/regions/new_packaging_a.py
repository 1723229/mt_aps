"""New Packaging A Region (Region B) constraint handler.

Lines: 030203 (3号线), 030204 (4号线), 030207 (7号线), 030211 (11号线)
Crews: pack03, pack04, pack07, pack15, pack17

Constraints:
- Flexible crew assignment
- pack17 NOT allowed on 030204
- Max 1 idle line per shift
- Prefer double shifts for utilization
"""

from typing import Dict, List, Optional
from .base_region import BaseRegion


class NewPackagingARegion(BaseRegion):
    """New packaging A region with flexible crew assignment."""
    
    def __init__(self):
        line_codes = {'030203', '030204', '030207', '030211'}
        crew_codes = {'pack03', 'pack04', 'pack07', 'pack15', 'pack17'}
        super().__init__(line_codes, crew_codes)
        
        # Special restriction: pack17 cannot work on 030204
        self.restricted_assignments = {
            ('030204', 'pack17'): "pack17 not allowed on line 030204"
        }
    
    def validate_shift_allocation(
        self,
        date: str,
        shift: str,
        line_assignments: Dict[str, List[str]],
    ) -> tuple[bool, Optional[str]]:
        """Validate new packaging A region constraints.
        
        Requirements:
        1. Max 1 idle line per shift
        2. pack17 not on 030204
        3. Flexible crew assignment otherwise
        """
        # Filter to this region's lines
        region_assignments = {
            line: crews for line, crews in line_assignments.items()
            if line in self.line_codes
        }
        
        # Count idle lines
        idle_lines = [
            line for line in self.line_codes 
            if line not in region_assignments or not region_assignments.get(line)
        ]
        
        # Max 1 idle line allowed
        if len(idle_lines) > 1:
            return False, f"New packaging A allows max 1 idle line, got {len(idle_lines)}: {idle_lines}"
        
        # Check restricted assignments
        for line, crews in region_assignments.items():
            for crew in crews:
                if (line, crew) in self.restricted_assignments:
                    return False, self.restricted_assignments[(line, crew)]
        
        return True, None
    
    def get_max_idle_lines(self) -> int:
        """New packaging A allows max 1 idle line."""
        return 1
    
    def get_constraints_description(self) -> str:
        return (
            "New Packaging A Region (Lines 030203, 030204, 030207, 030211): "
            "Flexible crew assignment, pack17 not on 030204, "
            "max 1 idle line per shift"
        )
    
    def is_crew_allowed_on_line(self, crew_code: str, line_code: str) -> bool:
        """Check if a crew is allowed on a line.
        
        Args:
            crew_code: Crew code
            line_code: Line code
        
        Returns:
            True if crew can work on this line
        """
        return (line_code, crew_code) not in self.restricted_assignments


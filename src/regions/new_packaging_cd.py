"""New Packaging C/D Region (Region D) constraint handler.

Lines: 030208 (8号线), 030209 (9号线), 030212 (12号线), 030213 (13号线)
Crews: pack08, pack09, pack12, pack16, pack18, pack19

Crew-line mappings:
  - 030208: pack08, pack09
  - 030209: pack08, pack09, pack12, pack18, pack19
  - 030212: pack18, pack19
  - 030213: pack08, pack09, pack12, pack16

Flexible Scheduling Rules:
- No fixed double-shift pairing requirement
- Allows:
  * Some lines running double shifts
  * Some lines running single shifts
  * Some lines idle
- Crew assignment constraints:
  * Crews can be flexibly assigned to compatible lines
  * Prefer double shifts (to maximize capacity utilization)
  * Release crews to other lines after product completion
"""

from typing import Dict, List, Optional
from .base_region import BaseRegion


class NewPackagingCDRegion(BaseRegion):
    """New packaging C/D region with flexible crew scheduling."""
    
    def __init__(self):
        line_codes = {'030208', '030209', '030212', '030213'}
        crew_codes = {'pack08', 'pack09', 'pack12', 'pack16', 'pack18', 'pack19'}
        super().__init__(line_codes, crew_codes)
        
        # Crew-line compatibility
        self.line_crews = {
            '030208': {'pack08', 'pack09'},
            '030209': {'pack08', 'pack09', 'pack12', 'pack18', 'pack19'},
            '030212': {'pack18', 'pack19'},
            '030213': {'pack08', 'pack09', 'pack12', 'pack16'},
        }
    
    def validate_shift_allocation(
        self,
        date: str,
        shift: str,
        line_assignments: Dict[str, List[str]],
    ) -> tuple[bool, Optional[str]]:
        """Validate new packaging C/D region constraints.
        
        Requirements:
        1. Crews must match their designated lines
        2. Maximum 2 crews per line
        3. Flexible scheduling: lines can be double shift, single shift, or idle
        """
        # Filter to this region's lines
        region_assignments = {
            line: crews for line, crews in line_assignments.items()
            if line in self.line_codes
        }
        
        # Check crew-line compatibility
        for line, crews in region_assignments.items():
            allowed_crews = self.line_crews[line]
            for crew in crews:
                if crew not in allowed_crews:
                    return False, f"Crew {crew} not allowed on line {line}, allowed: {allowed_crews}"
        
        # Check maximum crews per line
        for line in self.line_codes:
            crew_count = len(region_assignments.get(line, []))
            if crew_count > 2:
                return False, f"Line {line} has {crew_count} crews, max 2 allowed"
        
        # No fixed double-shift requirement - flexible scheduling allowed
        return True, None
    
    def get_max_idle_lines(self) -> int:
        """New packaging C/D allows flexible idle lines."""
        # All 4 lines can potentially be idle (flexible scheduling)
        return 4
    
    def get_constraints_description(self) -> str:
        return (
            "New Packaging C/D Region (Lines 030208, 030209, 030212, 030213): "
            "Flexible crew assignment, allows double/single/idle lines with no fixed pairing"
        )
    
    def is_crew_allowed_on_line(self, crew_code: str, line_code: str) -> bool:
        """Check if crew is allowed on line.
        
        Args:
            crew_code: Crew code
            line_code: Line code
        
        Returns:
            True if crew can work on this line
        """
        return crew_code in self.line_crews.get(line_code, set())
    
    def get_lines_for_crew(self, crew_code: str) -> List[str]:
        """Get all lines a crew can work on.
        
        Args:
            crew_code: Crew code
        
        Returns:
            List of line codes
        """
        lines = []
        for line, crews in self.line_crews.items():
            if crew_code in crews:
                lines.append(line)
        return lines


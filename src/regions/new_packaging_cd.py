"""New Packaging C/D Region (Region D) constraint handler.

Lines: 030208 (8号线), 030209 (9号线), 030212 (12号线), 030213 (13号线)
Crews: pack08, pack09, pack12, pack16, pack18, pack19

Crew-line mappings:
  - 030208: pack08, pack09
  - 030209: pack08, pack09, pack12, pack18, pack19
  - 030212: pack18, pack19
  - 030213: pack08, pack09, pack12, pack16

Constraints:
- Flexible crew assignment (crews can work on multiple lines)
- Must maintain "2 double + 2 single" balance:
  * Exactly 2 lines with 2 crews each (double shift)
  * Remaining lines: can be single or idle
  * Not allowed: 3 double + 1 single, or 1 double + 3 single
"""

from typing import Dict, List, Optional
from .base_region import BaseRegion


class NewPackagingCDRegion(BaseRegion):
    """New packaging C/D region with 2-double-2-single balance."""
    
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
        1. Exactly 2 lines must have 2 crews (double shift)
        2. Remaining lines can be single or idle
        3. Crews must match their designated lines
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
        
        # Count lines by number of crews
        double_lines = []
        single_lines = []
        
        for line in self.line_codes:
            crew_count = len(region_assignments.get(line, []))
            if crew_count == 2:
                double_lines.append(line)
            elif crew_count == 1:
                single_lines.append(line)
            elif crew_count > 2:
                return False, f"Line {line} has {crew_count} crews, max 2 allowed"
        
        # Must have exactly 2 double lines
        if len(double_lines) != 2:
            return False, (
                f"New packaging C/D requires exactly 2 double lines, "
                f"got {len(double_lines)}: {double_lines}"
            )
        
        return True, None
    
    def get_max_idle_lines(self) -> int:
        """New packaging C/D can have idle lines as long as 2 are double."""
        # Can have up to 2 idle lines (4 total - 2 double)
        return 2
    
    def get_constraints_description(self) -> str:
        return (
            "New Packaging C/D Region (Lines 030208, 030209, 030212, 030213): "
            "Flexible crew assignment, must maintain 2 double + 2 single/idle balance"
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


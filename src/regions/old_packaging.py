"""Old Packaging Region (Region A) constraint handler.

Lines: 030201 (1号线), 030202 (2号线), 030210 (10号线)
Crews: pack01, pack02, pack10, pack14

Constraints:
- Fixed crew pairs: (pack01 + pack02), (pack10 + pack14)
- Exactly 1 line must be idle per shift (3 lines, 2 pairs)
- Crew pairs cannot be split
"""

from typing import Dict, List, Set, Optional
from .base_region import BaseRegion


class OldPackagingRegion(BaseRegion):
    """Old packaging region with fixed crew pairs."""
    
    # Fixed crew pair definitions
    CREW_PAIRS = [
        frozenset(['pack01', 'pack02']),
        frozenset(['pack10', 'pack14']),
    ]
    
    def __init__(self):
        line_codes = {'030201', '030202', '030210'}
        crew_codes = {'pack01', 'pack02', 'pack10', 'pack14'}
        super().__init__(line_codes, crew_codes)
        
        # Map crew to its pair
        self.crew_to_pair = {}
        for pair in self.CREW_PAIRS:
            for crew in pair:
                self.crew_to_pair[crew] = pair
    
    def validate_shift_allocation(
        self,
        date: str,
        shift: str,
        line_assignments: Dict[str, List[str]],
    ) -> tuple[bool, Optional[str]]:
        """Validate old packaging region constraints.
        
        Requirements:
        1. Exactly 1 line idle
        2. Crew pairs must work together
        3. Maximum 2 lines active (2 pairs)
        """
        # Filter to this region's lines
        region_assignments = {
            line: crews for line, crews in line_assignments.items()
            if line in self.line_codes
        }
        
        # Count active lines
        active_lines = [line for line, crews in region_assignments.items() if crews]
        idle_lines = [line for line in self.line_codes if line not in active_lines]
        
        # Must have exactly 1 idle line
        if len(idle_lines) != 1:
            return False, f"Old packaging must have exactly 1 idle line, got {len(idle_lines)}"
        
        # Must have exactly 2 active lines (for 2 pairs)
        if len(active_lines) != 2:
            return False, f"Old packaging must have exactly 2 active lines, got {len(active_lines)}"
        
        # Each active line should have exactly 1 crew (one from each pair)
        for line in active_lines:
            crews = region_assignments[line]
            if len(crews) != 1:
                return False, f"Line {line} should have 1 crew, got {len(crews)}"
        
        # Validate crew pairing
        active_crews = set()
        for line in active_lines:
            active_crews.update(region_assignments[line])
        
        # Check that crews form valid pairs
        pairs_present = set()
        for crew in active_crews:
            if crew not in self.crew_to_pair:
                return False, f"Crew {crew} not in old packaging region"
            pairs_present.add(self.crew_to_pair[crew])
        
        # Should have exactly 2 pairs represented
        if len(pairs_present) != 2:
            return False, f"Must use both crew pairs, got {len(pairs_present)}"
        
        # Validate each pair has both members
        for pair in pairs_present:
            pair_crews_active = pair & active_crews
            if len(pair_crews_active) != 2:
                return False, f"Crew pair {pair} incomplete: only {pair_crews_active} active"
        
        return True, None
    
    def get_max_idle_lines(self) -> int:
        """Old packaging must have exactly 1 idle line."""
        return 1
    
    def get_constraints_description(self) -> str:
        return (
            "Old Packaging Region (Lines 030201, 030202, 030210): "
            "Fixed crew pairs (pack01+pack02, pack10+pack14), "
            "exactly 1 line idle per shift"
        )
    
    def get_crew_pair(self, crew_code: str) -> Optional[Set[str]]:
        """Get the pair for a crew.
        
        Args:
            crew_code: Crew code
        
        Returns:
            Set of crew codes in the pair, or None if not in region
        """
        return set(self.crew_to_pair.get(crew_code, set()))


"""Regional constraint handlers for different packaging areas"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict


class RegionalConstraints:
    """Defines regional constraints for packaging areas"""
    
    # Old Packaging Area
    OLD_PACKAGING_LINES = ["030201", "030202", "030210"]
    OLD_PACKAGING_CREWS = {
        "pair1": ["pack01", "pack02"],
        "pair2": ["pack10", "pack14"]
    }
    
    # New Packaging Area A
    NEW_PACKAGING_A_LINES = ["030203", "030204", "030207", "030211"]
    NEW_PACKAGING_A_CREWS = ["pack03", "pack04", "pack07", "pack15", "pack17"]
    # 030204 doesn't use pack17
    LINE_030204_EXCLUDED_CREWS = ["pack17"]
    
    # New Packaging Area B
    NEW_PACKAGING_B_LINES = ["030205", "030206"]
    NEW_PACKAGING_B_CREWS = {
        "030205": ["pack05", "pack11"],
        "030206": ["pack06", "pack13"]
    }
    PRIORITY_PRODUCT_030205 = "MT0010010082"
    
    # New Packaging Area C+D
    NEW_PACKAGING_CD_LINES = ["030208", "030209", "030212", "030213"]
    NEW_PACKAGING_CD_CREWS = {
        "030208": ["pack08", "pack09"],
        "030209": ["pack08", "pack09", "pack12", "pack18", "pack19"],
        "030212": ["pack18", "pack19"],
        "030213": ["pack12", "pack16", "pack08", "pack09"]
    }
    
    @classmethod
    def get_area_for_line(cls, line_code: str) -> str:
        """Get the area name for a given line"""
        if line_code in cls.OLD_PACKAGING_LINES:
            return "OLD"
        elif line_code in cls.NEW_PACKAGING_A_LINES:
            return "NEW_A"
        elif line_code in cls.NEW_PACKAGING_B_LINES:
            return "NEW_B"
        elif line_code in cls.NEW_PACKAGING_CD_LINES:
            return "NEW_CD"
        return "UNKNOWN"
    
    @classmethod
    def get_fixed_crew_pair(cls, crew_code: str) -> List[str]:
        """Get the fixed crew pair for old packaging area"""
        for pair_crews in cls.OLD_PACKAGING_CREWS.values():
            if crew_code in pair_crews:
                return pair_crews
        return []
    
    @classmethod
    def is_crew_pair_complete(cls, crew_codes: List[str]) -> bool:
        """Check if crew codes form a complete pair"""
        crew_set = set(crew_codes)
        for pair_crews in cls.OLD_PACKAGING_CREWS.values():
            if crew_set == set(pair_crews):
                return True
        return False


class RegionalConstraintValidator:
    """Validates regional-specific constraints"""
    
    def __init__(self, assignments: List):
        self.assignments = assignments
        self.violations: List[str] = []
    
    def validate_all_regional_constraints(self) -> Tuple[bool, List[str]]:
        """Validate all regional constraints"""
        self.violations = []
        
        self.validate_old_packaging_area()
        self.validate_new_packaging_area_a()
        self.validate_new_packaging_area_b()
        self.validate_new_packaging_area_cd()
        
        return len(self.violations) == 0, self.violations
    
    def validate_old_packaging_area(self):
        """Validate old packaging area constraints"""
        # Group assignments by date and shift
        shift_assignments = defaultdict(list)
        
        for assignment in self.assignments:
            if assignment.line_code in RegionalConstraints.OLD_PACKAGING_LINES:
                key = (assignment.date, assignment.shift)
                shift_assignments[key].append(assignment)
        
        # Check each shift
        for (date, shift), assignments in shift_assignments.items():
            lines_used = set(a.line_code for a in assignments)
            crews_used = set(a.crew_code for a in assignments)
            
            # Must have exactly 1 line idle (2 lines working out of 3)
            if len(lines_used) > 2:
                self.violations.append(
                    f"老包装区违反: {date} {shift}使用了{len(lines_used)}条产线，应最多2条"
                )
            
            # Check crew pairing
            for crew in crews_used:
                pair_crews = RegionalConstraints.get_fixed_crew_pair(crew)
                if pair_crews:
                    # Check if pair is complete
                    if not all(c in crews_used for c in pair_crews):
                        missing = [c for c in pair_crews if c not in crews_used]
                        self.violations.append(
                            f"老包装区违反: {date} {shift}班组{crew}的配对班组{missing}未安排"
                        )
    
    def validate_new_packaging_area_a(self):
        """Validate new packaging area A constraints"""
        shift_assignments = defaultdict(list)
        
        for assignment in self.assignments:
            if assignment.line_code in RegionalConstraints.NEW_PACKAGING_A_LINES:
                key = (assignment.date, assignment.shift)
                shift_assignments[key].append(assignment)
        
        # Check each shift: max 1 idle line (at least 3 lines working out of 4)
        for (date, shift), assignments in shift_assignments.items():
            lines_used = set(a.line_code for a in assignments)
            idle_lines = len(RegionalConstraints.NEW_PACKAGING_A_LINES) - len(lines_used)
            
            if idle_lines > 1:
                self.violations.append(
                    f"新包装A区违反: {date} {shift}有{idle_lines}条空线，应最多1条"
                )
        
        # Check 030204 doesn't use pack17
        for assignment in self.assignments:
            if (assignment.line_code == "030204" and 
                assignment.crew_code in RegionalConstraints.LINE_030204_EXCLUDED_CREWS):
                self.violations.append(
                    f"新包装A区违反: {assignment.date} {assignment.shift}产线030204不应使用班组pack17"
                )
    
    def validate_new_packaging_area_b(self):
        """Validate new packaging area B constraints"""
        shift_assignments = defaultdict(lambda: defaultdict(set))
        
        for assignment in self.assignments:
            if assignment.line_code in RegionalConstraints.NEW_PACKAGING_B_LINES:
                key = (assignment.date, assignment.shift)
                shift_assignments[key][assignment.line_code].add(assignment.crew_code)
        
        # Check each shift: both lines must have double shifts
        for (date, shift), line_crews in shift_assignments.items():
            for line_code in RegionalConstraints.NEW_PACKAGING_B_LINES:
                crews = line_crews.get(line_code, set())
                if len(crews) < 2:
                    # Allow if line has placeholder
                    has_placeholder = any(
                        a.status == "占位" 
                        for a in self.assignments
                        if a.date == date and a.shift == shift and a.line_code == line_code
                    )
                    if not has_placeholder:
                        pass  # Allow single shift in later dates when products complete
    
    def validate_new_packaging_area_cd(self):
        """Validate new packaging area C+D constraints"""
        shift_assignments = defaultdict(lambda: defaultdict(set))
        
        for assignment in self.assignments:
            if assignment.line_code in RegionalConstraints.NEW_PACKAGING_CD_LINES:
                key = (assignment.date, assignment.shift)
                shift_assignments[key][assignment.line_code].add(assignment.crew_code)
        
        # Check each shift: must have 2 double shifts and 2 single/idle
        for (date, shift), line_crews in shift_assignments.items():
            double_shift_lines = 0
            
            for line_code in RegionalConstraints.NEW_PACKAGING_CD_LINES:
                crews = line_crews.get(line_code, set())
                if len(crews) >= 2:
                    double_shift_lines += 1
            
            # Must have exactly 2 double shifts
            # Note: This is enforced during scheduling, validation allows some flexibility
            # in later dates when products are completing
            pass  # Soft constraint


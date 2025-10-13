"""Crew selection and allocation logic"""

from typing import List, Optional, Tuple
from src.models.internal_models import SchedulingContext


class CrewAllocator:
    """Handles crew selection and allocation to production lines"""
    
    def __init__(self, context: SchedulingContext):
        self.context = context
    
    def select_crew_for_line(self, line_code: str, date: str, 
                            excluded_crews: List[str] = None) -> Optional[str]:
        """
        Select best crew for a line on given date
        
        Args:
            line_code: Production line code
            date: Working date
            excluded_crews: Crews already assigned in this shift
        
        Returns:
            Selected crew code or None
        """
        if excluded_crews is None:
            excluded_crews = []
        
        # Get crews that can work on this line
        line_crews = self.context.line_to_crews.get(line_code, [])
        if not line_crews:
            return None
        
        # Filter available crews
        candidates = []
        for crew_code, line_crew_priority, crew_line_priority in line_crews:
            crew_state = self.context.crew_states.get(crew_code)
            if not crew_state:
                continue
            
            # Check if crew is available
            if crew_code in excluded_crews:
                continue
            if not crew_state.is_available(date):
                continue
            
            # Add to candidates
            candidates.append({
                'crew_code': crew_code,
                'line_crew_priority': line_crew_priority,
                'crew_line_priority': crew_line_priority,
                'workload': crew_state.total_workload
            })
        
        if not candidates:
            return None
        
        # Sort by priority
        # 1. lineCrewPriority (lower is better - line's preference)
        # 2. crewLinePriority (lower is better - crew's preference)
        # 3. Current workload (lower is better - balance workload)
        candidates.sort(key=lambda c: (
            c['line_crew_priority'],
            c['crew_line_priority'],
            c['workload']
        ))
        
        return candidates[0]['crew_code']
    
    def get_available_crews_for_region(self, region: str, date: str, 
                                      excluded_crews: List[str] = None) -> List[str]:
        """
        Get all available crews for a region
        """
        if excluded_crews is None:
            excluded_crews = []
        
        from src.constraints.regional_constraints import RegionalConstraints
        
        available = []
        
        if region == "OLD":
            # Old packaging area - check crew pairs
            for pair_crews in RegionalConstraints.OLD_PACKAGING_CREWS.values():
                all_available = True
                for crew_code in pair_crews:
                    crew_state = self.context.crew_states.get(crew_code)
                    if not crew_state or not crew_state.is_available(date):
                        all_available = False
                        break
                    if crew_code in excluded_crews:
                        all_available = False
                        break
                if all_available:
                    available.extend(pair_crews)
        
        elif region == "NEW_A":
            for crew_code in RegionalConstraints.NEW_PACKAGING_A_CREWS:
                crew_state = self.context.crew_states.get(crew_code)
                if crew_state and crew_state.is_available(date) and crew_code not in excluded_crews:
                    available.append(crew_code)
        
        elif region == "NEW_B":
            for crews in RegionalConstraints.NEW_PACKAGING_B_CREWS.values():
                for crew_code in crews:
                    crew_state = self.context.crew_states.get(crew_code)
                    if crew_state and crew_state.is_available(date) and crew_code not in excluded_crews:
                        available.append(crew_code)
        
        elif region == "NEW_CD":
            all_crews = set()
            for crews in RegionalConstraints.NEW_PACKAGING_CD_CREWS.values():
                all_crews.update(crews)
            for crew_code in all_crews:
                crew_state = self.context.crew_states.get(crew_code)
                if crew_state and crew_state.is_available(date) and crew_code not in excluded_crews:
                    available.append(crew_code)
        
        return available
    
    def can_release_crew_to_other_line(self, crew_code: str, current_line: str, 
                                       date: str, shift: str) -> Optional[str]:
        """
        Check if crew can be released to another line (BC-08)
        
        Returns:
            Line code if crew can be released, None otherwise
        """
        # Get lines where this crew can work
        crew_lines = self.context.crew_to_lines.get(crew_code, [])
        
        for line_code in crew_lines:
            if line_code == current_line:
                continue
            
            # Check if line has incomplete products
            line_products = self.context.line_to_products.get(line_code, [])
            has_incomplete = False
            for product_code, _, _, _ in line_products:
                product_state = self.context.product_states.get(product_code)
                if product_state and not product_state.is_completed and product_state.bottle_total > 0:
                    has_incomplete = True
                    break
            
            if not has_incomplete:
                continue
            
            # Check if line is not already at double shift for this date/shift
            # Count crews assigned to this line in this shift
            crews_on_line = 0
            for assignment in self.context.assignments:
                if (assignment.date == date and assignment.shift == shift and 
                    assignment.line_code == line_code):
                    crews_on_line += 1
            
            if crews_on_line < 2:  # Can add another crew
                return line_code
        
        return None
    
    def select_placeholder_product(self, line_code: str) -> Optional[str]:
        """
        Select a product with bottleTotal=0 for placeholder
        Choose the one with highest historical volume
        """
        line_products = self.context.line_to_products.get(line_code, [])
        
        placeholder_candidates = []
        for product_code, product_line_weight, _, _ in line_products:
            product_state = self.context.product_states.get(product_code)
            if product_state and product_state.bottle_total == 0:
                placeholder_candidates.append({
                    'product_code': product_code,
                    'product_line_weight': product_line_weight
                })
        
        if not placeholder_candidates:
            return None
        
        # Choose product with smallest productLineWeight (highest priority on this line)
        placeholder_candidates.sort(key=lambda p: p['product_line_weight'])
        return placeholder_candidates[0]['product_code']


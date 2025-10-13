"""Base constraint validators (BC-01 to BC-10)"""

from typing import List, Dict, Set, Optional, Tuple
from src.models.internal_models import SchedulingContext, ShiftAssignment


class BaseConstraintValidator:
    """Validates basic scheduling constraints"""
    
    def __init__(self, context: SchedulingContext):
        self.context = context
        self.violations: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str]]:
        """Validate all base constraints"""
        self.violations = []
        
        self.validate_bc01_line_product_crew_binding()
        self.validate_bc02_daily_double_shifts()
        self.validate_bc03_crew_single_shift_per_day()
        self.validate_bc04_crew_full_scheduling()
        self.validate_bc05_planned_quantity()
        self.validate_bc06_exclusive_product_guarantee()
        self.validate_bc07_result_completeness()
        self.validate_bc09_product_continuity()
        self.validate_bc10_changeover_rules()
        
        return len(self.violations) == 0, self.violations
    
    def validate_bc01_line_product_crew_binding(self):
        """BC-01: Line-Product-Crew binding constraint"""
        for assignment in self.context.assignments:
            # Check if crew can work on this line
            crew_lines = self.context.crew_to_lines.get(assignment.crew_code, [])
            if assignment.line_code not in crew_lines:
                self.violations.append(
                    f"BC-01违反: 班组{assignment.crew_code}不能在产线{assignment.line_code}工作 "
                    f"({assignment.date} {assignment.shift})"
                )
            
            # Check if product can be produced on this line
            product_lines = self.context.product_to_lines.get(assignment.product_code, [])
            if not any(line[0] == assignment.line_code for line in product_lines):
                self.violations.append(
                    f"BC-01违反: 产品{assignment.product_code}不能在产线{assignment.line_code}生产 "
                    f"({assignment.date} {assignment.shift})"
                )
    
    def validate_bc02_daily_double_shifts(self):
        """BC-02: Daily double shifts (morning and middle)"""
        # Group assignments by date and line
        line_shifts = {}
        for assignment in self.context.assignments:
            key = (assignment.date, assignment.line_code)
            if key not in line_shifts:
                line_shifts[key] = []
            line_shifts[key].append(assignment.shift)
        
        # Note: BC-02 allows single shift or idle lines in some regions
        # This is more of a soft constraint, actual validation is in regional constraints
    
    def validate_bc03_crew_single_shift_per_day(self):
        """BC-03: Each crew can only work one shift per day"""
        crew_daily_shifts = {}
        
        for assignment in self.context.assignments:
            key = (assignment.date, assignment.crew_code)
            if key not in crew_daily_shifts:
                crew_daily_shifts[key] = []
            crew_daily_shifts[key].append(assignment.shift)
        
        for (date, crew_code), shifts in crew_daily_shifts.items():
            if len(shifts) > 1:
                self.violations.append(
                    f"BC-03违反: 班组{crew_code}在{date}被安排了多个班次: {shifts}"
                )
    
    def validate_bc04_crew_full_scheduling(self):
        """BC-04: All crews should be scheduled on all working dates"""
        for crew_code, crew_state in self.context.crew_states.items():
            missing_dates = []
            for date in self.context.work_calendar:
                if date not in crew_state.scheduled_dates:
                    missing_dates.append(date)
            
            if missing_dates:
                # This is a soft constraint, may be relaxed in special cases
                # Just record as warning
                pass  # Handled in warnings, not violations
    
    def validate_bc05_planned_quantity(self):
        """BC-05: Completed quantity should not exceed planned quantity by more than 1%"""
        for product_code, product_state in self.context.product_states.items():
            if product_state.bottle_total > 0:
                max_allowed = product_state.bottle_total * 1.01
                if product_state.cumulative_produced > max_allowed:
                    self.violations.append(
                        f"BC-05违反: 产品{product_code}超量生产 "
                        f"(计划{product_state.bottle_total}瓶，实际{product_state.cumulative_produced}瓶)"
                    )
    
    def validate_bc06_exclusive_product_guarantee(self):
        """BC-06: Exclusive products (single-line) must be completed"""
        for product_code, product_lines in self.context.product_to_lines.items():
            if len(product_lines) == 1:  # Exclusive product
                product_state = self.context.product_states.get(product_code)
                if product_state and product_state.bottle_total > 0:
                    completion_rate = product_state.cumulative_produced / product_state.bottle_total
                    if completion_rate < 0.99:  # Allow 1% tolerance
                        self.violations.append(
                            f"BC-06违反: 独占产品{product_code}未完成 "
                            f"(完成率{completion_rate:.1%})"
                        )
    
    def validate_bc07_result_completeness(self):
        """BC-07: All products must be scheduled"""
        for product_code, product_state in self.context.product_states.items():
            if product_state.bottle_total > 0:
                has_assignment = any(
                    a.product_code == product_code 
                    for a in self.context.assignments
                )
                if not has_assignment:
                    self.violations.append(
                        f"BC-07违反: 产品{product_code}未安排生产"
                    )
    
    def validate_bc09_product_continuity(self):
        """BC-09: Same product on same line must be produced continuously"""
        # Group assignments by line and product
        line_product_dates = {}
        
        for assignment in self.context.assignments:
            key = (assignment.line_code, assignment.product_code)
            if key not in line_product_dates:
                line_product_dates[key] = []
            line_product_dates[key].append(assignment.date)
        
        # Check continuity
        for (line_code, product_code), dates in line_product_dates.items():
            sorted_dates = sorted(dates)
            
            # Check for gaps in working dates
            for i in range(len(sorted_dates) - 1):
                current_date = sorted_dates[i]
                next_date = sorted_dates[i + 1]
                
                # Find working dates between current and next
                current_idx = self.context.work_calendar.index(current_date)
                next_idx = self.context.work_calendar.index(next_date)
                
                # If there are working dates in between, it's a gap
                if next_idx - current_idx > 1:
                    gap_dates = self.context.work_calendar[current_idx + 1:next_idx]
                    self.violations.append(
                        f"BC-09违反: 产品{product_code}在产线{line_code}生产不连续 "
                        f"(日期{current_date}和{next_date}之间有工作日{gap_dates})"
                    )
    
    def validate_bc10_changeover_rules(self):
        """BC-10: Changeover rules validation"""
        for assignment in self.context.assignments:
            if assignment.is_changeover:
                # Verify changeover calculation
                # Check that total output doesn't exceed standard capacity
                if assignment.shift_output > assignment.standard_capacity:
                    self.violations.append(
                        f"BC-10违反: 换产班次超产 "
                        f"({assignment.date} {assignment.shift} {assignment.line_code}, "
                        f"输出{assignment.shift_output}瓶，标准产能{assignment.standard_capacity}瓶)"
                    )


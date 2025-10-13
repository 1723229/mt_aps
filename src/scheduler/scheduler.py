"""Main scheduling engine"""

from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime

from src.models.input_models import SchemeRequestModel
from src.models.internal_models import (
    SchedulingContext, ProductState, CrewState, LineState, ShiftAssignment
)
from src.utils.validators import InputValidator, CapacityFeasibilityChecker
from src.utils.priority_sorter import ProductPrioritySorter
from src.utils.capacity_calculator import CapacityCalculator
from src.scheduler.changeover_handler import ChangeoverHandler
from src.scheduler.crew_allocator import CrewAllocator
from src.scheduler.product_allocator import ProductAllocator
from src.constraints.regional_constraints import RegionalConstraints


class ProductionScheduler:
    """Main production scheduling engine"""
    
    def __init__(self, request: SchemeRequestModel):
        self.request = request
        self.context: SchedulingContext = None
        self.changeover_handler: ChangeoverHandler = None
        self.crew_allocator: CrewAllocator = None
        self.product_allocator: ProductAllocator = None
        self.priority_sorter: ProductPrioritySorter = None
        
    def schedule(self) -> Tuple[bool, SchedulingContext]:
        """
        Execute the scheduling algorithm
        Returns: (success, context)
        """
        # Phase 1: Preprocessing
        success = self._preprocess()
        if not success:
            return False, self.context
        
        # Phase 2: Product prioritization
        priority_products = self.priority_sorter.sort_products()
        
        # Phase 3: Main scheduling loop
        self._schedule_all_dates(priority_products)
        
        # Phase 4: Validation (done separately)
        
        return True, self.context
    
    def _preprocess(self) -> bool:
        """Phase 1: Preprocessing and validation"""
        # Validate input
        validator = InputValidator(self.request)
        is_valid, errors, warnings = validator.validate()
        
        if not is_valid:
            print(f"输入验证失败: {errors}")
            return False
        
        # Build context
        self.context = self._build_context()
        
        # Check capacity feasibility
        checker = CapacityFeasibilityChecker(self.context)
        ratio, status, messages = checker.check_capacity_sufficiency()
        
        for msg in messages:
            if status == "ERROR":
                self.context.errors.append(msg)
            else:
                self.context.warnings.append(msg)
        
        if status == "ERROR":
            return False
        
        # Check exclusive product conflicts
        conflicts = checker.check_exclusive_product_conflicts()
        if conflicts:
            self.context.errors.extend(conflicts)
            return False
        
        # Check priority constraints
        issues = checker.check_priority_constraints_feasibility()
        self.context.warnings.extend(issues)
        
        # Initialize helper classes
        self.changeover_handler = ChangeoverHandler(self.context)
        self.crew_allocator = CrewAllocator(self.context)
        self.product_allocator = ProductAllocator(self.context)
        self.priority_sorter = ProductPrioritySorter(
            self.context.product_states,
            self.context.product_priorities
        )
        
        return True
    
    def _build_context(self) -> SchedulingContext:
        """Build scheduling context from request data"""
        solution = self.request.solutions[0]
        
        # Build product states
        product_states = {}
        for plan in self.request.schedulePlans:
            product_states[plan.productCode] = ProductState(
                product_code=plan.productCode,
                product_name=plan.productName,
                bottle_total=plan.bottleTotal,
                remaining=plan.bottleTotal,
                spec=plan.spec,
                deliver_day=plan.deliverDay
            )
        
        # Build crew states
        crew_states = {}
        for crew_setting in solution.lineCrewSettingDetails:
            if crew_setting.crewCode not in crew_states:
                crew_states[crew_setting.crewCode] = CrewState(
                    crew_code=crew_setting.crewCode,
                    crew_name=crew_setting.crewName
                )
        
        # Build line states
        line_states = {}
        for line_setting in solution.lineProductSettingDetails:
            if line_setting.lineCode not in line_states:
                line_states[line_setting.lineCode] = LineState(
                    line_code=line_setting.lineCode,
                    line_name=line_setting.lineName
                )
        
        # Build relationship maps
        line_to_products = defaultdict(list)
        product_to_lines = defaultdict(list)
        
        for lp in solution.lineProductSettingDetails:
            line_to_products[lp.lineCode].append((
                lp.productCode,
                lp.productLineWeight,
                lp.standardCapacity,
                lp.productionCapacity
            ))
            product_to_lines[lp.productCode].append((
                lp.lineCode,
                lp.productLineWeight
            ))
            line_states[lp.lineCode].available_products.add(lp.productCode)
        
        line_to_crews = defaultdict(list)
        crew_to_lines = defaultdict(list)
        
        for lc in solution.lineCrewSettingDetails:
            line_to_crews[lc.lineCode].append((
                lc.crewCode,
                lc.lineCrewPriority,
                lc.crewLinePriority
            ))
            crew_to_lines[lc.crewCode].append(lc.lineCode)
            line_states[lc.lineCode].available_crews.add(lc.crewCode)
        
        # Build constraints
        forbidden_lines = defaultdict(set)
        product_priorities = {}
        
        for constraint in solution.constraintSettings:
            if not constraint.enable:
                continue
            
            if constraint.constraintType == "line_forbid_time":
                for item in constraint.constraintValue or []:
                    line_code = item.get('lineCode')
                    forbid_time = item.get('forbidTime')
                    if line_code and forbid_time:
                        forbidden_lines[forbid_time].add(line_code)
            
            elif constraint.constraintType == "product_priority":
                for item in constraint.constraintValue or []:
                    product_code = item.get('productCode')
                    distribute_period = item.get('distributePeriod', [])
                    
                    if product_code and distribute_period:
                        # Convert tons to bottles
                        periods = []
                        product_state = product_states.get(product_code)
                        if product_state:
                            for period in distribute_period:
                                assign_dun = period.get('assignDun', 0)
                                spec = product_state.spec
                                # Formula: bottles = tons × 500 × 2124 ÷ spec
                                assign_bottles = int(assign_dun * 500 * 2124 / spec)
                                
                                periods.append({
                                    'assignDate': period.get('assignDate', []),
                                    'assignBottles': assign_bottles
                                })
                                
                                # Mark product as having priority constraint
                                product_state.has_priority_constraint = True
                                product_state.priority_periods = periods
                        
                        product_priorities[product_code] = periods
        
        context = SchedulingContext(
            work_calendar=self.request.workCalendar,
            work_week=self.request.workWeek,
            product_states=product_states,
            crew_states=crew_states,
            line_states=line_states,
            line_to_products=dict(line_to_products),
            product_to_lines=dict(product_to_lines),
            line_to_crews=dict(line_to_crews),
            crew_to_lines=dict(crew_to_lines),
            forbidden_lines=dict(forbidden_lines),
            product_priorities=product_priorities
        )
        
        return context
    
    def _schedule_all_dates(self, priority_products: List[str]):
        """Phase 3: Main scheduling loop"""
        for date in self.context.work_calendar:
            week_num = self.context.work_week.get(date, 0)
            weekday = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
            
            # Get date-specific priority products
            date_priority_products = self.priority_sorter.get_products_for_date(
                date, priority_products
            )
            
            # Schedule each shift
            for shift in ["早班", "中班"]:
                self._schedule_shift(date, shift, week_num, weekday, date_priority_products)
    
    def _schedule_shift(self, date: str, shift: str, week_num: int, weekday: str,
                       priority_products: List[str]):
        """Schedule a single shift"""
        # Get available crews for this shift (not scheduled today)
        available_crews = [
            crew_code for crew_code, crew_state in self.context.crew_states.items()
            if crew_state.is_available(date)
        ]
        
        # Schedule by region
        self._schedule_old_packaging_area(date, shift, week_num, weekday, priority_products, available_crews)
        self._schedule_new_packaging_area_b(date, shift, week_num, weekday, priority_products, available_crews)
        self._schedule_new_packaging_area_a(date, shift, week_num, weekday, priority_products, available_crews)
        self._schedule_new_packaging_area_cd(date, shift, week_num, weekday, priority_products, available_crews)
    
    def _schedule_old_packaging_area(self, date: str, shift: str, week_num: int, weekday: str,
                                    priority_products: List[str], available_crews: List[str]):
        """Schedule old packaging area (fixed crew pairs, 1 line idle)"""
        lines = RegionalConstraints.OLD_PACKAGING_LINES
        crew_pairs = RegionalConstraints.OLD_PACKAGING_CREWS
        
        # Select crew pairs
        assigned_pairs = []
        for pair_name, pair_crews in crew_pairs.items():
            if all(crew in available_crews for crew in pair_crews):
                assigned_pairs.append(pair_crews)
                if len(assigned_pairs) >= 2:
                    break
        
        # Assign to lines (2 pairs to 3 lines = 1 line idle)
        lines_to_use = lines[:len(assigned_pairs)]
        
        for i, line_code in enumerate(lines_to_use):
            if i >= len(assigned_pairs):
                break
            
            pair_crews = assigned_pairs[i]
            for crew_code in pair_crews:
                self._assign_crew_to_line(
                    line_code, crew_code, date, shift, week_num, weekday, priority_products
                )
    
    def _schedule_new_packaging_area_b(self, date: str, shift: str, week_num: int, weekday: str,
                                      priority_products: List[str], available_crews: List[str]):
        """Schedule new packaging area B (double shifts on both lines)"""
        for line_code, crews in RegionalConstraints.NEW_PACKAGING_B_CREWS.items():
            for crew_code in crews:
                if crew_code in available_crews:
                    self._assign_crew_to_line(
                        line_code, crew_code, date, shift, week_num, weekday, priority_products
                    )
    
    def _schedule_new_packaging_area_a(self, date: str, shift: str, week_num: int, weekday: str,
                                      priority_products: List[str], available_crews: List[str]):
        """Schedule new packaging area A (flexible, max 1 idle line)"""
        lines = RegionalConstraints.NEW_PACKAGING_A_LINES
        
        for line_code in lines:
            # Get available crews for this line
            line_crews = self.context.line_to_crews.get(line_code, [])
            
            # Check 030204 exclusion
            excluded = []
            if line_code == "030204":
                excluded = RegionalConstraints.LINE_030204_EXCLUDED_CREWS
            
            for crew_code, _, _ in line_crews:
                if crew_code in available_crews and crew_code not in excluded:
                    # Try to assign
                    current_usage = self.product_allocator.count_line_usage(line_code, date, shift)
                    if current_usage < 2:  # Can add crew
                        self._assign_crew_to_line(
                            line_code, crew_code, date, shift, week_num, weekday, priority_products
                        )
                        if current_usage + 1 >= 1:  # At least one crew assigned
                            break  # Move to next line
    
    def _schedule_new_packaging_area_cd(self, date: str, shift: str, week_num: int, weekday: str,
                                       priority_products: List[str], available_crews: List[str]):
        """Schedule new packaging area C+D (2 double + 2 single)"""
        lines = RegionalConstraints.NEW_PACKAGING_CD_LINES
        
        # Try to achieve 2 double + 2 single pattern
        for line_code in lines:
            line_crews = self.context.line_to_crews.get(line_code, [])
            
            for crew_code, _, _ in line_crews:
                if crew_code in available_crews:
                    current_usage = self.product_allocator.count_line_usage(line_code, date, shift)
                    if current_usage < 2:
                        self._assign_crew_to_line(
                            line_code, crew_code, date, shift, week_num, weekday, priority_products
                        )
    
    def _assign_crew_to_line(self, line_code: str, crew_code: str, date: str, shift: str,
                            week_num: int, weekday: str, priority_products: List[str]):
        """Assign a crew to a line for a shift"""
        # Select product
        product_code = self.product_allocator.select_product_for_line(
            line_code, date, priority_products
        )
        
        if not product_code:
            # Try to find placeholder product
            product_code = self.crew_allocator.select_placeholder_product(line_code)
            if not product_code:
                return  # No product available
        
        product_state = self.context.product_states.get(product_code)
        if not product_state:
            return
        
        # Get capacity
        std_capacity, prod_capacity = CapacityCalculator.get_shift_capacity(
            line_code, product_code, self.context
        )
        
        if std_capacity == 0:
            return
        
        # Calculate output
        shift_output = CapacityCalculator.calculate_shift_output(product_state, prod_capacity)
        
        # Check for changeover
        is_changeover = False
        second_product_code = None
        second_product_output = None
        
        if self.changeover_handler.check_changeover_needed(product_code, prod_capacity, std_capacity):
            next_product = self.changeover_handler.select_next_product_for_changeover(
                line_code, product_code, date
            )
            if next_product:
                first_out, second_out, total_out = self.changeover_handler.calculate_changeover_output(
                    product_code, next_product, std_capacity
                )
                if second_out > 0:
                    shift_output = total_out
                    is_changeover = True
                    second_product_code = next_product
                    second_product_output = second_out
                    
                    # Update first product
                    product_state.update_production(first_out, date, line_code)
                    
                    # Update second product
                    second_product_state = self.context.product_states.get(next_product)
                    if second_product_state:
                        second_product_state.update_production(second_out, date, line_code)
        
        # Update product state (if not changeover)
        if not is_changeover:
            product_state.update_production(shift_output, date, line_code)
        
        # Calculate utilization
        utilization = CapacityCalculator.calculate_utilization(shift_output, std_capacity)
        
        # Create assignment
        assignment = ShiftAssignment(
            date=date,
            shift=shift,
            week_num=week_num,
            weekday=weekday,
            line_code=line_code,
            line_name=self.context.line_states[line_code].line_name,
            product_code=product_code,
            product_name=product_state.product_name,
            crew_code=crew_code,
            crew_name=self.context.crew_states[crew_code].crew_name,
            standard_capacity=std_capacity,
            shift_output=shift_output,
            cumulative_output=product_state.cumulative_produced,
            utilization=utilization,
            is_changeover=is_changeover,
            status="换产" if is_changeover else ("占位" if product_state.bottle_total == 0 else "正常生产"),
            second_product_code=second_product_code,
            second_product_output=second_product_output
        )
        
        self.context.assignments.append(assignment)
        
        # Update crew state
        crew_state = self.context.crew_states[crew_code]
        crew_state.assign_shift(date, line_code, shift_output, std_capacity)
        
        # Update line state
        line_state = self.context.line_states[line_code]
        if not line_state.current_product:
            line_state.start_product(product_code, date)
        if product_state.is_completed:
            line_state.complete_product()


"""Input validation and feasibility checking"""

from typing import Dict, List, Set, Tuple
from collections import defaultdict
from src.models.input_models import SchemeRequestModel, ConstraintSetting
from src.models.internal_models import SchedulingContext, ProductState, CrewState, LineState


class InputValidator:
    """Validates input data and checks scheduling feasibility"""
    
    def __init__(self, request: SchemeRequestModel):
        self.request = request
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate input data
        Returns: (is_valid, errors, warnings)
        """
        # Basic validation
        self._validate_work_calendar()
        self._validate_schedule_plans()
        self._validate_solutions()
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_work_calendar(self):
        """Validate work calendar"""
        if not self.request.workCalendar:
            self.errors.append("工作日历不能为空")
        
        if not self.request.workWeek:
            self.errors.append("周次映射不能为空")
    
    def _validate_schedule_plans(self):
        """Validate schedule plans"""
        if not self.request.schedulePlans:
            self.errors.append("排产计划不能为空")
            return
        
        # Check for duplicate product codes
        product_codes = [p.productCode for p in self.request.schedulePlans]
        if len(product_codes) != len(set(product_codes)):
            self.warnings.append("存在重复的产品编码")
    
    def _validate_solutions(self):
        """Validate solution configurations"""
        if not self.request.solutions:
            self.errors.append("方案配置不能为空")
            return
        
        solution = self.request.solutions[0]
        
        if not solution.lineProductSettingDetails:
            self.errors.append("产线产品配置不能为空")
        
        if not solution.lineCrewSettingDetails:
            self.errors.append("产线班组配置不能为空")


class CapacityFeasibilityChecker:
    """Checks if scheduling is feasible given capacity constraints"""
    
    def __init__(self, context: SchedulingContext):
        self.context = context
    
    def check_capacity_sufficiency(self) -> Tuple[float, str, List[str]]:
        """
        Calculate capacity sufficiency ratio
        Returns: (ratio, status, messages)
        status: "NORMAL" | "WARNING" | "ERROR"
        """
        total_demand = 0
        for product in self.context.product_states.values():
            if product.bottle_total > 0:
                total_demand += product.bottle_total
        
        # Calculate total available capacity
        total_capacity = 0
        num_dates = len(self.context.work_calendar)
        
        for line_code, line_state in self.context.line_states.items():
            # Get line products to find capacity
            line_products = self.context.line_to_products.get(line_code, [])
            if line_products:
                # Use max capacity for this line
                max_cap = max(lp[3] if lp[3] else lp[2] for lp in line_products)
                # 2 shifts per day
                total_capacity += max_cap * 2 * num_dates
        
        if total_capacity == 0:
            return 0.0, "ERROR", ["总可用产能为0，无法排产"]
        
        ratio = total_demand / total_capacity
        messages = []
        
        if ratio > 1.0:
            status = "ERROR"
            messages.append(f"产能严重不足：需求{total_demand}瓶，可用产能{total_capacity}瓶，比率{ratio:.1%}")
            messages.append("建议：增加工作日、减少计划量或增加产线")
        elif ratio > 0.9:
            status = "WARNING"
            messages.append(f"产能紧张：需求{total_demand}瓶，可用产能{total_capacity}瓶，比率{ratio:.1%}")
            messages.append("考虑换产损耗(10%)，实际可用产能约为90%")
        else:
            status = "NORMAL"
            messages.append(f"产能充足：需求{total_demand}瓶，可用产能{total_capacity}瓶，比率{ratio:.1%}")
        
        return ratio, status, messages
    
    def check_exclusive_product_conflicts(self) -> List[str]:
        """Check if exclusive products (single-line products) have conflicts"""
        conflicts = []
        
        for product_code, product_state in self.context.product_states.items():
            # Get lines that can produce this product
            product_lines = self.context.product_to_lines.get(product_code, [])
            
            if len(product_lines) == 1 and product_state.bottle_total > 0:
                # Exclusive product
                line_code = product_lines[0][0]
                
                # Check if line is forbidden on any date
                forbidden_dates = []
                for date in self.context.work_calendar:
                    if line_code in self.context.forbidden_lines.get(date, set()):
                        forbidden_dates.append(date)
                
                if forbidden_dates:
                    # Check if product can be completed on remaining dates
                    available_dates = len(self.context.work_calendar) - len(forbidden_dates)
                    
                    # Get line capacity
                    line_products = self.context.line_to_products.get(line_code, [])
                    line_capacity = 0
                    for lp in line_products:
                        if lp[0] == product_code:
                            line_capacity = lp[3] if lp[3] else lp[2]
                            break
                    
                    total_capacity = line_capacity * 2 * available_dates  # 2 shifts per day
                    
                    if product_state.bottle_total > total_capacity:
                        conflicts.append(
                            f"独占产品 {product_code} 在产线 {line_code} 无法完成："
                            f"需求{product_state.bottle_total}瓶，可用产能{total_capacity}瓶"
                        )
        
        return conflicts
    
    def check_priority_constraints_feasibility(self) -> List[str]:
        """Check if product priority constraints are achievable"""
        issues = []
        
        for product_code, priority_periods in self.context.product_priorities.items():
            product_state = self.context.product_states.get(product_code)
            if not product_state:
                continue
            
            for period in priority_periods:
                assign_dates = period.get('assignDate', [])
                assign_bottles = period.get('assignBottles', 0)
                
                if assign_bottles == 0:
                    continue
                
                # Count available dates in this period
                available_dates = [d for d in assign_dates if d in self.context.work_calendar]
                
                if not available_dates:
                    issues.append(
                        f"产品 {product_code} 的优先级约束日期都不在工作日历中"
                    )
                    continue
                
                # Get lines that can produce this product
                product_lines = self.context.product_to_lines.get(product_code, [])
                if not product_lines:
                    issues.append(f"产品 {product_code} 没有配置可用产线")
                    continue
                
                # Estimate capacity for this period
                max_capacity_per_shift = 0
                for line_code, _ in product_lines:
                    line_products = self.context.line_to_products.get(line_code, [])
                    for lp in line_products:
                        if lp[0] == product_code:
                            cap = lp[3] if lp[3] else lp[2]
                            max_capacity_per_shift = max(max_capacity_per_shift, cap)
                
                # Assuming best case: product uses all available capacity
                period_capacity = max_capacity_per_shift * 2 * len(available_dates)
                
                if assign_bottles > period_capacity:
                    issues.append(
                        f"产品 {product_code} 的优先级约束可能无法满足："
                        f"要求{assign_bottles}瓶，期间最大产能约{period_capacity}瓶"
                    )
        
        return issues


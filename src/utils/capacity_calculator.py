"""Capacity and utilization calculations"""

from typing import Dict, Tuple
from src.models.internal_models import SchedulingContext, ProductState, ShiftAssignment


class CapacityCalculator:
    """Calculates capacity and utilization metrics"""
    
    @staticmethod
    def get_shift_capacity(line_code: str, product_code: str, context: SchedulingContext) -> Tuple[int, int]:
        """
        Get standard and production capacity for a product on a line
        Returns: (standard_capacity, production_capacity)
        """
        line_products = context.line_to_products.get(line_code, [])
        
        for lp_product_code, _, std_cap, prod_cap in line_products:
            if lp_product_code == product_code:
                # Use production capacity if available, otherwise standard capacity
                actual_capacity = prod_cap if prod_cap and prod_cap > 0 else std_cap
                return std_cap, actual_capacity
        
        return 0, 0
    
    @staticmethod
    def calculate_shift_output(product_state: ProductState, capacity: int) -> int:
        """
        Calculate how much to produce in a shift
        """
        return min(product_state.remaining, capacity)
    
    @staticmethod
    def calculate_utilization(shift_output: int, standard_capacity: int) -> float:
        """Calculate capacity utilization rate"""
        if standard_capacity == 0:
            return 0.0
        return shift_output / standard_capacity
    
    @staticmethod
    def calculate_crew_workload(crew_code: str, context: SchedulingContext) -> Dict:
        """Calculate workload metrics for a crew"""
        crew_state = context.crew_states.get(crew_code)
        if not crew_state:
            return {}
        
        avg_utilization = 0.0
        if crew_state.shifts_worked > 0:
            avg_utilization = crew_state.total_workload / crew_state.shifts_worked
        
        return {
            'crew_code': crew_code,
            'shifts_worked': crew_state.shifts_worked,
            'total_bottles': crew_state.total_bottles_produced,
            'average_utilization': avg_utilization,
            'total_workload': crew_state.total_workload,
            'assigned_lines': list(crew_state.assigned_lines)
        }
    
    @staticmethod
    def calculate_overall_utilization(context: SchedulingContext) -> Dict:
        """Calculate overall capacity utilization"""
        total_shifts = 0
        effective_shifts = 0
        idle_shifts = 0
        changeover_shifts = 0
        total_utilization = 0.0
        max_utilization = 0.0
        min_utilization = 1.0
        
        for assignment in context.assignments:
            total_shifts += 1
            
            if assignment.shift_output > 0:
                effective_shifts += 1
                total_utilization += assignment.utilization
                max_utilization = max(max_utilization, assignment.utilization)
                min_utilization = min(min_utilization, assignment.utilization)
            else:
                idle_shifts += 1
            
            if assignment.is_changeover:
                changeover_shifts += 1
        
        avg_utilization = total_utilization / effective_shifts if effective_shifts > 0 else 0.0
        changeover_rate = changeover_shifts / effective_shifts if effective_shifts > 0 else 0.0
        
        # Calculate product completion
        total_planned = 0
        total_completed = 0
        for product_state in context.product_states.values():
            if product_state.bottle_total > 0:
                total_planned += product_state.bottle_total
                total_completed += product_state.cumulative_produced
        
        completion_rate = total_completed / total_planned if total_planned > 0 else 0.0
        
        return {
            'total_shifts': total_shifts,
            'effective_shifts': effective_shifts,
            'idle_shifts': idle_shifts,
            'average_utilization': avg_utilization,
            'max_utilization': max_utilization,
            'min_utilization': min_utilization if effective_shifts > 0 else 0.0,
            'changeover_shifts': changeover_shifts,
            'changeover_rate': changeover_rate,
            'total_planned_bottles': total_planned,
            'total_completed_bottles': total_completed,
            'total_completion_rate': completion_rate
        }
    
    @staticmethod
    def calculate_crew_balance(context: SchedulingContext) -> Dict:
        """Calculate crew workload balance metrics"""
        workloads = []
        
        for crew_state in context.crew_states.values():
            if crew_state.shifts_worked > 0:
                workloads.append(crew_state.total_workload)
        
        if not workloads:
            return {'balance_score': 1.0, 'max_diff_pct': 0.0}
        
        max_workload = max(workloads)
        min_workload = min(workloads)
        avg_workload = sum(workloads) / len(workloads)
        
        if avg_workload > 0:
            balance_diff_pct = (max_workload - min_workload) / avg_workload
        else:
            balance_diff_pct = 0.0
        
        return {
            'balance_score': 1.0 - balance_diff_pct,
            'max_diff_pct': balance_diff_pct,
            'max_workload': max_workload,
            'min_workload': min_workload,
            'avg_workload': avg_workload
        }


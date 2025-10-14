"""Capacity optimizer for production planning."""

from typing import Dict, Optional
from ..models.input_models import LineProductSetting


class CapacityOptimizer:
    """Optimizes capacity utilization for production scheduling."""
    
    def get_effective_capacity(self, setting: LineProductSetting) -> int:
        """Get effective capacity to use for scheduling.
        
        Uses productionCapacity if set, otherwise standardCapacity.
        
        Args:
            setting: Line-product setting
        
        Returns:
            Effective capacity in bottles
        """
        return setting.get_effective_capacity()
    
    def get_standard_capacity(self, setting: LineProductSetting) -> int:
        """Get standard capacity for utilization calculation.
        
        Always use standardCapacity for metrics.
        
        Args:
            setting: Line-product setting
        
        Returns:
            Standard capacity in bottles
        """
        return setting.standardCapacity
    
    def calculate_shift_quantity(
        self,
        remaining_bottles: int,
        effective_capacity: int,
        standard_capacity: int,
    ) -> int:
        """Calculate quantity to produce in a shift.
        
        Args:
            remaining_bottles: Remaining bottles for product
            effective_capacity: Effective capacity for this shift
            standard_capacity: Standard capacity (for limits)
        
        Returns:
            Quantity to produce (bottles)
        """
        # Don't exceed remaining
        quantity = min(remaining_bottles, effective_capacity)
        
        # Don't exceed standard capacity (hard limit)
        quantity = min(quantity, standard_capacity)
        
        return quantity
    
    def calculate_utilization(
        self,
        planned_quantity: int,
        standard_capacity: int,
    ) -> float:
        """Calculate capacity utilization for a shift.
        
        Args:
            planned_quantity: Bottles planned for production
            standard_capacity: Standard capacity
        
        Returns:
            Utilization as fraction (0.0 to 1.0)
        """
        if standard_capacity == 0:
            return 0.0
        return planned_quantity / standard_capacity
    
    def optimize_allocation(
        self,
        remaining_bottles: int,
        num_shifts_available: int,
        capacity_per_shift: int,
    ) -> list:
        """Optimize distribution of bottles across shifts.
        
        Tries to balance production across shifts.
        
        Args:
            remaining_bottles: Total bottles to allocate
            num_shifts_available: Number of shifts available
            capacity_per_shift: Capacity per shift
        
        Returns:
            List of quantities per shift
        """
        if num_shifts_available == 0:
            return []
        
        # Simple strategy: fill shifts evenly
        per_shift = remaining_bottles // num_shifts_available
        remainder = remaining_bottles % num_shifts_available
        
        allocations = []
        for i in range(num_shifts_available):
            qty = per_shift
            if i < remainder:
                qty += 1
            
            # Don't exceed capacity
            qty = min(qty, capacity_per_shift)
            allocations.append(qty)
        
        return allocations
    
    def can_fit_in_shift(
        self,
        current_quantity: int,
        additional_quantity: int,
        standard_capacity: int,
    ) -> bool:
        """Check if additional quantity can fit in a shift.
        
        Args:
            current_quantity: Already planned quantity
            additional_quantity: Additional quantity to add
            standard_capacity: Standard capacity limit
        
        Returns:
            True if it fits
        """
        total = current_quantity + additional_quantity
        return total <= standard_capacity


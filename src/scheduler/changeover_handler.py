"""Changeover handler - implements BC-10.

BC-10: 换产规则
- Triggered when product reaches bottleTotal with capacity remaining
- Only on the last shift for that product
- Calculate changeover capacity with 10% loss for setup
- Prefer same baseSpiritCode for second product
- Max one changeover per shift (2 products total)
"""

from typing import Optional, List, Tuple
from ..models.input_models import ScheduleIndices


class ChangeoverHandler:
    """Handles changeover logic and calculations."""
    
    def __init__(self, indices: ScheduleIndices):
        """Initialize handler.
        
        Args:
            indices: Schedule indices for lookups
        """
        self.indices = indices
    
    def should_changeover(
        self,
        line_code: str,
        product_code: str,
        remaining_bottles: int,
        standard_capacity: int,
    ) -> bool:
        """Determine if changeover should happen.
        
        Changeover happens when:
        1. Remaining bottles < standard capacity (product will complete this shift)
        2. Product is finishing (this is the last production)
        
        Args:
            line_code: Line code
            product_code: Product code
            remaining_bottles: Remaining bottles to produce
            standard_capacity: Standard capacity of the shift
        
        Returns:
            True if changeover should happen
        """
        # Only changeover if remaining less than capacity
        # (product completes in this shift with room left)
        return 0 < remaining_bottles < standard_capacity
    
    def calculate_changeover(
        self,
        line_code: str,
        first_product_code: str,
        first_remaining: int,
        standard_capacity: int,
        effective_capacity: int,
    ) -> Tuple[int, int]:
        """Calculate production quantities for changeover.
        
        Formula:
        1. First product uses all remaining
        2. Second product capacity = standard_capacity × (1 - first_used/standard - 0.1)
           where 0.1 = 10% changeover loss
        
        Args:
            line_code: Line code
            first_product_code: First product code
            first_remaining: Remaining bottles for first product
            standard_capacity: Standard capacity for utilization calc
            effective_capacity: Effective capacity for scheduling
        
        Returns:
            (first_quantity, second_available_capacity)
        """
        # First product uses all remaining
        first_qty = first_remaining
        
        # Calculate utilization of first product
        utilization = first_qty / standard_capacity
        
        # Second product gets remaining capacity minus 10% changeover loss
        # Available = standard_capacity × (1 - utilization - 0.1)
        second_available = int(standard_capacity * (1 - utilization - 0.1))
        
        # Ensure non-negative
        second_available = max(0, second_available)
        
        return first_qty, second_available
    
    def select_changeover_product(
        self,
        line_code: str,
        first_product_code: str,
        available_capacity: int,
        product_remaining: dict,
        products_on_line: set = None,
    ) -> Optional[str]:
        """Select the best product for changeover.
        
        Preference order:
        1. Same baseSpiritCode as first product
        2. Product with remaining quantity
        3. Product that can be produced on this line
        4. Product not already produced on this line (BC-09 protection)
        
        Args:
            line_code: Line code
            first_product_code: First product code
            available_capacity: Available capacity for second product
            product_remaining: Dict of product_code -> remaining bottles
            products_on_line: Set of products already produced on this line (for BC-09)
        
        Returns:
            Selected product code or None if no suitable product
        """
        if available_capacity <= 0:
            return None
        
        if products_on_line is None:
            products_on_line = set()
        
        first_product = self.indices.products_by_code.get(first_product_code)
        if not first_product:
            return None
        
        first_spirit = first_product.baseSpiritCode
        
        # Get products that can be produced on this line
        line_products = self.indices.products_for_line.get(line_code, [])
        
        candidates = []
        for setting in line_products:
            product_code = setting.productCode
            
            # Skip if no remaining quantity
            if product_remaining.get(product_code, 0) <= 0:
                continue
            
            # Skip if same as first product
            if product_code == first_product_code:
                continue
            
            # BC-09 PROTECTION: Skip products already produced on this line
            # (to avoid discontinuity)
            if product_code in products_on_line:
                continue
            
            product = self.indices.products_by_code.get(product_code)
            if not product:
                continue
            
            # Check if same spirit (higher priority)
            same_spirit = product.baseSpiritCode == first_spirit
            
            candidates.append((product_code, same_spirit, product_remaining[product_code]))
        
        if not candidates:
            return None
        
        # Sort by: same spirit first, then by remaining quantity (higher first)
        candidates.sort(key=lambda x: (not x[1], -x[2]))
        
        return candidates[0][0]
    
    def validate_changeover(
        self,
        first_qty: int,
        second_qty: int,
        standard_capacity: int,
    ) -> bool:
        """Validate changeover doesn't exceed capacity.
        
        Args:
            first_qty: First product quantity
            second_qty: Second product quantity
            standard_capacity: Standard capacity
        
        Returns:
            True if valid
        """
        total = first_qty + second_qty
        # Allow small rounding error
        return total <= standard_capacity + 1


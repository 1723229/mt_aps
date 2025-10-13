"""Product changeover logic with 0.9 coefficient"""

from typing import Optional, Tuple
from src.models.internal_models import SchedulingContext, ProductState


class ChangeoverHandler:
    """Handles product changeover scenarios"""
    
    # Changeover loss coefficient (10% capacity loss during changeover)
    CHANGEOVER_COEFFICIENT = 0.9
    
    def __init__(self, context: SchedulingContext):
        self.context = context
    
    def check_changeover_needed(self, product_code: str, shift_capacity: int, 
                                standard_capacity: int) -> bool:
        """
        Check if changeover is possible/needed for current shift
        Returns True if product will complete and there's room for another product
        """
        product_state = self.context.product_states.get(product_code)
        if not product_state:
            return False
        
        # Changeover only happens when product completes and there's remaining capacity
        remaining = product_state.remaining
        if remaining <= 0:
            return False
        
        if remaining < shift_capacity:
            # Product will complete in this shift
            # Check if there's enough remaining capacity for changeover
            available_capacity = standard_capacity - remaining
            if available_capacity > standard_capacity * 0.1:  # At least 10% capacity available
                return True
        
        return False
    
    def calculate_changeover_output(self, first_product_code: str, second_product_code: str,
                                   standard_capacity: int) -> Tuple[int, int, int]:
        """
        Calculate output for changeover scenario
        
        Args:
            first_product_code: Product completing in this shift
            second_product_code: Product starting in this shift
            standard_capacity: Standard capacity of second product on this line
        
        Returns:
            (first_product_output, second_product_output, total_output)
        """
        first_product = self.context.product_states.get(first_product_code)
        second_product = self.context.product_states.get(second_product_code)
        
        if not first_product or not second_product:
            return 0, 0, 0
        
        # First product uses its remaining quantity
        first_output = first_product.remaining
        
        # Calculate available capacity after completing first product
        available_capacity = standard_capacity - first_output
        
        # Apply changeover coefficient (10% loss for changeover preparation)
        usable_capacity = int(available_capacity * self.CHANGEOVER_COEFFICIENT)
        
        # Second product can use min of (usable capacity, its remaining quantity)
        second_output = min(usable_capacity, second_product.remaining)
        
        # Total output
        total_output = first_output + second_output
        
        # Verify no overproduction
        if total_output > standard_capacity:
            # Adjust second product output to not exceed standard capacity
            second_output = standard_capacity - first_output
            total_output = standard_capacity
        
        return first_output, second_output, total_output
    
    def select_next_product_for_changeover(self, line_code: str, 
                                          current_product_code: str,
                                          date: str) -> Optional[str]:
        """
        Select the next product to produce after changeover
        
        Args:
            line_code: Production line code
            current_product_code: Currently completing product
            date: Current date
        
        Returns:
            Product code or None if no suitable product
        """
        # Get products that can be produced on this line
        line_products = self.context.line_to_products.get(line_code, [])
        
        # Build candidate list
        candidates = []
        for product_code, _, _, _ in line_products:
            if product_code == current_product_code:
                continue
            
            product_state = self.context.product_states.get(product_code)
            if not product_state:
                continue
            
            # Skip completed products
            if product_state.is_completed or product_state.remaining <= 0:
                continue
            
            # Skip zero-quantity products (they're for placeholder only)
            if product_state.bottle_total == 0:
                continue
            
            # Check if product has priority for this date
            has_priority = False
            if product_code in self.context.product_priorities:
                for period in self.context.product_priorities[product_code]:
                    if date in period.get('assignDate', []):
                        has_priority = True
                        break
            
            # Add to candidates with priority info
            candidates.append({
                'product_code': product_code,
                'has_priority': has_priority,
                'has_delivery': product_state.deliver_day is not None,
                'deliver_day': product_state.deliver_day or '9999-12-31',
                'remaining': product_state.remaining
            })
        
        if not candidates:
            return None
        
        # Sort by priority
        candidates.sort(key=lambda c: (
            not c['has_priority'],  # Priority products first
            not c['has_delivery'],  # Products with delivery date
            c['deliver_day'],       # Earlier delivery first
            -c['remaining']         # Larger remaining quantity first
        ))
        
        return candidates[0]['product_code']
    
    def can_changeover(self, first_product_remaining: int, standard_capacity: int) -> bool:
        """
        Check if changeover is feasible
        """
        available = standard_capacity - first_product_remaining
        usable = available * self.CHANGEOVER_COEFFICIENT
        # Only worthwhile if we can produce at least 10% of capacity
        return usable >= standard_capacity * 0.1


"""Product priority sorting logic"""

from typing import List, Dict, Tuple
from src.models.internal_models import ProductState


class ProductPrioritySorter:
    """Sorts products by priority for scheduling"""
    
    def __init__(self, product_states: Dict[str, ProductState], product_priorities: Dict[str, List[Dict]]):
        self.product_states = product_states
        self.product_priorities = product_priorities
    
    def sort_products(self) -> List[str]:
        """
        Sort all products by priority
        Returns list of product codes in priority order
        """
        products = []
        
        for product_code, product_state in self.product_states.items():
            if product_state.bottle_total == 0:
                continue  # Skip zero-quantity products for now
            
            # Determine priority factors
            has_priority_constraint = product_code in self.product_priorities
            has_delivery_date = product_state.deliver_day is not None
            bottle_total = product_state.bottle_total
            
            products.append({
                'product_code': product_code,
                'has_priority_constraint': has_priority_constraint,
                'has_delivery_date': has_delivery_date,
                'deliver_day': product_state.deliver_day or '9999-12-31',
                'bottle_total': bottle_total
            })
        
        # Sort by priority rules:
        # 1. Products with priority constraints first
        # 2. Products with delivery date (earliest first)
        # 3. Products by bottle total (largest first)
        sorted_products = sorted(products, key=lambda p: (
            not p['has_priority_constraint'],  # False sorts before True
            not p['has_delivery_date'],
            p['deliver_day'],
            -p['bottle_total']
        ))
        
        return [p['product_code'] for p in sorted_products]
    
    def get_products_for_date(self, date: str, all_products: List[str]) -> List[str]:
        """
        Get products that should be prioritized for a specific date
        considering product_priority constraints
        """
        priority_products = []
        other_products = []
        
        for product_code in all_products:
            product_state = self.product_states.get(product_code)
            if not product_state or product_state.is_completed:
                continue
            
            # Check if product has priority constraint for this date
            if product_code in self.product_priorities:
                for period in self.product_priorities[product_code]:
                    assign_dates = period.get('assignDate', [])
                    if date in assign_dates:
                        # Check if we still need to produce for this period
                        assign_bottles = period.get('assignBottles', 0)
                        if assign_bottles > 0:
                            priority_products.append(product_code)
                            break
                else:
                    other_products.append(product_code)
            else:
                other_products.append(product_code)
        
        return priority_products + other_products
    
    def sort_products_for_line(self, line_code: str, available_products: List[str]) -> List[str]:
        """
        Sort products available for a specific line
        considering productLineWeight
        """
        product_priorities = []
        
        for product_code in available_products:
            product_state = self.product_states.get(product_code)
            if not product_state or product_state.is_completed:
                continue
            
            # This should be handled by product_to_lines mapping
            # which already has productLineWeight
            product_priorities.append(product_code)
        
        return product_priorities


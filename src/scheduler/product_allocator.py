"""Product-to-line assignment logic"""

from typing import List, Optional, Tuple
from src.models.internal_models import SchedulingContext


class ProductAllocator:
    """Handles product assignment to production lines"""
    
    def __init__(self, context: SchedulingContext):
        self.context = context
    
    def select_product_for_line(self, line_code: str, date: str, 
                               priority_products: List[str]) -> Optional[str]:
        """
        Select product to produce on a line for given date
        
        Args:
            line_code: Production line code
            date: Working date
            priority_products: List of products sorted by priority
        
        Returns:
            Selected product code or None
        """
        line_state = self.context.line_states.get(line_code)
        if not line_state:
            return None
        
        # First, check if line has ongoing product (continuity constraint BC-09)
        if line_state.current_product:
            product_state = self.context.product_states.get(line_state.current_product)
            if product_state and not product_state.is_completed and product_state.remaining > 0:
                return line_state.current_product
        
        # Get products that can be produced on this line
        line_products = self.context.line_to_products.get(line_code, [])
        line_product_codes = {lp[0]: lp[1] for lp in line_products}  # product_code: productLineWeight
        
        # Filter priority products to those available on this line
        candidates = []
        for product_code in priority_products:
            if product_code not in line_product_codes:
                continue
            
            product_state = self.context.product_states.get(product_code)
            if not product_state:
                continue
            
            # Skip completed products
            if product_state.is_completed or product_state.remaining <= 0:
                continue
            
            # Skip zero-quantity products (for now)
            if product_state.bottle_total == 0:
                continue
            
            # Check priority constraints for this date
            has_date_priority = False
            if product_code in self.context.product_priorities:
                for period in self.context.product_priorities[product_code]:
                    if date in period.get('assignDate', []):
                        has_date_priority = True
                        break
            
            candidates.append({
                'product_code': product_code,
                'product_line_weight': line_product_codes[product_code],
                'has_date_priority': has_date_priority,
                'remaining': product_state.remaining
            })
        
        if not candidates:
            return None
        
        # Sort by productLineWeight (lower is better - higher priority on this line)
        # Then by date priority, then by remaining quantity
        candidates.sort(key=lambda c: (
            not c['has_date_priority'],
            c['product_line_weight'],
            -c['remaining']
        ))
        
        return candidates[0]['product_code']
    
    def get_lines_for_product(self, product_code: str) -> List[Tuple[str, int]]:
        """
        Get lines that can produce this product, sorted by priority
        
        Returns:
            List of (line_code, productLineWeight) tuples, sorted by weight
        """
        product_lines = self.context.product_to_lines.get(product_code, [])
        
        # Sort by productLineWeight (lower is better)
        sorted_lines = sorted(product_lines, key=lambda x: x[1])
        
        return sorted_lines
    
    def is_line_available(self, line_code: str, date: str) -> bool:
        """
        Check if line is available (not forbidden) on given date
        """
        forbidden_lines = self.context.forbidden_lines.get(date, set())
        return line_code not in forbidden_lines
    
    def count_line_usage(self, line_code: str, date: str, shift: str) -> int:
        """
        Count how many crews are already assigned to this line in this shift
        """
        count = 0
        for assignment in self.context.assignments:
            if (assignment.line_code == line_code and 
                assignment.date == date and 
                assignment.shift == shift):
                count += 1
        return count
    
    def select_line_for_product(self, product_code: str, date: str, shift: str,
                               available_crews: List[str]) -> Optional[str]:
        """
        Select best line for producing a product
        
        Args:
            product_code: Product to produce
            date: Working date
            shift: Shift ("早班" or "中班")
            available_crews: Available crews for assignment
        
        Returns:
            Selected line code or None
        """
        # Get lines sorted by priority for this product
        product_lines = self.get_lines_for_product(product_code)
        
        for line_code, _ in product_lines:
            # Check if line is available
            if not self.is_line_available(line_code, date):
                continue
            
            # Check if line is not full (max 2 crews per shift)
            current_usage = self.count_line_usage(line_code, date, shift)
            if current_usage >= 2:
                continue
            
            # Check if there's a crew available for this line
            line_crews = self.context.line_to_crews.get(line_code, [])
            has_available_crew = False
            for crew_code, _, _ in line_crews:
                if crew_code in available_crews:
                    crew_state = self.context.crew_states.get(crew_code)
                    if crew_state and crew_state.is_available(date):
                        has_available_crew = True
                        break
            
            if not has_available_crew:
                continue
            
            # This line is suitable
            return line_code
        
        return None
    
    def check_product_priority_constraint(self, product_code: str, date: str) -> bool:
        """
        Check if product has priority constraint for this date
        """
        if product_code not in self.context.product_priorities:
            return False
        
        for period in self.context.product_priorities[product_code]:
            if date in period.get('assignDate', []):
                return True
        
        return False


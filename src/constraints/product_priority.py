"""Product priority constraint handler."""

from typing import Dict, List
from dataclasses import dataclass
from ..models.input_models import ConstraintSetting, SchedulePlan
from ..utils.helpers import calculate_bottles_from_tons


@dataclass
class PriorityPeriod:
    """A priority period for a product."""
    
    product_code: str
    dates: List[str]  # Dates in this period
    required_bottles: int  # Bottles that must be produced in this period
    spec: int  # Product specification
    order: int  # Order in constraint list (for prioritization)


class ProductPriorityConstraint:
    """Handles product_priority constraints."""
    
    def __init__(
        self, 
        constraints: List[ConstraintSetting],
        products: Dict[str, SchedulePlan],
    ):
        """Initialize from constraint settings.
        
        Args:
            constraints: List of product_priority constraint settings
            products: Product lookup by code
        """
        self.products = products
        self.priority_periods: List[PriorityPeriod] = []
        
        for constraint in constraints:
            if constraint.constraintType == 'product_priority' and constraint.enable:
                self._parse_constraint(constraint)
    
    def _parse_constraint(self, constraint: ConstraintSetting):
        """Parse a product_priority constraint.
        
        Expected format:
        {
            "constraintValue": [
                {
                    "productCode": "MT0010010778",
                    "productName": "...",
                    "distributePeriod": [
                        {
                            "assignDate": ["2025-10-07", "2025-10-08", ...],
                            "assignDun": 204.71
                        },
                        ...
                    ]
                },
                ...
            ]
        }
        """
        if not isinstance(constraint.constraintValue, list):
            return
        
        order = 0
        for item in constraint.constraintValue:
            if not isinstance(item, dict):
                continue
            
            product_code = item.get('productCode')
            if not product_code or product_code not in self.products:
                continue
            
            product = self.products[product_code]
            distribute_periods = item.get('distributePeriod', [])
            
            for period in distribute_periods:
                if not isinstance(period, dict):
                    continue
                
                dates = period.get('assignDate', [])
                assign_dun = period.get('assignDun', 0)
                
                if not dates or not assign_dun:
                    continue
                
                # Convert tons to bottles
                required_bottles = calculate_bottles_from_tons(assign_dun, product.spec)
                
                # Don't exceed total plan
                required_bottles = min(required_bottles, product.bottleTotal)
                
                priority_period = PriorityPeriod(
                    product_code=product_code,
                    dates=dates,
                    required_bottles=required_bottles,
                    spec=product.spec,
                    order=order,
                )
                
                self.priority_periods.append(priority_period)
                order += 1
    
    def get_priority_periods(self) -> List[PriorityPeriod]:
        """Get all priority periods sorted by order.
        
        Returns:
            List of PriorityPeriod sorted by constraint order
        """
        return sorted(self.priority_periods, key=lambda p: p.order)
    
    def get_periods_for_product(self, product_code: str) -> List[PriorityPeriod]:
        """Get priority periods for a specific product.
        
        Args:
            product_code: Product code
        
        Returns:
            List of PriorityPeriod for this product
        """
        return [p for p in self.priority_periods if p.product_code == product_code]
    
    def get_periods_for_date(self, date: str) -> List[PriorityPeriod]:
        """Get priority periods that include a date.
        
        Args:
            date: Date string
        
        Returns:
            List of PriorityPeriod that include this date
        """
        return [p for p in self.priority_periods if date in p.dates]
    
    def has_priority(self, product_code: str) -> bool:
        """Check if a product has any priority constraints.
        
        Args:
            product_code: Product code
        
        Returns:
            True if product has priority constraints
        """
        return any(p.product_code == product_code for p in self.priority_periods)


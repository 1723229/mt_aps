"""Internal scheduling state management."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime


@dataclass
class ProductionRecord:
    """Record of production for a specific shift slot."""
    
    line_code: str
    date: str
    shift: str  # 'early' or 'middle'
    product_code: str
    crew_code: str
    planned_quantity: int  # Bottles to produce
    standard_capacity: int  # Standard capacity for utilization calc
    is_changeover: bool = False  # True if this is part of changeover
    changeover_sequence: int = 0  # 0 for normal, 1 for first, 2 for second in changeover


@dataclass
class ShiftSlot:
    """Represents a single line-date-shift slot."""
    
    line_code: str
    date: str
    shift: str
    
    def __hash__(self):
        return hash((self.line_code, self.date, self.shift))
    
    def __eq__(self, other):
        if not isinstance(other, ShiftSlot):
            return False
        return (
            self.line_code == other.line_code
            and self.date == other.date
            and self.shift == other.shift
        )


class ScheduleState:
    """Maintains the current state of the schedule."""
    
    def __init__(
        self,
        products: Dict[str, int],  # product_code -> bottleTotal
        work_calendar: List[str],
        work_week: Dict[str, int],
        all_lines: Set[str],
        all_crews: Set[str],
    ):
        # Product tracking
        self.products = products.copy()
        self.product_remaining: Dict[str, int] = products.copy()
        self.product_scheduled: Dict[str, int] = {p: 0 for p in products}
        
        # Calendar
        self.work_calendar = work_calendar
        self.work_week = work_week
        self.all_lines = all_lines
        self.all_crews = all_crews
        
        # Production records
        self.records: List[ProductionRecord] = []
        
        # Slot assignments
        self.slot_assignments: Dict[ShiftSlot, List[ProductionRecord]] = {}
        
        # Crew tracking (crew -> date -> shift or None)
        self.crew_date_shift: Dict[str, Dict[str, Optional[str]]] = {
            crew: {date: None for date in work_calendar}
            for crew in all_crews
        }
        
        # Line tracking for continuity (line -> current_product or None)
        # Tracks the last product on each line to enforce BC-09
        self.line_current_product: Dict[str, Optional[str]] = {
            line: None for line in all_lines
        }
        
        # Track when a line's current product is finished
        self.line_product_finished: Dict[Tuple[str, str], bool] = {}
        
        # Crew shift preferences (crew -> date -> preferred_shift)
        # Set by crew_shift_planner
        self.crew_shift_plan: Dict[str, Dict[str, str]] = {}
    
    def add_production(
        self,
        line_code: str,
        date: str,
        shift: str,
        product_code: str,
        crew_code: str,
        quantity: int,
        standard_capacity: int,
        is_changeover: bool = False,
        changeover_sequence: int = 0,
    ) -> ProductionRecord:
        """Add a production record to the schedule."""
        # Validate
        if quantity > self.product_remaining.get(product_code, 0):
            raise ValueError(
                f"Quantity {quantity} exceeds remaining {self.product_remaining[product_code]} "
                f"for product {product_code}"
            )
        
        # Create record
        record = ProductionRecord(
            line_code=line_code,
            date=date,
            shift=shift,
            product_code=product_code,
            crew_code=crew_code,
            planned_quantity=quantity,
            standard_capacity=standard_capacity,
            is_changeover=is_changeover,
            changeover_sequence=changeover_sequence,
        )
        
        # Update tracking
        self.records.append(record)
        
        slot = ShiftSlot(line_code, date, shift)
        if slot not in self.slot_assignments:
            self.slot_assignments[slot] = []
        self.slot_assignments[slot].append(record)
        
        # Update product quantities
        self.product_remaining[product_code] -= quantity
        self.product_scheduled[product_code] += quantity
        
        # Update crew assignment
        self.crew_date_shift[crew_code][date] = shift
        
        # Update line current product
        # Only update if not changeover or if first in changeover
        if not is_changeover or changeover_sequence == 1:
            self.line_current_product[line_code] = product_code
        
        # Check if product is finished on this line
        if self.product_remaining[product_code] == 0:
            self.line_product_finished[(line_code, product_code)] = True
        
        return record
    
    def is_crew_available(self, crew_code: str, date: str, shift: str) -> bool:
        """Check if crew is available for a shift."""
        return self.crew_date_shift[crew_code][date] is None
    
    def is_slot_available(self, line_code: str, date: str, shift: str) -> bool:
        """Check if a shift slot is available."""
        slot = ShiftSlot(line_code, date, shift)
        return slot not in self.slot_assignments or len(self.slot_assignments[slot]) == 0
    
    def get_slot_assignment(self, line_code: str, date: str, shift: str) -> List[ProductionRecord]:
        """Get production records for a slot."""
        slot = ShiftSlot(line_code, date, shift)
        return self.slot_assignments.get(slot, [])
    
    def can_continue_product(self, line_code: str, product_code: str) -> bool:
        """Check if a product can continue on a line (BC-09 continuity).
        
        BC-09: Same product on same line must be continuous.
        Once a product starts, it should not be interrupted by another product.
        """
        current = self.line_current_product.get(line_code)
        
        # No current product - can start any product
        if current is None:
            return True
        
        # Same product - can always continue
        if current == product_code:
            return True
        
        # Different product - only allow if current product is globally finished
        # (has no remaining quantity anywhere)
        current_remaining = self.product_remaining.get(current, 0)
        if current_remaining == 0:
            return True
        
        # Otherwise, check if marked as finished on this line
        return self.line_product_finished.get((line_code, current), False)
    
    def get_products_produced_at_least_once(self) -> Set[str]:
        """Get set of products that have been scheduled at least once."""
        return {p for p, qty in self.product_scheduled.items() if qty > 0}
    
    def get_products_not_scheduled(self) -> Set[str]:
        """Get set of products that haven't been scheduled yet."""
        return {p for p, qty in self.product_scheduled.items() if qty == 0}
    
    def get_capacity_utilization(self) -> float:
        """Calculate overall capacity utilization."""
        total_planned = sum(r.planned_quantity for r in self.records)
        total_capacity = sum(r.standard_capacity for r in self.records)
        if total_capacity == 0:
            return 0.0
        return total_planned / total_capacity
    
    def get_total_scheduled(self) -> int:
        """Get total bottles scheduled."""
        return sum(self.product_scheduled.values())
    
    def get_total_planned(self) -> int:
        """Get total bottles in plan."""
        return sum(self.products.values())


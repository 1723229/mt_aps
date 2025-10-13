"""Internal state tracking models"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProductState:
    """Tracks the state of a product during scheduling"""
    product_code: str
    product_name: str
    bottle_total: int  # Total target quantity
    remaining: int  # Remaining quantity to produce
    spec: int  # Specification in ml
    deliver_day: Optional[str]  # Delivery date
    
    # Tracking
    assigned_lines: Set[str] = field(default_factory=set)  # Lines producing this product
    cumulative_produced: int = 0  # Total produced so far
    first_production_date: Optional[str] = None
    last_production_date: Optional[str] = None
    is_completed: bool = False
    
    # Priority info
    has_priority_constraint: bool = False
    priority_periods: List[Dict] = field(default_factory=list)
    
    def update_production(self, amount: int, date: str, line_code: str):
        """Update production tracking"""
        self.cumulative_produced += amount
        self.remaining = max(0, self.bottle_total - self.cumulative_produced)
        self.assigned_lines.add(line_code)
        
        if self.first_production_date is None:
            self.first_production_date = date
        self.last_production_date = date
        
        # Check completion (allow 1% tolerance)
        if self.cumulative_produced >= self.bottle_total * 0.99:
            self.is_completed = True
    
    def is_nearly_complete(self, capacity: int) -> bool:
        """Check if product will complete in current shift"""
        return self.remaining <= capacity and self.remaining > 0


@dataclass
class CrewState:
    """Tracks the state of a crew during scheduling"""
    crew_code: str
    crew_name: str
    
    # Workload tracking
    total_workload: float = 0.0  # Sum of (shift_output / standard_capacity)
    shifts_worked: int = 0
    total_bottles_produced: int = 0
    
    # Scheduling tracking
    scheduled_dates: Set[str] = field(default_factory=set)  # Dates already scheduled
    assigned_lines: Set[str] = field(default_factory=set)  # Lines worked on
    
    def is_available(self, date: str) -> bool:
        """Check if crew is available on given date"""
        return date not in self.scheduled_dates
    
    def assign_shift(self, date: str, line_code: str, output: int, standard_capacity: int):
        """Assign crew to a shift"""
        self.scheduled_dates.add(date)
        self.assigned_lines.add(line_code)
        self.shifts_worked += 1
        self.total_bottles_produced += output
        self.total_workload += output / standard_capacity if standard_capacity > 0 else 0


@dataclass
class LineState:
    """Tracks the state of a line during scheduling"""
    line_code: str
    line_name: str
    
    # Current production
    current_product: Optional[str] = None  # Current product being produced
    current_product_start_date: Optional[str] = None
    
    # Tracking
    total_shifts: int = 0
    idle_shifts: int = 0
    double_shifts: int = 0  # Number of shifts with 2 crews
    
    # Configuration
    available_products: Set[str] = field(default_factory=set)
    available_crews: Set[str] = field(default_factory=set)
    
    def start_product(self, product_code: str, date: str):
        """Start producing a new product"""
        self.current_product = product_code
        self.current_product_start_date = date
    
    def complete_product(self):
        """Mark current product as completed"""
        self.current_product = None
        self.current_product_start_date = None


@dataclass
class ShiftAssignment:
    """Complete record of one shift assignment"""
    date: str
    shift: str  # "早班" or "中班"
    week_num: int
    weekday: str
    line_code: str
    line_name: str
    product_code: str
    product_name: str
    crew_code: str
    crew_name: str
    standard_capacity: int
    shift_output: int  # Actual production for this shift
    cumulative_output: int  # Cumulative production for this product
    utilization: float  # shift_output / standard_capacity
    is_changeover: bool = False  # Whether this shift involves product changeover
    status: str = "正常生产"  # 正常生产/换产/占位/已完成
    
    # For changeover shifts
    second_product_code: Optional[str] = None
    second_product_output: Optional[int] = None


@dataclass
class SchedulingContext:
    """Global context for scheduling process"""
    work_calendar: List[str]
    work_week: Dict[str, int]
    
    # State tracking
    product_states: Dict[str, ProductState]
    crew_states: Dict[str, CrewState]
    line_states: Dict[str, LineState]
    
    # Configuration maps
    line_to_products: Dict[str, List[Tuple[str, int, int, int]]]  # line -> [(product, productLineWeight, std_cap, prod_cap)]
    product_to_lines: Dict[str, List[Tuple[str, int]]]  # product -> [(line, productLineWeight)]
    line_to_crews: Dict[str, List[Tuple[str, int, int]]]  # line -> [(crew, lineCrewPriority, crewLinePriority)]
    crew_to_lines: Dict[str, List[str]]  # crew -> [lines]
    
    # Constraints
    forbidden_lines: Dict[str, Set[str]]  # date -> set of forbidden line codes
    product_priorities: Dict[str, List[Dict]]  # product_code -> priority periods
    
    # Results
    assignments: List[ShiftAssignment] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


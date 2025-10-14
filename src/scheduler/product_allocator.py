"""Product allocator - core allocation engine."""

from typing import Dict, List, Optional, Set, Tuple
from ..models.input_models import ScheduleIndices, LineProductSetting, LineCrewSetting
from ..models.schedule_state import ScheduleState
from ..constraints.line_constraints import LineForbidTimeConstraint
from ..regions.region_manager import RegionManager
from .capacity_optimizer import CapacityOptimizer
from .crew_shift_planner import CrewShiftPlanner


class ProductAllocator:
    """Allocates products to line-crew-shift slots."""
    
    def __init__(
        self,
        indices: ScheduleIndices,
        state: ScheduleState,
        line_constraints: LineForbidTimeConstraint,
        region_manager: RegionManager,
        capacity_optimizer: CapacityOptimizer,
        crew_shift_planner: CrewShiftPlanner,
    ):
        """Initialize allocator.
        
        Args:
            indices: Schedule indices
            state: Schedule state
            line_constraints: Line forbidden time constraints
            region_manager: Regional constraint manager
            capacity_optimizer: Capacity optimizer
            crew_shift_planner: Crew shift planner
        """
        self.indices = indices
        self.state = state
        self.line_constraints = line_constraints
        self.region_manager = region_manager
        self.capacity_optimizer = capacity_optimizer
        self.crew_shift_planner = crew_shift_planner
    
    def allocate_product_to_shift(
        self,
        product_code: str,
        line_code: str,
        date: str,
        shift: str,
        quantity: Optional[int] = None,
    ) -> bool:
        """Allocate a product to a specific line-shift.
        
        Args:
            product_code: Product to allocate
            line_code: Line to use
            date: Date
            shift: 'early' or 'middle'
            quantity: Optional specific quantity (otherwise use capacity)
        
        Returns:
            True if allocation succeeded
        """
        # Get line-product setting
        setting = self.indices.get_line_setting(line_code, product_code)
        if not setting:
            return False
        
        # Check line not forbidden
        if self.line_constraints.is_line_forbidden(line_code, date):
            return False
        
        # Check product continuity (BC-09)
        if not self.state.can_continue_product(line_code, product_code):
            return False
        
        # Check slot available
        if not self.state.is_slot_available(line_code, date, shift):
            return False
        
        # Get available crew
        crew_code = self._select_crew(line_code, date, shift)
        if not crew_code:
            return False
        
        # Calculate quantity
        if quantity is None:
            effective_capacity = self.capacity_optimizer.get_effective_capacity(setting)
            standard_capacity = self.capacity_optimizer.get_standard_capacity(setting)
            remaining = self.state.product_remaining.get(product_code, 0)
            
            quantity = self.capacity_optimizer.calculate_shift_quantity(
                remaining, effective_capacity, standard_capacity
            )
        
        if quantity <= 0:
            return False
        
        # Check we have enough remaining
        if quantity > self.state.product_remaining.get(product_code, 0):
            return False
        
        # Add production
        try:
            standard_capacity = self.capacity_optimizer.get_standard_capacity(setting)
            self.state.add_production(
                line_code=line_code,
                date=date,
                shift=shift,
                product_code=product_code,
                crew_code=crew_code,
                quantity=quantity,
                standard_capacity=standard_capacity,
            )
            return True
        except ValueError:
            return False
    
    def _select_crew(
        self,
        line_code: str,
        date: str,
        shift: str,
    ) -> Optional[str]:
        """Select best available crew for a line-shift.
        
        Selection criteria:
        1. Crew must be available (not assigned this date)
        2. Crew must match shift plan (BC-11)
        3. Crew must be allowed on this line
        4. Prefer by priority (lineCrewPriority, crewLinePriority)
        
        Args:
            line_code: Line code
            date: Date
            shift: Shift
        
        Returns:
            Selected crew code or None
        """
        # Get crews for this line
        line_crews = self.indices.crews_for_line.get(line_code, [])
        
        candidates = []
        for crew_setting in line_crews:
            crew_code = crew_setting.crewCode
            
            # Check availability
            if not self.state.is_crew_available(crew_code, date, shift):
                continue
            
            # Check shift plan (BC-11)
            planned_shift = self.crew_shift_planner.get_shift_for_crew(crew_code, date)
            if planned_shift != shift:
                continue
            
            # Check regional restrictions
            region = self.region_manager.get_region_for_line(line_code)
            if region:
                # Check crew is in region
                if not region.get_crew_in_region(crew_code):
                    continue
                
                # Check specific restrictions (e.g., pack17 on 030204)
                if hasattr(region, 'is_crew_allowed_on_line'):
                    if not region.is_crew_allowed_on_line(crew_code, line_code):
                        continue
            
            # Calculate priority score (lower is better)
            score = (crew_setting.lineCrewPriority * 1000 + crew_setting.crewLinePriority)
            candidates.append((crew_code, score))
        
        if not candidates:
            return None
        
        # Sort by score and return best
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]
    
    def get_available_lines_for_product(
        self,
        product_code: str,
        date: str,
        shift: str,
    ) -> List[str]:
        """Get available lines that can produce a product.
        
        Lines are sorted by productLineWeight (lower = higher priority).
        Filtered for:
        - Line not forbidden on date
        - Line has slot available
        - Line has available crew
        - Product continuity (BC-09)
        
        Args:
            product_code: Product code
            date: Date
            shift: Shift
        
        Returns:
            List of available line codes (sorted by priority)
        """
        line_settings = self.indices.lines_for_product.get(product_code, [])
        
        available = []
        for setting in line_settings:
            line_code = setting.lineCode
            
            # Check line not forbidden
            if self.line_constraints.is_line_forbidden(line_code, date):
                continue
            
            # Check product continuity
            if not self.state.can_continue_product(line_code, product_code):
                continue
            
            # Check slot available (or can add to existing)
            # For now, we only use empty slots
            if not self.state.is_slot_available(line_code, date, shift):
                continue
            
            # Check crew available
            crew = self._select_crew(line_code, date, shift)
            if not crew:
                continue
            
            available.append(line_code)
        
        return available
    
    def try_allocate_product(
        self,
        product_code: str,
        date: str,
        shift: str,
        preferred_lines: Optional[List[str]] = None,
    ) -> bool:
        """Try to allocate a product to any available line.
        
        Args:
            product_code: Product to allocate
            date: Date
            shift: Shift
            preferred_lines: Optional list of preferred lines (in order)
        
        Returns:
            True if allocated successfully
        """
        if preferred_lines is None:
            preferred_lines = self.get_available_lines_for_product(product_code, date, shift)
        
        for line_code in preferred_lines:
            if self.allocate_product_to_shift(product_code, line_code, date, shift):
                return True
        
        return False


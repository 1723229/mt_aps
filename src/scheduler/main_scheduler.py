"""Main scheduler - orchestrates all scheduling phases."""

from typing import Dict, List, Set, Optional
import logging

from ..models.input_models import ScheduleRequest, ScheduleIndices
from ..models.schedule_state import ScheduleState
from ..constraints.line_constraints import LineForbidTimeConstraint
from ..constraints.product_priority import ProductPriorityConstraint
from ..regions.region_manager import RegionManager
from .crew_shift_planner import CrewShiftPlanner
from .product_allocator import ProductAllocator
from .changeover_handler import ChangeoverHandler
from .capacity_optimizer import CapacityOptimizer


logger = logging.getLogger(__name__)


class MainScheduler:
    """Main scheduling orchestrator implementing 5-phase algorithm."""
    
    def __init__(self, request: ScheduleRequest):
        """Initialize scheduler.
        
        Args:
            request: Schedule request with all configuration
        """
        self.request = request
        self.indices = request.build_indices()
        
        # Build product quantities
        products = {
            plan.productCode: plan.bottleTotal
            for plan in request.schedulePlans
        }
        
        # Initialize state
        self.state = ScheduleState(
            products=products,
            work_calendar=request.workCalendar,
            work_week=request.workWeek,
            all_lines=self.indices.all_lines,
            all_crews=self.indices.all_crews,
        )
        
        # Initialize constraints
        solution = request.get_primary_solution()
        
        self.line_constraints = LineForbidTimeConstraint(
            self.indices.constraints_by_type.get('line_forbid_time', [])
        )
        
        self.priority_constraints = ProductPriorityConstraint(
            self.indices.constraints_by_type.get('product_priority', []),
            self.indices.products_by_code,
        )
        
        # Initialize components
        self.region_manager = RegionManager()
        self.capacity_optimizer = CapacityOptimizer()
        
        self.crew_shift_planner = CrewShiftPlanner(
            work_calendar=request.workCalendar,
            work_week=request.workWeek,
            all_crews=self.indices.all_crews,
        )
        
        self.changeover_handler = ChangeoverHandler(self.indices)
        
        self.allocator = ProductAllocator(
            indices=self.indices,
            state=self.state,
            line_constraints=self.line_constraints,
            region_manager=self.region_manager,
            capacity_optimizer=self.capacity_optimizer,
            crew_shift_planner=self.crew_shift_planner,
        )
    
    def schedule(self) -> ScheduleState:
        """Execute full scheduling algorithm.
        
        Optimized 5 Phases:
        1. Plan crew shifts (BC-11)
        2. Schedule exclusive products FIRST (BC-06 - must complete)
        3. Schedule priority products
        4. Schedule remaining products (BC-07 - all must be scheduled)
        5. Handle changeovers and optimization
        
        Returns:
            Final schedule state
        """
        logger.info("Starting scheduling...")
        
        # Phase 1: Plan crew shifts
        logger.info("Phase 1: Planning crew shifts...")
        self._phase1_plan_crew_shifts()
        
        # Phase 2: Schedule exclusive products FIRST (BC-06 critical!)
        # Moved before priority products to ensure capacity availability
        logger.info("Phase 2: Scheduling exclusive products (BC-06)...")
        self._phase3_schedule_exclusive_products()
        
        # Phase 3: Schedule priority products
        logger.info("Phase 3: Scheduling priority products...")
        self._phase2_schedule_priority_products()
        
        # Phase 4: Schedule remaining products (BC-07 - all products must be scheduled)
        logger.info("Phase 4: Scheduling remaining products (BC-07)...")
        self._phase4_schedule_remaining_products()
        
        # Phase 5: Optimization and changeovers
        logger.info("Phase 5: Handling changeovers...")
        self._phase5_handle_changeovers()
        
        logger.info(f"Scheduling complete. Utilization: {self.state.get_capacity_utilization():.2%}")
        logger.info(f"Products scheduled: {len(self.state.get_products_produced_at_least_once())}/{len(self.state.products)}")
        
        return self.state
    
    def _phase1_plan_crew_shifts(self):
        """Phase 1: Plan crew shift assignments across weeks."""
        self.crew_shift_planner.plan_shifts()
        self.state.crew_shift_plan = self.crew_shift_planner.crew_shift_plan
        
        # Validate plan
        valid, errors = self.crew_shift_planner.validate_plan()
        if not valid:
            logger.warning(f"Crew shift plan validation warnings: {errors}")
    
    def _phase2_schedule_priority_products(self):
        """Phase 2: Schedule products with priority constraints."""
        priority_periods = self.priority_constraints.get_priority_periods()
        
        for period in priority_periods:
            product_code = period.product_code
            required_bottles = period.required_bottles
            # Filter to only dates in work calendar
            dates = [d for d in sorted(period.dates) if d in self.request.workCalendar]
            
            if not dates:
                logger.warning(f"Priority product {product_code} has no dates in work calendar")
                continue
            
            logger.info(f"Scheduling priority product {product_code}: {required_bottles} bottles over {len(dates)} days")
            
            # Allocate across the dates
            scheduled = 0
            for date in dates:
                if scheduled >= required_bottles:
                    break
                
                for shift in ['early', 'middle']:
                    if scheduled >= required_bottles:
                        break
                    
                    # Try to allocate
                    if self.allocator.try_allocate_product(product_code, date, shift):
                        scheduled += self.state.product_scheduled.get(product_code, 0)
    
    def _phase3_schedule_exclusive_products(self):
        """Phase 3: Schedule products that can only be produced on one line.
        
        This is critical - exclusive products MUST complete (BC-06).
        """
        exclusive_products = self.indices.get_exclusive_products()
        
        logger.info(f"Scheduling {len(exclusive_products)} exclusive products...")
        
        # Sort by remaining quantity (larger first) to prioritize big exclusive products
        exclusive_with_remaining = [
            (p, self.state.product_remaining.get(p, 0))
            for p in exclusive_products
        ]
        exclusive_with_remaining.sort(key=lambda x: -x[1])  # Descending by remaining
        
        for product_code, remaining in exclusive_with_remaining:
            if remaining <= 0:
                continue
            
            logger.info(f"Scheduling exclusive product {product_code}: {remaining} bottles remaining")
            
            # Schedule continuously and aggressively
            self._schedule_product_continuously(product_code)
    
    def _phase4_schedule_remaining_products(self):
        """Phase 4: Schedule all remaining products.
        
        CRITICAL: BC-07 requires ALL products to be scheduled.
        Must ensure every product gets at least one shift.
        """
        # Get products with remaining quantity
        remaining_products = [
            product_code for product_code in self.indices.all_products
            if self.state.product_remaining.get(product_code, 0) > 0
        ]
        
        # Separate into scheduled and unscheduled
        scheduled_products = [
            p for p in remaining_products
            if self.state.product_scheduled.get(p, 0) > 0
        ]
        unscheduled_products = [
            p for p in remaining_products
            if self.state.product_scheduled.get(p, 0) == 0
        ]
        
        logger.info(f"Phase 4: {len(scheduled_products)} partially scheduled, {len(unscheduled_products)} not yet scheduled")
        
        # FIRST: Ensure all unscheduled products get at least ONE shift (BC-07)
        if unscheduled_products:
            logger.info(f"PRIORITY: Scheduling {len(unscheduled_products)} unscheduled products (BC-07)")
            for product_code in unscheduled_products:
                # Try to schedule at least one shift
                success = False
                for date in self.request.workCalendar:
                    if success:
                        break
                    for shift in ['early', 'middle']:
                        if self.allocator.try_allocate_product(product_code, date, shift):
                            logger.info(f"  ✓ Scheduled {product_code} (first time)")
                            success = True
                            break
                
                if not success:
                    logger.warning(f"  ✗ Could not schedule {product_code} - may need capacity relaxation")
        
        # SECOND: Continue scheduling all products with remaining quantity
        remaining_products.sort(
            key=lambda p: (
                not self.priority_constraints.has_priority(p),  # Priority products first
                self.state.product_scheduled.get(p, 0) == 0,  # Unscheduled products
                -self.state.product_remaining[p],  # Then by remaining quantity
            )
        )
        
        logger.info(f"Continuing to schedule {len(remaining_products)} products...")
        
        for product_code in remaining_products:
            remaining = self.state.product_remaining.get(product_code, 0)
            if remaining > 0:
                self._schedule_product_continuously(product_code)
    
    def _schedule_product_continuously(self, product_code: str):
        """Schedule a product continuously until complete or no capacity.
        
        Args:
            product_code: Product to schedule
        """
        max_attempts = len(self.request.workCalendar) * 2 * 10  # dates × shifts × lines (approx)
        attempts = 0
        
        while self.state.product_remaining.get(product_code, 0) > 0 and attempts < max_attempts:
            attempts += 1
            
            # Try to schedule on any date/shift
            scheduled = False
            for date in self.request.workCalendar:
                if self.state.product_remaining.get(product_code, 0) <= 0:
                    break
                
                for shift in ['early', 'middle']:
                    if self.state.product_remaining.get(product_code, 0) <= 0:
                        break
                    
                    if self.allocator.try_allocate_product(product_code, date, shift):
                        scheduled = True
                        break
                
                if scheduled:
                    break
            
            if not scheduled:
                # Can't schedule anymore
                break
    
    def _phase5_handle_changeovers(self):
        """Phase 5: Handle changeovers where products complete early."""
        # Look for shifts where product completes with capacity remaining
        for date in self.request.workCalendar:
            for shift in ['early', 'middle']:
                for line_code in self.indices.all_lines:
                    self._try_changeover_for_slot(line_code, date, shift)
    
    def _try_changeover_for_slot(self, line_code: str, date: str, shift: str):
        """Try to add changeover for a shift slot if applicable.
        
        IMPORTANT: Changeover must respect BC-09 (product continuity).
        The second product in changeover must not have already been scheduled
        on this line (which would create a discontinuity).
        
        Args:
            line_code: Line code
            date: Date
            shift: Shift
        """
        # Get current production for this slot
        records = self.state.get_slot_assignment(line_code, date, shift)
        
        if not records or len(records) > 1:
            # No production or already has changeover
            return
        
        record = records[0]
        
        # Check if product is complete and used less than full capacity
        product_code = record.product_code
        remaining = self.state.product_remaining.get(product_code, 0)
        
        # Only changeover if this product is now complete (0 remaining)
        # and this was the last shift (used < capacity)
        if remaining > 0:
            return
        
        if record.planned_quantity >= record.standard_capacity:
            return  # Used full capacity, no room
        
        # Calculate changeover
        setting = self.indices.get_line_setting(line_code, product_code)
        if not setting:
            return
        
        effective_capacity = self.capacity_optimizer.get_effective_capacity(setting)
        
        first_qty, second_available = self.changeover_handler.calculate_changeover(
            line_code=line_code,
            first_product_code=product_code,
            first_remaining=record.planned_quantity,
            standard_capacity=record.standard_capacity,
            effective_capacity=effective_capacity,
        )
        
        if second_available <= 0:
            return
        
        # Select second product
        second_product = self.changeover_handler.select_changeover_product(
            line_code=line_code,
            first_product_code=product_code,
            available_capacity=second_available,
            product_remaining=self.state.product_remaining,
        )
        
        if not second_product:
            return
        
        # BC-09 CHECK: Ensure second product hasn't been produced on this line before
        # (which would violate continuity when we add it here)
        for existing_record in self.state.records:
            if (existing_record.line_code == line_code and 
                existing_record.product_code == second_product):
                # This product was already produced on this line
                # Adding it here would violate continuity, so skip
                logger.debug(
                    f"Skipping changeover to {second_product} on {line_code} - "
                    f"would violate BC-09 continuity"
                )
                return
        
        # Get crew from first record
        crew_code = record.crew_code
        
        # Calculate second product quantity
        second_remaining = self.state.product_remaining.get(second_product, 0)
        second_qty = min(second_available, second_remaining)
        
        if second_qty <= 0:
            return
        
        # Add second production
        try:
            second_setting = self.indices.get_line_setting(line_code, second_product)
            if not second_setting:
                return
            
            standard_capacity = self.capacity_optimizer.get_standard_capacity(second_setting)
            
            self.state.add_production(
                line_code=line_code,
                date=date,
                shift=shift,
                product_code=second_product,
                crew_code=crew_code,
                quantity=second_qty,
                standard_capacity=standard_capacity,
                is_changeover=True,
                changeover_sequence=2,
            )
            
            # Mark first as changeover too
            record.is_changeover = True
            record.changeover_sequence = 1
            
            logger.info(f"Changeover on {line_code} {date} {shift}: {product_code}→{second_product}")
            
        except ValueError as e:
            logger.warning(f"Failed to add changeover: {e}")


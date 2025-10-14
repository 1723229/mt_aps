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
            indices=self.indices,
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
        
        Optimized 6 Phases:
        1. Plan crew shifts (BC-11)
        2. Schedule exclusive products FIRST (BC-06 - must complete)
        3. Schedule priority products
        4. Schedule remaining products (BC-07 - all must be scheduled)
        5. Handle changeovers and optimization
        6. Fill with zero-quantity products (BC-04, BC-08)
        
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
        
        # Phase 6: Fill gaps with zero-quantity products (BC-04, BC-08)
        logger.info("Phase 6: Filling gaps with zero-quantity products...")
        self._phase6_fill_with_zero_products()
        
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
        # First, identify the last occurrence of each product on each line
        last_occurrence = {}  # (line_code, product_code) -> (date, shift, record)
        
        for record in self.state.records:
            key = (record.line_code, record.product_code)
            # Keep updating to get the last occurrence (records are ordered by date/shift)
            last_occurrence[key] = (record.date, record.shift, record)
        
        # Try changeover only for these last occurrences
        for (line_code, product_code), (date, shift, record) in last_occurrence.items():
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
        product_code = record.product_code
        
        # Check if this shift used less than full capacity (room for changeover)
        if record.planned_quantity >= record.standard_capacity:
            logger.debug(f"Skipping changeover on {line_code} {date} {shift}: {product_code} used full capacity ({record.planned_quantity}/{record.standard_capacity})")
            return  # Used full capacity, no room
        
        logger.debug(f"Checking changeover on {line_code} {date} {shift}: {product_code} last shift with {record.planned_quantity}/{record.standard_capacity} capacity used")
        
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
        
        logger.debug(f"Changeover capacity calculation: first={first_qty}, second_available={second_available}")
        
        if second_available <= 0:
            logger.debug(f"Skipping changeover: no capacity available for second product")
            return
        
        # Build list of products already produced on this line (for BC-09 protection)
        products_on_line = set()
        for existing_record in self.state.records:
            if existing_record.line_code == line_code:
                products_on_line.add(existing_record.product_code)
        
        # Select second product (BC-09 protection built into selection)
        second_product = self.changeover_handler.select_changeover_product(
            line_code=line_code,
            first_product_code=product_code,
            available_capacity=second_available,
            product_remaining=self.state.product_remaining,
            products_on_line=products_on_line,
        )
        
        logger.debug(f"Selected second product for changeover: {second_product}")
        
        if not second_product:
            logger.debug(f"Skipping changeover: no suitable second product found (checked {len(products_on_line)} products already on line)")
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
    
    def _phase6_fill_with_zero_products(self):
        """Phase 6: Fill empty slots with zero-quantity products.
        
        根据需求5.5节：
        - 当产线所有有计划产品已完成
        - 班组无法释放到其他产线
        - 班组必须排产（BC-04约束）
        - 安排计划量为0的产品占位
        
        选择规则：
        1. 必须是该产线配置的产品
        2. 选择该产线计划量瓶数最大的产品（即使已完成）
        3. 若瓶数相同，选择 productLineWeight 值最小的
        """
        filled_count = 0
        
        # Iterate through all dates and shifts
        for date in self.request.workCalendar:
            for shift in ['early', 'middle']:
                # Get crews that should work this shift
                expected_crews = {
                    crew_code: expected_shift
                    for crew_code, expected_shift in self.state.crew_shift_plan.items()
                    if expected_shift.get(date) == shift
                }
                
                # Check which crews are already assigned
                assigned_crews = set()
                for line_code in self.indices.all_lines:
                    records = self.state.get_slot_assignment(line_code, date, shift)
                    for record in records:
                        assigned_crews.add(record.crew_code)
                
                # Find crews that should work but aren't assigned
                unassigned_crews = set(expected_crews.keys()) - assigned_crews
                
                for crew_code in unassigned_crews:
                    # Find lines this crew can work on
                    crew_settings = self.indices.lines_for_crew.get(crew_code, [])
                    possible_lines = [setting.lineCode for setting in crew_settings]
                    
                    for line_code in possible_lines:
                        # Check if line is available (not forbidden, not already occupied)
                        if not self.state.is_slot_available(line_code, date, shift):
                            continue
                        
                        # Check if all planned products on this line are complete
                        # Build line_products by checking all products
                        line_products = []
                        for product_code in self.indices.all_products:
                            if product_code in self.indices.lines_for_product:
                                line_settings = self.indices.lines_for_product[product_code]
                                if any(s.lineCode == line_code for s in line_settings):
                                    line_products.append(product_code)
                        
                        all_complete = True
                        for product_code in line_products:
                            product = self.indices.products_by_code[product_code]
                            if product.bottleTotal > 0 and self.state.product_remaining.get(product_code, 0) > 0:
                                all_complete = False
                                break
                        
                        if not all_complete:
                            continue
                        
                        # Select zero-quantity product for this line
                        # IMPORTANT: Must not violate BC-09 continuity
                        zero_product = self._select_zero_quantity_product(line_code, date, shift)
                        if not zero_product:
                            continue
                        
                        # Get standard capacity for this product on this line
                        setting = self.indices.get_line_setting(line_code, zero_product)
                        if not setting:
                            continue
                        
                        standard_capacity = self.capacity_optimizer.get_standard_capacity(setting)
                        
                        # Add zero-quantity production (quantity = 0)
                        try:
                            self.state.add_production(
                                line_code=line_code,
                                date=date,
                                shift=shift,
                                product_code=zero_product,
                                crew_code=crew_code,
                                quantity=0,  # Zero quantity!
                                standard_capacity=standard_capacity,
                                is_changeover=False,
                                changeover_sequence=0,
                            )
                            filled_count += 1
                            logger.info(f"Filled gap: {line_code} {date} {shift} with {zero_product} (crew {crew_code}, qty=0)")
                            break  # Crew is now assigned
                        except ValueError as e:
                            logger.debug(f"Failed to fill gap: {e}")
                            continue
        
        logger.info(f"Filled {filled_count} gaps with zero-quantity products")
    
    def _select_zero_quantity_product(self, line_code: str, date: str, shift: str) -> str:
        """Select a zero-quantity product for a line.
        
        选择规则（需求5.5.1 + BC-09保护）：
        1. 必须是该产线配置的产品
        2. 不能是之前在该产线生产过的产品（避免违反BC-09连续性）
        3. 选择该产线计划量瓶数最大的产品
        4. 若瓶数相同，选择 productLineWeight 值最小的
        
        Args:
            line_code: Line code
            date: Date
            shift: Shift
        
        Returns:
            Product code to use for zero-quantity production
        """
        # Build line_products by checking all products
        line_products = []
        for product_code in self.indices.all_products:
            if product_code in self.indices.lines_for_product:
                line_settings = self.indices.lines_for_product[product_code]
                if any(s.lineCode == line_code for s in line_settings):
                    line_products.append(product_code)
        
        if not line_products:
            return None
        
        # Get products already produced on this line (to avoid BC-09 violation)
        products_on_line = set()
        for record in self.state.records:
            if record.line_code == line_code:
                products_on_line.add(record.product_code)
        
        # Get all line-product settings for this line
        candidates = []
        
        for product_code in line_products:
            # BC-09 PROTECTION: Skip products already produced on this line
            if product_code in products_on_line:
                continue
            
            product = self.indices.products_by_code.get(product_code)
            if not product:
                continue
            
            # Find the setting for this line-product combination
            settings = self.indices.lines_for_product.get(product_code, [])
            for setting in settings:
                if setting.lineCode == line_code:
                    candidates.append({
                        'product_code': product_code,
                        'bottle_total': product.bottleTotal,
                        'product_line_weight': setting.productLineWeight,
                    })
                    break
        
        if not candidates:
            # Fallback: if no unused products, use current line product if available
            current_product = self.state.line_current_product.get(line_code)
            if current_product:
                logger.debug(f"Using current product {current_product} for zero-quantity on {line_code} (all products used)")
                return current_product
            return None
        
        # Sort by: bottleTotal desc, productLineWeight asc
        candidates.sort(key=lambda x: (-x['bottle_total'], x['product_line_weight']))
        
        selected = candidates[0]['product_code']
        logger.debug(f"Selected zero-quantity product for {line_code}: {selected} (bottleTotal={candidates[0]['bottle_total']})")
        
        return selected


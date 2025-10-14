"""Constraint validation functions."""

from typing import Dict, List, Set
from ..models.schedule_state import ScheduleState, ProductionRecord


def validate_crew_single_shift(state: ScheduleState) -> tuple[bool, List[str]]:
    """Validate BC-03: Each crew works only one shift per day.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    for crew_code, date_shifts in state.crew_date_shift.items():
        for date, shift in date_shifts.items():
            if shift is None:
                continue
            
            # Count how many shifts this crew has on this date
            shifts_on_date = [s for d, s in date_shifts.items() if d == date and s is not None]
            if len(shifts_on_date) > 1:
                errors.append(
                    f"Crew {crew_code} assigned to multiple shifts on {date}: {shifts_on_date}"
                )
    
    return len(errors) == 0, errors


def validate_product_continuity(state: ScheduleState, indices) -> tuple[bool, List[str]]:
    """Validate BC-09: Same product on same line must be continuous.
    
    A product cannot be interrupted and then resumed on the same line
    (except by non-working days).
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    # Track product production periods on each line
    line_product_periods: Dict[str, Dict[str, List[str]]] = {}
    
    for record in state.records:
        line = record.line_code
        product = record.product_code
        date = record.date
        
        if line not in line_product_periods:
            line_product_periods[line] = {}
        if product not in line_product_periods[line]:
            line_product_periods[line][product] = []
        
        if date not in line_product_periods[line][product]:
            line_product_periods[line][product].append(date)
    
    # Check continuity for each line-product combination
    work_dates = sorted(state.work_calendar)
    
    for line, products in line_product_periods.items():
        for product, dates in products.items():
            if len(dates) <= 1:
                continue  # Single date, no continuity issue
            
            sorted_dates = sorted(dates)
            
            # Find gaps in production
            for i in range(len(sorted_dates) - 1):
                current_date = sorted_dates[i]
                next_date = sorted_dates[i + 1]
                
                # Get dates between current and next
                current_idx = work_dates.index(current_date)
                next_idx = work_dates.index(next_date)
                
                if next_idx - current_idx > 1:
                    # There are work days between these production days
                    gap_dates = work_dates[current_idx + 1:next_idx]
                    
                    # Check if line was producing something else during gap
                    line_busy_in_gap = False
                    for gap_date in gap_dates:
                        for rec in state.records:
                            if (rec.line_code == line and 
                                rec.date == gap_date and 
                                rec.product_code != product):
                                line_busy_in_gap = True
                                errors.append(
                                    f"Product {product} interrupted on line {line}: "
                                    f"produced on {current_date}, then line produced {rec.product_code} "
                                    f"on {gap_date}, then {product} resumed on {next_date}"
                                )
                                break
                    
                    if not line_busy_in_gap and len(gap_dates) > 0:
                        # Line was idle but could have continued - acceptable
                        pass
    
    return len(errors) == 0, errors


def validate_capacity_limit(state: ScheduleState) -> tuple[bool, List[str]]:
    """Validate BC-05: Production should not exceed planned quantity.
    
    Allow up to 1% overproduction (bottleTotal ).
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    for product_code, planned_total in state.products.items():
        scheduled = state.product_scheduled.get(product_code, 0)
        max_allowed = int(planned_total * 1)
        
        if scheduled > max_allowed:
            errors.append(
                f"Product {product_code} overproduced: "
                f"scheduled {scheduled}, planned {planned_total}, "
                f"max allowed {max_allowed}"
            )
    
    return len(errors) == 0, errors


def validate_all_products_scheduled(state: ScheduleState) -> tuple[bool, List[str]]:
    """Validate BC-07: All products must be scheduled at least once.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    unscheduled = state.get_products_not_scheduled()
    
    if unscheduled:
        errors.append(
            f"Products not scheduled: {sorted(unscheduled)}"
        )
    
    return len(errors) == 0, errors


def validate_exclusive_products(state: ScheduleState, indices) -> tuple[bool, List[str]]:
    """Validate BC-06: Single-line products must complete production.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    exclusive_products = indices.get_exclusive_products()
    
    for product_code in exclusive_products:
        scheduled = state.product_scheduled.get(product_code, 0)
        planned = state.products.get(product_code, 0)
        
        if scheduled < planned:
            errors.append(
                f"Exclusive product {product_code} not completed: "
                f"scheduled {scheduled} of {planned} planned"
            )
    
    return len(errors) == 0, errors


def validate_shift_capacity(state: ScheduleState) -> tuple[bool, List[str]]:
    """Validate that no shift exceeds 100% of standard capacity.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    for slot, records in state.slot_assignments.items():
        if not records:
            continue
        
        # All records in a slot should have same standard capacity
        standard_capacity = records[0].standard_capacity
        total_planned = sum(r.planned_quantity for r in records)
        
        if total_planned > standard_capacity:
            errors.append(
                f"Shift exceeded capacity on {slot.line_code} {slot.date} {slot.shift}: "
                f"planned {total_planned}, capacity {standard_capacity}"
            )
    
    return len(errors) == 0, errors


def validate_all_constraints(state: ScheduleState, indices) -> tuple[bool, Dict[str, List[str]]]:
    """Run all constraint validations.
    
    Returns:
        (all_valid, errors_by_constraint)
    """
    results = {}
    
    valid, errors = validate_crew_single_shift(state)
    results['BC-03: Crew Single Shift'] = errors
    
    valid, errors = validate_product_continuity(state, indices)
    results['BC-09: Product Continuity'] = errors
    
    valid, errors = validate_capacity_limit(state)
    results['BC-05: Capacity Limit'] = errors
    
    valid, errors = validate_all_products_scheduled(state)
    results['BC-07: All Products Scheduled'] = errors
    
    valid, errors = validate_exclusive_products(state, indices)
    results['BC-06: Exclusive Products'] = errors
    
    valid, errors = validate_shift_capacity(state)
    results['Shift Capacity'] = errors
    
    all_valid = all(len(errs) == 0 for errs in results.values())
    
    return all_valid, results


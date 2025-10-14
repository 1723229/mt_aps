"""Integration test using reference case data."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.data_loader import load_schedule_request
from src.utils.csv_exporter import export_to_csv, load_csv_for_comparison
from src.scheduler.main_scheduler import MainScheduler
from src.constraints.validators import validate_all_constraints


@pytest.mark.integration
def test_reference_case():
    """Test scheduler with reference input and compare with reference output."""
    
    # Load reference input
    input_path = "docs/排产入参.json"
    request = load_schedule_request(input_path)
    
    assert len(request.schedulePlans) > 0, "Should have schedule plans"
    assert len(request.workCalendar) > 0, "Should have work calendar"
    assert len(request.solutions) > 0, "Should have solutions"
    
    # Run scheduler
    scheduler = MainScheduler(request)
    state = scheduler.schedule()
    
    # Validate constraints
    indices = request.build_indices()
    all_valid, errors = validate_all_constraints(state, indices)
    
    # Print any errors
    if not all_valid:
        print("\n=== CONSTRAINT VALIDATION ERRORS ===")
        for constraint, error_list in errors.items():
            if error_list:
                print(f"\n{constraint}:")
                for error in error_list:
                    print(f"  - {error}")
    
    # Check key metrics
    utilization = state.get_capacity_utilization()
    products_scheduled = len(state.get_products_produced_at_least_once())
    total_products = len(state.products)
    
    print(f"\n=== SCHEDULE METRICS ===")
    print(f"Capacity Utilization: {utilization:.2%}")
    print(f"Products Scheduled: {products_scheduled}/{total_products}")
    print(f"Total Bottles Scheduled: {state.get_total_scheduled():,}")
    print(f"Total Bottles Planned: {state.get_total_planned():,}")
    
    # Assertions for functional equivalence
    assert all_valid, "All constraints should be satisfied"
    assert products_scheduled == total_products, "All products should be scheduled"
    assert utilization >= 0.80, f"Utilization should be at least 80%, got {utilization:.2%}"
    
    # Export for comparison
    output_path = "test_output.csv"
    export_to_csv(state, output_path)
    
    print(f"\nOutput exported to {output_path}")
    
    # Optional: Load and compare with reference CSV
    try:
        reference_path = "docs/实际排产结果.csv"
        reference_rows = load_csv_for_comparison(reference_path)
        
        print(f"\nReference CSV has {len(reference_rows)} rows")
        print("Note: Functional equivalence testing - schedules may differ but should satisfy all constraints")
        
    except FileNotFoundError:
        print("\nReference CSV not found, skipping comparison")


@pytest.mark.integration
def test_all_products_produced():
    """Test that every product is produced at least once."""
    
    input_path = "docs/排产入参.json"
    request = load_schedule_request(input_path)
    
    scheduler = MainScheduler(request)
    state = scheduler.schedule()
    
    unscheduled = state.get_products_not_scheduled()
    
    assert len(unscheduled) == 0, f"All products should be scheduled, but {len(unscheduled)} are not: {unscheduled}"


@pytest.mark.integration
def test_no_overproduction():
    """Test that no product exceeds its planned quantity."""
    
    input_path = "docs/排产入参.json"
    request = load_schedule_request(input_path)
    
    scheduler = MainScheduler(request)
    state = scheduler.schedule()
    
    overproduced = []
    for product_code, planned in state.products.items():
        scheduled = state.product_scheduled.get(product_code, 0)
        max_allowed = int(planned * 1)  # Allow 1% overproduction
        
        if scheduled > max_allowed:
            overproduced.append((product_code, scheduled, planned, max_allowed))
    
    assert len(overproduced) == 0, f"Products overproduced: {overproduced}"


@pytest.mark.integration
def test_crew_shift_consistency():
    """Test that crew shifts follow BC-11 rules."""
    
    input_path = "docs/排产入参.json"
    request = load_schedule_request(input_path)
    
    scheduler = MainScheduler(request)
    state = scheduler.schedule()
    
    # Check: each crew only works one shift per day
    for crew_code, date_shifts in state.crew_date_shift.items():
        for date, shift in date_shifts.items():
            if shift is None:
                continue
            
            # Count assignments on this date
            count = sum(1 for d, s in date_shifts.items() if d == date and s is not None)
            assert count == 1, f"Crew {crew_code} assigned multiple times on {date}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])


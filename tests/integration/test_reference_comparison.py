"""Integration test comparing with reference CSV"""

import json
import csv
import pytest
from pathlib import Path
from collections import defaultdict

from src.models.input_models import SchemeRequestModel
from src.scheduler.scheduler import ProductionScheduler


def parse_reference_csv(csv_path: str):
    """Parse reference CSV file"""
    schedules = defaultdict(lambda: defaultdict(list))
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        # Get line codes from header (excluding metadata columns)
        line_columns = header[1:-5]  # Exclude first and last 5 columns
        
        for row in reader:
            key = row[0]  # date;shift;week_num
            date_shift = row[-4:-2]  # date, shift
            
            for i, line_code in enumerate(line_columns):
                cell_data = row[i + 1]
                if cell_data:
                    # Parse assignment data
                    # Format: [('productCode', 'crewCode', stdCap, output, cumulative)]
                    try:
                        assignments = eval(cell_data)
                        if isinstance(assignments, list):
                            schedules[tuple(date_shift)][line_code].extend(assignments)
                    except:
                        pass
    
    return schedules


def test_compare_with_reference():
    """Compare scheduling output with reference CSV"""
    input_file = Path("docs/排产入参.json")
    reference_file = Path("docs/实际排产结果.csv")
    
    if not input_file.exists() or not reference_file.exists():
        pytest.skip("Input or reference file not found")
    
    # Load and run scheduling
    with open(input_file, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
    request = SchemeRequestModel(**input_data)
    scheduler = ProductionScheduler(request)
    success, context = scheduler.schedule()
    
    assert success
    
    # Parse reference
    reference_schedules = parse_reference_csv(reference_file)
    
    # Build our schedules
    our_schedules = defaultdict(lambda: defaultdict(list))
    for assignment in context.assignments:
        key = (assignment.date, assignment.shift)
        our_schedules[key][assignment.line_code].append({
            'product_code': assignment.product_code,
            'crew_code': assignment.crew_code,
            'output': assignment.shift_output
        })
    
    # Compare statistics
    print(f"\n{'='*80}")
    print("COMPARISON WITH REFERENCE")
    print(f"{'='*80}")
    
    # Product totals comparison
    print("\nProduct Completion Comparison:")
    print(f"{'Product':<20} {'Our Output':>12} {'Expected':>12} {'Diff %':>10}")
    print("-" * 60)
    
    # Collect product totals from reference
    reference_totals = defaultdict(int)
    for date_shift_schedules in reference_schedules.values():
        for line_assignments in date_shift_schedules.values():
            for assignment in line_assignments:
                if isinstance(assignment, tuple) and len(assignment) >= 4:
                    product_code = assignment[0]
                    output = assignment[3]
                    reference_totals[product_code] += output
    
    # Compare with our totals
    total_diff = 0
    for product_code, product_state in context.product_states.items():
        if product_state.bottle_total > 0:
            our_output = product_state.cumulative_produced
            expected = reference_totals.get(product_code, 0)
            
            if expected > 0:
                diff_pct = (our_output - expected) / expected * 100
            else:
                diff_pct = 0
            
            total_diff += abs(diff_pct)
            print(f"{product_code:<20} {our_output:>12} {expected:>12} {diff_pct:>9.1f}%")
    
    # Overall comparison
    our_total = sum(p.cumulative_produced for p in context.product_states.values() if p.bottle_total > 0)
    ref_total = sum(reference_totals.values())
    
    print("-" * 60)
    print(f"{'TOTAL':<20} {our_total:>12} {ref_total:>12} {((our_total-ref_total)/ref_total*100 if ref_total > 0 else 0):>9.1f}%")
    
    # Crew usage comparison
    print("\nCrew Utilization Comparison:")
    our_crew_shifts = {crew: state.shifts_worked for crew, state in context.crew_states.items()}
    
    # Count reference crew shifts
    ref_crew_shifts = defaultdict(int)
    for date_shift_schedules in reference_schedules.values():
        for line_assignments in date_shift_schedules.values():
            for assignment in line_assignments:
                if isinstance(assignment, tuple) and len(assignment) >= 2:
                    crew_code = assignment[1]
                    ref_crew_shifts[crew_code] += 1
    
    print(f"{'Crew':<15} {'Our Shifts':>12} {'Ref Shifts':>12} {'Diff':>8}")
    print("-" * 50)
    for crew_code in sorted(set(list(our_crew_shifts.keys()) + list(ref_crew_shifts.keys()))):
        our_shifts = our_crew_shifts.get(crew_code, 0)
        ref_shifts = ref_crew_shifts.get(crew_code, 0)
        diff = our_shifts - ref_shifts
        print(f"{crew_code:<15} {our_shifts:>12} {ref_shifts:>12} {diff:>8}")
    
    # Assertions (with tolerance)
    if ref_total > 0:
        output_diff_pct = abs((our_total - ref_total) / ref_total)
        # Allow up to 10% difference (algorithm may differ)
        assert output_diff_pct < 0.10, f"Total output differs by more than 10%: {output_diff_pct:.1%}"
    
    print(f"\n{'='*80}")
    print("✓ Comparison complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


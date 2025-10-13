"""Unit tests for constraint validators"""

import pytest
from src.constraints.base_constraints import BaseConstraintValidator
from src.constraints.regional_constraints import RegionalConstraints
from src.models.internal_models import SchedulingContext, ShiftAssignment, ProductState, CrewState, LineState
from collections import defaultdict


def create_test_context():
    """Create a minimal test context"""
    context = SchedulingContext(
        work_calendar=["2025-10-01", "2025-10-02"],
        work_week={"2025-10-01": 1, "2025-10-02": 1},
        product_states={
            "P001": ProductState("P001", "Product 1", 10000, 10000, 500, None),
            "P002": ProductState("P002", "Product 2", 5000, 5000, 500, None)
        },
        crew_states={
            "C001": CrewState("C001", "Crew 1"),
            "C002": CrewState("C002", "Crew 2")
        },
        line_states={
            "L001": LineState("L001", "Line 1"),
            "L002": LineState("L002", "Line 2")
        },
        line_to_products={
            "L001": [("P001", 1, 10000, 10000)],
            "L002": [("P002", 1, 8000, 8000)]
        },
        product_to_lines={
            "P001": [("L001", 1)],
            "P002": [("L002", 1)]
        },
        line_to_crews={
            "L001": [("C001", 1, 1)],
            "L002": [("C002", 1, 1)]
        },
        crew_to_lines={
            "C001": ["L001"],
            "C002": ["L002"]
        },
        forbidden_lines={},
        product_priorities={}
    )
    return context


def test_bc01_line_product_crew_binding():
    """Test BC-01: Line-Product-Crew binding"""
    context = create_test_context()
    
    # Valid assignment
    assignment = ShiftAssignment(
        date="2025-10-01",
        shift="早班",
        week_num=1,
        weekday="Monday",
        line_code="L001",
        line_name="Line 1",
        product_code="P001",
        product_name="Product 1",
        crew_code="C001",
        crew_name="Crew 1",
        standard_capacity=10000,
        shift_output=8000,
        cumulative_output=8000,
        utilization=0.8
    )
    context.assignments.append(assignment)
    
    validator = BaseConstraintValidator(context)
    validator.validate_bc01_line_product_crew_binding()
    assert len(validator.violations) == 0
    
    # Invalid assignment (wrong crew for line)
    invalid_assignment = ShiftAssignment(
        date="2025-10-01",
        shift="早班",
        week_num=1,
        weekday="Monday",
        line_code="L001",
        line_name="Line 1",
        product_code="P001",
        product_name="Product 1",
        crew_code="C002",  # Wrong crew
        crew_name="Crew 2",
        standard_capacity=10000,
        shift_output=8000,
        cumulative_output=8000,
        utilization=0.8
    )
    context.assignments.append(invalid_assignment)
    
    validator2 = BaseConstraintValidator(context)
    validator2.validate_bc01_line_product_crew_binding()
    assert len(validator2.violations) > 0


def test_bc03_crew_single_shift():
    """Test BC-03: Crew can only work one shift per day"""
    context = create_test_context()
    
    # Same crew, same date, different shifts (violation)
    assignment1 = ShiftAssignment(
        date="2025-10-01",
        shift="早班",
        week_num=1,
        weekday="Monday",
        line_code="L001",
        line_name="Line 1",
        product_code="P001",
        product_name="Product 1",
        crew_code="C001",
        crew_name="Crew 1",
        standard_capacity=10000,
        shift_output=8000,
        cumulative_output=8000,
        utilization=0.8
    )
    assignment2 = ShiftAssignment(
        date="2025-10-01",
        shift="中班",  # Same date, different shift
        week_num=1,
        weekday="Monday",
        line_code="L001",
        line_name="Line 1",
        product_code="P001",
        product_name="Product 1",
        crew_code="C001",  # Same crew
        crew_name="Crew 1",
        standard_capacity=10000,
        shift_output=8000,
        cumulative_output=8000,
        utilization=0.8
    )
    
    context.assignments.extend([assignment1, assignment2])
    
    validator = BaseConstraintValidator(context)
    validator.validate_bc03_crew_single_shift_per_day()
    assert len(validator.violations) > 0


def test_bc05_planned_quantity():
    """Test BC-05: No overproduction beyond 1% tolerance"""
    context = create_test_context()
    
    # Overproduction
    context.product_states["P001"].cumulative_produced = 12000  # 20% over
    
    validator = BaseConstraintValidator(context)
    validator.validate_bc05_planned_quantity()
    assert len(validator.violations) > 0
    
    # Within tolerance
    context2 = create_test_context()
    context2.product_states["P001"].cumulative_produced = 10050  # 0.5% over
    
    validator2 = BaseConstraintValidator(context2)
    validator2.validate_bc05_planned_quantity()
    assert len(validator2.violations) == 0


def test_regional_constraints_old_packaging():
    """Test old packaging area constraints"""
    # Check crew pairs
    assert RegionalConstraints.get_fixed_crew_pair("pack01") == ["pack01", "pack02"]
    assert RegionalConstraints.get_fixed_crew_pair("pack10") == ["pack10", "pack14"]
    
    # Check area identification
    assert RegionalConstraints.get_area_for_line("030201") == "OLD"
    assert RegionalConstraints.get_area_for_line("030206") == "NEW_B"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


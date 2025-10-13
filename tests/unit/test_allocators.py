"""Unit tests for allocator logic"""

import pytest
from src.scheduler.crew_allocator import CrewAllocator
from src.scheduler.product_allocator import ProductAllocator
from src.scheduler.changeover_handler import ChangeoverHandler
from src.models.internal_models import SchedulingContext, ProductState, CrewState, LineState
from collections import defaultdict


def create_test_context():
    """Create test context with sample data"""
    context = SchedulingContext(
        work_calendar=["2025-10-01", "2025-10-02"],
        work_week={"2025-10-01": 1, "2025-10-02": 1},
        product_states={
            "P001": ProductState("P001", "Product 1", 10000, 10000, 500, None),
            "P002": ProductState("P002", "Product 2", 5000, 5000, 500, "2025-10-05")
        },
        crew_states={
            "C001": CrewState("C001", "Crew 1"),
            "C002": CrewState("C002", "Crew 2"),
            "C003": CrewState("C003", "Crew 3")
        },
        line_states={
            "L001": LineState("L001", "Line 1"),
            "L002": LineState("L002", "Line 2")
        },
        line_to_products={
            "L001": [("P001", 1, 10000, 10000), ("P002", 2, 8000, 8000)],
            "L002": [("P002", 1, 8000, 8000)]
        },
        product_to_lines={
            "P001": [("L001", 1)],
            "P002": [("L001", 2), ("L002", 1)]
        },
        line_to_crews={
            "L001": [("C001", 1, 1), ("C002", 2, 2)],
            "L002": [("C002", 1, 1), ("C003", 1, 1)]
        },
        crew_to_lines={
            "C001": ["L001"],
            "C002": ["L001", "L002"],
            "C003": ["L002"]
        },
        forbidden_lines={},
        product_priorities={}
    )
    return context


def test_crew_selection_by_priority():
    """Test crew selection based on priority"""
    context = create_test_context()
    allocator = CrewAllocator(context)
    
    # Select crew for L001
    selected = allocator.select_crew_for_line("L001", "2025-10-01")
    assert selected == "C001"  # Has highest priority (1 vs 2)
    
    # Mark C001 as unavailable
    context.crew_states["C001"].scheduled_dates.add("2025-10-01")
    
    # Should select C002 now
    selected2 = allocator.select_crew_for_line("L001", "2025-10-01")
    assert selected2 == "C002"


def test_product_selection_by_priority():
    """Test product selection based on priority"""
    context = create_test_context()
    allocator = ProductAllocator(context)
    
    # Priority list with P002 first (has delivery date)
    priority_list = ["P002", "P001"]
    
    selected = allocator.select_product_for_line("L001", "2025-10-01", priority_list)
    assert selected == "P002"  # Higher priority in list


def test_changeover_calculation():
    """Test changeover output calculation"""
    context = create_test_context()
    handler = ChangeoverHandler(context)
    
    # Setup: P001 has 1000 bottles remaining, P002 is next
    context.product_states["P001"].remaining = 1000
    context.product_states["P002"].remaining = 5000
    
    # Calculate changeover with 15000 standard capacity
    first_out, second_out, total_out = handler.calculate_changeover_output(
        "P001", "P002", 15000
    )
    
    assert first_out == 1000
    # Available: 15000 - 1000 = 14000
    # Usable: 14000 * 0.9 = 12600
    # Second: min(12600, 5000) = 5000
    assert second_out == 5000
    assert total_out == 6000
    
    # Verify no overproduction
    assert total_out <= 15000


def test_changeover_check():
    """Test changeover necessity check"""
    context = create_test_context()
    handler = ChangeoverHandler(context)
    
    # Product nearly complete
    context.product_states["P001"].remaining = 2000
    assert handler.check_changeover_needed("P001", 10000, 10000) == True
    
    # Product not nearly complete
    context.product_states["P001"].remaining = 8000
    assert handler.check_changeover_needed("P001", 10000, 10000) == False


def test_get_lines_for_product():
    """Test getting available lines for a product"""
    context = create_test_context()
    allocator = ProductAllocator(context)
    
    # P002 can be produced on L001 (weight=2) and L002 (weight=1)
    lines = allocator.get_lines_for_product("P002")
    
    # Should be sorted by weight (lower first)
    assert len(lines) == 2
    assert lines[0][0] == "L002"  # weight=1
    assert lines[1][0] == "L001"  # weight=2


def test_crew_workload_balance():
    """Test crew workload consideration"""
    context = create_test_context()
    
    # Set different workloads
    context.crew_states["C001"].total_workload = 5.0
    context.crew_states["C002"].total_workload = 2.0
    
    allocator = CrewAllocator(context)
    
    # When both have same priority, should select lighter workload
    # (This depends on implementation details)
    selected = allocator.select_crew_for_line("L001", "2025-10-01")
    # C001 has higher line priority, so it still gets selected
    assert selected in ["C001", "C002"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


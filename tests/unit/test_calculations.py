"""Unit tests for capacity calculations"""

import pytest
from src.utils.capacity_calculator import CapacityCalculator
from src.models.internal_models import ProductState, SchedulingContext, ShiftAssignment
from collections import defaultdict


def test_calculate_utilization():
    """Test capacity utilization calculation"""
    # Normal case
    assert CapacityCalculator.calculate_utilization(8500, 10000) == 0.85
    
    # Full utilization
    assert CapacityCalculator.calculate_utilization(10000, 10000) == 1.0
    
    # Zero capacity
    assert CapacityCalculator.calculate_utilization(5000, 0) == 0.0


def test_calculate_shift_output():
    """Test shift output calculation"""
    # Remaining < capacity
    product = ProductState(
        product_code="TEST001",
        product_name="Test Product",
        bottle_total=10000,
        remaining=5000,
        spec=500,
        deliver_day=None
    )
    output = CapacityCalculator.calculate_shift_output(product, 8000)
    assert output == 5000
    
    # Remaining > capacity
    product.remaining = 12000
    output = CapacityCalculator.calculate_shift_output(product, 8000)
    assert output == 8000


def test_product_state_update():
    """Test product state updates"""
    product = ProductState(
        product_code="TEST001",
        product_name="Test Product",
        bottle_total=10000,
        remaining=10000,
        spec=500,
        deliver_day=None
    )
    
    # First production
    product.update_production(5000, "2025-10-01", "030206")
    assert product.cumulative_produced == 5000
    assert product.remaining == 5000
    assert product.first_production_date == "2025-10-01"
    assert "030206" in product.assigned_lines
    assert not product.is_completed
    
    # Second production (complete)
    product.update_production(5000, "2025-10-02", "030206")
    assert product.cumulative_produced == 10000
    assert product.remaining == 0
    assert product.is_completed


def test_product_nearly_complete():
    """Test nearly complete detection"""
    product = ProductState(
        product_code="TEST001",
        product_name="Test Product",
        bottle_total=10000,
        remaining=2000,
        spec=500,
        deliver_day=None
    )
    
    # Nearly complete
    assert product.is_nearly_complete(5000) == True
    
    # Not nearly complete
    product.remaining = 8000
    assert product.is_nearly_complete(5000) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


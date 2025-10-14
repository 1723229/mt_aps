"""Unit tests for constraint validators."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.schedule_state import ScheduleState
from src.constraints.validators import (
    validate_crew_single_shift,
    validate_capacity_limit,
    validate_all_products_scheduled,
)


@pytest.mark.unit
class TestConstraintValidators:
    """Test constraint validation functions."""
    
    def test_crew_single_shift_valid(self):
        """Test valid crew shift assignments."""
        state = ScheduleState(
            products={'P1': 1000},
            work_calendar=['2025-10-01', '2025-10-02'],
            work_week={'2025-10-01': 1, '2025-10-02': 1},
            all_lines={'L1'},
            all_crews={'C1', 'C2'},
        )
        
        # Add productions
        state.add_production('L1', '2025-10-01', 'early', 'P1', 'C1', 100, 200)
        state.add_production('L1', '2025-10-02', 'early', 'P1', 'C2', 100, 200)
        
        valid, errors = validate_crew_single_shift(state)
        assert valid, f"Should be valid but got errors: {errors}"
    
    def test_capacity_limit_valid(self):
        """Test capacity limit validation."""
        state = ScheduleState(
            products={'P1': 1000},
            work_calendar=['2025-10-01'],
            work_week={'2025-10-01': 1},
            all_lines={'L1'},
            all_crews={'C1'},
        )
        
        # Add production within limit
        state.add_production('L1', '2025-10-01', 'early', 'P1', 'C1', 1000, 1000)
        
        valid, errors = validate_capacity_limit(state)
        assert valid, f"Should be valid but got errors: {errors}"
    
    def test_capacity_limit_overproduction(self):
        """Test capacity limit catches overproduction."""
        state = ScheduleState(
            products={'P1': 1000},
            work_calendar=['2025-10-01', '2025-10-02'],
            work_week={'2025-10-01': 1, '2025-10-02': 1},
            all_lines={'L1'},
            all_crews={'C1', 'C2'},
        )
        
        # Manually set overproduction (bypassing add_production validation)
        state.product_scheduled['P1'] = 1200  
        
        valid, errors = validate_capacity_limit(state)
        assert not valid, "Should catch overproduction"
    
    def test_all_products_scheduled_valid(self):
        """Test all products scheduled validation."""
        state = ScheduleState(
            products={'P1': 1000, 'P2': 500},
            work_calendar=['2025-10-01'],
            work_week={'2025-10-01': 1},
            all_lines={'L1'},
            all_crews={'C1', 'C2'},
        )
        
        # Schedule both products
        state.add_production('L1', '2025-10-01', 'early', 'P1', 'C1', 100, 1000)
        state.add_production('L1', '2025-10-01', 'middle', 'P2', 'C2', 50, 500)
        
        valid, errors = validate_all_products_scheduled(state)
        assert valid, f"Should be valid but got errors: {errors}"
    
    def test_all_products_scheduled_missing(self):
        """Test detection of unscheduled products."""
        state = ScheduleState(
            products={'P1': 1000, 'P2': 500},
            work_calendar=['2025-10-01'],
            work_week={'2025-10-01': 1},
            all_lines={'L1'},
            all_crews={'C1'},
        )
        
        # Only schedule P1, not P2
        state.add_production('L1', '2025-10-01', 'early', 'P1', 'C1', 100, 1000)
        
        valid, errors = validate_all_products_scheduled(state)
        assert not valid, "Should detect unscheduled product"
        assert any('P2' in str(e) for e in errors)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


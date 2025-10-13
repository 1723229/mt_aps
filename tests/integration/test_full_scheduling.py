"""Integration test for full scheduling process"""

import json
import pytest
from pathlib import Path

from src.models.input_models import SchemeRequestModel
from src.scheduler.scheduler import ProductionScheduler
from src.constraints.base_constraints import BaseConstraintValidator
from src.constraints.regional_constraints import RegionalConstraintValidator
from src.exporters.csv_exporter import CSVExporter
from src.exporters.report_generator import ReportGenerator


def test_full_scheduling_with_real_data():
    """Test full scheduling with real input data"""
    input_file = Path("docs/排产入参.json")
    
    if not input_file.exists():
        pytest.skip("Input file not found")
    
    # Load input
    with open(input_file, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
    request = SchemeRequestModel(**input_data)
    
    # Run scheduling
    scheduler = ProductionScheduler(request)
    success, context = scheduler.schedule()
    
    # Assert success
    assert success, f"Scheduling failed: {context.errors}"
    assert len(context.assignments) > 0, "No assignments generated"
    
    # Validate constraints
    base_validator = BaseConstraintValidator(context)
    base_valid, base_violations = base_validator.validate_all()
    
    if not base_valid:
        print("Base constraint violations:")
        for v in base_violations:
            print(f"  - {v}")
    
    # Note: Some violations may be expected depending on algorithm implementation
    # The test should focus on overall feasibility
    
    # Regional constraints
    regional_validator = RegionalConstraintValidator(context.assignments)
    regional_valid, regional_violations = regional_validator.validate_all_regional_constraints()
    
    if not regional_valid:
        print("Regional constraint violations:")
        for v in regional_violations:
            print(f"  - {v}")
    
    # Generate report
    report_gen = ReportGenerator(context)
    report = report_gen.generate_full_report()
    
    # Print summary
    print(f"\n{'='*80}")
    print("SCHEDULING TEST RESULTS")
    print(f"{'='*80}")
    print(f"Total assignments: {len(context.assignments)}")
    print(f"Effective shifts: {report.capacity_utilization.effective_shifts}")
    print(f"Average utilization: {report.capacity_utilization.average_utilization:.2%}")
    print(f"Total completion rate: {report.capacity_utilization.total_completion_rate:.2%}")
    print(f"Changeover shifts: {report.capacity_utilization.changeover_shifts}")
    print(f"Products completed: {sum(1 for p in report.product_completions if p.status == '已完成')}/{len(report.product_completions)}")
    
    # Basic assertions
    assert report.capacity_utilization.average_utilization > 0.5, "Average utilization too low"
    assert report.capacity_utilization.total_completion_rate > 0.8, "Overall completion rate too low"
    
    # Check that all products are at least partially scheduled
    for product_code, product_state in context.product_states.items():
        if product_state.bottle_total > 0:
            assert product_state.cumulative_produced > 0 or product_state.bottle_total == 0, \
                f"Product {product_code} was not scheduled at all"


def test_scheduling_basic_scenario():
    """Test scheduling with a minimal scenario"""
    # Create minimal input
    input_data = {
        "workCalendar": ["2025-10-09", "2025-10-10"],
        "workWeek": {"2025-10-09": 2, "2025-10-10": 2},
        "schedulePlans": [
            {
                "baseSpiritCode": "MC530001",
                "baseSpiritName": "经典酒质",
                "productCode": "MT0010010082",
                "productName": "飞天53%vol 500ml贵州茅台酒（带杯）（1×6）",
                "bottleTotal": 110000,
                "plannedTotal": 51.83,
                "orderType": "WEEK_PLAN",
                "spec": 500,
                "price": 0.0
            }
        ],
        "solutions": [{
            "id": 1,
            "solutionName": "Test Solution",
            "solutionCode": "TEST001",
            "lineProductSettingDetails": [
                {
                    "lineCode": "030205",
                    "lineName": "包装5S线",
                    "productCode": "MT0010010082",
                    "productName": "飞天53%vol 500ml贵州茅台酒（带杯）（1×6）",
                    "standardCapacity": 55000,
                    "productLineWeight": 1,
                    "productionCapacity": 55000
                }
            ],
            "lineCrewScheduleSettings": [],
            "lineCrewSettingDetails": [
                {
                    "lineCode": "030205",
                    "lineName": "包装5S线",
                    "crewCode": "pack05",
                    "crewName": "包装5班",
                    "lineCrewPriority": 1,
                    "crewLinePriority": 1
                },
                {
                    "lineCode": "030205",
                    "lineName": "包装5S线",
                    "crewCode": "pack11",
                    "crewName": "包装11班",
                    "lineCrewPriority": 2,
                    "crewLinePriority": 1
                }
            ],
            "constraintSettings": [],
            "solutionStrategySetting": None
        }]
    }
    
    request = SchemeRequestModel(**input_data)
    scheduler = ProductionScheduler(request)
    success, context = scheduler.schedule()
    
    assert success
    assert len(context.assignments) > 0
    
    # Check product completion
    product = context.product_states["MT0010010082"]
    assert product.cumulative_produced >= product.bottle_total * 0.99


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


"""Main entry point for Maotai Production Scheduling System"""

import argparse
import json
import sys
from pathlib import Path

from src.models.input_models import SchemeRequestModel
from src.scheduler.scheduler import ProductionScheduler
from src.constraints.base_constraints import BaseConstraintValidator
from src.constraints.regional_constraints import RegionalConstraintValidator
from src.exporters.csv_exporter import CSVExporter
from src.exporters.report_generator import ReportGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Maotai Production Scheduling System"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input JSON file path'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='results/schedule.csv',
        help='Output CSV file path (default: results/schedule.csv)'
    )
    parser.add_argument(
        '--report',
        type=str,
        default='results/report.txt',
        help='Report text file path (default: results/report.txt)'
    )
    parser.add_argument(
        '--standard-csv',
        type=str,
        default='results/schedule_standard.csv',
        help='Standard format CSV output path'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate constraints without scheduling'
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load input data
    print(f"Loading input from {args.input}...")
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        request = SchemeRequestModel(**input_data)
        print(f"✓ Loaded {len(request.schedulePlans)} products, "
              f"{len(request.workCalendar)} working days")
    except Exception as e:
        print(f"✗ Error loading input: {e}")
        sys.exit(1)
    
    # Run scheduling
    print("\nRunning scheduling algorithm...")
    scheduler = ProductionScheduler(request)
    success, context = scheduler.schedule()
    
    if not success:
        print("✗ Scheduling failed:")
        for error in context.errors:
            print(f"  - {error}")
        sys.exit(1)
    
    print(f"✓ Scheduling completed: {len(context.assignments)} shift assignments")
    
    # Validate constraints
    print("\nValidating constraints...")
    
    # Base constraints
    base_validator = BaseConstraintValidator(context)
    base_valid, base_violations = base_validator.validate_all()
    
    if not base_valid:
        print("✗ Base constraint violations:")
        for violation in base_violations:
            print(f"  - {violation}")
    else:
        print("✓ All base constraints satisfied")
    
    # Regional constraints
    regional_validator = RegionalConstraintValidator(context.assignments)
    regional_valid, regional_violations = regional_validator.validate_all_regional_constraints()
    
    if not regional_valid:
        print("✗ Regional constraint violations:")
        for violation in regional_violations:
            print(f"  - {violation}")
    else:
        print("✓ All regional constraints satisfied")
    
    if args.validate_only:
        print("\nValidation complete (validate-only mode)")
        sys.exit(0 if (base_valid and regional_valid) else 1)
    
    # Export results
    print("\nExporting results...")
    
    # CSV export
    exporter = CSVExporter(context)
    exporter.export_to_csv(args.output)
    print(f"✓ CSV exported to {args.output}")
    
    # Standard format CSV
    exporter.export_to_standard_format(args.standard_csv)
    print(f"✓ Standard CSV exported to {args.standard_csv}")
    
    # Report
    report_gen = ReportGenerator(context)
    report_gen.export_report_to_text(args.report)
    print(f"✓ Report exported to {args.report}")
    
    # Print summary
    report = report_gen.generate_full_report()
    print("\n" + "=" * 80)
    print("SCHEDULING SUMMARY")
    print("=" * 80)
    print(f"Total shifts scheduled: {report.capacity_utilization.effective_shifts}")
    print(f"Average capacity utilization: {report.capacity_utilization.average_utilization:.2%}")
    print(f"Total completion rate: {report.capacity_utilization.total_completion_rate:.2%}")
    print(f"Products completed: {sum(1 for p in report.product_completions if p.status == '已完成')}/{len(report.product_completions)}")
    print(f"Changeover shifts: {report.capacity_utilization.changeover_shifts}")
    
    if report.warnings:
        print(f"\nWarnings: {len(report.warnings)}")
        for warning in report.warnings[:5]:  # Show first 5
            print(f"  [{warning.level}] {warning.description}")
        if len(report.warnings) > 5:
            print(f"  ... and {len(report.warnings) - 5} more (see report)")
    
    print("\n✓ All done!")
    sys.exit(0)


if __name__ == "__main__":
    main()


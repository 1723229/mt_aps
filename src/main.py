"""Main entry point for the scheduling system."""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.data_loader import load_schedule_request
from src.utils.csv_exporter import export_to_csv
from src.scheduler.main_scheduler import MainScheduler
from src.constraints.validators import validate_all_constraints


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Maotai Production Scheduling System'
    )
    parser.add_argument(
        '--input',
        '-i',
        required=True,
        help='Path to input JSON file'
    )
    parser.add_argument(
        '--output',
        '-o',
        default='schedule_output.csv',
        help='Path to output CSV file (default: schedule_output.csv)'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load request
        logger.info(f"Loading schedule request from {args.input}...")
        request = load_schedule_request(args.input)
        logger.info(f"Loaded {len(request.schedulePlans)} products, {len(request.workCalendar)} dates")
        
        # Create scheduler
        logger.info("Initializing scheduler...")
        scheduler = MainScheduler(request)
        
        # Run scheduling
        logger.info("Running scheduling algorithm...")
        state = scheduler.schedule()
        
        # Validate results
        logger.info("Validating schedule...")
        indices = request.build_indices()
        all_valid, errors = validate_all_constraints(state, indices)
        
        if not all_valid:
            logger.error("Schedule validation failed!")
            for constraint, error_list in errors.items():
                if error_list:
                    logger.error(f"{constraint}:")
                    for error in error_list:
                        logger.error(f"  - {error}")
        else:
            logger.info("All constraints validated successfully!")
        
        # Print summary
        logger.info("="*60)
        logger.info("SCHEDULE SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Capacity Utilization: {state.get_capacity_utilization():.2%}")
        logger.info(f"Total Bottles Scheduled: {state.get_total_scheduled():,}")
        logger.info(f"Total Bottles Planned: {state.get_total_planned():,}")
        logger.info(f"Products Scheduled: {len(state.get_products_produced_at_least_once())}/{len(state.products)}")
        logger.info(f"Total Production Records: {len(state.records)}")
        logger.info("="*60)
        
        # Export to CSV
        logger.info(f"Exporting schedule to {args.output}...")
        export_to_csv(state, args.output)
        logger.info("Export complete!")
        
        if not all_valid:
            sys.exit(1)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()


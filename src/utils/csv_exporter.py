"""CSV export utilities."""

import csv
from typing import List, Dict
from pathlib import Path
from ..models.schedule_state import ScheduleState
from ..models.output_models import ScheduleOutput


def export_to_csv(state: ScheduleState, output_path: str) -> None:
    """Export schedule state to CSV file.
    
    Args:
        state: ScheduleState to export
        output_path: Path for output CSV file
    """
    output = ScheduleOutput(state)
    rows = output.to_csv_rows()
    
    if not rows:
        raise ValueError("No schedule data to export")
    
    # Get all unique line codes for column ordering
    # Match reference CSV column order
    line_columns = sorted(state.all_lines)
    
    # Define column order matching reference CSV
    fieldnames = ['row_key'] + line_columns + ['日期', '班次', '周次', '星期', '已使用班组']
    
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_csv_for_comparison(csv_path: str) -> List[Dict]:
    """Load CSV file for comparison.
    
    Args:
        csv_path: Path to CSV file
    
    Returns:
        List of row dictionaries
    """
    rows = []
    path = Path(csv_path)
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    return rows


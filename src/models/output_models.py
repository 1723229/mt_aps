"""Output data models for schedule results."""

from typing import Dict, List, Tuple
from dataclasses import dataclass
from .schedule_state import ScheduleState, ProductionRecord


@dataclass
class ScheduleOutput:
    """Formatted schedule output matching CSV structure."""
    
    state: ScheduleState
    
    def to_csv_rows(self) -> List[Dict]:
        """Convert schedule state to CSV row format matching reference.
        
        CSV format:
        - One row per date-shift combination
        - Columns for each production line
        - Cell format: list of (product_code, crew_code, capacity, quantity, 0)
        - Additional columns: date, shift, week, day_of_week, crews_used
        """
        from ..utils.helpers import get_day_of_week
        
        rows = []
        
        # Group by date and shift
        shifts_by_date: Dict[str, Dict[str, List[ProductionRecord]]] = {}
        for record in self.state.records:
            if record.date not in shifts_by_date:
                shifts_by_date[record.date] = {'early': [], 'middle': []}
            shifts_by_date[record.date][record.shift].append(record)
        
        # Create rows in order
        for date in sorted(self.state.work_calendar):
            for shift in ['early', 'middle']:
                shift_label = '早班' if shift == 'early' else '中班'
                
                # Build row
                row = {}
                
                # Date info columns (at the end in reference CSV)
                week_num = self.state.work_week[date]
                day_name = get_day_of_week(date)
                
                row['日期'] = date
                row['班次'] = shift_label
                row['周次'] = week_num
                row['星期'] = day_name
                
                # Key for matching row identifier (used in CSV first column)
                row_key = f"{date};{shift_label};{week_num}"
                row['row_key'] = row_key
                
                # Get all records for this shift
                records = shifts_by_date.get(date, {}).get(shift, [])
                
                # Group by line
                lines_data: Dict[str, List[ProductionRecord]] = {}
                for record in records:
                    if record.line_code not in lines_data:
                        lines_data[record.line_code] = []
                    lines_data[record.line_code].append(record)
                
                # Create column for each line
                for line_code in sorted(self.state.all_lines):
                    if line_code in lines_data:
                        # Format: [(product, crew, capacity, quantity, 0)]
                        productions = []
                        for rec in lines_data[line_code]:
                            productions.append((
                                rec.product_code,
                                rec.crew_code,
                                rec.standard_capacity,
                                rec.planned_quantity,
                                0  # Reserved field
                            ))
                        row[line_code] = str(productions)
                    else:
                        row[line_code] = ""
                
                # Crews used
                crews_used = sorted(set(r.crew_code for r in records))
                row['已使用班组'] = str(crews_used)
                
                rows.append(row)
        
        return rows
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            'total_utilization': self.state.get_capacity_utilization(),
            'total_scheduled': self.state.get_total_scheduled(),
            'total_planned': self.state.get_total_planned(),
            'products_scheduled': len(self.state.get_products_produced_at_least_once()),
            'total_products': len(self.state.products),
            'records': [
                {
                    'line': r.line_code,
                    'date': r.date,
                    'shift': r.shift,
                    'product': r.product_code,
                    'crew': r.crew_code,
                    'quantity': r.planned_quantity,
                    'capacity': r.standard_capacity,
                    'is_changeover': r.is_changeover,
                }
                for r in self.state.records
            ]
        }


"""CSV exporter to match reference format"""

import csv
from collections import defaultdict
from typing import List, Dict
from src.models.internal_models import SchedulingContext, ShiftAssignment


class CSVExporter:
    """Exports scheduling results to CSV format"""
    
    def __init__(self, context: SchedulingContext):
        self.context = context
    
    def export_to_csv(self, output_path: str):
        """Export scheduling results to CSV file matching reference format"""
        # Group assignments by date and shift
        grouped = defaultdict(lambda: defaultdict(list))
        
        for assignment in self.context.assignments:
            key = f"{assignment.date};{assignment.shift};{assignment.week_num}"
            grouped[key][assignment.line_code].append(assignment)
        
        # Get all unique lines
        all_lines = sorted(set(a.line_code for a in self.context.assignments))
        
        # Build CSV rows
        rows = []
        
        # Header row
        header = [''] + all_lines + ['日期', '班次', '周次', '星期', '已使用班组']
        rows.append(header)
        
        # Data rows
        for date in self.context.work_calendar:
            for shift in ["早班", "中班"]:
                week_num = self.context.work_week.get(date, 0)
                
                # Find weekday
                from datetime import datetime
                weekday = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
                
                key = f"{date};{shift};{week_num}"
                line_assignments = grouped.get(key, {})
                
                # Build row
                row = [key]  # First column: date;shift;week_num
                
                # For each line
                for line_code in all_lines:
                    assignments = line_assignments.get(line_code, [])
                    if assignments:
                        # Format: [('productCode', 'crewCode', stdCap, output, cumulative)]
                        line_data = []
                        for a in assignments:
                            line_data.append((
                                a.product_code,
                                a.crew_code,
                                a.standard_capacity,
                                a.shift_output,
                                0  # Not sure what this field represents
                            ))
                        row.append(str(line_data))
                    else:
                        row.append('')
                
                # Add metadata columns
                row.extend([date, shift, week_num, weekday])
                
                # Used crews
                used_crews = sorted(set(
                    a.crew_code for a in line_assignments.values() 
                    for a in a
                ))
                row.append(str(used_crews))
                
                rows.append(row)
        
        # Write to CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
    
    def export_to_standard_format(self, output_path: str):
        """Export to standard table format (one row per shift per line)"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                '日期', '班次', '周次', '星期',
                '产线编码', '产线名称',
                '产品编码', '产品名称',
                '班组编码', '班组名称',
                '标准产能', '班次计划量', '累计完成量',
                '产能利用率', '是否换产', '状态'
            ])
            
            # Data
            for assignment in self.context.assignments:
                writer.writerow([
                    assignment.date,
                    assignment.shift,
                    assignment.week_num,
                    assignment.weekday,
                    assignment.line_code,
                    assignment.line_name,
                    assignment.product_code,
                    assignment.product_name,
                    assignment.crew_code,
                    assignment.crew_name,
                    assignment.standard_capacity,
                    assignment.shift_output,
                    assignment.cumulative_output,
                    f"{assignment.utilization:.2%}",
                    "是" if assignment.is_changeover else "否",
                    assignment.status
                ])


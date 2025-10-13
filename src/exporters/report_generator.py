"""Analysis report generator"""

from typing import List
from src.models.internal_models import SchedulingContext
from src.models.output_models import (
    ProductCompletionReport, CrewWorkloadReport,
    CapacityUtilizationReport, Warning, SchedulingOutput
)
from src.utils.capacity_calculator import CapacityCalculator


class ReportGenerator:
    """Generates analysis reports"""
    
    def __init__(self, context: SchedulingContext):
        self.context = context
    
    def generate_full_report(self) -> SchedulingOutput:
        """Generate complete scheduling output report"""
        product_completions = self.generate_product_completion_report()
        crew_workloads = self.generate_crew_workload_report()
        capacity_utilization = self.generate_capacity_utilization_report()
        warnings = self.generate_warnings()
        
        success = len(self.context.errors) == 0
        message = "排产成功" if success else f"排产失败: {'; '.join(self.context.errors)}"
        
        return SchedulingOutput(
            success=success,
            message=message,
            product_completions=product_completions,
            crew_workloads=crew_workloads,
            capacity_utilization=capacity_utilization,
            warnings=warnings
        )
    
    def generate_product_completion_report(self) -> List[ProductCompletionReport]:
        """Generate product completion status report"""
        reports = []
        
        for product_code, product_state in self.context.product_states.items():
            if product_state.bottle_total == 0:
                continue
            
            completion_rate = product_state.cumulative_produced / product_state.bottle_total if product_state.bottle_total > 0 else 0
            
            # Determine status
            if completion_rate >= 0.99:
                status = "已完成"
            elif product_state.cumulative_produced > 0:
                status = "部分完成"
            else:
                status = "未开始"
            
            # Calculate production days
            production_days = 0
            if product_state.first_production_date and product_state.last_production_date:
                dates = [d for d in self.context.work_calendar 
                        if d >= product_state.first_production_date and d <= product_state.last_production_date]
                production_days = len(dates)
            
            reports.append(ProductCompletionReport(
                product_code=product_code,
                product_name=product_state.product_name,
                planned_bottles=product_state.bottle_total,
                completed_bottles=product_state.cumulative_produced,
                completion_rate=completion_rate,
                start_date=product_state.first_production_date,
                completion_date=product_state.last_production_date,
                production_days=production_days,
                assigned_lines=list(product_state.assigned_lines),
                status=status
            ))
        
        return reports
    
    def generate_crew_workload_report(self) -> List[CrewWorkloadReport]:
        """Generate crew workload statistics"""
        reports = []
        
        # Calculate workloads
        crew_workloads = []
        for crew_code, crew_state in self.context.crew_states.items():
            if crew_state.shifts_worked > 0:
                workload_data = CapacityCalculator.calculate_crew_workload(crew_code, self.context)
                crew_workloads.append(workload_data)
        
        # Rank by workload
        crew_workloads.sort(key=lambda x: x['total_workload'], reverse=True)
        
        for rank, crew_data in enumerate(crew_workloads, 1):
            reports.append(CrewWorkloadReport(
                crew_code=crew_data['crew_code'],
                crew_name=self.context.crew_states[crew_data['crew_code']].crew_name,
                shifts_worked=crew_data['shifts_worked'],
                total_bottles=crew_data['total_bottles'],
                average_utilization=crew_data['average_utilization'],
                total_workload=crew_data['total_workload'],
                workload_rank=rank,
                assigned_lines=crew_data['assigned_lines']
            ))
        
        return reports
    
    def generate_capacity_utilization_report(self) -> CapacityUtilizationReport:
        """Generate capacity utilization statistics"""
        metrics = CapacityCalculator.calculate_overall_utilization(self.context)
        
        return CapacityUtilizationReport(
            total_shifts=metrics['total_shifts'],
            effective_shifts=metrics['effective_shifts'],
            idle_shifts=metrics['idle_shifts'],
            average_utilization=metrics['average_utilization'],
            max_utilization=metrics['max_utilization'],
            min_utilization=metrics['min_utilization'],
            changeover_shifts=metrics['changeover_shifts'],
            changeover_rate=metrics['changeover_rate'],
            total_planned_bottles=metrics['total_planned_bottles'],
            total_completed_bottles=metrics['total_completed_bottles'],
            total_completion_rate=metrics['total_completion_rate']
        )
    
    def generate_warnings(self) -> List[Warning]:
        """Generate warning messages"""
        warnings = []
        
        # Add errors
        for error in self.context.errors:
            warnings.append(Warning(
                level="错误",
                type="约束冲突",
                description=error,
                suggestion=None
            ))
        
        # Add warnings
        for warning in self.context.warnings:
            warnings.append(Warning(
                level="警告",
                type="产能不足",
                description=warning,
                suggestion=None
            ))
        
        # Check incomplete products
        for product_code, product_state in self.context.product_states.items():
            if product_state.bottle_total > 0:
                completion_rate = product_state.cumulative_produced / product_state.bottle_total
                if completion_rate < 0.99:
                    warnings.append(Warning(
                        level="警告",
                        type="产品未完成",
                        product=product_code,
                        description=f"产品{product_code}未完成，完成率{completion_rate:.1%}",
                        suggestion="增加工作日或调整产品分配"
                    ))
        
        # Check crew workload balance
        balance_metrics = CapacityCalculator.calculate_crew_balance(self.context)
        if balance_metrics.get('max_diff_pct', 0) > 0.15:
            warnings.append(Warning(
                level="提示",
                type="负荷不均衡",
                description=f"班组负荷不均衡，差异{balance_metrics['max_diff_pct']:.1%}",
                suggestion="调整班组分配以平衡负荷"
            ))
        
        return warnings
    
    def export_report_to_text(self, output_path: str):
        """Export report to text file"""
        report = self.generate_full_report()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("茅台生产排产系统 - 排产结果报告\n")
            f.write("=" * 80 + "\n\n")
            
            # Status
            f.write(f"排产状态: {'成功' if report.success else '失败'}\n")
            f.write(f"消息: {report.message}\n\n")
            
            # Capacity utilization
            f.write("-" * 80 + "\n")
            f.write("产能利用率统计\n")
            f.write("-" * 80 + "\n")
            util = report.capacity_utilization
            f.write(f"总排产班次数: {util.total_shifts}\n")
            f.write(f"有效班次数: {util.effective_shifts}\n")
            f.write(f"空线班次数: {util.idle_shifts}\n")
            f.write(f"平均利用率: {util.average_utilization:.2%}\n")
            f.write(f"最高利用率: {util.max_utilization:.2%}\n")
            f.write(f"最低利用率: {util.min_utilization:.2%}\n")
            f.write(f"换产班次数: {util.changeover_shifts}\n")
            f.write(f"换产率: {util.changeover_rate:.2%}\n")
            f.write(f"总计划量: {util.total_planned_bottles} 瓶\n")
            f.write(f"总完成量: {util.total_completed_bottles} 瓶\n")
            f.write(f"总完成率: {util.total_completion_rate:.2%}\n\n")
            
            # Product completions
            f.write("-" * 80 + "\n")
            f.write("产品完成情况\n")
            f.write("-" * 80 + "\n")
            for pc in report.product_completions:
                f.write(f"\n产品: {pc.product_code} - {pc.product_name}\n")
                f.write(f"  计划量: {pc.planned_bottles} 瓶\n")
                f.write(f"  完成量: {pc.completed_bottles} 瓶\n")
                f.write(f"  完成率: {pc.completion_rate:.2%}\n")
                f.write(f"  状态: {pc.status}\n")
                f.write(f"  生产天数: {pc.production_days}\n")
                f.write(f"  涉及产线: {', '.join(pc.assigned_lines)}\n")
            
            # Crew workloads
            f.write("\n" + "-" * 80 + "\n")
            f.write("班组负荷统计\n")
            f.write("-" * 80 + "\n")
            for cw in report.crew_workloads[:10]:  # Top 10
                f.write(f"\n班组: {cw.crew_code} - {cw.crew_name}\n")
                f.write(f"  排名: {cw.workload_rank}\n")
                f.write(f"  排产班次数: {cw.shifts_worked}\n")
                f.write(f"  总生产量: {cw.total_bottles} 瓶\n")
                f.write(f"  平均利用率: {cw.average_utilization:.2%}\n")
                f.write(f"  总负荷: {cw.total_workload:.2f}\n")
            
            # Warnings
            if report.warnings:
                f.write("\n" + "-" * 80 + "\n")
                f.write("警告信息\n")
                f.write("-" * 80 + "\n")
                for warning in report.warnings:
                    f.write(f"\n[{warning.level}] {warning.type}\n")
                    f.write(f"  {warning.description}\n")
                    if warning.suggestion:
                        f.write(f"  建议: {warning.suggestion}\n")


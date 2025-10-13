"""Output data models"""

from typing import List, Dict, Optional
from pydantic import BaseModel


class ProductCompletionReport(BaseModel):
    """Product completion status report"""
    product_code: str
    product_name: str
    planned_bottles: int
    completed_bottles: int
    completion_rate: float
    start_date: Optional[str]
    completion_date: Optional[str]
    production_days: int
    assigned_lines: List[str]
    status: str  # 已完成/部分完成/未开始


class CrewWorkloadReport(BaseModel):
    """Crew workload statistics"""
    crew_code: str
    crew_name: str
    shifts_worked: int
    total_bottles: int
    average_utilization: float
    total_workload: float
    workload_rank: int
    assigned_lines: List[str]


class CapacityUtilizationReport(BaseModel):
    """Capacity utilization statistics"""
    total_shifts: int
    effective_shifts: int
    idle_shifts: int
    average_utilization: float
    max_utilization: float
    min_utilization: float
    changeover_shifts: int
    changeover_rate: float
    total_planned_bottles: int
    total_completed_bottles: int
    total_completion_rate: float


class Warning(BaseModel):
    """Warning or error message"""
    level: str  # 错误/警告/提示
    type: str  # 产能不足/约束冲突/异常状态
    date: Optional[str] = None
    line: Optional[str] = None
    product: Optional[str] = None
    crew: Optional[str] = None
    description: str
    suggestion: Optional[str] = None


class SchedulingOutput(BaseModel):
    """Complete scheduling output"""
    success: bool
    message: str
    product_completions: List[ProductCompletionReport]
    crew_workloads: List[CrewWorkloadReport]
    capacity_utilization: CapacityUtilizationReport
    warnings: List[Warning]


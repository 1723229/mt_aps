"""Input data models for schedule requests."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SchedulePlan(BaseModel):
    """Schedule plan detail for a product."""
    
    id: int
    baseSpiritCode: str
    baseSpiritName: str
    productType: Optional[str] = None
    productId: int
    productCode: str
    productName: str
    bottleTotal: int  # Total planned quantity in bottles
    plannedTotal: float  # Total planned quantity in tons
    orderType: str
    bomVer: Optional[float] = None
    deliverDay: Optional[str] = None
    spec: int  # Specification in ml (e.g., 500, 1000, 200)
    price: float = 0.0


class LineProductSetting(BaseModel):
    """Line-product configuration with capacity and priority."""
    
    headerId: int = Field(alias='headerId', default=0)  # Map headerId to id
    lineCode: str
    lineName: str
    productCode: str
    productName: str
    standardCapacity: int  # Standard capacity per shift
    productionCapacity: Optional[int] = None  # Actual capacity (use if set)
    workerNum: Optional[int] = None
    standardScore: Optional[int] = None
    conversionTime: Optional[int] = None  # Changeover time in minutes
    scheduleType: Optional[str] = None  # Not used
    priority: Optional[int] = None  # Not used
    lineProductWeight: Optional[int] = None  # Not used
    productLineWeight: int  # Core priority field (lower = higher priority)
    
    class Config:
        populate_by_name = True
    
    def get_effective_capacity(self) -> int:
        """Get the effective capacity to use for scheduling."""
        if self.productionCapacity and self.productionCapacity > 0:
            return self.productionCapacity
        return self.standardCapacity


class LineCrewSetting(BaseModel):
    """Line-crew configuration with priorities."""
    
    headerId: int = Field(alias='headerId', default=0)
    lineCode: str
    lineName: str
    crewCode: str
    crewName: str
    priority: Optional[int] = None  # Not used
    lineCrewPriority: int  # Line's preference for crew (lower = higher)
    crewLinePriority: int  # Crew's preference for line (lower = higher)
    
    class Config:
        populate_by_name = True


class ConstraintSetting(BaseModel):
    """Constraint configuration."""
    
    headerId: int = Field(alias='headerId', default=0)
    enable: bool
    constraintType: str
    constraintName: str
    constraintValue: Any
    orderNum: int
    
    class Config:
        populate_by_name = True


class SolutionStrategySetting(BaseModel):
    """Solution strategy settings (not currently used)."""
    
    id: Optional[int] = None
    solutionStrategy: Optional[str] = None
    strategyValue: Optional[Any] = None


class LineCrewScheduleSetting(BaseModel):
    """Line crew schedule settings (not currently used)."""
    
    id: Optional[int] = None
    # Add fields as needed


class Solution(BaseModel):
    """Complete solution configuration."""
    
    id: int
    solutionName: str
    solutionCode: str
    lineProductSettingDetails: List[LineProductSetting]
    lineCrewScheduleSettings: Optional[List[LineCrewScheduleSetting]] = Field(default_factory=list)
    lineCrewSettingDetails: List[LineCrewSetting]
    constraintSettings: List[ConstraintSetting]
    solutionStrategySetting: Optional[SolutionStrategySetting] = None


class ScheduleRequest(BaseModel):
    """Top-level schedule request model."""
    
    workCalendar: List[str]  # List of work dates in "YYYY-MM-DD" format
    workWeek: Dict[str, int]  # Mapping from date to week number
    schedulePlans: List[SchedulePlan]
    solutions: List[Solution]
    
    def get_primary_solution(self) -> Solution:
        """Get the first solution (primary configuration)."""
        if not self.solutions:
            raise ValueError("No solutions provided in request")
        return self.solutions[0]
    
    def build_indices(self) -> "ScheduleIndices":
        """Build lookup indices for efficient access."""
        return ScheduleIndices(self)


class ScheduleIndices:
    """Pre-built indices for efficient lookups."""
    
    def __init__(self, request: ScheduleRequest):
        solution = request.get_primary_solution()
        
        # Product lookup
        self.products_by_code: Dict[str, SchedulePlan] = {
            plan.productCode: plan for plan in request.schedulePlans
        }
        
        # Line-product mappings
        self.lines_for_product: Dict[str, List[LineProductSetting]] = {}
        for setting in solution.lineProductSettingDetails:
            if setting.productCode not in self.lines_for_product:
                self.lines_for_product[setting.productCode] = []
            self.lines_for_product[setting.productCode].append(setting)
        
        # Sort by productLineWeight (lower = higher priority)
        for product_code in self.lines_for_product:
            self.lines_for_product[product_code].sort(
                key=lambda x: x.productLineWeight
            )
        
        # Product-line mappings
        self.products_for_line: Dict[str, List[LineProductSetting]] = {}
        for setting in solution.lineProductSettingDetails:
            if setting.lineCode not in self.products_for_line:
                self.products_for_line[setting.lineCode] = []
            self.products_for_line[setting.lineCode].append(setting)
        
        # Line-crew mappings
        self.crews_for_line: Dict[str, List[LineCrewSetting]] = {}
        for setting in solution.lineCrewSettingDetails:
            if setting.lineCode not in self.crews_for_line:
                self.crews_for_line[setting.lineCode] = []
            self.crews_for_line[setting.lineCode].append(setting)
        
        # Sort by priority (lineCrewPriority, then crewLinePriority)
        for line_code in self.crews_for_line:
            self.crews_for_line[line_code].sort(
                key=lambda x: (x.lineCrewPriority, x.crewLinePriority)
            )
        
        # Crew-line mappings
        self.lines_for_crew: Dict[str, List[LineCrewSetting]] = {}
        for setting in solution.lineCrewSettingDetails:
            if setting.crewCode not in self.lines_for_crew:
                self.lines_for_crew[setting.crewCode] = []
            self.lines_for_crew[setting.crewCode].append(setting)
        
        # Line-product settings lookup
        self.line_product_settings: Dict[tuple, LineProductSetting] = {}
        for setting in solution.lineProductSettingDetails:
            key = (setting.lineCode, setting.productCode)
            self.line_product_settings[key] = setting
        
        # All unique line codes
        self.all_lines = set(s.lineCode for s in solution.lineProductSettingDetails)
        
        # All unique crew codes
        self.all_crews = set(s.crewCode for s in solution.lineCrewSettingDetails)
        
        # All unique product codes with plans
        self.all_products = set(plan.productCode for plan in request.schedulePlans)
        
        # Constraints by type
        self.constraints_by_type: Dict[str, List[ConstraintSetting]] = {}
        for constraint in solution.constraintSettings:
            if constraint.enable:
                if constraint.constraintType not in self.constraints_by_type:
                    self.constraints_by_type[constraint.constraintType] = []
                self.constraints_by_type[constraint.constraintType].append(constraint)
    
    def get_line_setting(self, line_code: str, product_code: str) -> Optional[LineProductSetting]:
        """Get line-product setting if exists."""
        return self.line_product_settings.get((line_code, product_code))
    
    def can_produce(self, line_code: str, product_code: str) -> bool:
        """Check if a line can produce a product."""
        return (line_code, product_code) in self.line_product_settings
    
    def get_exclusive_products(self) -> List[str]:
        """Get products that can only be produced on one line."""
        exclusive = []
        for product_code in self.all_products:
            if len(self.lines_for_product.get(product_code, [])) == 1:
                exclusive.append(product_code)
        return exclusive


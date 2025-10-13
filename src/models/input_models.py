"""Pydantic models for input data validation"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class SchedulePlanDetail(BaseModel):
    """Single product planning detail"""
    id: Optional[int] = None
    baseSpiritCode: str
    baseSpiritName: str
    productType: Optional[str] = None
    productId: Optional[int] = None
    productCode: str
    productName: str
    bottleTotal: int  # Target production quantity in bottles
    plannedTotal: float  # Planned quantity in tons
    orderType: str
    bomVer: Optional[float] = None
    deliverDay: Optional[str] = None  # Delivery date YYYY-MM-DD
    spec: int  # Specification in ml (e.g., 500, 1000)
    price: float


class LineProductSettingDetail(BaseModel):
    """Line-Product configuration"""
    headerId: Optional[int] = None
    lineCode: str
    lineName: str
    productId: Optional[int] = None
    productCode: str
    productName: str
    standardCapacity: int  # Standard capacity per shift (bottles)
    workerNum: Optional[int] = None
    standardScore: Optional[int] = None
    conversionTime: Optional[int] = None
    scheduleType: Optional[str] = None
    priority: Optional[int] = None
    lineProductWeight: Optional[int] = None  # Not used
    productLineWeight: int  # Lower value = higher priority
    productionCapacity: Optional[int] = None  # Actual usable capacity


class LineCrewScheduleSetting(BaseModel):
    """Line scheduling type configuration"""
    headerId: Optional[int] = None
    lineCode: str
    scheduleType: Optional[str] = None
    priorityCrewCode: Optional[str] = None


class LineCrewSettingDetail(BaseModel):
    """Line-Crew binding configuration"""
    id: Optional[int] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None
    creatorId: Optional[int] = None
    updaterId: Optional[int] = None
    siteNum: Optional[str] = None
    headerId: Optional[int] = None
    lineCode: str
    lineName: str
    crewCode: str
    crewName: str
    priority: Optional[int] = None  # Not used
    lineCrewPriority: int  # Line's preference for crew (lower = higher priority)
    crewLinePriority: int  # Crew's preference for line (lower = higher priority)


class LineForbidTimeConstraint(BaseModel):
    """Line unavailable time constraint value"""
    lineCode: str
    forbidTime: str  # Date in YYYY-MM-DD format


class ProductPriorityDistributePeriod(BaseModel):
    """Product priority assignment period"""
    assignDate: List[str]  # List of dates
    assignDun: float  # Assigned quantity in tons


class ProductPriorityConstraint(BaseModel):
    """Product priority constraint value"""
    productCode: str
    productName: str
    distributePeriod: List[ProductPriorityDistributePeriod]


class ConstraintSetting(BaseModel):
    """Constraint configuration"""
    id: Optional[int] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None
    creatorId: Optional[int] = None
    updaterId: Optional[int] = None
    siteNum: Optional[str] = None
    headerId: Optional[int] = None
    enable: bool
    constraintValue: Optional[Any] = None  # Type varies by constraintType
    constraintType: str
    constraintName: str
    orderNum: int


class SolutionStrategySetting(BaseModel):
    """Solution strategy settings"""
    # To be defined if needed
    pass


class SchemeModel(BaseModel):
    """Solution scheme model"""
    id: int
    solutionName: str
    solutionCode: str
    lineProductSettingDetails: List[LineProductSettingDetail]
    lineCrewScheduleSettings: List[LineCrewScheduleSetting]
    lineCrewSettingDetails: List[LineCrewSettingDetail]
    constraintSettings: List[ConstraintSetting]
    solutionStrategySetting: Optional[SolutionStrategySetting] = None


class SchemeRequestModel(BaseModel):
    """Main scheduling request model"""
    workCalendar: List[str]  # Working dates in YYYY-MM-DD format
    workWeek: Dict[str, int]  # Date to week number mapping
    schedulePlans: List[SchedulePlanDetail]
    solutions: List[SchemeModel]


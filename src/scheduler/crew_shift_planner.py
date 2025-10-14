"""Crew shift planner - implements BC-11.

BC-11: Crew班次规则
1. 班组在同一周内，固定班次生产，全部早班或全部中班
2. 班组跨周，切换班次；上周早班，这周就中班
"""

from typing import Dict, List, Set


class CrewShiftPlanner:
    """Plans crew shift assignments across weeks."""
    
    def __init__(
        self,
        work_calendar: List[str],
        work_week: Dict[str, int],
        all_crews: Set[str],
    ):
        """Initialize planner.
        
        Args:
            work_calendar: List of work dates
            work_week: Mapping from date to week number
            all_crews: Set of all crew codes
        """
        self.work_calendar = work_calendar
        self.work_week = work_week
        self.all_crews = all_crews
        
        # Result: crew -> date -> shift
        self.crew_shift_plan: Dict[str, Dict[str, str]] = {}
    
    def plan_shifts(self) -> Dict[str, Dict[str, str]]:
        """Plan shift assignments for all crews.
        
        Strategy:
        - Each crew starts with 'early' in week 1
        - Within a week, crew stays on same shift
        - When week changes, crew alternates shift
        
        Returns:
            crew_shift_plan: crew -> date -> 'early' or 'middle'
        """
        # Get unique weeks in order
        weeks = sorted(set(self.work_week.values()))
        
        # Plan for each crew
        for crew in self.all_crews:
            crew_plan = {}
            
            # Alternate starting shift per crew for diversity
            # Even crews start early, odd crews start middle
            crew_num = self._extract_crew_number(crew)
            current_shift = 'early' if crew_num % 2 == 0 else 'middle'
            
            # Track shift per week
            week_shift = {}
            for week in weeks:
                week_shift[week] = current_shift
                # Alternate for next week
                current_shift = 'middle' if current_shift == 'early' else 'early'
            
            # Assign to all dates
            for date in self.work_calendar:
                week = self.work_week[date]
                crew_plan[date] = week_shift[week]
            
            self.crew_shift_plan[crew] = crew_plan
        
        return self.crew_shift_plan
    
    def get_shift_for_crew(self, crew_code: str, date: str) -> str:
        """Get the planned shift for a crew on a date.
        
        Args:
            crew_code: Crew code
            date: Date string
        
        Returns:
            'early' or 'middle'
        """
        if crew_code not in self.crew_shift_plan:
            raise ValueError(f"No shift plan for crew {crew_code}")
        
        if date not in self.crew_shift_plan[crew_code]:
            raise ValueError(f"No shift plan for crew {crew_code} on date {date}")
        
        return self.crew_shift_plan[crew_code][date]
    
    def get_crews_for_shift(self, date: str, shift: str) -> Set[str]:
        """Get all crews planned for a specific shift on a date.
        
        Args:
            date: Date string
            shift: 'early' or 'middle'
        
        Returns:
            Set of crew codes
        """
        crews = set()
        for crew, plan in self.crew_shift_plan.items():
            if plan.get(date) == shift:
                crews.add(crew)
        return crews
    
    def _extract_crew_number(self, crew_code: str) -> int:
        """Extract numeric part from crew code.
        
        Args:
            crew_code: Crew code like 'pack01', 'pack15'
        
        Returns:
            Numeric part as int
        """
        # Extract digits from crew code
        digits = ''.join(c for c in crew_code if c.isdigit())
        return int(digits) if digits else 0
    
    def validate_plan(self) -> tuple[bool, List[str]]:
        """Validate the shift plan satisfies BC-11.
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        for crew, plan in self.crew_shift_plan.items():
            # Check: same shift within each week
            week_shifts: Dict[int, Set[str]] = {}
            
            for date, shift in plan.items():
                week = self.work_week[date]
                if week not in week_shifts:
                    week_shifts[week] = set()
                week_shifts[week].add(shift)
            
            # Each week should have only one shift
            for week, shifts in week_shifts.items():
                if len(shifts) > 1:
                    errors.append(
                        f"Crew {crew} has multiple shifts in week {week}: {shifts}"
                    )
        
        return len(errors) == 0, errors


"""Data loading utilities."""

import json
from typing import Dict
from pathlib import Path
from ..models.input_models import ScheduleRequest


def load_schedule_request(json_path: str) -> ScheduleRequest:
    """Load schedule request from JSON file.
    
    Args:
        json_path: Path to JSON file
    
    Returns:
        Parsed ScheduleRequest object
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return ScheduleRequest(**data)


def load_json(json_path: str) -> Dict:
    """Load raw JSON data.
    
    Args:
        json_path: Path to JSON file
    
    Returns:
        Dictionary of JSON data
    """
    path = Path(json_path)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


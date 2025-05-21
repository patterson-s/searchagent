# src/models.py
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from pydantic import BaseModel

class VerticalItem(BaseModel):
    value: str   # concatenated string shown in the prompt
    index: str   # unique slug (e.g., UN_Dundex)

class Prompt(BaseModel):
    vertical: str
    horizontal_category: str
    index: str
    prompt: str

class ExecutionResult(BaseModel):
    prompt: str
    raw_response: Dict[str, Any]
    response_text: str
    parsed_json: Optional[Dict[str, Any]]
    execution_time: float
    success: bool
    error_message: Optional[str]

# Convenient type aliases for clarity inside the service layer
VerticalData   = List[Tuple[str, str]]       # [(vertical_value, vertical_index)]
HorizontalData = Dict[str, List[str]]        # {"category": [terms]}
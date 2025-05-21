# src/models.py
from pathlib import Path
from typing import List, Dict, Tuple
from pydantic import BaseModel

class VerticalItem(BaseModel):
    value: str   # concatenated string shown in the prompt
    index: str   # unique slug (e.g., UN_Dundex)

class Prompt(BaseModel):
    vertical: str
    horizontal_category: str
    index: str
    prompt: str

# Convenient type aliases for clarity inside the service layer
VerticalData   = List[Tuple[str, str]]       # [(vertical_value, vertical_index)]
HorizontalData = Dict[str, List[str]]        # {"category": [terms]}

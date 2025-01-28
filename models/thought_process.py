from pydantic import BaseModel, Field
from typing import List, Dict, Type, Any, Optional
from enum import Enum

class ThoughtCategory(Enum):
    GENERAL = "general"
    TECHNICAL = "technical"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    PLANNING = "planning"

class Metadata(BaseModel):
    key: str
    value: str
    category: ThoughtCategory = ThoughtCategory.GENERAL

class ThoughtStep(BaseModel):
    step_number: int
    reasoning: str
    conclusion: str
    confidence: float
    category: ThoughtCategory
    requires_tools: bool = False
    suggested_tools: List[str] = Field(default_factory=list)

class ChainOfThought(BaseModel):
    initial_thought: str
    steps: List[ThoughtStep]
    final_conclusion: str
    metadata: List[Metadata] = Field(default_factory=list)
    estimated_complexity: int = Field(ge=1, le=10)
    requires_realtime: bool = True
    suggested_models: List[str] = Field(default_factory=list)

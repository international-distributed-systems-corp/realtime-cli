"""
DSPy-based reasoning tools for enhanced AI cognition
"""
from .base import BaseReasoningTool, ReasoningResult
from .logical import (
    DeductiveReasoningTool, 
    InductiveReasoningTool, 
    AbductiveReasoningTool,
    ArgumentAnalysisTool,
    ConditionalReasoningTool
)
from .analytical import (
    CausalAnalysisTool,
    RiskAssessmentTool,
    TrendAnalysisTool
)
from .creative import (
    BrainstormingTool,
    AnalogyReasoningTool,
    ReframingTool
)
from .orchestrator import ReasoningOrchestrator

__all__ = [
    "BaseReasoningTool",
    "ReasoningResult", 
    "DeductiveReasoningTool",
    "InductiveReasoningTool",
    "AbductiveReasoningTool",
    "ArgumentAnalysisTool",
    "ConditionalReasoningTool",
    "CausalAnalysisTool",
    "RiskAssessmentTool",
    "TrendAnalysisTool",
    "BrainstormingTool",
    "AnalogyReasoningTool",
    "ReframingTool",
    "ReasoningOrchestrator"
]
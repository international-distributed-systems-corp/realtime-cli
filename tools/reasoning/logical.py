"""
Logical reasoning tools using DSPy
"""
import json
import dspy
from typing import ClassVar, Literal, Optional
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseReasoningTool, ReasoningResult, ReasoningSignatures


class DeductiveReasoningTool(BaseReasoningTool):
    """Apply deductive logic to reach conclusions from premises"""
    
    name: ClassVar[Literal["deductive_reasoning"]] = "deductive_reasoning"
    api_type: ClassVar[Literal["deductive_reasoning_20241022"]] = "deductive_reasoning_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.DeductiveReasoning
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        return ReasoningResult(
            conclusion=raw_result.conclusion,
            reasoning_steps=raw_result.reasoning_steps.split('\n') if hasattr(raw_result, 'reasoning_steps') else [],
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=[raw_result.logical_validity] if hasattr(raw_result, 'logical_validity') else [],
            assumptions=[],
            alternatives=[],
            metadata={"reasoning_type": "deductive", "validity": getattr(raw_result, 'logical_validity', 'unknown')}
        )
    
    async def __call__(
        self,
        *,
        premises: str,
        query: str,
        **kwargs
    ) -> ReasoningResult:
        """Execute deductive reasoning"""
        return await self.execute_reasoning(premises=premises, query=query)
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class InductiveReasoningTool(BaseReasoningTool):
    """Generate generalizations from specific observations"""
    
    name: ClassVar[Literal["inductive_reasoning"]] = "inductive_reasoning"
    api_type: ClassVar[Literal["inductive_reasoning_20241022"]] = "inductive_reasoning_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.InductiveReasoning
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        return ReasoningResult(
            conclusion=raw_result.generalization,
            reasoning_steps=raw_result.reasoning_steps.split('\n') if hasattr(raw_result, 'reasoning_steps') else [],
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=raw_result.supporting_evidence.split('\n') if hasattr(raw_result, 'supporting_evidence') else [],
            assumptions=[],
            alternatives=[],
            metadata={
                "reasoning_type": "inductive",
                "limitations": getattr(raw_result, 'limitations', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        observations: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute inductive reasoning"""
        return await self.execute_reasoning(observations=observations, context=context or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class AbductiveReasoningTool(BaseReasoningTool):
    """Find the best explanation for observations"""
    
    name: ClassVar[Literal["abductive_reasoning"]] = "abductive_reasoning"
    api_type: ClassVar[Literal["abductive_reasoning_20241022"]] = "abductive_reasoning_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.AbductiveReasoning
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        alternatives = []
        if hasattr(raw_result, 'alternative_explanations'):
            alternatives = raw_result.alternative_explanations.split('\n')
        
        return ReasoningResult(
            conclusion=raw_result.best_explanation,
            reasoning_steps=raw_result.reasoning_steps.split('\n') if hasattr(raw_result, 'reasoning_steps') else [],
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=[],
            assumptions=[],
            alternatives=alternatives,
            metadata={
                "reasoning_type": "abductive",
                "evidence_requirements": getattr(raw_result, 'evidence_requirements', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        observations: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute abductive reasoning"""
        return await self.execute_reasoning(observations=observations, context=context or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class ArgumentAnalysisTool(BaseReasoningTool):
    """Analyze the structure and validity of arguments"""
    
    name: ClassVar[Literal["argument_analysis"]] = "argument_analysis"
    api_type: ClassVar[Literal["argument_analysis_20241022"]] = "argument_analysis_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.ArgumentAnalysis
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        premises = []
        if hasattr(raw_result, 'premises'):
            premises = raw_result.premises.split('\n')
        
        return ReasoningResult(
            conclusion=raw_result.conclusion if hasattr(raw_result, 'conclusion') else "No conclusion identified",
            reasoning_steps=[raw_result.argument_structure] if hasattr(raw_result, 'argument_structure') else [],
            confidence=float(raw_result.strength_score) if hasattr(raw_result, 'strength_score') else 0.5,
            evidence=premises,
            assumptions=[],
            alternatives=[raw_result.improvement_suggestions] if hasattr(raw_result, 'improvement_suggestions') else [],
            metadata={
                "reasoning_type": "argument_analysis",
                "validity": getattr(raw_result, 'validity_assessment', 'unknown'),
                "fallacies": getattr(raw_result, 'fallacies', 'none identified')
            }
        )
    
    async def __call__(
        self,
        *,
        argument_text: str,
        **kwargs
    ) -> ReasoningResult:
        """Execute argument analysis"""
        return await self.execute_reasoning(argument_text=argument_text)
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class ConditionalReasoningTool(BaseReasoningTool):
    """Handle if-then reasoning and counterfactuals"""
    
    name: ClassVar[Literal["conditional_reasoning"]] = "conditional_reasoning"
    api_type: ClassVar[Literal["conditional_reasoning_20241022"]] = "conditional_reasoning_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.ConditionalReasoning
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        implications = []
        if hasattr(raw_result, 'implications'):
            implications = raw_result.implications.split('\n')
        
        return ReasoningResult(
            conclusion=raw_result.evaluation,
            reasoning_steps=raw_result.reasoning_steps.split('\n') if hasattr(raw_result, 'reasoning_steps') else [],
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=[raw_result.truth_conditions] if hasattr(raw_result, 'truth_conditions') else [],
            assumptions=[],
            alternatives=implications,
            metadata={
                "reasoning_type": "conditional",
                "truth_conditions": getattr(raw_result, 'truth_conditions', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        conditional_statement: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute conditional reasoning"""
        return await self.execute_reasoning(
            conditional_statement=conditional_statement, 
            context=context or ""
        )
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }
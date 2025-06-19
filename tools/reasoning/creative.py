"""
Creative reasoning tools using DSPy
"""
import json
import dspy
from typing import ClassVar, Literal, Optional
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseReasoningTool, ReasoningResult, ReasoningSignatures


class BrainstormingTool(BaseReasoningTool):
    """Generate creative ideas and solutions"""
    
    name: ClassVar[Literal["brainstorming"]] = "brainstorming"
    api_type: ClassVar[Literal["brainstorming_20241022"]] = "brainstorming_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.Brainstorming
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        ideas = []
        if hasattr(raw_result, 'ideas'):
            ideas = raw_result.ideas.split('\n')
        
        creative_approaches = []
        if hasattr(raw_result, 'creative_approaches'):
            creative_approaches = raw_result.creative_approaches.split('\n')
        
        next_steps = []
        if hasattr(raw_result, 'next_steps'):
            next_steps = raw_result.next_steps.split('\n')
        
        reasoning_steps = []
        if hasattr(raw_result, 'idea_evaluation'):
            reasoning_steps.append(f"Idea Evaluation: {raw_result.idea_evaluation}")
        
        return ReasoningResult(
            conclusion=f"Generated {len(ideas)} ideas with {len(creative_approaches)} creative approaches",
            reasoning_steps=reasoning_steps,
            confidence=float(raw_result.novelty_score) if hasattr(raw_result, 'novelty_score') else 0.5,
            evidence=ideas,
            assumptions=[],
            alternatives=creative_approaches + next_steps,
            metadata={
                "reasoning_type": "brainstorming",
                "novelty_score": getattr(raw_result, 'novelty_score', 0.5),
                "idea_count": len(ideas),
                "creative_approach_count": len(creative_approaches)
            }
        )
    
    async def __call__(
        self,
        *,
        problem: str,
        constraints: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute brainstorming"""
        return await self.execute_reasoning(problem=problem, constraints=constraints or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class AnalogyReasoningTool(BaseReasoningTool):
    """Find and apply analogies for understanding"""
    
    name: ClassVar[Literal["analogy_reasoning"]] = "analogy_reasoning"
    api_type: ClassVar[Literal["analogy_reasoning_20241022"]] = "analogy_reasoning_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.AnalogyReasoning
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        analogies = []
        if hasattr(raw_result, 'analogies'):
            analogies = raw_result.analogies.split('\n')
        
        insights = []
        if hasattr(raw_result, 'insights'):
            insights = raw_result.insights.split('\n')
        
        limitations = []
        if hasattr(raw_result, 'limitations'):
            limitations = raw_result.limitations.split('\n')
        
        reasoning_steps = []
        if hasattr(raw_result, 'mapping'):
            reasoning_steps.append(f"Analogy Mapping: {raw_result.mapping}")
        
        return ReasoningResult(
            conclusion=f"Found {len(analogies)} relevant analogies with key insights",
            reasoning_steps=reasoning_steps,
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=analogies,
            assumptions=limitations,
            alternatives=insights,
            metadata={
                "reasoning_type": "analogy_reasoning",
                "analogy_count": len(analogies),
                "mapping": getattr(raw_result, 'mapping', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        source_domain: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute analogy reasoning"""
        return await self.execute_reasoning(source_domain=source_domain, context=context or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class ReframingTool(BaseReasoningTool):
    """Reframe problems from different perspectives"""
    
    name: ClassVar[Literal["reframing"]] = "reframing"
    api_type: ClassVar[Literal["reframing_20241022"]] = "reframing_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.Reframing
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        alternative_frames = []
        if hasattr(raw_result, 'alternative_frames'):
            alternative_frames = raw_result.alternative_frames.split('\n')
        
        new_insights = []
        if hasattr(raw_result, 'new_insights'):
            new_insights = raw_result.new_insights.split('\n')
        
        solution_approaches = []
        if hasattr(raw_result, 'solution_approaches'):
            solution_approaches = raw_result.solution_approaches.split('\n')
        
        reasoning_steps = []
        if hasattr(raw_result, 'perspective_value'):
            reasoning_steps.append(f"Perspective Value: {raw_result.perspective_value}")
        if hasattr(raw_result, 'recommended_frame'):
            reasoning_steps.append(f"Recommended Frame: {raw_result.recommended_frame}")
        
        return ReasoningResult(
            conclusion=raw_result.recommended_frame if hasattr(raw_result, 'recommended_frame') else "Multiple reframing options identified",
            reasoning_steps=reasoning_steps,
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=alternative_frames,
            assumptions=new_insights,
            alternatives=solution_approaches,
            metadata={
                "reasoning_type": "reframing",
                "frame_count": len(alternative_frames),
                "perspective_value": getattr(raw_result, 'perspective_value', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        original_problem: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute problem reframing"""
        return await self.execute_reasoning(original_problem=original_problem, context=context or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }
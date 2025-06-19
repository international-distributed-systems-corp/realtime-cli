"""
Base classes for DSPy-powered reasoning tools
"""
import json
import dspy
from typing import ClassVar, Literal, Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
from anthropic.types.beta import BetaToolUnionParam

from ..base import BaseAnthropicTool, ToolResult


@dataclass
class ReasoningResult:
    """Enhanced result class for reasoning operations"""
    conclusion: str
    reasoning_steps: List[str]
    confidence: float
    evidence: List[str]
    assumptions: List[str]
    alternatives: List[str]
    metadata: Dict[str, Any]
    
    def to_tool_result(self) -> ToolResult:
        """Convert to standard ToolResult format"""
        output = {
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "reasoning_steps": self.reasoning_steps,
            "evidence": self.evidence,
            "assumptions": self.assumptions,
            "alternatives": self.alternatives,
            "metadata": self.metadata
        }
        return ToolResult(output=json.dumps(output, indent=2))


class BaseReasoningTool(BaseAnthropicTool, ABC):
    """Base class for all DSPy-powered reasoning tools"""
    
    def __init__(self):
        # Initialize DSPy with GPT-4.1
        self.lm = dspy.LM(
            model="gpt-4o-2024-08-06",  # Using latest GPT-4 model
            api_key=None,  # Will use OPENAI_API_KEY environment variable
            max_tokens=4000,
            temperature=0.1  # Low temperature for consistent reasoning
        )
        dspy.configure(lm=self.lm)
        super().__init__()
    
    @abstractmethod
    def get_reasoning_signature(self) -> dspy.Signature:
        """Return the DSPy signature for this reasoning tool"""
        pass
    
    @abstractmethod
    def process_reasoning_result(self, raw_result: Any) -> ReasoningResult:
        """Process the raw DSPy result into structured ReasoningResult"""
        pass
    
    async def execute_reasoning(self, **kwargs) -> ReasoningResult:
        """Execute the reasoning process using DSPy"""
        try:
            # Get the reasoning signature
            signature = self.get_reasoning_signature()
            
            # Create a DSPy predictor
            predictor = dspy.Predict(signature)
            
            # Execute reasoning
            raw_result = predictor(**kwargs)
            
            # Process result
            result = self.process_reasoning_result(raw_result)
            
            return result
            
        except Exception as e:
            return ReasoningResult(
                conclusion=f"Reasoning failed: {str(e)}",
                reasoning_steps=[],
                confidence=0.0,
                evidence=[],
                assumptions=[],
                alternatives=[],
                metadata={"error": str(e)}
            )


class ReasoningSignatures:
    """Collection of DSPy signatures for different reasoning types"""
    
    class DeductiveReasoning(dspy.Signature):
        """Apply deductive logic to reach conclusions from premises"""
        premises: str = dspy.InputField(desc="The given premises or facts")
        query: str = dspy.InputField(desc="The question or conclusion to evaluate")
        conclusion: str = dspy.OutputField(desc="The logical conclusion")
        reasoning_steps: str = dspy.OutputField(desc="Step-by-step logical reasoning")
        confidence: float = dspy.OutputField(desc="Confidence level (0-1)")
        logical_validity: str = dspy.OutputField(desc="Assessment of logical validity")
    
    class InductiveReasoning(dspy.Signature):
        """Generate generalizations from specific observations"""
        observations: str = dspy.InputField(desc="Specific observations or examples")
        context: str = dspy.InputField(desc="Additional context or domain information")
        generalization: str = dspy.OutputField(desc="The induced general pattern or rule")
        reasoning_steps: str = dspy.OutputField(desc="Step-by-step inductive reasoning")
        confidence: float = dspy.OutputField(desc="Confidence in the generalization (0-1)")
        supporting_evidence: str = dspy.OutputField(desc="Evidence supporting the generalization")
        limitations: str = dspy.OutputField(desc="Limitations or exceptions to the generalization")
    
    class AbductiveReasoning(dspy.Signature):
        """Find the best explanation for observations"""
        observations: str = dspy.InputField(desc="The phenomena or facts to explain")
        context: str = dspy.InputField(desc="Relevant background context")
        best_explanation: str = dspy.OutputField(desc="The most likely explanation")
        reasoning_steps: str = dspy.OutputField(desc="Step-by-step abductive reasoning")
        confidence: float = dspy.OutputField(desc="Confidence in the explanation (0-1)")
        alternative_explanations: str = dspy.OutputField(desc="Other possible explanations")
        evidence_requirements: str = dspy.OutputField(desc="What evidence would strengthen this explanation")
    
    class ArgumentAnalysis(dspy.Signature):
        """Analyze the structure and validity of arguments"""
        argument_text: str = dspy.InputField(desc="The argument to analyze")
        premises: str = dspy.OutputField(desc="Identified premises")
        conclusion: str = dspy.OutputField(desc="Identified conclusion")
        argument_structure: str = dspy.OutputField(desc="The logical structure of the argument")
        validity_assessment: str = dspy.OutputField(desc="Assessment of logical validity")
        fallacies: str = dspy.OutputField(desc="Any logical fallacies identified")
        strength_score: float = dspy.OutputField(desc="Overall argument strength (0-1)")
        improvement_suggestions: str = dspy.OutputField(desc="How to strengthen the argument")
    
    class ConditionalReasoning(dspy.Signature):
        """Handle if-then reasoning and counterfactuals"""
        conditional_statement: str = dspy.InputField(desc="The if-then statement or counterfactual")
        context: str = dspy.InputField(desc="Relevant context and facts")
        evaluation: str = dspy.OutputField(desc="Evaluation of the conditional")
        reasoning_steps: str = dspy.OutputField(desc="Step-by-step conditional reasoning")
        truth_conditions: str = dspy.OutputField(desc="Conditions under which this would be true/false")
        implications: str = dspy.OutputField(desc="Logical implications and consequences")
        confidence: float = dspy.OutputField(desc="Confidence in the evaluation (0-1)")
    
    class CausalAnalysis(dspy.Signature):
        """Analyze cause-effect relationships"""
        situation: str = dspy.InputField(desc="The situation or phenomenon to analyze")
        context: str = dspy.InputField(desc="Relevant background information")
        causal_chain: str = dspy.OutputField(desc="Identified causal relationships")
        primary_causes: str = dspy.OutputField(desc="Most important causal factors")
        confounding_factors: str = dspy.OutputField(desc="Potential confounding variables")
        evidence_strength: str = dspy.OutputField(desc="Strength of causal evidence")
        alternative_explanations: str = dspy.OutputField(desc="Non-causal alternative explanations")
        confidence: float = dspy.OutputField(desc="Confidence in causal analysis (0-1)")
    
    class RiskAssessment(dspy.Signature):
        """Assess risks and their probabilities"""
        scenario: str = dspy.InputField(desc="The scenario or decision to assess")
        context: str = dspy.InputField(desc="Relevant context and constraints")
        risk_factors: str = dspy.OutputField(desc="Identified risk factors")
        probability_assessment: str = dspy.OutputField(desc="Probability estimates for key risks")
        impact_analysis: str = dspy.OutputField(desc="Potential impact of identified risks")
        mitigation_strategies: str = dspy.OutputField(desc="Risk mitigation approaches")
        overall_risk_level: str = dspy.OutputField(desc="Overall risk assessment")
        confidence: float = dspy.OutputField(desc="Confidence in risk assessment (0-1)")
    
    class Brainstorming(dspy.Signature):
        """Generate creative ideas and solutions"""
        problem: str = dspy.InputField(desc="The problem or challenge to address")
        constraints: str = dspy.InputField(desc="Any constraints or requirements")
        ideas: str = dspy.OutputField(desc="Generated ideas and solutions")
        creative_approaches: str = dspy.OutputField(desc="Unconventional or creative approaches")
        idea_evaluation: str = dspy.OutputField(desc="Brief evaluation of key ideas")
        next_steps: str = dspy.OutputField(desc="Recommended next steps for promising ideas")
        novelty_score: float = dspy.OutputField(desc="Creativity/novelty score (0-1)")
    
    class AnalogyReasoning(dspy.Signature):
        """Find and apply analogies for understanding"""
        source_domain: str = dspy.InputField(desc="The domain or concept to understand")
        context: str = dspy.InputField(desc="Additional context about the problem")
        analogies: str = dspy.OutputField(desc="Relevant analogies from other domains")
        mapping: str = dspy.OutputField(desc="How the analogy maps to the source domain")
        insights: str = dspy.OutputField(desc="Insights gained from the analogy")
        limitations: str = dspy.OutputField(desc="Limitations of the analogy")
        confidence: float = dspy.OutputField(desc="Confidence in the analogy (0-1)")
    
    class Reframing(dspy.Signature):
        """Reframe problems from different perspectives"""
        original_problem: str = dspy.InputField(desc="The original problem statement")
        context: str = dspy.InputField(desc="Current context and constraints")
        alternative_frames: str = dspy.OutputField(desc="Alternative ways to frame the problem")
        new_insights: str = dspy.OutputField(desc="New insights from reframing")
        solution_approaches: str = dspy.OutputField(desc="New solution approaches revealed")
        perspective_value: str = dspy.OutputField(desc="Value of each perspective")
        recommended_frame: str = dspy.OutputField(desc="Most promising reframe")
        confidence: float = dspy.OutputField(desc="Confidence in reframing (0-1)")
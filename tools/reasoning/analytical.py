"""
Analytical reasoning tools using DSPy
"""
import json
import dspy
from typing import ClassVar, Literal, Optional
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseReasoningTool, ReasoningResult, ReasoningSignatures


class CausalAnalysisTool(BaseReasoningTool):
    """Analyze cause-effect relationships"""
    
    name: ClassVar[Literal["causal_analysis"]] = "causal_analysis"
    api_type: ClassVar[Literal["causal_analysis_20241022"]] = "causal_analysis_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.CausalAnalysis
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        causal_steps = []
        if hasattr(raw_result, 'causal_chain'):
            causal_steps = raw_result.causal_chain.split('\n')
        
        primary_causes = []
        if hasattr(raw_result, 'primary_causes'):
            primary_causes = raw_result.primary_causes.split('\n')
        
        alternatives = []
        if hasattr(raw_result, 'alternative_explanations'):
            alternatives = raw_result.alternative_explanations.split('\n')
        
        return ReasoningResult(
            conclusion=f"Primary causes identified: {'; '.join(primary_causes)}",
            reasoning_steps=causal_steps,
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=[raw_result.evidence_strength] if hasattr(raw_result, 'evidence_strength') else [],
            assumptions=[raw_result.confounding_factors] if hasattr(raw_result, 'confounding_factors') else [],
            alternatives=alternatives,
            metadata={
                "reasoning_type": "causal_analysis",
                "confounding_factors": getattr(raw_result, 'confounding_factors', 'unknown'),
                "evidence_strength": getattr(raw_result, 'evidence_strength', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        situation: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute causal analysis"""
        return await self.execute_reasoning(situation=situation, context=context or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class RiskAssessmentTool(BaseReasoningTool):
    """Assess risks and their probabilities"""
    
    name: ClassVar[Literal["risk_assessment"]] = "risk_assessment"
    api_type: ClassVar[Literal["risk_assessment_20241022"]] = "risk_assessment_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return ReasoningSignatures.RiskAssessment
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        risk_factors = []
        if hasattr(raw_result, 'risk_factors'):
            risk_factors = raw_result.risk_factors.split('\n')
        
        mitigation_strategies = []
        if hasattr(raw_result, 'mitigation_strategies'):
            mitigation_strategies = raw_result.mitigation_strategies.split('\n')
        
        reasoning_steps = []
        if hasattr(raw_result, 'probability_assessment'):
            reasoning_steps.append(f"Probability Assessment: {raw_result.probability_assessment}")
        if hasattr(raw_result, 'impact_analysis'):
            reasoning_steps.append(f"Impact Analysis: {raw_result.impact_analysis}")
        
        return ReasoningResult(
            conclusion=raw_result.overall_risk_level if hasattr(raw_result, 'overall_risk_level') else "Risk level unknown",
            reasoning_steps=reasoning_steps,
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=risk_factors,
            assumptions=[],
            alternatives=mitigation_strategies,
            metadata={
                "reasoning_type": "risk_assessment",
                "probability_assessment": getattr(raw_result, 'probability_assessment', 'unknown'),
                "impact_analysis": getattr(raw_result, 'impact_analysis', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        scenario: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute risk assessment"""
        return await self.execute_reasoning(scenario=scenario, context=context or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }


class TrendAnalysisTool(BaseReasoningTool):
    """Analyze patterns and trends for forecasting"""
    
    name: ClassVar[Literal["trend_analysis"]] = "trend_analysis"
    api_type: ClassVar[Literal["trend_analysis_20241022"]] = "trend_analysis_20241022"
    
    def get_reasoning_signature(self) -> dspy.Signature:
        # Create a custom signature for trend analysis
        class TrendAnalysisSignature(dspy.Signature):
            """Analyze trends and patterns in data"""
            data_description: str = dspy.InputField(desc="Description of the data or observations")
            context: str = dspy.InputField(desc="Context and timeframe for analysis")
            identified_trends: str = dspy.OutputField(desc="Key trends and patterns identified")
            trend_strength: str = dspy.OutputField(desc="Assessment of trend strength and consistency")
            future_projection: str = dspy.OutputField(desc="Projection of future trends")
            confidence: float = dspy.OutputField(desc="Confidence in trend analysis (0-1)")
            influencing_factors: str = dspy.OutputField(desc="Factors that may influence future trends")
            uncertainty_factors: str = dspy.OutputField(desc="Sources of uncertainty in projections")
        
        return TrendAnalysisSignature
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        trends = []
        if hasattr(raw_result, 'identified_trends'):
            trends = raw_result.identified_trends.split('\n')
        
        factors = []
        if hasattr(raw_result, 'influencing_factors'):
            factors = raw_result.influencing_factors.split('\n')
        
        uncertainties = []
        if hasattr(raw_result, 'uncertainty_factors'):
            uncertainties = raw_result.uncertainty_factors.split('\n')
        
        reasoning_steps = []
        if hasattr(raw_result, 'trend_strength'):
            reasoning_steps.append(f"Trend Strength: {raw_result.trend_strength}")
        if hasattr(raw_result, 'future_projection'):
            reasoning_steps.append(f"Future Projection: {raw_result.future_projection}")
        
        return ReasoningResult(
            conclusion=raw_result.future_projection if hasattr(raw_result, 'future_projection') else "No clear projection available",
            reasoning_steps=reasoning_steps,
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=trends,
            assumptions=factors,
            alternatives=uncertainties,
            metadata={
                "reasoning_type": "trend_analysis",
                "trend_strength": getattr(raw_result, 'trend_strength', 'unknown'),
                "influencing_factors": getattr(raw_result, 'influencing_factors', 'unknown')
            }
        )
    
    async def __call__(
        self,
        *,
        data_description: str,
        context: Optional[str] = "",
        **kwargs
    ) -> ReasoningResult:
        """Execute trend analysis"""
        return await self.execute_reasoning(data_description=data_description, context=context or "")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }
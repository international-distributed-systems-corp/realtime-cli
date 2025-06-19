"""
Reasoning tool orchestrator using DSPy for complex multi-step reasoning
"""
import json
import dspy
from typing import ClassVar, Literal, Optional, List, Dict, Any
from anthropic.types.beta import BetaToolUnionParam

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


class ReasoningOrchestrator(BaseReasoningTool):
    """Orchestrate multiple reasoning tools for complex problem solving"""
    
    name: ClassVar[Literal["reasoning_orchestrator"]] = "reasoning_orchestrator"
    api_type: ClassVar[Literal["reasoning_orchestrator_20241022"]] = "reasoning_orchestrator_20241022"
    
    def __init__(self):
        super().__init__()
        
        # Initialize all available reasoning tools
        self.reasoning_tools = {
            "deductive": DeductiveReasoningTool(),
            "inductive": InductiveReasoningTool(),
            "abductive": AbductiveReasoningTool(),
            "argument_analysis": ArgumentAnalysisTool(),
            "conditional": ConditionalReasoningTool(),
            "causal_analysis": CausalAnalysisTool(),
            "risk_assessment": RiskAssessmentTool(),
            "trend_analysis": TrendAnalysisTool(),
            "brainstorming": BrainstormingTool(),
            "analogy": AnalogyReasoningTool(),
            "reframing": ReframingTool()
        }
        
        # Create orchestration signature
        class OrchestrationSignature(dspy.Signature):
            """Determine the best reasoning approach for a complex problem"""
            problem_description: str = dspy.InputField(desc="The complex problem to solve")
            context: str = dspy.InputField(desc="Additional context and constraints")
            reasoning_strategy: str = dspy.OutputField(desc="Recommended sequence of reasoning tools")
            reasoning_justification: str = dspy.OutputField(desc="Why this strategy is optimal")
            expected_insights: str = dspy.OutputField(desc="What insights each step should provide")
            confidence: float = dspy.OutputField(desc="Confidence in the strategy (0-1)")
        
        self.orchestration_signature = OrchestrationSignature
    
    def get_reasoning_signature(self) -> dspy.Signature:
        return self.orchestration_signature
    
    def process_reasoning_result(self, raw_result) -> ReasoningResult:
        strategy_steps = []
        if hasattr(raw_result, 'reasoning_strategy'):
            strategy_steps = raw_result.reasoning_strategy.split('\n')
        
        expected_insights = []
        if hasattr(raw_result, 'expected_insights'):
            expected_insights = raw_result.expected_insights.split('\n')
        
        return ReasoningResult(
            conclusion=raw_result.reasoning_strategy if hasattr(raw_result, 'reasoning_strategy') else "Strategy determined",
            reasoning_steps=[raw_result.reasoning_justification] if hasattr(raw_result, 'reasoning_justification') else [],
            confidence=float(raw_result.confidence) if hasattr(raw_result, 'confidence') else 0.5,
            evidence=strategy_steps,
            assumptions=expected_insights,
            alternatives=[],
            metadata={
                "reasoning_type": "orchestration",
                "strategy": getattr(raw_result, 'reasoning_strategy', 'unknown'),
                "justification": getattr(raw_result, 'reasoning_justification', 'unknown')
            }
        )
    
    async def execute_multi_step_reasoning(
        self,
        problem_description: str,
        context: str = "",
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """Execute a multi-step reasoning process"""
        
        # Step 1: Determine reasoning strategy
        strategy_result = await self.execute_reasoning(
            problem_description=problem_description,
            context=context
        )
        
        results = {
            "strategy": strategy_result,
            "steps": [],
            "final_synthesis": None
        }
        
        if not auto_execute:
            return results
        
        # Step 2: Parse and execute the strategy
        try:
            strategy_text = strategy_result.conclusion
            steps = self._parse_strategy(strategy_text)
            
            for i, step in enumerate(steps):
                tool_name = step.get("tool")
                parameters = step.get("parameters", {})
                
                if tool_name in self.reasoning_tools:
                    tool = self.reasoning_tools[tool_name]
                    step_result = await tool(**parameters)
                    
                    results["steps"].append({
                        "step_number": i + 1,
                        "tool": tool_name,
                        "parameters": parameters,
                        "result": step_result
                    })
                else:
                    results["steps"].append({
                        "step_number": i + 1,
                        "tool": tool_name,
                        "error": f"Unknown tool: {tool_name}"
                    })
            
            # Step 3: Synthesize results
            synthesis = await self._synthesize_results(results["steps"], problem_description)
            results["final_synthesis"] = synthesis
            
        except Exception as e:
            results["error"] = f"Execution failed: {str(e)}"
        
        return results
    
    def _parse_strategy(self, strategy_text: str) -> List[Dict[str, Any]]:
        """Parse strategy text into executable steps"""
        steps = []
        lines = strategy_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Simple parsing - look for tool names
            for tool_name in self.reasoning_tools.keys():
                if tool_name.replace('_', ' ') in line.lower():
                    # Extract parameters (basic implementation)
                    parameters = self._extract_parameters(line, tool_name)
                    steps.append({
                        "tool": tool_name,
                        "parameters": parameters
                    })
                    break
        
        return steps
    
    def _extract_parameters(self, line: str, tool_name: str) -> Dict[str, str]:
        """Extract parameters from strategy line (basic implementation)"""
        # This is a simplified parameter extraction
        # In a full implementation, you'd use more sophisticated NLP
        parameters = {}
        
        # Map common parameter patterns
        param_mapping = {
            "deductive": {"premises": "premises", "query": "query"},
            "inductive": {"observations": "observations", "context": "context"},
            "abductive": {"observations": "observations", "context": "context"},
            "argument_analysis": {"argument_text": "argument"},
            "conditional": {"conditional_statement": "statement", "context": "context"},
            "causal_analysis": {"situation": "situation", "context": "context"},
            "risk_assessment": {"scenario": "scenario", "context": "context"},
            "trend_analysis": {"data_description": "data", "context": "context"},
            "brainstorming": {"problem": "problem", "constraints": "constraints"},
            "analogy": {"source_domain": "domain", "context": "context"},
            "reframing": {"original_problem": "problem", "context": "context"}
        }
        
        # Use original problem as default for most tools
        if tool_name in param_mapping:
            for param, keyword in param_mapping[tool_name].items():
                if keyword in line.lower():
                    # Extract text after keyword (simplified)
                    start = line.lower().find(keyword)
                    if start != -1:
                        parameters[param] = line[start + len(keyword):].strip()
        
        return parameters
    
    async def _synthesize_results(
        self, 
        steps: List[Dict[str, Any]], 
        original_problem: str
    ) -> ReasoningResult:
        """Synthesize results from multiple reasoning steps"""
        
        class SynthesisSignature(dspy.Signature):
            """Synthesize insights from multiple reasoning steps"""
            original_problem: str = dspy.InputField(desc="The original problem")
            reasoning_steps: str = dspy.InputField(desc="Results from reasoning steps")
            synthesis: str = dspy.OutputField(desc="Integrated synthesis of all insights")
            key_insights: str = dspy.OutputField(desc="Most important insights discovered")
            confidence: float = dspy.OutputField(desc="Overall confidence in synthesis (0-1)")
            recommendations: str = dspy.OutputField(desc="Recommended actions or conclusions")
        
        # Prepare input for synthesis
        steps_summary = []
        for step in steps:
            if "result" in step:
                result = step["result"]
                steps_summary.append(f"Step {step['step_number']} ({step['tool']}): {result.conclusion}")
        
        steps_text = "\n".join(steps_summary)
        
        # Execute synthesis
        predictor = dspy.Predict(SynthesisSignature)
        synthesis_result = predictor(
            original_problem=original_problem,
            reasoning_steps=steps_text
        )
        
        # Convert to ReasoningResult
        key_insights = []
        if hasattr(synthesis_result, 'key_insights'):
            key_insights = synthesis_result.key_insights.split('\n')
        
        recommendations = []
        if hasattr(synthesis_result, 'recommendations'):
            recommendations = synthesis_result.recommendations.split('\n')
        
        return ReasoningResult(
            conclusion=synthesis_result.synthesis,
            reasoning_steps=[f"Synthesized from {len(steps)} reasoning steps"],
            confidence=float(synthesis_result.confidence) if hasattr(synthesis_result, 'confidence') else 0.5,
            evidence=key_insights,
            assumptions=[],
            alternatives=recommendations,
            metadata={
                "reasoning_type": "synthesis",
                "steps_count": len(steps),
                "tools_used": [step.get("tool", "unknown") for step in steps]
            }
        )
    
    async def __call__(
        self,
        *,
        problem_description: str,
        context: Optional[str] = "",
        mode: Literal["strategy_only", "full_execution"] = "full_execution",
        **kwargs
    ) -> ReasoningResult:
        """Execute orchestrated reasoning"""
        
        if mode == "strategy_only":
            return await self.execute_reasoning(
                problem_description=problem_description,
                context=context or ""
            )
        else:
            # Full execution mode
            multi_step_results = await self.execute_multi_step_reasoning(
                problem_description=problem_description,
                context=context or "",
                auto_execute=True
            )
            
            if "final_synthesis" in multi_step_results and multi_step_results["final_synthesis"]:
                return multi_step_results["final_synthesis"]
            else:
                # Return strategy if synthesis failed
                return multi_step_results.get("strategy", ReasoningResult(
                    conclusion="Orchestration failed",
                    reasoning_steps=[],
                    confidence=0.0,
                    evidence=[],
                    assumptions=[],
                    alternatives=[],
                    metadata={"error": "Execution failed"}
                ))
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }
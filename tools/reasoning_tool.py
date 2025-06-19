"""
Main reasoning tool that integrates DSPy reasoning capabilities
"""
import json
from typing import ClassVar, Literal, Optional
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult
from .reasoning import (
    DeductiveReasoningTool,
    InductiveReasoningTool,
    AbductiveReasoningTool,
    ArgumentAnalysisTool,
    ConditionalReasoningTool,
    CausalAnalysisTool,
    RiskAssessmentTool,
    TrendAnalysisTool,
    BrainstormingTool,
    AnalogyReasoningTool,
    ReframingTool,
    ReasoningOrchestrator
)


class ReasoningTool(BaseAnthropicTool):
    """
    Advanced reasoning tool powered by DSPy and GPT-4.1
    Provides logical, analytical, and creative reasoning capabilities
    """
    
    name: ClassVar[Literal["reasoning"]] = "reasoning"
    api_type: ClassVar[Literal["reasoning_20241022"]] = "reasoning_20241022"
    
    def __init__(self):
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
            "reframing": ReframingTool(),
            "orchestrate": ReasoningOrchestrator()
        }
        super().__init__()
    
    async def __call__(
        self,
        *,
        reasoning_type: Literal[
            "deductive",
            "inductive", 
            "abductive",
            "argument_analysis",
            "conditional",
            "causal_analysis",
            "risk_assessment",
            "trend_analysis",
            "brainstorming",
            "analogy",
            "reframing",
            "orchestrate"
        ],
        **kwargs
    ) -> ToolResult:
        """Execute advanced reasoning operations"""
        
        try:
            if reasoning_type not in self.reasoning_tools:
                return ToolResult(output="", error=f"Unknown reasoning type: {reasoning_type}")
            
            tool = self.reasoning_tools[reasoning_type]
            
            # Execute the reasoning tool
            if reasoning_type == "deductive":
                premises = kwargs.get("premises", "")
                query = kwargs.get("query", "")
                if not premises or not query:
                    return ToolResult(output="", error="Deductive reasoning requires 'premises' and 'query' parameters")
                result = await tool(premises=premises, query=query)
                
            elif reasoning_type == "inductive":
                observations = kwargs.get("observations", "")
                context = kwargs.get("context", "")
                if not observations:
                    return ToolResult(output="", error="Inductive reasoning requires 'observations' parameter")
                result = await tool(observations=observations, context=context)
                
            elif reasoning_type == "abductive":
                observations = kwargs.get("observations", "")
                context = kwargs.get("context", "")
                if not observations:
                    return ToolResult(output="", error="Abductive reasoning requires 'observations' parameter")
                result = await tool(observations=observations, context=context)
                
            elif reasoning_type == "argument_analysis":
                argument_text = kwargs.get("argument_text", "")
                if not argument_text:
                    return ToolResult(output="", error="Argument analysis requires 'argument_text' parameter")
                result = await tool(argument_text=argument_text)
                
            elif reasoning_type == "conditional":
                conditional_statement = kwargs.get("conditional_statement", "")
                context = kwargs.get("context", "")
                if not conditional_statement:
                    return ToolResult(output="", error="Conditional reasoning requires 'conditional_statement' parameter")
                result = await tool(conditional_statement=conditional_statement, context=context)
                
            elif reasoning_type == "causal_analysis":
                situation = kwargs.get("situation", "")
                context = kwargs.get("context", "")
                if not situation:
                    return ToolResult(output="", error="Causal analysis requires 'situation' parameter")
                result = await tool(situation=situation, context=context)
                
            elif reasoning_type == "risk_assessment":
                scenario = kwargs.get("scenario", "")
                context = kwargs.get("context", "")
                if not scenario:
                    return ToolResult(output="", error="Risk assessment requires 'scenario' parameter")
                result = await tool(scenario=scenario, context=context)
                
            elif reasoning_type == "trend_analysis":
                data_description = kwargs.get("data_description", "")
                context = kwargs.get("context", "")
                if not data_description:
                    return ToolResult(output="", error="Trend analysis requires 'data_description' parameter")
                result = await tool(data_description=data_description, context=context)
                
            elif reasoning_type == "brainstorming":
                problem = kwargs.get("problem", "")
                constraints = kwargs.get("constraints", "")
                if not problem:
                    return ToolResult(output="", error="Brainstorming requires 'problem' parameter")
                result = await tool(problem=problem, constraints=constraints)
                
            elif reasoning_type == "analogy":
                source_domain = kwargs.get("source_domain", "")
                context = kwargs.get("context", "")
                if not source_domain:
                    return ToolResult(output="", error="Analogy reasoning requires 'source_domain' parameter")
                result = await tool(source_domain=source_domain, context=context)
                
            elif reasoning_type == "reframing":
                original_problem = kwargs.get("original_problem", "")
                context = kwargs.get("context", "")
                if not original_problem:
                    return ToolResult(output="", error="Reframing requires 'original_problem' parameter")
                result = await tool(original_problem=original_problem, context=context)
                
            elif reasoning_type == "orchestrate":
                problem_description = kwargs.get("problem_description", "")
                context = kwargs.get("context", "")
                mode = kwargs.get("mode", "full_execution")
                if not problem_description:
                    return ToolResult(output="", error="Orchestration requires 'problem_description' parameter")
                result = await tool(
                    problem_description=problem_description, 
                    context=context, 
                    mode=mode
                )
            
            else:
                return ToolResult(output="", error=f"Unhandled reasoning type: {reasoning_type}")
            
            # Convert ReasoningResult to ToolResult
            return result.to_tool_result()
            
        except Exception as e:
            return ToolResult(output="", error=f"Reasoning operation failed: {str(e)}")
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }
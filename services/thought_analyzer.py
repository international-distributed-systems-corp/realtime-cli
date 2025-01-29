import openai
from typing import List, Dict, Any, Optional
from models.thought_process import ChainOfThought, ThoughtStep, Metadata, ThoughtCategory
import logging
import json
from models.pricing import ModelType

logger = logging.getLogger(__name__)

class ThoughtAnalyzer:
    """Analyzes user queries using chain of thought reasoning"""
    
    def __init__(self):
        import os
        self.api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = self.api_key
        
    async def analyze_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> ChainOfThought:
        """Analyze a user query using chain of thought reasoning"""
        
        system_prompt = """
        You are an expert AI system analyzer. Break down user queries into clear reasoning steps.
        For each step:
        1. Provide detailed reasoning
        2. Draw a specific conclusion
        3. Assign a confidence level (0-1)
        4. Categorize the thought type
        5. Identify if specific tools are needed
        
        Consider:
        - Query complexity and requirements
        - Whether realtime interaction is necessary
        - Appropriate models for the task
        - Required tools or external resources
        
        Structure your response as a formal chain of thought analysis.
        """
        
        # Include context in prompt if provided
        user_prompt = query
        if context:
            user_prompt = f"Context:\n{json.dumps(context)}\n\nQuery:\n{query}"
        
        try:
            response = await openai.AsyncOpenAI().beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format=ChainOfThought
            )
            
            # Parse the response into structured format
            content = response.choices[0].message.parsed
            print(json.dumps(content.dict(), indent=2))
            return content
            
        except Exception as e:
            logger.error(f"Error analyzing query: {str(e)}")
            raise
        
    def _calculate_complexity(self, steps: List[ThoughtStep]) -> int:
        """Calculate overall complexity score"""
        if not steps:
            return 1
            
        factors = {
            "num_steps": len(steps),
            "avg_confidence": sum(s.confidence for s in steps) / len(steps),
            "tool_requirements": sum(1 for s in steps if s.requires_tools),
            "technical_steps": sum(1 for s in steps if s.category == ThoughtCategory.TECHNICAL)
        }
        
        # Weight and combine factors
        complexity = (
            factors["num_steps"] * 0.3 +
            (1 - factors["avg_confidence"]) * 0.3 +
            factors["tool_requirements"] * 0.2 +
            factors["technical_steps"] * 0.2
        )
        
        # Scale to 1-10 range
        return max(1, min(10, int(complexity * 2 + 1)))
        
    def _requires_realtime(self, steps: List[ThoughtStep]) -> bool:
        """Determine if realtime interaction is needed"""
        if not steps:
            return True
            
        # Check for indicators that realtime is needed
        realtime_indicators = {
            "interactive": False,
            "continuous": False,
            "streaming": False,
            "audio": False
        }
        
        for step in steps:
            lower_reasoning = step.reasoning.lower()
            if "interact" in lower_reasoning or "conversation" in lower_reasoning:
                realtime_indicators["interactive"] = True
            if "continuous" in lower_reasoning or "ongoing" in lower_reasoning:
                realtime_indicators["continuous"] = True
            if "stream" in lower_reasoning or "real-time" in lower_reasoning:
                realtime_indicators["streaming"] = True
            if "audio" in lower_reasoning or "voice" in lower_reasoning:
                realtime_indicators["audio"] = True
                
        # If any two indicators are True, suggest realtime
        return sum(realtime_indicators.values()) >= 2
        
    def _suggest_models(self, thought: ChainOfThought) -> List[str]:
        """Suggest appropriate models based on analysis"""
        models = []
        
        # Add base model based on complexity
        if thought.estimated_complexity >= 7:
            models.append(ModelType.GPT4O_REALTIME.value)
        else:
            models.append(ModelType.GPT4O_MINI_REALTIME.value)
            
        # Add audio model if needed
        has_audio = any(
            step.category == ThoughtCategory.TECHNICAL and
            ("audio" in step.reasoning.lower() or "voice" in step.reasoning.lower())
            for step in thought.steps
        )
        
        if has_audio:
            models.append(ModelType.GPT4O_REALTIME.value)
            
        return list(set(models))  # Remove duplicates

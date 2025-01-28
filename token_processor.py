from typing import Callable, Dict, List, Optional, Pattern, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import logging
import asyncio
from collections import defaultdict
from queue import PriorityQueue
import json

logger = logging.getLogger(__name__)

class TriggerState(Enum):
    """Possible states for a trigger"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    PENDING = "pending"
    EXECUTING = "executing"
    FAILED = "failed"

class TriggerType(Enum):
    """Types of triggers"""
    PATTERN = "pattern"
    CONDITIONAL = "conditional"
    COMPOSITE = "composite"
    CHAIN = "chain"

@dataclass
class TriggerContext:
    """Context information for trigger execution"""
    window_before: List[str] = field(default_factory=list)
    window_after: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    matched_text: Optional[str] = None
    chain_results: List[Any] = field(default_factory=list)

@dataclass
class TokenTrigger:
    """Advanced token sequence trigger with context and conditions"""
    pattern: Pattern
    handler: Callable
    description: str
    trigger_type: TriggerType = TriggerType.PATTERN
    priority: int = 0
    state: TriggerState = TriggerState.ENABLED
    context_window: int = 5  # Number of tokens before/after to include
    conditions: List[Callable[[TriggerContext], bool]] = field(default_factory=list)
    chain: List['TokenTrigger'] = field(default_factory=list)
    filters: List[Callable[[str], bool]] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[float] = None
    retry_count: int = 0
    dependencies: Set[str] = field(default_factory=set)

class TokenProcessor:
    """Advanced processor for token sequences with context and state management"""
    
    def __init__(self):
        self.triggers: Dict[str, TokenTrigger] = {}
        self._buffer: List[str] = []
        self._context_buffer: List[str] = []
        self.max_buffer_size = 1000
        self.max_context_size = 100
        self._priority_queue = PriorityQueue()
        self._state: Dict[str, Any] = {}
        self._trigger_history: List[Dict[str, Any]] = []
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._composite_triggers: Dict[str, List[str]] = {}
        
    def register_trigger(self, 
                        pattern: str,
                        handler: Callable,
                        description: str,
                        trigger_type: TriggerType = TriggerType.PATTERN,
                        priority: int = 0,
                        context_window: int = 5,
                        conditions: Optional[List[Callable[[TriggerContext], bool]]] = None,
                        chain: Optional[List[TokenTrigger]] = None,
                        filters: Optional[List[Callable[[str], bool]]] = None,
                        variables: Optional[Dict[str, Any]] = None,
                        timeout: Optional[float] = None,
                        retry_count: int = 0,
                        dependencies: Optional[Set[str]] = None) -> str:
        """Register an advanced token trigger"""
        try:
            compiled_pattern = re.compile(pattern)
            trigger_id = f"trigger_{len(self.triggers)}"
            
            # Create trigger with advanced features
            trigger = TokenTrigger(
                pattern=compiled_pattern,
                handler=handler,
                description=description,
                trigger_type=trigger_type,
                priority=priority,
                context_window=context_window,
                conditions=conditions or [],
                chain=chain or [],
                filters=filters or [],
                variables=variables or {},
                timeout=timeout,
                retry_count=retry_count,
                dependencies=dependencies or set()
            )
            
            # Update dependency graph
            for dep in trigger.dependencies:
                self._dependency_graph[dep].add(trigger_id)
            
            # Store trigger
            self.triggers[trigger_id] = trigger
            self._priority_queue.put((-priority, trigger_id))
            
            logger.info(f"Registered {trigger_type.value} trigger: {description}")
            return trigger_id
            
        except re.error as e:
            logger.error(f"Invalid trigger pattern '{pattern}': {e}")
            raise ValueError(f"Invalid trigger pattern: {e}")
            
    async def process_tokens(self, tokens: List[str]) -> None:
        """Process tokens with advanced features and context"""
        # Update buffers
        self._buffer.extend(tokens)
        self._context_buffer.extend(tokens)
        
        # Trim buffers
        if len(self._buffer) > self.max_buffer_size:
            self._buffer = self._buffer[-self.max_buffer_size:]
        if len(self._context_buffer) > self.max_context_size:
            self._context_buffer = self._context_buffer[-self.max_context_size:]
            
        buffer_text = " ".join(self._buffer)
        
        # Process triggers in priority order
        while not self._priority_queue.empty():
            _, trigger_id = self._priority_queue.get()
            trigger = self.triggers[trigger_id]
            
            if trigger.state != TriggerState.ENABLED:
                continue
                
            # Check dependencies
            if not self._check_dependencies(trigger_id):
                continue
                
            try:
                if match := trigger.pattern.search(buffer_text):
                    # Create context
                    ctx = self._create_context(match, trigger)
                    
                    # Apply filters
                    if not all(f(ctx.matched_text) for f in trigger.filters):
                        continue
                        
                    # Check conditions
                    if not all(c(ctx) for c in trigger.conditions):
                        continue
                    
                    # Execute handler with timeout if specified
                    trigger.state = TriggerState.EXECUTING
                    try:
                        if trigger.timeout:
                            result = await asyncio.wait_for(
                                self._execute_handler(trigger, ctx),
                                timeout=trigger.timeout
                            )
                        else:
                            result = await self._execute_handler(trigger, ctx)
                            
                        # Handle chaining
                        if trigger.chain:
                            await self._execute_chain(trigger.chain, ctx, result)
                            
                        # Update state and history
                        self._state[trigger_id] = result
                        self._trigger_history.append({
                            "trigger_id": trigger_id,
                            "matched_text": ctx.matched_text,
                            "result": result,
                            "timestamp": asyncio.get_event_loop().time()
                        })
                        
                        trigger.state = TriggerState.ENABLED
                        logger.debug(f"Triggered handler for: {ctx.matched_text}")
                        
                    except asyncio.TimeoutError:
                        trigger.state = TriggerState.FAILED
                        if trigger.retry_count > 0:
                            trigger.retry_count -= 1
                            self._priority_queue.put((-trigger.priority, trigger_id))
                        logger.error(f"Trigger {trigger_id} timed out")
                        
                    except Exception as e:
                        trigger.state = TriggerState.FAILED
                        logger.error(f"Error in trigger handler: {e}")
                    
                    # Update buffer
                    token_count = len(ctx.matched_text.split())
                    self._buffer = self._buffer[token_count:]
                    
            except Exception as e:
                logger.error(f"Error processing trigger: {e}")
                
    def clear_buffer(self) -> None:
        """Clear the token buffer"""
        self._buffer.clear()
        
    def disable_trigger(self, trigger_id: str) -> None:
        """Disable a specific trigger"""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = False
            
    def enable_trigger(self, trigger_id: str) -> None:
        """Enable a specific trigger"""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = True
            
    def remove_trigger(self, trigger_id: str) -> None:
        """Remove a registered trigger"""
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
    def _check_dependencies(self, trigger_id: str) -> bool:
        """Check if all dependencies are satisfied"""
        for dep in self.triggers[trigger_id].dependencies:
            if dep not in self._state:
                return False
        return True
        
    def _create_context(self, match: re.Match, trigger: TokenTrigger) -> TriggerContext:
        """Create context for trigger execution"""
        matched_text = match.group(0)
        start_idx = len(" ".join(self._buffer[:match.start()]).split())
        
        # Get context windows
        window_before = self._context_buffer[max(0, start_idx - trigger.context_window):start_idx]
        window_after = self._context_buffer[start_idx + len(matched_text.split()):
                                          start_idx + len(matched_text.split()) + trigger.context_window]
        
        return TriggerContext(
            window_before=window_before,
            window_after=window_after,
            variables=trigger.variables.copy(),
            matched_text=matched_text
        )
        
    async def _execute_handler(self, trigger: TokenTrigger, ctx: TriggerContext) -> Any:
        """Execute trigger handler with context"""
        if asyncio.iscoroutinefunction(trigger.handler):
            return await trigger.handler(ctx)
        return trigger.handler(ctx)
        
    async def _execute_chain(self, chain: List[TokenTrigger], ctx: TriggerContext, result: Any) -> None:
        """Execute a chain of triggers"""
        ctx.chain_results.append(result)
        for next_trigger in chain:
            if next_trigger.state == TriggerState.ENABLED:
                try:
                    result = await self._execute_handler(next_trigger, ctx)
                    ctx.chain_results.append(result)
                except Exception as e:
                    logger.error(f"Error in chain execution: {e}")
                    break
                    
    def create_composite_trigger(self, trigger_ids: List[str], name: str) -> str:
        """Create a composite trigger from multiple triggers"""
        if not all(tid in self.triggers for tid in trigger_ids):
            raise ValueError("All trigger IDs must exist")
            
        composite_id = f"composite_{name}"
        self._composite_triggers[composite_id] = trigger_ids
        return composite_id
        
    def get_trigger_state(self, trigger_id: str) -> Dict[str, Any]:
        """Get the current state of a trigger"""
        if trigger_id in self.triggers:
            trigger = self.triggers[trigger_id]
            return {
                "state": trigger.state.value,
                "variables": trigger.variables,
                "retry_count": trigger.retry_count,
                "last_result": self._state.get(trigger_id)
            }
        elif trigger_id in self._composite_triggers:
            return {
                "type": "composite",
                "triggers": [self.get_trigger_state(tid) 
                           for tid in self._composite_triggers[trigger_id]]
            }
        raise ValueError(f"Unknown trigger ID: {trigger_id}")
        
    def get_trigger_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get trigger execution history"""
        history = self._trigger_history
        if limit:
            history = history[-limit:]
        return history
        
    def export_trigger_config(self, trigger_id: str) -> Dict[str, Any]:
        """Export trigger configuration"""
        if trigger_id not in self.triggers:
            raise ValueError(f"Unknown trigger ID: {trigger_id}")
            
        trigger = self.triggers[trigger_id]
        return {
            "pattern": trigger.pattern.pattern,
            "description": trigger.description,
            "trigger_type": trigger.trigger_type.value,
            "priority": trigger.priority,
            "context_window": trigger.context_window,
            "timeout": trigger.timeout,
            "retry_count": trigger.retry_count,
            "dependencies": list(trigger.dependencies),
            "variables": trigger.variables
        }
        
    def import_trigger_config(self, config: Dict[str, Any]) -> str:
        """Import trigger configuration"""
        return self.register_trigger(
            pattern=config["pattern"],
            handler=lambda ctx: None,  # Placeholder handler
            description=config["description"],
            trigger_type=TriggerType(config["trigger_type"]),
            priority=config["priority"],
            context_window=config["context_window"],
            timeout=config.get("timeout"),
            retry_count=config.get("retry_count", 0),
            dependencies=set(config.get("dependencies", [])),
            variables=config.get("variables", {})
        )

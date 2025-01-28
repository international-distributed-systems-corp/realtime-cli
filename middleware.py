from typing import Dict, Any, List, Optional, Callable
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

class MiddlewareType(Enum):
    PRE_PROCESS = "pre_process"
    POST_PROCESS = "post_process"
    ERROR_HANDLER = "error_handler"
    RATE_LIMITER = "rate_limiter"
    CACHE = "cache"
    METRICS = "metrics"
    VALIDATOR = "validator"

@dataclass
class MiddlewareContext:
    """Context passed through middleware chain"""
    request_id: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    cache_hits: int = 0
    errors: List[Exception] = field(default_factory=list)
    
class MiddlewareManager:
    """Manages middleware execution chains"""
    
    def __init__(self):
        self.middlewares: Dict[MiddlewareType, List[Callable]] = defaultdict(list)
        self.metrics: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._cache: Dict[str, Any] = {}
        
    async def execute_chain(self, 
                          mtype: MiddlewareType,
                          data: Any,
                          context: MiddlewareContext) -> Any:
        """Execute a middleware chain"""
        try:
            result = data
            start_time = time.time()
            
            for middleware in self.middlewares[mtype]:
                try:
                    result = await middleware(result, context)
                except Exception as e:
                    logger.error(f"Middleware error: {str(e)}")
                    context.errors.append(e)
                    if mtype == MiddlewareType.ERROR_HANDLER:
                        raise  # Don't catch errors in error handlers
                    
            # Record metrics
            duration = time.time() - start_time
            self.metrics[mtype.value]["total_time"] = duration
            self.metrics[mtype.value]["count"] = \
                self.metrics[mtype.value].get("count", 0) + 1
            
            return result
            
        except Exception as e:
            if mtype != MiddlewareType.ERROR_HANDLER:
                # Try error handlers
                try:
                    return await self.execute_chain(
                        MiddlewareType.ERROR_HANDLER,
                        e,
                        context
                    )
                except Exception as handler_error:
                    logger.critical(
                        f"Error handler failed: {str(handler_error)}"
                    )
            raise

    def add_middleware(self,
                      mtype: MiddlewareType,
                      middleware: Callable) -> None:
        """Add a middleware to a chain"""
        self.middlewares[mtype].append(middleware)
        
    def get_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get middleware performance metrics"""
        return self.metrics
        
    def clear_metrics(self) -> None:
        """Clear collected metrics"""
        self.metrics.clear()
        
    def cache_get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        return self._cache.get(key)
        
    def cache_set(self, key: str, value: Any) -> None:
        """Set cache item"""
        self._cache[key] = value
        
    def cache_clear(self) -> None:
        """Clear the cache"""
        self._cache.clear()

# Example middleware implementations
async def timing_middleware(data: Any, context: MiddlewareContext) -> Any:
    """Record timing metrics"""
    start = time.time()
    result = data
    duration = time.time() - start
    context.metrics["processing_time"] = duration
    return result
    
async def validation_middleware(data: Any, context: MiddlewareContext) -> Any:
    """Validate data"""
    if not data:
        raise ValueError("Empty data")
    return data
    
async def caching_middleware(data: Any, context: MiddlewareContext) -> Any:
    """Cache results"""
    cache_key = str(data)
    cached = context.metadata.get("middleware_manager").cache_get(cache_key)
    if cached:
        context.cache_hits += 1
        return cached
    return data
    
async def error_handling_middleware(error: Exception,
                                  context: MiddlewareContext) -> Any:
    """Handle errors"""
    logger.error(f"Error in middleware chain: {str(error)}")
    return {"error": str(error), "context": context}

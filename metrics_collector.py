from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import time
import json
import asyncio
from collections import deque
import numpy as np
import logging

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """System performance metrics"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    latency_ms: float = 0.0
    throughput: float = 0.0
    error_rate: float = 0.0
    
@dataclass
class TokenMetrics:
    """Token processing metrics"""
    tokens_processed: int = 0
    tokens_per_second: float = 0.0
    average_token_length: float = 0.0
    pattern_match_time_ms: float = 0.0
    trigger_execution_time_ms: float = 0.0

@dataclass
class SystemMetrics:
    """Overall system metrics"""
    uptime_seconds: float = 0.0
    total_requests: int = 0
    active_connections: int = 0
    queue_depth: int = 0
    cache_hit_ratio: float = 0.0

class MetricsCollector:
    """Collects and analyzes system metrics"""
    
    def __init__(self, window_size: int = 100):
        self.start_time = time.time()
        self.performance = PerformanceMetrics()
        self.tokens = TokenMetrics()
        self.system = SystemMetrics()
        
        # Rolling windows for analysis
        self.latency_window = deque(maxlen=window_size)
        self.throughput_window = deque(maxlen=window_size)
        self.error_window = deque(maxlen=window_size)
        
        # Async collection task
        self.collection_task: Optional[asyncio.Task] = None
        
    async def start_collection(self, interval: float = 1.0):
        """Start async metrics collection"""
        async def collect_metrics():
            while True:
                try:
                    await self._collect_current_metrics()
                    await asyncio.sleep(interval)
                except Exception as e:
                    logger.error(f"Metrics collection error: {str(e)}")
                    
        self.collection_task = asyncio.create_task(collect_metrics())
        
    def stop_collection(self):
        """Stop metrics collection"""
        if self.collection_task:
            self.collection_task.cancel()
            
    async def _collect_current_metrics(self):
        """Collect current system metrics"""
        # Update rolling windows
        self.latency_window.append(self.performance.latency_ms)
        self.throughput_window.append(self.tokens.tokens_per_second)
        
        # Calculate derived metrics
        if self.latency_window:
            self.performance.latency_ms = np.mean(self.latency_window)
        if self.throughput_window:
            self.tokens.tokens_per_second = np.mean(self.throughput_window)
            
        # Update system metrics
        self.system.uptime_seconds = time.time() - self.start_time
        
    def record_token_processed(self, token: str, 
                             pattern_time: float,
                             trigger_time: float):
        """Record token processing metrics"""
        self.tokens.tokens_processed += 1
        self.tokens.average_token_length = (
            (self.tokens.average_token_length * 
             (self.tokens.tokens_processed - 1) +
             len(token)) / self.tokens.tokens_processed
        )
        self.tokens.pattern_match_time_ms = pattern_time * 1000
        self.tokens.trigger_execution_time_ms = trigger_time * 1000
        
    def record_error(self, error: Exception):
        """Record an error occurrence"""
        self.error_window.append(time.time())
        if self.error_window:
            window_duration = time.time() - self.error_window[0]
            self.performance.error_rate = (
                len(self.error_window) / window_duration
                if window_duration > 0 else 0
            )
            
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        return {
            "performance": self.performance.__dict__,
            "tokens": self.tokens.__dict__,
            "system": self.system.__dict__
        }
        
    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format"""
        metrics = self.get_current_metrics()
        if format == "json":
            return json.dumps(metrics, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
            
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze system performance"""
        return {
            "latency_percentiles": {
                "p50": np.percentile(self.latency_window, 50),
                "p95": np.percentile(self.latency_window, 95),
                "p99": np.percentile(self.latency_window, 99)
            },
            "throughput_stats": {
                "mean": np.mean(self.throughput_window),
                "std": np.std(self.throughput_window),
                "max": np.max(self.throughput_window)
            },
            "error_rate_trend": (
                "increasing" if self.performance.error_rate > 0.1
                else "stable"
            ),
            "system_health": (
                "healthy" if self.performance.error_rate < 0.05
                and self.performance.latency_ms < 100
                else "degraded"
            )
        }

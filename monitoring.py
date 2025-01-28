import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import psutil
import numpy as np

@dataclass
class SystemMetrics:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_usage_percent: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    
@dataclass
class AudioMetrics:
    input_level: float = 0.0
    output_level: float = 0.0
    noise_floor: float = 0.0
    clipping_events: int = 0
    dropout_events: int = 0

@dataclass
class PerformanceMetrics:
    latency_ms: List[float] = field(default_factory=list)
    error_count: int = 0
    retry_count: int = 0
    successful_operations: int = 0

class MetricsMonitor:
    """Advanced system metrics monitoring"""
    
    def __init__(self, logging_interval: int = 60):
        self.logging_interval = logging_interval
        self.system_metrics = SystemMetrics()
        self.audio_metrics = AudioMetrics()
        self.performance_metrics = PerformanceMetrics()
        self._stop_event = threading.Event()
        self._metrics_history: List[Dict] = []
        
    def start(self):
        """Start metrics collection thread"""
        self._collection_thread = threading.Thread(target=self._collect_metrics)
        self._collection_thread.daemon = True
        self._collection_thread.start()
        
    def stop(self):
        """Stop metrics collection"""
        self._stop_event.set()
        if hasattr(self, '_collection_thread'):
            self._collection_thread.join()
            
    def _collect_metrics(self):
        """Collect system metrics periodically"""
        while not self._stop_event.is_set():
            try:
                # System metrics
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
                net = psutil.net_io_counters()
                
                self.system_metrics = SystemMetrics(
                    cpu_percent=cpu,
                    memory_percent=mem,
                    disk_usage_percent=disk,
                    network_bytes_sent=net.bytes_sent,
                    network_bytes_recv=net.bytes_recv
                )
                
                # Calculate performance statistics
                if self.performance_metrics.latency_ms:
                    latency_stats = {
                        'mean': np.mean(self.performance_metrics.latency_ms),
                        'p95': np.percentile(self.performance_metrics.latency_ms, 95),
                        'p99': np.percentile(self.performance_metrics.latency_ms, 99)
                    }
                else:
                    latency_stats = {'mean': 0, 'p95': 0, 'p99': 0}
                
                # Store metrics history
                self._metrics_history.append({
                    'timestamp': datetime.now(),
                    'system': self.system_metrics.__dict__,
                    'audio': self.audio_metrics.__dict__,
                    'performance': {
                        'latency_stats': latency_stats,
                        'error_rate': self.performance_metrics.error_count / 
                                    max(1, self.performance_metrics.successful_operations),
                        'retry_rate': self.performance_metrics.retry_count /
                                    max(1, self.performance_metrics.successful_operations)
                    }
                })
                
                # Trim history to last 24 hours
                cutoff = datetime.now() - timedelta(hours=24)
                self._metrics_history = [m for m in self._metrics_history 
                                      if m['timestamp'] > cutoff]
                
                # Log metrics summary
                if len(self._metrics_history) % self.logging_interval == 0:
                    self._log_metrics_summary()
                    
            except Exception as e:
                logging.error(f"Error collecting metrics: {e}")
                
            time.sleep(1)
            
    def _log_metrics_summary(self):
        """Log a summary of recent metrics"""
        recent = self._metrics_history[-self.logging_interval:]
        
        summary = {
            'cpu_avg': np.mean([m['system']['cpu_percent'] for m in recent]),
            'memory_avg': np.mean([m['system']['memory_percent'] for m in recent]),
            'latency_p95': np.percentile([m['performance']['latency_stats']['p95'] 
                                        for m in recent], 95),
            'error_rate': np.mean([m['performance']['error_rate'] for m in recent])
        }
        
        logging.info(f"Metrics Summary: {summary}")
        
    def record_latency(self, latency_ms: float):
        """Record a latency measurement"""
        self.performance_metrics.latency_ms.append(latency_ms)
        
    def record_error(self):
        """Record an error occurrence"""
        self.performance_metrics.error_count += 1
        
    def record_retry(self):
        """Record a retry attempt"""
        self.performance_metrics.retry_count += 1
        
    def record_success(self):
        """Record a successful operation"""
        self.performance_metrics.successful_operations += 1
        
    def record_audio_metrics(self, input_level: float, output_level: float,
                           noise_floor: Optional[float] = None):
        """Record audio-related metrics"""
        self.audio_metrics.input_level = input_level
        self.audio_metrics.output_level = output_level
        if noise_floor is not None:
            self.audio_metrics.noise_floor = noise_floor
            
    def get_summary(self) -> Dict:
        """Get a summary of current metrics"""
        return {
            'system': self.system_metrics.__dict__,
            'audio': self.audio_metrics.__dict__,
            'performance': {
                'error_rate': self.performance_metrics.error_count / 
                            max(1, self.performance_metrics.successful_operations),
                'retry_rate': self.performance_metrics.retry_count /
                            max(1, self.performance_metrics.successful_operations),
                'latency_stats': {
                    'mean': np.mean(self.performance_metrics.latency_ms) 
                            if self.performance_metrics.latency_ms else 0,
                    'p95': np.percentile(self.performance_metrics.latency_ms, 95)
                            if self.performance_metrics.latency_ms else 0
                }
            }
        }

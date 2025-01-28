from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class UsageMetrics:
    """Detailed usage metrics"""
    total_tokens: int = 0
    total_audio_minutes: float = 0
    total_compute_minutes: float = 0
    total_storage_bytes: int = 0
    total_bandwidth_bytes: int = 0
    total_function_calls: int = 0
    peak_concurrent_sessions: int = 0
    average_session_duration: float = 0
    error_rate: float = 0
    cache_hit_rate: float = 0

class UsageAnalyzer:
    """Analyzes user usage patterns and provides insights"""
    
    def __init__(self):
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.current_period_start = datetime.now()
        
    def record_usage(self, user_id: str, metrics: Dict[str, Any]) -> None:
        """Record usage metrics for a user"""
        self.metrics_history[user_id].append({
            "timestamp": datetime.now(),
            **metrics
        })
        
    def get_usage_trends(self, user_id: str, 
                        days: int = 30) -> Dict[str, Any]:
        """Analyze usage trends for a user"""
        history = self.metrics_history[user_id]
        start_date = datetime.now() - timedelta(days=days)
        
        # Filter recent history
        recent = [
            m for m in history 
            if m["timestamp"] >= start_date
        ]
        
        if not recent:
            return {}
            
        # Calculate trends
        daily_totals = defaultdict(list)
        for entry in recent:
            day = entry["timestamp"].date()
            for key, value in entry.items():
                if isinstance(value, (int, float)):
                    daily_totals[key].append(value)
                    
        trends = {}
        for key, values in daily_totals.items():
            if len(values) > 1:
                slope = np.polyfit(range(len(values)), values, 1)[0]
                trends[key] = {
                    "direction": "increasing" if slope > 0 else "decreasing",
                    "change_rate": abs(slope),
                    "average": np.mean(values),
                    "peak": max(values)
                }
                
        return trends
        
    def predict_usage(self, user_id: str, 
                     days_ahead: int = 7) -> Dict[str, Any]:
        """Predict future usage based on historical patterns"""
        trends = self.get_usage_trends(user_id)
        
        predictions = {}
        for metric, trend in trends.items():
            if "change_rate" in trend:
                predicted = (
                    trend["average"] + 
                    trend["change_rate"] * days_ahead
                )
                predictions[metric] = max(0, predicted)
                
        return predictions
        
    def get_usage_anomalies(self, user_id: str,
                           threshold: float = 2.0) -> List[Dict[str, Any]]:
        """Detect anomalous usage patterns"""
        history = self.metrics_history[user_id]
        if not history:
            return []
            
        anomalies = []
        metrics = defaultdict(list)
        
        # Gather metric histories
        for entry in history:
            for key, value in entry.items():
                if isinstance(value, (int, float)):
                    metrics[key].append(value)
                    
        # Detect anomalies using z-score
        for key, values in metrics.items():
            if len(values) > 10:  # Need enough samples
                mean = np.mean(values)
                std = np.std(values)
                if std > 0:
                    z_scores = np.abs((values - mean) / std)
                    anomaly_indices = np.where(z_scores > threshold)[0]
                    
                    for idx in anomaly_indices:
                        anomalies.append({
                            "metric": key,
                            "value": values[idx],
                            "timestamp": history[idx]["timestamp"],
                            "z_score": z_scores[idx]
                        })
                        
        return sorted(anomalies, 
                     key=lambda x: x["z_score"],
                     reverse=True)
        
    def get_usage_recommendations(self, user_id: str) -> List[str]:
        """Generate usage optimization recommendations"""
        trends = self.get_usage_trends(user_id)
        predictions = self.predict_usage(user_id)
        anomalies = self.get_usage_anomalies(user_id)
        
        recommendations = []
        
        # Check for high token usage
        if predictions.get("total_tokens", 0) > 1_000_000:
            recommendations.append(
                "Consider implementing token caching to reduce API costs"
            )
            
        # Check for low cache hit rate
        if trends.get("cache_hit_rate", {}).get("average", 1) < 0.5:
            recommendations.append(
                "Your cache hit rate is low. Review cache invalidation strategy"
            )
            
        # Check for high error rate
        if trends.get("error_rate", {}).get("average", 0) > 0.05:
            recommendations.append(
                "Error rate is above 5%. Review error patterns and add handling"
            )
            
        # Check for inefficient compute usage
        if anomalies:
            recommendations.append(
                f"Detected {len(anomalies)} usage anomalies. Review system logs"
            )
            
        return recommendations

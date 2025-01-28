from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class SubscriptionTier(BaseModel):
    """Subscription tier configuration"""
    name: str
    price_monthly: float
    price_yearly: float
    limits: Dict[str, int]
    features: Dict[str, Any]

class Subscription(BaseModel):
    """User subscription details"""
    id: str
    user_id: str
    tier: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    payment_method_id: Optional[str] = None
    latest_invoice_id: Optional[str] = None

SUBSCRIPTION_TIERS = {
    "free": SubscriptionTier(
        name="Free",
        price_monthly=0,
        price_yearly=0,
        limits={
            "daily_tokens": 50000,
            "monthly_tokens": 1000000,
            "concurrent_sessions": 1
        },
        features={
            "audio_enabled": False,
            "max_context_length": 4000,
            "available_models": ["gpt-4"]
        }
    ),
    "pro": SubscriptionTier(
        name="Pro",
        price_monthly=20,
        price_yearly=200,
        limits={
            "daily_tokens": 200000,
            "monthly_tokens": 5000000,
            "concurrent_sessions": 5
        },
        features={
            "audio_enabled": True,
            "max_context_length": 8000,
            "available_models": ["gpt-4", "gpt-4-turbo"]
        }
    ),
    "enterprise": SubscriptionTier(
        name="Enterprise",
        price_monthly=100,
        price_yearly=1000,
        limits={
            "daily_tokens": 1000000,
            "monthly_tokens": 20000000,
            "concurrent_sessions": 20
        },
        features={
            "audio_enabled": True,
            "max_context_length": 32000,
            "available_models": ["gpt-4", "gpt-4-turbo", "gpt-4-32k"]
        }
    )
}

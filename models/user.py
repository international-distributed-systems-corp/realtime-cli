from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

class User(BaseModel):
    """User model for authentication and billing"""
    id: str
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    subscription_tier: str = "free"
    subscription_expires: Optional[datetime] = None
    api_key: Optional[str] = None
    usage_limits: dict = {
        "daily_tokens": 50000,
        "monthly_tokens": 1000000,
        "concurrent_sessions": 1
    }
    current_usage: dict = {
        "daily_tokens": 0,
        "monthly_tokens": 0,
        "active_sessions": 0,
        "audio_minutes": 0,
        "text_input_tokens": 0,
        "text_output_tokens": 0,
        "audio_input_tokens": 0,
        "audio_output_tokens": 0,
        "cached_tokens": 0
    }
    billing: dict = {
        "current_charges": 0.0,
        "last_billing_date": None,
        "payment_method": None,
        "region_code": "US",
        "tax_rate": 0.0,
        "currency": "USD"
    }

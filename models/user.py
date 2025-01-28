from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, validator
from enum import Enum

class UserStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"
    PENDING = "pending"

class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    MANAGER = "manager"
    READONLY = "readonly"

class User(BaseModel):
    """User model for authentication and billing"""
    id: str
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    status: UserStatus = UserStatus.PENDING
    roles: List[UserRole] = [UserRole.USER]
    organization_id: Optional[str] = None
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
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
        "cached_tokens": 0,
        "function_calls": 0,
        "api_requests": 0,
        "storage_bytes": 0,
        "bandwidth_bytes": 0,
        "compute_minutes": 0,
        "custom_model_training_minutes": 0
    }
    usage_history: List[Dict[str, Any]] = []
    usage_alerts: Dict[str, Dict[str, Any]] = {
        "tokens": {"threshold": 0.8, "notified": False},
        "audio": {"threshold": 0.8, "notified": False},
        "compute": {"threshold": 0.8, "notified": False}
    }
    billing: dict = {
        "current_charges": 0.0,
        "last_billing_date": None,
        "payment_method": None,
        "region_code": "US",
        "tax_rate": 0.0,
        "currency": "USD"
    }

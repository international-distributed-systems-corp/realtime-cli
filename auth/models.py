from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserInDB(BaseModel):
    id: str
    email: EmailStr
    name: str
    hashed_password: str
    api_key: str
    created_at: datetime
    is_active: bool = True
    usage_limit: Optional[int] = None

class UsageRecord(BaseModel):
    user_id: str
    timestamp: datetime
    tokens_used: int
    audio_seconds: float
    request_type: str

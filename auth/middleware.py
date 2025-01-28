from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .db import Database
from typing import Optional
import os

security = HTTPBearer()

class AuthMiddleware:
    def __init__(self):
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.db = Database(mongo_url)

    async def authenticate(self, credentials: Optional[HTTPAuthorizationCredentials]) -> dict:
        if not credentials:
            raise HTTPException(status_code=401, detail="Missing authentication")
            
        api_key = credentials.credentials
        user = await self.db.get_user_by_api_key(api_key)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")
            
        return user

    async def record_usage(self, user_id: str, tokens: int, audio_seconds: float, request_type: str):
        usage = UsageRecord(
            user_id=user_id,
            timestamp=datetime.utcnow(),
            tokens_used=tokens,
            audio_seconds=audio_seconds,
            request_type=request_type
        )
        await self.db.record_usage(usage)

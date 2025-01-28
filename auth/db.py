import motor.motor_asyncio
from datetime import datetime
from typing import Optional
from .models import UserInDB, UsageRecord
import bcrypt
import secrets

class Database:
    def __init__(self, mongo_url: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        self.db = self.client.realtime_relay
        self.users = self.db.users
        self.usage = self.db.usage

    async def create_user(self, user_data: dict) -> UserInDB:
        # Hash password and generate API key
        hashed = bcrypt.hashpw(user_data["password"].encode(), bcrypt.gensalt())
        api_key = f"rt_{secrets.token_urlsafe(32)}"
        
        user = {
            "email": user_data["email"],
            "name": user_data["name"],
            "hashed_password": hashed.decode(),
            "api_key": api_key,
            "created_at": datetime.utcnow(),
            "is_active": True
        }
        
        result = await self.users.insert_one(user)
        user["id"] = str(result.inserted_id)
        return UserInDB(**user)

    async def get_user_by_api_key(self, api_key: str) -> Optional[UserInDB]:
        user = await self.users.find_one({"api_key": api_key})
        if user:
            user["id"] = str(user["_id"])
            return UserInDB(**user)
        return None

    async def record_usage(self, usage: UsageRecord):
        await self.usage.insert_one(usage.dict())

    async def get_user_usage(self, user_id: str, start_date: datetime) -> list:
        cursor = self.usage.find({
            "user_id": user_id,
            "timestamp": {"$gte": start_date}
        })
        return await cursor.to_list(length=None)

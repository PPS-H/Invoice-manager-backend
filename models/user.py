from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

class LinkedEmailAccount(BaseModel):
    provider: str
    email: EmailStr
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None

class UserModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    google_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    linked_accounts: List[LinkedEmailAccount] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def dict(self, **kwargs):
        """Override dict method to exclude None _id field for MongoDB insertion"""
        # Get the dictionary representation
        data = super().dict(**kwargs)

        # Remove _id if it's None to let MongoDB generate it
        if data.get("_id") is None:
            data.pop("_id", None)

        # Set timestamps if not provided
        if not data.get("created_at"):
            data["created_at"] = datetime.utcnow()
        if not data.get("updated_at"):
            data["updated_at"] = datetime.utcnow()

        return data

    class Config:
        # Allow population by field name or alias
        populate_by_name = True
        # Enable JSON encoding for ObjectId
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        } 
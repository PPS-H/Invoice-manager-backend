from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class GoogleGroupModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")  # MongoDB document ID - optional for new records
    user_id: str
    email_account_id: str
    group_id: str  # Google's group ID
    name: str
    email: str
    description: Optional[str] = None
    member_count: int = 0
    is_active: bool = True
    connected: bool = False  # Whether this group is selected for scanning
    last_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
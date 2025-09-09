from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class InviteLinkStatus(str, Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"

class InviteLinkModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    inviter_user_id: str
    email_account_id: str
    invite_token: str
    status: InviteLinkStatus = InviteLinkStatus.ACTIVE
    expires_at: datetime
    used_at: Optional[datetime] = None
    used_by_user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
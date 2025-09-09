from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class InviteModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    inviter_user_id: str
    invite_type: str = "share_access"  # "share_access" or "add_email_account"
    email_account_id: Optional[str] = None  # For share_access invites
    invited_email: Optional[str] = None  # For add_email_account invites
    invite_token: str
    status: str = "active"  # active, used, expired, ready_for_oauth
    expires_at: datetime
    used_at: Optional[datetime] = None
    used_by_user_id: Optional[str] = None
    added_email_account_id: Optional[str] = None  # For add_email_account invites
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
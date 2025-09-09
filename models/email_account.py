from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class EmailProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    YAHOO = "yahoo"

class EmailAccountStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PROCESSING = "processing"

class EmailAccountModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    
    def dict(self, *args, **kwargs):
        """Override dict to exclude id field when inserting"""
        data = super().dict(*args, **kwargs)
        if 'id' in data and data['id'] is None:
            data.pop('id', None)
        return data
    user_id: str
    email: EmailStr
    provider: EmailProvider
    display_name: Optional[str] = None
    status: EmailAccountStatus = EmailAccountStatus.CONNECTED
    
    # OAuth tokens
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    
    # Connection metadata
    last_sync_at: Optional[datetime] = None
    sync_frequency: int = 3600  # seconds
    is_active: bool = True
    
    # Processing settings
    scan_invoices: bool = True
    scan_receipts: bool = True
    auto_categorize: bool = True
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
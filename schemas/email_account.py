from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from models.email_account import EmailProvider, EmailAccountStatus

# Request Schemas
class LinkEmailAccountRequest(BaseModel):
    email: EmailStr
    provider: EmailProvider
    display_name: Optional[str] = None
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

class UpdateEmailAccountRequest(BaseModel):
    display_name: Optional[str] = None
    sync_frequency: Optional[int] = None
    scan_invoices: Optional[bool] = None
    scan_receipts: Optional[bool] = None
    auto_categorize: Optional[bool] = None
    is_active: Optional[bool] = None

class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None
    provider: EmailProvider

# Response Schemas
class EmailAccountResponse(BaseModel):
    id: str
    user_id: str
    email: EmailStr
    provider: EmailProvider
    display_name: Optional[str] = None
    status: EmailAccountStatus
    last_sync_at: Optional[datetime] = None
    sync_frequency: int
    is_active: bool
    scan_invoices: bool
    scan_receipts: bool
    auto_categorize: bool
    created_at: datetime
    updated_at: datetime
    account_type: Optional[str] = None  # "owned" or "invited"
    owner_user_id: Optional[str] = None  # ID of the user who owns this account

class EmailAccountListResponse(BaseModel):
    email_accounts: List[EmailAccountResponse]
    total: int

class OAuthUrlResponse(BaseModel):
    auth_url: str
    state: str

class SyncStatusResponse(BaseModel):
    email_account_id: str
    status: str
    last_sync_at: Optional[datetime] = None
    sync_progress: Optional[int] = None
    total_emails: Optional[int] = None
    processed_emails: Optional[int] = None 
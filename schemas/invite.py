from pydantic import BaseModel
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .invite import InviteResponse

class CreateInviteRequest(BaseModel):
    email_account_id: str
    expires_in_hours: Optional[int] = 24

class CreateEmailAccountInviteRequest(BaseModel):
    invited_email: str
    expires_in_hours: Optional[int] = 24

class InviteResponse(BaseModel):
    id: str
    inviter_user_id: str
    invite_type: str
    email_account_id: Optional[str] = None
    invited_email: Optional[str] = None
    invite_token: str
    status: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    used_by_user_id: Optional[str] = None
    added_email_account_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class CreateInviteResponse(BaseModel):
    success: bool
    invite_link: InviteResponse
    invite_url: str

class AcceptInviteRequest(BaseModel):
    invite_token: str

class AcceptInviteResponse(BaseModel):
    success: bool
    message: str
    email_account_id: Optional[str] = None

class InviteListResponse(BaseModel):
    invites: List[InviteResponse]
    total: int 
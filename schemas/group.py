from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.group import GroupType

class CreateGroupRequest(BaseModel):
    name: str
    description: Optional[str] = None
    type: GroupType = GroupType.CUSTOM
    color: Optional[str] = "#3B82F6"

class UpdateGroupRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[GroupType] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None

class GroupResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    type: GroupType
    color: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    invoice_count: Optional[int] = 0

class GroupListResponse(BaseModel):
    groups: List[GroupResponse]
    total: int
    page: int
    page_size: int 
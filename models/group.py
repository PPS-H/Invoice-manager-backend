from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class GroupType(str, Enum):
    DEPARTMENT = "department"
    PROJECT = "project"
    CLIENT = "client"
    CATEGORY = "category"
    CUSTOM = "custom"

class GroupModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    description: Optional[str] = None
    type: GroupType = GroupType.CUSTOM
    color: Optional[str] = "#3B82F6"  # Default blue
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
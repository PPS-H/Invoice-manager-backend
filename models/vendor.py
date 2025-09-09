from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class VendorModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    display_name: str
    category: Optional[str] = "software"  # software, cloud, billing, etc.
    typical_email_domains: List[str] = []  # billing@vendor.com, noreply@vendor.com
    typical_email_addresses: List[str] = []  # Specific email addresses
    common_keywords: List[str] = []  # keywords that appear in invoice subjects
    logo_url: Optional[str] = None
    website: Optional[str] = None
    is_active: bool = True
    is_global: bool = True  # NEW: True for system vendors, False for user-created
    created_by: Optional[str] = None  # NEW: user_id who created this vendor
    usage_count: int = 0  # NEW: Track how many users have selected this vendor
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
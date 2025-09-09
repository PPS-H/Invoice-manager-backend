from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class SelectedVendor(BaseModel):
    vendor_id: str
    vendor_name: str
    email_domains: List[str] = []
    is_custom: bool = False

class CustomVendor(BaseModel):
    vendor_id: str
    vendor_name: str
    email_domains: List[str] = []
    category: str = "software"
    is_custom: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ScanSettings(BaseModel):
    days_back: int = 30
    include_attachments: bool = True
    auto_scan_enabled: bool = False

class UserVendorPreferences(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    selected_vendors: List[SelectedVendor] = []
    custom_vendors: List[CustomVendor] = []
    scan_settings: ScanSettings = Field(default_factory=ScanSettings)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Request/Response models for API
class UserVendorPreferencesRequest(BaseModel):
    selected_vendors: List[str] = []  # List of vendor IDs
    custom_vendors: List[Dict] = []   # List of custom vendor objects
    scan_settings: Optional[Dict] = None

class CustomVendorRequest(BaseModel):
    name: str
    email_domains: List[str]
    category: str = "software"

class VendorPreferencesResponse(BaseModel):
    success: bool
    message: str
    data: Optional[UserVendorPreferences] = None 
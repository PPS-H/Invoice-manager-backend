from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class FilterMode(str, Enum):
    INCLUDE_ONLY = "include_only"  # Only scan emails from these addresses
    EXCLUDE = "exclude"  # Exclude emails from these addresses
    ALL = "all"  # Scan all emails (default)

class EmailFilterModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str  # Filter name for identification
    description: Optional[str] = None
    
    # Email filtering settings
    mode: FilterMode = FilterMode.ALL
    email_addresses: List[str] = []  # List of email addresses to include/exclude
    domains: List[str] = []  # List of domains to include/exclude
    
    # Time filtering
    scan_last_months: int = 3  # Scan emails from last N months
    priority_scan: bool = False  # If true, scan these first
    
    # Status
    is_active: bool = True
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class VendorIgnoreModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    vendor_name: str  # Exact vendor name or pattern
    ignore_reason: Optional[str] = None  # Why this vendor is ignored
    
    # Settings
    is_active: bool = True
    auto_delete: bool = False  # If true, auto-delete invoices from this vendor
    
    # Statistics
    ignored_count: int = 0  # How many invoices have been ignored
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
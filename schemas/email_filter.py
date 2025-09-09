from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from models.email_filter import FilterMode

# Email Filter Schemas
class CreateEmailFilterRequest(BaseModel):
    name: str
    description: Optional[str] = None
    mode: FilterMode = FilterMode.ALL
    email_addresses: List[str] = []
    domains: List[str] = []
    scan_last_months: int = 3
    priority_scan: bool = False

class UpdateEmailFilterRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[FilterMode] = None
    email_addresses: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    scan_last_months: Optional[int] = None
    priority_scan: Optional[bool] = None
    is_active: Optional[bool] = None

class EmailFilterResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str]
    mode: FilterMode
    email_addresses: List[str]
    domains: List[str]
    scan_last_months: int
    priority_scan: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

class EmailFilterListResponse(BaseModel):
    filters: List[EmailFilterResponse]
    total: int

# Vendor Ignore Schemas
class CreateVendorIgnoreRequest(BaseModel):
    vendor_name: str
    ignore_reason: Optional[str] = None
    auto_delete: bool = False

class UpdateVendorIgnoreRequest(BaseModel):
    ignore_reason: Optional[str] = None
    auto_delete: Optional[bool] = None
    is_active: Optional[bool] = None

class VendorIgnoreResponse(BaseModel):
    id: str
    user_id: str
    vendor_name: str
    ignore_reason: Optional[str]
    is_active: bool
    auto_delete: bool
    ignored_count: int
    created_at: datetime
    updated_at: datetime

class VendorIgnoreListResponse(BaseModel):
    ignored_vendors: List[VendorIgnoreResponse]
    total: int

# Scanning Request Schemas
class PriorityScanRequest(BaseModel):
    filter_id: str
    force_rescan: bool = False

class PriorityScanResponse(BaseModel):
    success: bool
    message: str
    processed_count: int
    total_emails: int
    filter_name: str 
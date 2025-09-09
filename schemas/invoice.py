from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from models.invoice import InvoiceStatus

# Request Schemas
class CreateInvoiceRequest(BaseModel):
    email_account_id: str
    vendor_name: str
    invoice_number: Optional[str] = None
    invoice_date: datetime
    due_date: Optional[datetime] = None
    amount: float
    currency: str = "USD"
    tax_amount: Optional[float] = None
    total_amount: float
    category: Optional[str] = None
    tags: List[str] = []

class UpdateInvoiceRequest(BaseModel):
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[InvoiceStatus] = None

class InvoiceFilterRequest(BaseModel):
    vendor_name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[InvoiceStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    tags: Optional[List[str]] = None
    email_account_id: Optional[str] = None

# Response Schemas
class InvoiceResponse(BaseModel):
    id: str
    user_id: str
    email_account_id: str
    vendor_name: str
    invoice_number: Optional[str] = None
    invoice_date: datetime
    due_date: Optional[datetime] = None
    amount: float
    currency: str
    tax_amount: Optional[float] = None
    total_amount: float
    status: InvoiceStatus
    category: Optional[str] = None
    tags: List[str] = []
    
    # Google Drive storage
    drive_file_id: Optional[str] = None
    drive_file_name: Optional[str] = None
    drive_folder_id: Optional[str] = None
    drive_view_link: Optional[str] = None  # Direct link to view invoice in Drive
    
    # Email metadata
    email_subject: Optional[str] = None
    email_sender: Optional[str] = None
    email_date: Optional[datetime] = None
    
    # Source tracking
    source_type: str = "email"  # "email" or "group"
    source_group_id: Optional[str] = None  # Google Group ID if from group
    source_group_email: Optional[str] = None  # Group email address if from group
    
    # Processing metadata
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    total_amount: float  # Total amount of all matching invoices (not just current page)

class InvoiceStatsResponse(BaseModel):
    total_invoices: int
    total_amount: float
    currency: str
    monthly_totals: List[dict]
    vendor_totals: List[dict]
    category_totals: List[dict] 
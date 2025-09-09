from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class InvoiceStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    ERROR = "error"

class InvoiceModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    email_account_id: str
    vendor_name: str
    invoice_number: Optional[str] = None
    invoice_date: datetime
    due_date: Optional[datetime] = None
    amount: float
    currency: str = "USD"
    tax_amount: Optional[float] = None
    total_amount: float
    status: InvoiceStatus = InvoiceStatus.PENDING
    category: Optional[str] = None
    tags: List[str] = []
    
    # Google Drive storage
    drive_file_id: Optional[str] = None
    drive_file_name: Optional[str] = None
    drive_folder_id: Optional[str] = None
    drive_view_link: Optional[str] = None  # Direct link to view invoice in Drive
    
    # Local file storage
    local_file_path: Optional[str] = None
    local_file_name: Optional[str] = None
    local_file_size: Optional[int] = None
    
    # Email metadata
    email_subject: Optional[str] = None
    email_sender: Optional[str] = None
    email_date: Optional[datetime] = None
    email_message_id: Optional[str] = None
    
    # Source tracking
    source_type: str = "email"  # "email" or "group"
    source_group_id: Optional[str] = None  # Google Group ID if from group
    source_group_email: Optional[str] = None  # Group email address if from group
    
    # Group assignment
    group_id: Optional[str] = None
    
    # Processing metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
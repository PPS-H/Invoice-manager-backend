"""
Database model for scanning task tracking
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    DONE = "DONE"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"

class ScanType(str, Enum):
    INBOX = "inbox"
    GROUPS = "groups"
    ALL = "all"

class ScanningTaskModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    task_id: str = Field(..., description="Celery task ID")
    user_id: str = Field(..., description="User ID")
    account_id: str = Field(..., description="Email account ID")
    scan_type: ScanType = Field(..., description="Type of scan")
    months: int = Field(default=1, ge=1, le=12, description="Number of months to scan")
    
    # Task status and progress
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    current_status: Optional[str] = Field(None, description="Current status message")
    
    # Results
    result: Optional[Dict[str, Any]] = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Error message if failed")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None, description="When task started")
    completed_at: Optional[datetime] = Field(None, description="When task completed")
    
    # Metadata
    estimated_duration: Optional[int] = Field(default=5, description="Estimated duration in minutes")
    actual_duration: Optional[int] = Field(None, description="Actual duration in minutes")
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def dict(self, **kwargs):
        """Override dict method to exclude None _id field for MongoDB insertion"""
        data = super().dict(**kwargs)
        
        # Remove _id if it's None to let MongoDB generate it
        if data.get("_id") is None:
            data.pop("_id", None)
        
        return data
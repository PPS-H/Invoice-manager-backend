from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from datetime import datetime
from bson import ObjectId

class SubscriptionModel(BaseModel):
    """MongoDB model for user subscriptions"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str  # Reference to user document
    stripe_customer_id: str
    stripe_subscription_id: str
    price_id: str
    status: str  # active, canceled, past_due, etc.
    current_period_start: datetime
    current_period_end: datetime
    latest_invoice_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('id', mode='before')
    @classmethod
    def convert_objectid_to_str(cls, v):
        """Convert ObjectId to string"""
        if isinstance(v, ObjectId):
            return str(v)
        return v

    def dict(self, **kwargs):
        """Override dict method to exclude None _id field for MongoDB insertion"""
        data = super().dict(**kwargs)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data

    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
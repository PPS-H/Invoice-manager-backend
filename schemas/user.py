from pydantic import BaseModel, EmailStr
from typing import List, Optional

class LinkedEmailAccountSchema(BaseModel):
    provider: str
    email: EmailStr

class UserSchema(BaseModel):
    id: str
    google_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    linked_accounts: List[LinkedEmailAccountSchema] = [] 
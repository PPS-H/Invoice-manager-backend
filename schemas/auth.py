from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

# Request Schemas
class GoogleAuthRequest(BaseModel):
    """Request schema for Google OAuth login"""
    state: Optional[str] = Field(None, description="Optional state parameter for OAuth flow")

class GoogleCallbackRequest(BaseModel):
    """Request schema for Google OAuth callback"""
    code: str = Field(..., description="Authorization code from Google")
    state: Optional[str] = Field(None, description="State parameter from OAuth flow")

class GoogleExchangeRequest(BaseModel):
    """Request schema for Google OAuth code exchange"""
    code: str = Field(..., description="Authorization code from Google")

# Response Schemas
class TokenResponse(BaseModel):
    """JWT token response schema"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: Optional[int] = Field(None, description="Token expiration in seconds")

class UserResponse(BaseModel):
    """User information response schema"""
    id: str = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User full name")
    picture: Optional[str] = Field(None, description="User profile picture URL")
    google_id: Optional[str] = Field(None, description="Google user ID")
    created_at: Optional[datetime] = Field(None, description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

class AuthResponse(BaseModel):
    """Complete authentication response schema"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: Optional[int] = Field(None, description="Token expiration in seconds")
    user: UserResponse = Field(..., description="Authenticated user information")

class GoogleAuthUrlResponse(BaseModel):
    """Google OAuth URL response schema"""
    auth_url: str = Field(..., description="Google OAuth authorization URL")
    state: Optional[str] = Field(None, description="State parameter for OAuth flow") 
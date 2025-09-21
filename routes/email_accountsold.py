from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from models.user import UserModel
from models.email_account import EmailAccountModel, EmailProvider, EmailAccountStatus
from models.invoice import InvoiceModel
from core.jwt import get_current_user
from core.database import mongodb
from services.invoice_processor import InvoiceProcessor
from services.factory import create_invoice_processor, create_email_scanner
from services.email_body_parser import EmailBodyParser
from services.task_manager import task_manager
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import httplib2
import logging
from core.config import settings
import json
import asyncio

logger = logging.getLogger(__name__)

# Google OAuth2 settings
GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
from bson import ObjectId
import os
import requests
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])

# Pydantic schemas for requests/responses
class SyncInboxRequest(BaseModel):
    months: Optional[int] = Field(default=1, ge=1, le=12, description="Number of months to scan back")

class LinkEmailAccountRequest(BaseModel):
    provider: str
    code: str
    
class UpdateEmailAccountRequest(BaseModel):
    is_active: Optional[bool] = None
    scan_frequency: Optional[int] = None
    
class EmailAccountResponse(BaseModel):
    id: str
    email: str
    provider: str
    is_active: bool
    status: str
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    
class SyncStatusResponse(BaseModel):
    message: str
    account_id: str
    status: str
    estimated_time: str
    
class EmailAccountListResponse(BaseModel):
    email_accounts: List[EmailAccountResponse]
    total: int
    
class OAuthUrlResponse(BaseModel):
    auth_url: str
security = HTTPBearer()

# OAuth Configuration is already defined above from settings

# Invoice processor will be initialized in route functions when needed

# Helper to check DB connection
def ensure_db():
    if mongodb is None or getattr(mongodb, 'db', None) is None:
        raise HTTPException(status_code=500, detail='Database connection not available')

@router.get("/debug/oauth-config")
async def debug_oauth_config():
    """Debug endpoint to check OAuth configuration"""
    return {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret_set": bool(GOOGLE_CLIENT_SECRET),
        "redirect_uri": "http://localhost:5173/email-accounts/callback",
        "token_url": "https://oauth2.googleapis.com/token",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth"
    }

# Move the url-public route before the url route to avoid route conflicts
# More specific routes should come before more general ones

@router.get("/oauth/{provider}/url-public")
async def get_oauth_url_public(provider: str):
    """Get OAuth URL for email provider (public - for invited users)"""
    if provider == "gmail":
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": "http://localhost:5173/auth/callback",  # Use the same redirect URI as main auth
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": "email_account_oauth_public"
        }
        from urllib.parse import urlencode
        query_string = urlencode(params)
        auth_url = f"{auth_url}?{query_string}"
        
        return OAuthUrlResponse(auth_url=auth_url, state="email_account_oauth_public")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )

@router.get("/oauth/{provider}/url")
async def get_oauth_url(provider: str):
    """Get OAuth URL for email provider"""
    if provider == "gmail":
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": "http://localhost:5173/email-accounts/callback",
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": "email_account_oauth"
        }
        from urllib.parse import urlencode
        query_string = urlencode(params)
        auth_url = f"{auth_url}?{query_string}"
        
        return OAuthUrlResponse(auth_url=auth_url, state="email_oauth")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )

# Move the callback-public route before the callback route to avoid route conflicts
# More specific routes should come before more general ones

@router.get("/oauth/{provider}/callback-public")
async def oauth_callback_public(
    provider: str,
    code: str = Query(..., description="Authorization code from OAuth provider")
):
    """Handle OAuth callback for email provider (public - no authentication required)"""
    print(f"📧 Public OAuth callback - Provider: {provider}")
    print(f"   Code received: {code[:20] if code else 'None'}...")
    print(f"   This is for invited users who need to complete OAuth without authentication")
    
    # Validate code parameter
    if not code:
        print(f"   ❌ No authorization code received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code is required"
        )
    
    try:
        if provider == "gmail":
            # Exchange code for tokens
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": "http://localhost:5173/auth/callback"  # Use the same redirect URI as main auth
            }
            
            print(f"   Exchanging code for tokens...")
            response = requests.post(token_url, data=token_data)
            if response.status_code != 200:
                print(f"   ❌ Token exchange failed: {response.status_code} - {response.text}")
                error_detail = response.json() if response.headers.get('content-type') == 'application/json' else response.text
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to exchange code for tokens: {error_detail}"
                )
            
            tokens = response.json()
            print(f"   ✅ Got tokens: {tokens.keys()}")
            
            # Get user info from Google
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            print(f"   Requesting user info from Google...")
            user_response = requests.get(user_info_url, headers=headers)
            
            if user_response.status_code != 200:
                print(f"   ❌ User info request failed: {user_response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get user info from Google: {user_response.status_code}"
                )
                
            user_info = user_response.json()
            print(f"   📧 Got user info: {user_info.get('email')}")
            
            # Check if this email is being connected as part of an invitation
            ensure_db()
            invitation_check = await mongodb.db["invites"].find_one({
                "invite_type": "add_email_account",
                "invited_email": user_info["email"].lower(),
                "status": "ready_for_oauth"
            })
            
            if not invitation_check:
                print(f"   ❌ No pending invitation found for email: {user_info['email']}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No pending invitation found for this email address"
                )
            
            print(f"   📧 Found invitation for email: {user_info['email']}")
            print(f"      Invitation ID: {invitation_check['_id']}")
            print(f"      Inviter user ID: {invitation_check.get('inviter_user_id')}")
            print(f"      Invitation status: {invitation_check.get('status')}")
            print(f"      Invitation created: {invitation_check.get('created_at')}")
            
            # Check if email account already exists
            existing_account = await mongodb.db["email_accounts"].find_one({
                "email": user_info["email"]
            })
            
            if existing_account:
                print(f"   ⚠️ Email account already exists: {existing_account['_id']}")
                # Update existing account with new tokens
                await mongodb.db["email_accounts"].update_one(
                    {"_id": existing_account["_id"]},
                    {"$set": {
                        "access_token": tokens.get("access_token"),
                        "refresh_token": tokens.get("refresh_token"),
                        "token_expires_at": datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
                        "status": "connected",
                        "updated_at": datetime.utcnow()
                    }}
                )
                account_id = str(existing_account["_id"])
                print(f"   ✅ Updated existing account: {account_id}")
            else:
                print(f"   🆕 Creating new email account for invited user")
                
                # Create new email account with inviter's user_id
                owner_user_id = invitation_check["inviter_user_id"]
                print(f"      Owner user ID: {owner_user_id}")
                print(f"      Invited email: {user_info['email']}")
                print(f"      Provider: GMAIL")
                print(f"      Display name: {user_info.get('name', '')}")
                
                # Create email account model
                email_account = EmailAccountModel(
                    user_id=owner_user_id,  # Link to inviter's system
                    email=user_info["email"],
                    provider=EmailProvider.GMAIL,
                    display_name=user_info.get("name", ""),
                    access_token=tokens.get("access_token"),
                    refresh_token=tokens.get("refresh_token"),
                    token_expires_at=datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
                    status=EmailAccountStatus.CONNECTED,
                    # Set default values for required fields
                    sync_frequency=3600,
                    is_active=True,
                    scan_invoices=True,
                    scan_receipts=False,
                    auto_categorize=True
                )
                
                print(f"   📝 Email account model created successfully")
                print(f"      User ID: {email_account.user_id}")
                print(f"      Email: {email_account.email}")
                print(f"      Status: {email_account.status}")
                print(f"      Scan invoices: {email_account.scan_invoices}")
                
                # Insert the email account
                insert_data = email_account.dict(by_alias=True)
                print(f"   📝 Insert data prepared: {list(insert_data.keys())}")
                
                # Remove id and _id fields if they are None
                for key in ['id', '_id']:
                    if key in insert_data and insert_data[key] is None:
                        insert_data.pop(key)
                
                # Convert Enums to their values for MongoDB
                for k, v in insert_data.items():
                    if hasattr(v, 'value'):
                        insert_data[k] = v.value
                        print(f"      Converted {k}: {v.value}")
                
                print(f"   📝 Final insert data prepared")
                print(f"      User ID: {insert_data.get('user_id')}")
                print(f"      Email: {insert_data.get('email')}")
                print(f"      Provider: {insert_data.get('provider')}")
                print(f"      Status: {insert_data.get('status')}")
                
                # Insert into database
                result = await mongodb.db["email_accounts"].insert_one(insert_data)
                if not result or not hasattr(result, 'inserted_id') or result.inserted_id is None:
                    print(f"   ❌ Failed to insert email account")
                    raise HTTPException(status_code=500, detail="Failed to insert email account")
                
                account_id = str(result.inserted_id)
                print(f"   ✅ Created new email account: {account_id}")
                
                # Verify the account was created correctly
                created_account = await mongodb.db["email_accounts"].find_one({"_id": result.inserted_id})
                if created_account:
                    print(f"   ✅ Account verified in database:")
                    print(f"      ID: {created_account['_id']}")
                    print(f"      User ID: {created_account.get('user_id')}")
                    print(f"      Email: {created_account.get('email')}")
                    print(f"      Status: {created_account.get('status')}")
                    print(f"      Scan invoices: {created_account.get('scan_invoices')}")
                else:
                    print(f"   ❌ Account not found in database after creation!")
            
            # Update invitation status to used
            # Note: For public OAuth, we don't have a current_user, so we'll set used_by_user_id to None
            # The important thing is that the email account is linked to the inviter's system
            await mongodb.db["invites"].update_one(
                {"_id": invitation_check["_id"]},
                {
                    "$set": {
                        "status": "used",
                        "used_at": datetime.utcnow(),
                        "used_by_user_id": None,  # Public OAuth doesn't have a current_user
                        "added_email_account_id": account_id,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            print(f"   📝 Updated invitation status to 'used'")
            print(f"   📝 Email account {account_id} linked to inviter {invitation_check['inviter_user_id']}")
            
            # Verify that the account is properly linked and visible to the inviter
            print(f"   🔍 Verifying account linking...")
            
            # Check if the account is visible to the inviter
            inviter_id = invitation_check["inviter_user_id"]
            linked_account = await mongodb.db["email_accounts"].find_one({
                "_id": result.inserted_id if 'result' in locals() else ObjectId(account_id)
            })
            
            if linked_account:
                print(f"   ✅ Account linking verified:")
                print(f"      Account ID: {linked_account['_id']}")
                print(f"      User ID (should be inviter): {linked_account.get('user_id')}")
                print(f"      Inviter ID: {inviter_id}")
                print(f"      Email: {linked_account.get('email')}")
                print(f"      Status: {linked_account.get('status')}")
                print(f"      Scan invoices: {linked_account.get('scan_invoices')}")
                
                # Verify the account will be visible to the inviter
                if linked_account.get('user_id') == inviter_id:
                    print(f"   ✅ Account properly linked to inviter!")
                else:
                    print(f"   ❌ Account NOT properly linked to inviter!")
                    print(f"      Expected user_id: {inviter_id}")
                    print(f"      Actual user_id: {linked_account.get('user_id')}")
            else:
                print(f"   ❌ Could not verify account linking!")
            
            # Return success response
            print(f"   🎯 Final result:")
            print(f"      Email account ID: {account_id}")
            print(f"      Email: {user_info['email']}")
            print(f"      Owner user ID: {invitation_check['inviter_user_id']}")
            print(f"      Invitation status: used")
            print(f"      Account linked to inviter's system successfully!")
            
            return {
                "message": "Email account connected successfully!",
                "account_id": account_id,
                "email": user_info["email"],
                "inviter_user_id": str(invitation_check["inviter_user_id"]),
                "redirect_url": "/dashboard"  # Redirect to dashboard after success
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in public OAuth callback: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process public OAuth callback: {str(e)}"
        )

@router.post("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from OAuth provider"),
    current_user: UserModel = Depends(get_current_user)
):
    """Handle OAuth callback for email provider (authenticated users)"""
    print(f"Email account OAuth callback - Provider: {provider}, Code: {code[:20]}...")
    print(f"Current user: {current_user.email} (ID: {current_user.id})")
    
    # This endpoint is for authenticated users
    # For invited users, they should use the public OAuth callback endpoint
    
    try:
        if provider == "gmail":
            # Exchange code for tokens
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": "http://localhost:5173/email-accounts/callback"
            }
            
            print(f"Exchanging code for tokens...")
            print(f"Token request data: {dict(token_data)}")
            response = requests.post(token_url, data=token_data)
            if response.status_code != 200:
                print(f"Token exchange failed: {response.status_code} - {response.text}")
                error_detail = response.json() if response.headers.get('content-type') == 'application/json' else response.text
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to exchange code for tokens: {error_detail}"
                )
            
            tokens = response.json()
            print(f"Got tokens: {tokens.keys()}")
            
            # Get user info from Google
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            print(f"Requesting user info from: {user_info_url}")
            user_response = requests.get(user_info_url, headers=headers)
            
            if user_response.status_code != 200:
                print(f"User info request failed: {user_response.status_code} - {user_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get user info from Google: {user_response.status_code}"
                )
                
            user_info = user_response.json()
            print(f"Got user info: {user_info.get('email')}")
            
            # Check if email account already exists
            ensure_db()
            existing_account = await mongodb.db["email_accounts"].find_one({
                "user_id": current_user.id,
                "email": user_info["email"]
            })
            
            # Also check if this email is being connected as part of an invitation
            # This helps us understand if this is a public invitation flow
            invitation_check = await mongodb.db["invites"].find_one({
                "invite_type": "add_email_account",
                "invited_email": user_info["email"].lower(),
                "status": {"$in": ["ready_for_oauth", "used"]}
            })
            
            if invitation_check:
                print(f"📧 Found invitation for email: {user_info['email']}")
                print(f"   Invitation status: {invitation_check.get('status')}")
                print(f"   Inviter user ID: {invitation_check.get('inviter_user_id')}")
                print(f"   Current user ID: {current_user.id}")
            else:
                print(f"📧 No invitation found for email: {user_info['email']}")
            
            if existing_account:
                if "_id" not in existing_account:
                    raise HTTPException(status_code=500, detail="Corrupt email account record: missing _id")
                print(f"Updating existing account: {existing_account['_id']}")
                # Update existing account
                await mongodb.db["email_accounts"].update_one(
                    {"_id": existing_account["_id"]},
                    {"$set": {
                        "access_token": tokens.get("access_token"),
                        "refresh_token": tokens.get("refresh_token"),
                        "token_expires_at": datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
                        "status": "connected",
                        "updated_at": datetime.utcnow()
                    }}
                )
                account_id = str(existing_account["_id"])
            else:
                print(f"Creating new email account for user: {current_user.id}")
                
                # Check if this user has a pending "add_email_account" invite
                # Look for any invite where this user accepted and the email matches
                pending_invite = await mongodb.db["invites"].find_one({
                    "used_by_user_id": current_user.id,
                    "invite_type": "add_email_account",
                    "status": "used"
                })
                
                print(f"🔍 Checking for pending invites...")
                print(f"   Direct invite (used_by_user_id): {pending_invite is not None}")
                
                # If no direct invite found, also check if the email matches any pending invite
                if not pending_invite:
                    pending_invite = await mongodb.db["invites"].find_one({
                        "invite_type": "add_email_account",
                        "status": "used",
                        "invited_email": user_info["email"].lower()
                    })
                    print(f"   Email match invite (status=used): {pending_invite is not None}")
                
                # Also check for public invites that are ready for OAuth
                if not pending_invite:
                    # Only consider recent invitations (within last 7 days) to prevent old ones from interfering
                    week_ago = datetime.utcnow() - timedelta(days=7)
                    pending_invite = await mongodb.db["invites"].find_one({
                        "invite_type": "add_email_account",
                        "status": "ready_for_oauth",
                        "invited_email": user_info["email"].lower(),
                        "created_at": {"$gte": week_ago}  # Only recent invitations
                    })
                    print(f"   Recent public invite (status=ready_for_oauth): {pending_invite is not None}")
                    
                    # If we found a public invite, mark it as used by this user
                    if pending_invite:
                        print(f"   📧 Processing public invite: {pending_invite['_id']}")
                        await mongodb.db["invites"].update_one(
                            {"_id": pending_invite["_id"]},
                            {
                                "$set": {
                                    "status": "used",
                                    "used_at": datetime.utcnow(),
                                    "used_by_user_id": current_user.id
                                }
                            }
                        )
                        print(f"   ✅ Public invite marked as used by user {current_user.id}")
                        logger.info(f"Public invite {pending_invite['_id']} now used by user {current_user.id}")
                
                # If we found an invitation, validate it's still relevant
                if pending_invite:
                    # Check if invitation is expired
                    if pending_invite.get("expires_at") and datetime.utcnow() > pending_invite["expires_at"]:
                        print(f"   ⚠️ Found expired invitation: {pending_invite['_id']}")
                        # Mark as expired
                        await mongodb.db["invites"].update_one(
                            {"_id": pending_invite["_id"]},
                            {
                                "$set": {
                                    "status": "expired",
                                    "updated_at": datetime.utcnow(),
                                    "expired_reason": "Expired during OAuth flow"
                                }
                            }
                        )
                        print(f"   ✅ Marked expired invitation as expired")
                        pending_invite = None
                    else:
                        print(f"   ✅ Found valid invitation: {pending_invite['_id']}")
                        print(f"      Inviter: {pending_invite.get('inviter_user_id')}")
                        print(f"      Status: {pending_invite.get('status')}")
                        print(f"      Expires: {pending_invite.get('expires_at')}")
                
                # CRITICAL FIX: Check if this is actually the user's own email account
                # If the user is connecting their own email (not someone else's), 
                # it should always belong to them regardless of any invitations
                user_owns_email = user_info["email"].lower() == current_user.email.lower()
                print(f"🔍 Email ownership check:")
                print(f"   User's email: {current_user.email}")
                print(f"   Connecting email: {user_info['email']}")
                print(f"   User owns this email: {user_owns_email}")
                
                # Determine the user_id for the email account
                # IMPORTANT: Only use inviter's user_id if this is explicitly an invitation flow
                # If user is connecting their own email account, it should belong to them
                owner_user_id = current_user.id
                
                # Check if this is actually an invitation flow (not just a user connecting their own account)
                is_invitation_flow = False
                if pending_invite and not user_owns_email:
                    # This is an invitation flow - check if the email belongs to the inviter's system
                    # or if it's a team collaboration where the invited user is connecting an account for the inviter
                    inviter_id = pending_invite["inviter_user_id"]
                    
                    # If the current user is the inviter, this is their own account
                    if str(current_user.id) == str(inviter_id):
                        print(f"   👤 Current user is the inviter - linking to own account: {current_user.id}")
                        owner_user_id = current_user.id
                        is_invitation_flow = False
                    else:
                        # This is a team collaboration - the invited user is connecting an account for the inviter
                        print(f"   🔗 Team collaboration - linking email account to inviter: {inviter_id}")
                        print(f"   📧 Email: {user_info['email']}")
                        print(f"   👤 Current user: {current_user.id}")
                        print(f"   👥 Owner will be: {inviter_id}")
                        owner_user_id = inviter_id
                        is_invitation_flow = True
                elif user_owns_email:
                    print(f"   👤 User is connecting their own email account - linking to self: {current_user.id}")
                    owner_user_id = current_user.id
                    is_invitation_flow = False
                    # Clear any pending invite since this is the user's own account
                    if pending_invite:
                        print(f"   🧹 Clearing pending invite since this is user's own account")
                        # Mark old invitation as expired to prevent future interference
                        await mongodb.db["invites"].update_one(
                            {"_id": pending_invite["_id"]},
                            {
                                "$set": {
                                    "status": "expired",
                                    "updated_at": datetime.utcnow(),
                                    "expired_reason": "User connecting own email account"
                                }
                            }
                        )
                        print(f"   ✅ Marked old invitation as expired")
                        pending_invite = None
                else:
                    print(f"   👤 No invite found and not user's own email - linking to current user: {current_user.id}")
                    is_invitation_flow = False
                
                # Create new email account
                email_account = EmailAccountModel(
                    user_id=owner_user_id,  # This might be the inviter's ID
                    email=user_info["email"],
                    provider=EmailProvider.GMAIL,
                    display_name=user_info.get("name", ""),
                    access_token=tokens.get("access_token"),
                    refresh_token=tokens.get("refresh_token"),
                    token_expires_at=datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
                    status="connected"
                )
                
                # CRITICAL VALIDATION: Verify the user_id is set correctly
                print(f"🔍 Email account model validation:")
                print(f"   Model user_id: {email_account.user_id}")
                print(f"   Expected user_id: {owner_user_id}")
                print(f"   Current user ID: {current_user.id}")
                print(f"   Is invitation flow: {is_invitation_flow}")
                print(f"   User owns email: {user_owns_email}")
                
                # Double-check that the user_id is correct
                if str(email_account.user_id) != str(owner_user_id):
                    print(f"   ❌ CRITICAL ERROR: user_id mismatch!")
                    print(f"      Model has: {email_account.user_id}")
                    print(f"      Expected: {owner_user_id}")
                    print(f"      Current user ID: {current_user.id}")
                    print(f"      Is invitation flow: {is_invitation_flow}")
                    print(f"      User owns email: {user_owns_email}")
                    # Force the correct user_id
                    email_account.user_id = owner_user_id
                    print(f"      Fixed to: {email_account.user_id}")
                
                # Insert the email account (without id field)
                insert_data = email_account.dict(by_alias=True)
                # Remove id and _id fields if they are None
                for key in ['id', '_id']:
                    if key in insert_data and insert_data[key] is None:
                        insert_data.pop(key)
                # Convert Enums to their values for MongoDB
                for k, v in insert_data.items():
                    if hasattr(v, 'value'):
                        insert_data[k] = v.value
                print(f"Email account data: {insert_data}")
                
                # FINAL VALIDATION: Check insert_data before database insertion
                print(f"🔍 Final validation before database insertion:")
                print(f"   Insert data user_id: {insert_data.get('user_id')}")
                print(f"   Expected user_id: {owner_user_id}")
                print(f"   Match: {str(insert_data.get('user_id')) == str(owner_user_id)}")
                
                if str(insert_data.get('user_id')) != str(owner_user_id):
                    print(f"   ❌ CRITICAL ERROR: Insert data user_id mismatch!")
                    print(f"      Insert data has: {insert_data.get('user_id')}")
                    print(f"      Expected: {owner_user_id}")
                    # Force the correct user_id in insert_data
                    insert_data['user_id'] = owner_user_id
                    print(f"      Fixed insert_data to: {insert_data['user_id']}")
                
                # FINAL SAFETY CHECK: Ensure user_id is correct before database insertion
                # This is the critical fix for the user_id assignment issue
                if str(insert_data.get('user_id')) != str(owner_user_id):
                    print(f"   🚨 FINAL SAFETY CHECK FAILED - FORCING CORRECT USER_ID")
                    insert_data['user_id'] = owner_user_id
                    print(f"      Final user_id set to: {insert_data['user_id']}")
                
                print(f"   ✅ Final insert_data user_id: {insert_data.get('user_id')}")
                print(f"   ✅ Expected user_id: {owner_user_id}")
                print(f"   ✅ Match: {str(insert_data.get('user_id')) == str(owner_user_id)}")

                ensure_db()
                result = await mongodb.db["email_accounts"].insert_one(insert_data)
                if not result or not hasattr(result, 'inserted_id') or result.inserted_id is None:
                    raise HTTPException(status_code=500, detail="Failed to insert email account")
                account_id = str(result.inserted_id)
                
                print(f"✅ Created email account: {account_id}")
                print(f"   📧 Email: {user_info['email']}")
                print(f"   👤 Owner User ID: {owner_user_id}")
                print(f"   🔗 Linked to inviter: {is_invitation_flow}")
                print(f"   🎯 Final user_id in database: {owner_user_id}")
                
                # Verify the account was created with the correct user_id
                created_account = await mongodb.db["email_accounts"].find_one({"_id": result.inserted_id})
                if created_account:
                    print(f"   ✅ Account verification in database:")
                    print(f"      Database user_id: {created_account.get('user_id')}")
                    print(f"      Expected user_id: {owner_user_id}")
                    print(f"      Match: {str(created_account.get('user_id')) == str(owner_user_id)}")
                else:
                    print(f"   ❌ Could not verify account in database!")
                
                # If this was created for an invite, update the invite with the new email account ID
                if pending_invite and is_invitation_flow:
                    await mongodb.db["invites"].update_one(
                        {"_id": pending_invite["_id"]},
                        {"$set": {
                            "added_email_account_id": account_id,
                            "updated_at": datetime.utcnow()
                        }}
                    )
                    print(f"   📝 Updated invite {pending_invite['_id']} with email account ID: {account_id}")
                    print(f"   🎯 Email account now properly linked to inviter's system")
                elif pending_invite and not is_invitation_flow:
                    print(f"   📝 Invite exists but this is user's own account - no need to update invite")
                else:
                    print(f"   📝 No invite involved - this is user's own email account")
                
                # FINAL SUMMARY LOG
                print(f"🎯 FINAL DECISION SUMMARY:")
                print(f"   📧 Email: {user_info['email']}")
                print(f"   👤 Current user ID: {current_user.id}")
                print(f"   👥 Final owner user ID: {owner_user_id}")
                print(f"   🔗 Is invitation flow: {is_invitation_flow}")
                print(f"   📧 User owns email: {user_owns_email}")
                print(f"   ✅ Account created with user_id: {created_account.get('user_id') if created_account else 'UNKNOWN'}")
                if str(created_account.get('user_id')) == str(owner_user_id):
                    print(f"   🎉 SUCCESS: Email account correctly linked!")
                else:
                    print(f"   ❌ ERROR: Email account user_id mismatch!")
            
            return {"message": "Email account linked successfully", "account_id": account_id}
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link email account: {str(e)}"
        )



@router.get("/", response_model=EmailAccountListResponse)
async def get_email_accounts(current_user: UserModel = Depends(get_current_user)):
    """Get all email accounts for current user"""
    ensure_db()
    
    # Get email accounts owned by the current user
    owned_accounts = await mongodb.db["email_accounts"].find({"user_id": current_user.id}).to_list(length=None)
    
    # Get email accounts that were invited by the current user (for other users)
    invited_accounts = await mongodb.db["email_accounts"].find({
        "user_id": {"$ne": current_user.id}  # Not owned by current user
    }).to_list(length=None)
    
    # Check which of these invited accounts were actually invited by the current user
    invited_by_current_user = []
    for account in invited_accounts:
        # Check if there's an invitation from current user to this email
        # For public OAuth, used_by_user_id might be None, so we check by inviter_user_id
        invitation = await mongodb.db["invites"].find_one({
            "inviter_user_id": current_user.id,
            "invite_type": "add_email_account",
            "invited_email": account.get("email", "").lower(),
            "status": "used",
            "added_email_account_id": str(account["_id"])
        })
        
        if invitation:
            invited_by_current_user.append(account)
            print(f"   📧 Found invited account: {account.get('email')} (Owner: {account.get('user_id')})")
        # Remove the else clause to avoid confusing log messages
    
    # Combine owned and invited accounts
    all_accounts = owned_accounts + invited_by_current_user
    
    print(f"📧 Email accounts for user {current_user.id}:")
    print(f"   Owned accounts: {len(owned_accounts)}")
    print(f"   Invited accounts: {len(invited_by_current_user)}")
    print(f"   Total accounts: {len(all_accounts)}")
    
    email_accounts = []
    for account in all_accounts:
        if account is None or "_id" not in account:
            continue
            
        # Determine if this is an owned or invited account
        is_owned = account.get("user_id") == current_user.id
        account_type = "owned" if is_owned else "invited"
        
        # Prepare account data with required fields
        account_data = {
            "id": str(account["_id"]),
            "email": account.get("email", ""),
            "provider": account.get("provider", "gmail"),
            "is_active": account.get("is_active", True),
            "status": account.get("status", "connected"),
            "last_sync_at": account.get("last_sync_at"),
            "created_at": account.get("created_at", datetime.utcnow()),
            "updated_at": account.get("updated_at", datetime.utcnow()),
            "sync_frequency": account.get("sync_frequency", 1),
            "scan_invoices": account.get("scan_invoices", True),
            "scan_receipts": account.get("scan_receipts", False),
            "auto_categorize": account.get("auto_categorize", True),
            "account_type": account_type,  # Add account type for frontend
            "owner_user_id": account.get("user_id")  # Add owner info
        }
        email_accounts.append(EmailAccountResponse(**account_data))
        
        print(f"   - {account.get('email')} ({account_type}) - Owner: {account.get('user_id')}")
    
    return EmailAccountListResponse(
        email_accounts=email_accounts,
        total=len(email_accounts)
    )

@router.get("/{account_id}", response_model=EmailAccountResponse)
async def get_email_account(
    account_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get specific email account"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account or "_id" not in account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Prepare account data with required fields
    account_data = {
        "id": str(account["_id"]),
        "email": account.get("email", ""),
        "provider": account.get("provider", "gmail"),
        "is_active": account.get("is_active", True),
        "status": account.get("status", "connected"),
        "last_sync_at": account.get("last_sync_at"),
        "created_at": account.get("created_at", datetime.utcnow())
    }
    return EmailAccountResponse(**account_data)

@router.put("/{account_id}")
async def update_email_account(
    account_id: str,
    update_data: UpdateEmailAccountRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Update email account settings"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    # Check if account exists and belongs to user
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account or "_id" not in account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Update account
    update_dict = update_data.dict(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()
    
    await mongodb.db["email_accounts"].update_one(
        {"_id": object_id},
        {"$set": update_dict}
    )
    
    return {"message": "Email account updated successfully"}

@router.delete("/{account_id}")
async def delete_email_account(
    account_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Delete email account and its invoices"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    # Check if account exists and belongs to user
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account or "_id" not in account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Delete related invoices
    await mongodb.db["invoices"].delete_many({"email_account_id": str(object_id)})
    # Delete account
    await mongodb.db["email_accounts"].delete_one({"_id": object_id})
    
    return {"message": "Email account and related invoices deleted successfully"}

@router.post("/{account_id}/sync")
async def sync_email_account(
    account_id: str,
    background_tasks: BackgroundTasks,
    current_user: UserModel = Depends(get_current_user)
):
    """Start email sync for account with real invoice processing"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    # Check if account exists and belongs to user
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account or "_id" not in account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Update sync status to processing
    await mongodb.db["email_accounts"].update_one(
        {"_id": object_id},
        {"$set": {
            "status": "processing",
            "updated_at": datetime.utcnow()
        }}
    )
    
    # Start background sync task
    background_tasks.add_task(
        process_email_sync_background,
        current_user.id,
        account_id
    )
    
    return {
        "message": "Email sync started", 
        "account_id": account_id,
        "status": "processing"
    }

async def process_email_sync_background(user_id: str, account_id: str):
    """Background task for email sync processing"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
        
        # Fetch selected group emails for the user (if any)
        # For now, fetch all group emails for the user from Google Groups
        from services.google_groups_service import GoogleGroupsService
        email_account = await mongodb.db["email_accounts"].find_one({
            "_id": object_id,
            "user_id": user_id
        })
        group_emails = []
        if email_account:
            groups_service = GoogleGroupsService()
            if groups_service.authenticate(email_account["access_token"], email_account.get("refresh_token")):
                groups = groups_service.get_user_groups(email_account["email"])
                group_emails = [g["email"] for g in groups]
        
        # Process emails using invoice processor (now uses user preferred vendors)
        invoice_processor = InvoiceProcessor()  # Create fresh instance with database connection
        result = await invoice_processor.process_user_preferred_vendors(user_id, account_id)
        
        # Update account status based on result
        status = "connected" if result["success"] else "error"
        
        await mongodb.db["email_accounts"].update_one(
            {"_id": object_id},
            {"$set": {
                "status": status,
                "last_sync_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Log sync results
        if result["success"]:
            logger.info(f"Email sync completed for account {account_id}: {result['invoices_found']} invoices found")
        else:
            logger.error(f"Email sync failed for account {account_id}: {result['error']}")
            
    except Exception as e:
        logger.error(f"Background email sync error for account {account_id}: {str(e)}")
        
        # Update account status to error
        try:
            object_id = ObjectId(account_id)
            ensure_db()
            await mongodb.db["email_accounts"].update_one(
                {"_id": object_id},
                {"$set": {
                    "status": "error",
                    "updated_at": datetime.utcnow()
                }}
            )
        except Exception:
            pass

@router.get("/{account_id}/sync-status")
async def get_sync_status(
    account_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get real-time sync status for an email account using Celery"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    # Get account
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Get active task for this account
    active_task = await task_manager.get_active_task_for_account(account_id)
    
    if not active_task:
        return {
            "status": account.get("status", "idle"),
            "message": "No sync in progress",
            "last_sync": account.get("last_sync_at"),
            "account_id": account_id
        }
    
    # Get detailed task status
    task_status = await task_manager.get_task_status(active_task["task_id"])
    
    return {
        "account_id": account_id,
        "task_id": active_task["task_id"],
        "status": task_status.get("status", "unknown"),
        "progress": task_status.get("progress", 0),
        "current_status": task_status.get("current_status", ""),
        "estimated_duration": task_status.get("estimated_duration"),
        "actual_duration": task_status.get("actual_duration"),
        "created_at": task_status.get("created_at"),
        "updated_at": task_status.get("updated_at"),
        "result": task_status.get("result"),
        "error": task_status.get("error")
    }

@router.post("/{account_id}/sync-inbox")
async def sync_inbox_only(
    account_id: str,
    sync_request: SyncInboxRequest = SyncInboxRequest(),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Sync inbox emails using Celery for non-blocking processing
    """
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Update status to processing
    await mongodb.db["email_accounts"].update_one(
        {"_id": object_id},
        {"$set": {"status": "processing", "updated_at": datetime.utcnow()}}
    )
    
    # Start Celery task
    try:
        result = await task_manager.start_email_scan(
            user_id=current_user.id,
            account_id=account_id,
            scan_type="inbox",
            months=sync_request.months
        )
        
        return {
            "message": result["message"],
            "account_id": account_id,
            "task_id": result["task_id"],
            "status": "processing",
            "scan_months": sync_request.months,
            "estimated_duration": result["estimated_duration"]
        }
        
    except Exception as e:
        # Revert status on error
        await mongodb.db["email_accounts"].update_one(
            {"_id": object_id},
            {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start email scan: {str(e)}"
        )

@router.post("/{account_id}/sync-groups")
async def sync_groups_only(
    account_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Start groups-only email sync for account using Celery"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account or "_id" not in account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Update status to processing
    await mongodb.db["email_accounts"].update_one(
        {"_id": object_id},
        {"$set": {"status": "processing", "updated_at": datetime.utcnow()}}
    )
    
    # Start Celery task
    try:
        result = await task_manager.start_email_scan(
            user_id=current_user.id,
            account_id=account_id,
            scan_type="groups",
            months=3  # Default 3 months for groups
        )
        
        return {
            "message": "Groups sync started",
            "account_id": account_id,
            "task_id": result["task_id"],
            "status": "processing",
            "estimated_duration": result["estimated_duration"]
        }
        
    except Exception as e:
        # Revert status on error
        await mongodb.db["email_accounts"].update_one(
            {"_id": object_id},
            {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start groups sync: {str(e)}"
        )

# Background task for user preferred vendors scanning
async def process_user_preferred_vendors_background(user_id: str, account_id: str, days_back: int):
    """Background task for processing emails using user preferred vendors"""
    try:
        logger.info(f"🚀 Starting background vendor scan for account {account_id}")
        
        # Create invoice processor
        processor = InvoiceProcessor()
        
        # Process using user preferred vendors
        result = await processor.process_user_preferred_vendors(
            user_id=user_id,
            email_account_id=account_id,
            days_back=days_back
        )
        
        # Update account status based on result
        object_id = ObjectId(account_id)
        if result["success"]:
            await mongodb.db["email_accounts"].update_one(
                {"_id": object_id},
                {"$set": {"status": "active", "updated_at": datetime.utcnow()}}
            )
        else:
            await mongodb.db["email_accounts"].update_one(
                {"_id": object_id},
                {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
            )
            
        logger.info(f"✅ Background vendor scan completed: {result}")
        
    except Exception as e:
        logger.error(f"❌ Error in background vendor scan: {str(e)}")
        await mongodb.db["email_accounts"].update_one(
            {"_id": ObjectId(account_id)},
            {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
        )

# Background tasks for inbox-only and groups-only sync
async def process_email_sync_background_inbox(user_id: str, account_id: str):
    """Background task for processing emails - now runs as async task"""
    try:
        logger.info(f"🚀 Starting background inbox sync for account {account_id}")
        logger.info(f"🔍 Debug: user_id={user_id}, account_id={account_id}")
        
        object_id = ObjectId(account_id)
        
        # Create invoice processor using factory
        logger.info(f"🏭 Creating invoice processor...")
        logger.info(f"🔍 Debug: About to call create_invoice_processor()")
        
        invoice_processor = create_invoice_processor()
        
        logger.info(f"🔍 Debug: Invoice processor created: {invoice_processor is not None}")
        
        if not invoice_processor:
            logger.error(f"❌ Failed to create invoice processor for account {account_id}")
            await mongodb.db["email_accounts"].update_one(
                {"_id": object_id},
                {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
            )
            return
        
        logger.info(f"📧 Starting email processing for user {user_id}")
        logger.info(f"🔍 Debug: About to call process_user_emails()")
        
        # Add timeout to prevent hanging indefinitely
        try:
            result = await asyncio.wait_for(
                invoice_processor.process_user_emails(user_id, account_id, group_emails=None),
                timeout=300  # 5 minute timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"⏰ Email processing timeout after 5 minutes for account {account_id}")
            await mongodb.db["email_accounts"].update_one(
                {"_id": object_id},
                {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
            )
            return
        
        status = "connected" if result["success"] else "error"
        await mongodb.db["email_accounts"].update_one(
            {"_id": object_id},
            {"$set": {"status": status, "last_sync_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )
        
        if result["success"]:
            logger.info(f"✅ Inbox-only sync completed for account {account_id}: {result['processed_count']} invoices processed")
        else:
            logger.error(f"❌ Inbox-only sync failed for account {account_id}: {result['error']}")
            
    except Exception as e:
        logger.error(f"❌ Inbox-only sync error for account {account_id}: {str(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        
        try:
            object_id = ObjectId(account_id)
            ensure_db()
            await mongodb.db["email_accounts"].update_one(
                {"_id": object_id},
                {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
            )
        except Exception:
            pass

async def process_email_sync_background_groups(user_id: str, account_id: str):
    """🚨 UPDATED: Background task for processing group emails with new validation system"""
    ensure_db()
    try:
        logger.info(f"🚀 Starting groups sync with new validation system for account {account_id}")
        
        object_id = ObjectId(account_id)
        
        # 🚨 NEW: Use the same user preferred vendors approach
        invoice_processor = InvoiceProcessor()
        result = await invoice_processor.process_user_preferred_vendors(
            user_id=user_id,
            email_account_id=account_id,
            days_back=90  # Default to 90 days for groups
        )
        
        # Update status based on result
        status = "connected" if result["success"] else "error"
        await mongodb.db["email_accounts"].update_one(
            {"_id": object_id},
            {"$set": {
                "status": status,
                "last_sync_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result["success"]:
            logger.info(f"✅ Groups sync completed for account {account_id}:")
            logger.info(f"   📧 Emails processed: {result.get('processed_count', 0)}")
            logger.info(f"   💰 Invoices found: {result.get('invoices_found', 0)}")
            logger.info(f"   🏢 Vendors processed: {result.get('vendors_processed', 0)}")
        else:
            logger.error(f"❌ Groups sync failed for account {account_id}: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"❌ Error in groups sync: {str(e)}")
        try:
            object_id = ObjectId(account_id)
            ensure_db()
            await mongodb.db["email_accounts"].update_one(
                {"_id": object_id},
                {"$set": {"status": "error", "updated_at": datetime.utcnow()}}
            )
        except Exception:
            pass 

# New Celery-based task management endpoints

@router.post("/{account_id}/cancel-scan")
async def cancel_email_scan(
    account_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Cancel an active email scan task"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    # Check if account exists and belongs to user
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Get active task for this account
    active_task = await task_manager.get_active_task_for_account(account_id)
    
    if not active_task:
        return {
            "message": "No active scan found for this account",
            "account_id": account_id,
            "status": "no_active_scan"
        }
    
    # Cancel the task
    cancel_result = await task_manager.cancel_task(active_task["task_id"])
    
    # Update account status
    await mongodb.db["email_accounts"].update_one(
        {"_id": object_id},
        {"$set": {"status": "connected", "updated_at": datetime.utcnow()}}
    )
    
    return {
        "message": "Email scan cancelled successfully",
        "account_id": account_id,
        "task_id": active_task["task_id"],
        "status": "cancelled"
    }

@router.get("/{account_id}/task-history")
async def get_task_history(
    account_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: UserModel = Depends(get_current_user)
):
    """Get task history for an email account"""
    ensure_db()
    try:
        object_id = ObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID format"
        )
    
    # Check if account exists and belongs to user
    account = await mongodb.db["email_accounts"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Get task history for this account
    tasks = await mongodb.db["scanning_tasks"].find(
        {"account_id": account_id}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    return {
        "account_id": account_id,
        "tasks": tasks,
        "total": len(tasks)
    }

@router.get("/tasks/my-tasks")
async def get_my_tasks(
    limit: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(get_current_user)
):
    """Get all tasks for the current user"""
    ensure_db()
    
    # Get user's tasks
    tasks = await task_manager.get_user_tasks(current_user.id, limit)
    
    return {
        "user_id": current_user.id,
        "tasks": tasks,
        "total": len(tasks)
    }

@router.get("/tasks/{task_id}/status")
async def get_task_status_by_id(
    task_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get status of a specific task by task ID"""
    ensure_db()
    
    # Get task status
    task_status = await task_manager.get_task_status(task_id)
    
    if "error" in task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=task_status["error"]
        )
    
    # Verify task belongs to user
    task_record = await mongodb.db["scanning_tasks"].find_one({"task_id": task_id})
    if not task_record or task_record["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this task"
        )
    
    return task_status

# Remove the old sync-vendor-emails endpoint - now using vendor preferences system
# The new approach is in /api/vendors/scan-selected 
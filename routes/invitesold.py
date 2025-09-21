from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
import logging
from bson import ObjectId
from core.database import mongodb
from core.jwt import get_current_user
from models.user import UserModel
from models.invite import InviteModel
from schemas.invite import (
    CreateInviteRequest,
    CreateEmailAccountInviteRequest,
    CreateInviteResponse,
    AcceptInviteRequest,
    AcceptInviteResponse,
    InviteListResponse,
    InviteResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invites", tags=["invites"])

@router.post("/", response_model=CreateInviteResponse)
async def create_invite(
    invite_data: CreateInviteRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Create a new invite link"""
    try:
        # Verify email account belongs to user
        email_account = await mongodb.db["email_accounts"].find_one({
            "_id": ObjectId(invite_data.email_account_id),
            "user_id": current_user.id
        })
        
        if not email_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email account not found"
            )
        
        # Generate invite token
        invite_token = secrets.token_urlsafe(32)
        
        # Calculate expiration
        expires_in_hours = invite_data.expires_in_hours or 24
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        # Create invite
        invite = InviteModel(
            inviter_user_id=current_user.id,
            invite_type="share_access",
            email_account_id=invite_data.email_account_id,
            invite_token=invite_token,
            status="active",
            expires_at=expires_at
        )
        
        # Insert invite
        result = await mongodb.db["invites"].insert_one(invite.dict(exclude={'id'}))
        invite.id = str(result.inserted_id)
        
        # Generate invite URL
        invite_url = f"http://localhost:5173/invite/{invite_token}"
        
        return CreateInviteResponse(
            success=True,
            invite_link=InviteResponse(**invite.dict()),
            invite_url=invite_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating invite: {str(e)}"
        )

@router.post("/email-account", response_model=CreateInviteResponse)
async def create_email_account_invite(
    invite_data: CreateEmailAccountInviteRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Create an invite for someone to add their email account to your system"""
    try:
        # Generate invite token
        invite_token = secrets.token_urlsafe(32)
        
        # Calculate expiration
        expires_in_hours = invite_data.expires_in_hours or 24
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        # Create invite
        invite = InviteModel(
            inviter_user_id=current_user.id,
            invite_type="add_email_account",
            invited_email=invite_data.invited_email,
            invite_token=invite_token,
            status="active",
            expires_at=expires_at
        )
        
        # Insert invite
        result = await mongodb.db["invites"].insert_one(invite.dict(exclude={'id'}))
        invite.id = str(result.inserted_id)
        
        # Send invitation email
        try:
            from services.email_service import EmailService
            
            email_service = EmailService()
            inviter_name = current_user.name or current_user.email.split('@')[0]
            
            logger.info(f"📧 Sending invitation email to {invite_data.invited_email}")
            logger.info(f"   Inviter: {inviter_name}")
            logger.info(f"   Token: {invite_token[:20]}...")
            
            email_sent = email_service.send_invitation_email(
                invited_email=invite_data.invited_email,
                inviter_name=inviter_name,
                invite_token=invite_token,
                expires_at=expires_at
            )
            
            if email_sent:
                logger.info(f"✅ Invitation email sent successfully to {invite_data.invited_email}")
            else:
                logger.warning(f"⚠️ Failed to send invitation email to {invite_data.invited_email}")
                logger.warning("   The invitation was created but email delivery failed")
                
        except ImportError as import_error:
            logger.error(f"❌ Could not import EmailService: {str(import_error)}")
            logger.error("   Email service not available - invitation created without email")
        except Exception as email_error:
            logger.error(f"❌ Error sending invitation email: {str(email_error)}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            logger.error("   The invitation was created but email delivery failed")
            # Continue even if email fails - the invite URL is still generated
        
        # Generate invite URL (fallback)
        invite_url = f"http://localhost:5173/invite/add-email/{invite_token}"
        
        return CreateInviteResponse(
            success=True,
            invite_link=InviteResponse(**invite.dict()),
            invite_url=invite_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating email account invite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating email account invite: {str(e)}"
        )

@router.get("/", response_model=InviteListResponse)
async def get_invites(
    current_user: UserModel = Depends(get_current_user)
):
    """Get all invite links for the current user"""
    try:
        invites_data = await mongodb.db["invites"].find({
            "inviter_user_id": current_user.id
        }).to_list(length=None)
        
        invites = []
        for invite_data in invites_data:
            invite_data['id'] = str(invite_data['_id'])
            del invite_data['_id']  # Remove ObjectId field to avoid validation error
            invites.append(InviteResponse(**invite_data))
        
        return InviteListResponse(
            invites=invites,
            total=len(invites)
        )
        
    except Exception as e:
        logger.error(f"Error fetching invites: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching invites: {str(e)}"
        )


@router.get("/validate/{token}")
async def validate_invite_token(
    token: str
):
    """Validate an invite token - public endpoint"""
    try:
        invite = await mongodb.db["invites"].find_one({
            "invite_token": token,
            "status": "active"
        })
        
        if not invite:
            return {
                "valid": False,
                "message": "Invalid invite link"
            }
        
        # Check if invite is expired
        if datetime.utcnow() > invite["expires_at"]:
            # Update invite status to expired
            await mongodb.db["invites"].update_one(
                {"_id": invite["_id"]},
                {"$set": {"status": "expired"}}
            )
            return {
                "valid": False,
                "message": "Invite link has expired"
            }
        
        # Handle different invite types
        invite_type = invite.get("invite_type", "share_access")
        
        if invite_type == "share_access":
            # Get email account details for share access invites
            email_account = await mongodb.db["email_accounts"].find_one({
                "_id": ObjectId(invite["email_account_id"])
            })
            
            if not email_account:
                return {
                    "valid": False,
                    "message": "Email account not found"
                }
            
            return {
                "valid": True,
                "message": "Valid invite link",
                "invite_type": "share_access",
                "email_account": {
                    "id": str(email_account["_id"]),
                    "email": email_account["email"],
                    "provider": email_account["provider"]
                },
                "expires_at": invite["expires_at"]
            }
        
        elif invite_type == "add_email_account":
            # For add email account invites, we don't need existing email account details
            return {
                "valid": True,
                "message": "Valid email account invite link",
                "invite_type": "add_email_account",
                "invited_email": invite.get("invited_email"),
                "expires_at": invite["expires_at"],
                "inviter_user_id": str(invite.get("inviter_user_id")),
                "invite_id": str(invite.get("_id"))
            }
        
        else:
            return {
                "valid": False,
                "message": "Unknown invite type"
            }
        

        
    except Exception as e:
        logger.error(f"Error validating invite token: {str(e)}")
        return {
            "valid": False,
            "message": "Error validating invite link"
        }

@router.get("/{invite_id}", response_model=InviteResponse)
async def get_invite(
    invite_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get a specific invite link"""
    try:
        object_id = ObjectId(invite_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite ID format"
        )
    
    invite = await mongodb.db["invites"].find_one({
        "_id": object_id,
        "inviter_user_id": current_user.id
    })
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found"
        )
    
    invite['id'] = str(invite['_id'])
    return InviteResponse(**invite)

@router.delete("/{invite_id}")
async def delete_invite(
    invite_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Delete an invite link"""
    try:
        object_id = ObjectId(invite_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite ID format"
        )
    
    # Check if invite exists and belongs to user
    invite = await mongodb.db["invites"].find_one({
        "_id": object_id,
        "inviter_user_id": current_user.id
    })
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found"
        )
    
    # Delete invite
    await mongodb.db["invites"].delete_one({"_id": object_id})
    
    return {"message": "Invite deleted successfully"}

# Move the accept-public route before the accept route to avoid route conflicts
# More specific routes should come before more general ones

@router.post("/accept-public", response_model=AcceptInviteResponse)
async def accept_invite_public(
    accept_data: AcceptInviteRequest
):
    """Accept an invite link publicly (no authentication required)"""
    try:
        # Find invite by token
        invite = await mongodb.db["invites"].find_one({
            "invite_token": accept_data.invite_token,
            "status": "active"
        })
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired invite link"
            )
        
        # Check if invite is expired
        if datetime.utcnow() > invite["expires_at"]:
            # Update invite status to expired
            await mongodb.db["invites"].update_one(
                {"_id": invite["_id"]},
                {"$set": {"status": "expired"}}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite link has expired"
            )
        
        # Handle different invite types
        invite_type = invite.get("invite_type", "share_access")
        
        if invite_type == "add_email_account":
            # For add_email_account invites, mark as ready for OAuth
            # The actual user will be determined during OAuth flow
            
            # Update invite status to ready_for_oauth
            await mongodb.db["invites"].update_one(
                {"_id": invite["_id"]},
                {
                    "$set": {
                        "status": "ready_for_oauth",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            return AcceptInviteResponse(
                success=True,
                message="Invitation accepted! Please log in with Google to connect your email account.",
                email_account_id=None
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite type requires authentication"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting public invite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error accepting invite: {str(e)}"
        )

@router.post("/accept", response_model=AcceptInviteResponse)
async def accept_invite(
    accept_data: AcceptInviteRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Accept an invite link (requires authentication)"""
    try:
        # Find invite by token
        invite = await mongodb.db["invites"].find_one({
            "invite_token": accept_data.invite_token,
            "status": "active"
        })
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired invite link"
            )
        
        # Check if invite is expired
        if datetime.utcnow() > invite["expires_at"]:
            # Update invite status to expired
            await mongodb.db["invites"].update_one(
                {"_id": invite["_id"]},
                {"$set": {"status": "expired"}}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite link has expired"
            )
        
        # Handle different invite types
        invite_type = invite.get("invite_type", "share_access")
        
        if invite_type == "share_access":
            # Check if user already has access to this email account
            existing_access = await mongodb.db["email_accounts"].find_one({
                "_id": ObjectId(invite["email_account_id"]),
                "user_id": current_user.id
            })
            
            if existing_access:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You already have access to this email account"
                )
            
            # Update invite status to used
            await mongodb.db["invites"].update_one(
                {"_id": invite["_id"]},
                {
                    "$set": {
                        "status": "used",
                        "used_at": datetime.utcnow(),
                        "used_by_user_id": current_user.id
                    }
                }
            )
            
            return AcceptInviteResponse(
                success=True,
                message="Invite accepted successfully",
                email_account_id=invite["email_account_id"]
            )
        
        elif invite_type == "add_email_account":
            # For add_email_account invites, we just mark as ready for email connection
            # The actual email account will be added when the user connects their OAuth
            
            # Allow any logged-in user to accept the invite
            # The email validation will happen during OAuth when the actual email account is connected
            
            # Update invite status to used
            await mongodb.db["invites"].update_one(
                {"_id": invite["_id"]},
                {
                    "$set": {
                        "status": "used",
                        "used_at": datetime.utcnow(),
                        "used_by_user_id": current_user.id
                    }
                }
            )
            
            return AcceptInviteResponse(
                success=True,
                message="Email account invite accepted! Please connect your email account to complete the setup.",
                email_account_id=None
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown invite type"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error accepting invite: {str(e)}"
        )


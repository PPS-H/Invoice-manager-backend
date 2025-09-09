from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime
import os
import logging
from bson import ObjectId
from core.database import mongodb
from core.jwt import get_current_user
from models.user import UserModel
from models.group import GroupModel, GroupType
from schemas.group import (
    CreateGroupRequest,
    UpdateGroupRequest,
    GroupResponse,
    GroupListResponse
)
from services.google_groups_service import GoogleGroupsService
from models.google_group import GoogleGroupModel
from models.email_account import EmailAccountModel
from services.email_scanner import EnhancedEmailScanner as EmailScanner
from services.invoice_processor import InvoiceProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/groups", tags=["groups"])

@router.post("/", response_model=GroupResponse)
async def create_group(
    group_data: CreateGroupRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Create a new group"""
    # Check if group with same name exists
    existing_group = await mongodb.db["groups"].find_one({
        "user_id": current_user.id,
        "name": group_data.name
    })
    
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group with this name already exists"
        )
    
    # Create group
    group_dict = group_data.dict()
    group_dict["user_id"] = current_user.id
    group_dict["created_at"] = datetime.utcnow()
    group_dict["updated_at"] = datetime.utcnow()
    
    result = await mongodb.db["groups"].insert_one(group_dict)
    group_dict["_id"] = str(result.inserted_id)
    
    return GroupResponse(**group_dict)

@router.get("/", response_model=GroupListResponse)
async def get_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(get_current_user)
):
    """Get user's groups"""
    skip = (page - 1) * page_size
    
    # Get groups with invoice count
    pipeline = [
        {"$match": {"user_id": current_user.id}},
        {"$lookup": {
            "from": "invoices",
            "localField": "_id",
            "foreignField": "group_id",
            "as": "invoices"
        }},
        {"$addFields": {
            "invoice_count": {"$size": "$invoices"}
        }},
        {"$project": {"invoices": 0}},
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": page_size}
    ]
    
    groups = await mongodb.db["groups"].aggregate(pipeline).to_list(length=None)
    
    # Get total count
    total = await mongodb.db["groups"].count_documents({"user_id": current_user.id})
    
    # Convert ObjectIds to strings
    for group in groups:
        group["id"] = str(group["_id"])
        del group["_id"]
    
    return GroupListResponse(
        groups=[GroupResponse(**group) for group in groups],
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get a specific group"""
    try:
        object_id = ObjectId(group_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format"
        )
    
    group = await mongodb.db["groups"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    group["id"] = str(group["_id"])
    del group["_id"]
    
    return GroupResponse(**group)

@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str,
    group_data: UpdateGroupRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Update a group"""
    try:
        object_id = ObjectId(group_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format"
        )
    
    # Check if group exists
    existing_group = await mongodb.db["groups"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not existing_group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check for name conflict if name is being updated
    if group_data.name and group_data.name != existing_group["name"]:
        name_conflict = await mongodb.db["groups"].find_one({
            "user_id": current_user.id,
            "name": group_data.name,
            "_id": {"$ne": object_id}
        })
        
        if name_conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group with this name already exists"
            )
    
    # Update group
    update_data = group_data.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    
    await mongodb.db["groups"].update_one(
        {"_id": object_id},
        {"$set": update_data}
    )
    
    # Get updated group
    updated_group = await mongodb.db["groups"].find_one({"_id": object_id})
    updated_group["id"] = str(updated_group["_id"])
    del updated_group["_id"]
    
    return GroupResponse(**updated_group)

@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Delete a group"""
    try:
        object_id = ObjectId(group_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format"
        )
    
    # Check if group exists
    existing_group = await mongodb.db["groups"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not existing_group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Remove group from invoices
    await mongodb.db["invoices"].update_many(
        {"group_id": object_id},
        {"$unset": {"group_id": ""}}
    )
    
    # Delete group
    await mongodb.db["groups"].delete_one({"_id": object_id})
    
    return {"message": "Group deleted successfully"}

# Google Groups API endpoints
@router.get("/google/list")
async def get_google_groups(
    current_user: UserModel = Depends(get_current_user)
):
    """Get user's Google Groups"""
    try:
        # Get user's email account for authentication
        email_account = await mongodb.db["email_accounts"].find_one({
            "user_id": current_user.id
        })
        
        if not email_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No email account found. Please connect your Gmail account first."
            )
        
        # Initialize Google Groups service
        groups_service = GoogleGroupsService()
        
        # Authenticate with Google
        if not groups_service.authenticate(
            email_account["access_token"],
            email_account.get("refresh_token")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with Google Groups API"
            )
        
        # Get user's groups
        groups = groups_service.get_user_groups(current_user.email)
        
        return {
            "groups": groups,
            "total": len(groups)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error fetching Google Groups: {error_msg}")
        
        # Check if it's a 403 error (insufficient permissions)
        if "403" in error_msg or "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to access Google Groups. Please reconnect your account with the required permissions."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch Google Groups"
            )

from pydantic import BaseModel

class ScanGroupsRequest(BaseModel):
    group_emails: List[str]

@router.post("/google/scan")
async def scan_google_groups(
    request: ScanGroupsRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Scan specific Google Groups for invoices"""

    try:
        group_emails = request.group_emails
        if not group_emails:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No groups selected for scanning"
            )

        # Get user's email account
        email_account = await mongodb.db["email_accounts"].find_one({
            "user_id": current_user.id
        })
        if not email_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No email account found. Please connect your Gmail account first."
            )

        # Authenticate with Gmail
        email_scanner = EmailScanner()
        if not email_scanner.authenticate(
            email_account.get("access_token", ""),
            email_account.get("refresh_token")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with Gmail"
            )

        # 🚨 UPDATED: Use new validation system and user preferences
        logger.info(f"🔄 Groups scanning now using new validation system with user preferences")
        
        # Check if user has selected vendors (required for new system)
        preferences = await mongodb.db["user_vendor_preferences"].find_one({
            "user_id": current_user.id
        })
        
        if not preferences or not preferences.get("selected_vendors"):
            logger.warning(f"⚠️ User {current_user.id} has no vendor preferences - scanning with basic validation only")
        
        # Create invoice processor with validation
        invoice_processor = InvoiceProcessor()
        
        processed_count = 0
        errors = []
        total_emails = 0
        skipped_by_validation = 0
        
        for group_email in group_emails:
            logger.info(f"\n🏢 Processing group: {group_email}")
            
            group_emails_found = email_scanner.search_group_emails([group_email], days_back=90)
            logger.info(f"📧 Found {len(group_emails_found)} emails from group {group_email}")
            total_emails += len(group_emails_found)
            
            for email_index, email_data in enumerate(group_emails_found):
                subject = email_data.get('subject', 'no subject')
                sender = email_data.get('sender', 'unknown')
                message_id = email_data.get('message_id', '')
                email_date = email_data.get('date', 'unknown date')
                
                logger.info(f"\n{'='*50}")
                logger.info(f"📤 PROCESSING GROUP EMAIL {email_index + 1}/{len(group_emails_found)}:")
                logger.info(f"   📨 Subject: {subject[:70]}{'...' if len(subject) > 70 else ''}")
                logger.info(f"   👤 Sender: {sender}")
                logger.info(f"   📅 Date: {email_date}")
                logger.info(f"   🔗 Message ID: {message_id}")
                logger.info(f"   🏢 Group: {group_email}")
                logger.info(f"{'='*50}")
                
                try:
                    # 🚨 NEW: Use the same validation path as inbox scanning
                    invoice_result = await invoice_processor._process_single_invoice(
                        str(current_user.id),
                        str(email_account["_id"]),
                        email_data,
                        source_type="group",
                        source_group_id=None,  # Groups don't need specific IDs for validation
                        source_group_email=group_email
                    )
                    
                    if invoice_result:
                        logger.info(f"✅ INVOICE SAVED FROM GROUP EMAIL!")
                        logger.info(f"   📄 Invoice: {invoice_result.get('invoice_number', 'No #')}")
                        logger.info(f"   💰 Amount: ${invoice_result.get('total_amount', 0)}")
                        logger.info(f"   🏢 Vendor: {invoice_result.get('vendor_name', 'Unknown')}")
                        processed_count += 1
                    else:
                        logger.info(f"⏭️ SKIPPED GROUP EMAIL")
                        logger.info(f"   📝 Reason: Validation failed or not an invoice")
                        skipped_by_validation += 1
                        
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ Error processing email {message_id}: {error_msg}")
                    
                    # Log specific validation failures differently
                    if "Duplicate invoice" in error_msg or "already processed" in error_msg:
                        logger.info(f"📝 Validation blocked duplicate: {message_id}")
                        skipped_by_validation += 1
                    elif "not a genuine invoice" in error_msg:
                        logger.info(f"📝 Validation classified as non-invoice: {message_id}")
                        skipped_by_validation += 1
                    else:
                        errors.append(error_msg)
        
        logger.info(f"\n🎯 GROUPS SCAN SUMMARY:")
        logger.info(f"   📧 Total emails processed: {total_emails}")
        logger.info(f"   ✅ Invoices saved: {processed_count}")
        logger.info(f"   ⏭️ Skipped by validation: {skipped_by_validation}")
        logger.info(f"   ❌ Errors: {len(errors)}")
        return {
            "message": f"Scanned {len(group_emails)} groups with validation system.",
            "processed_count": processed_count,
            "invoices_found": processed_count,
            "total_emails": total_emails,
            "skipped_by_validation": skipped_by_validation,
            "errors": errors,
            "validation_enabled": True,
            "status": "completed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scanning Google Groups: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to scan Google Groups"
        )

# Additional Google Groups API endpoints for frontend
@router.get("/google/db", response_model=List[GoogleGroupModel])
async def get_google_groups_from_db(
    email_account_id: Optional[str] = Query(None),
    current_user: UserModel = Depends(get_current_user)
):
    """Get all Google Groups from database for the current user"""
    try:
        query = {'user_id': current_user.id}
        if email_account_id:
            query['email_account_id'] = email_account_id
        
        # Check if collection exists, if not return empty list
        collections = await mongodb.db.list_collection_names()
        if "google_groups" not in collections:
            return []
        
        groups_data = await mongodb.db["google_groups"].find(query).to_list(length=None)
        groups = []
        for group_data in groups_data:
            group_data['id'] = str(group_data['_id'])
            del group_data['_id']  # Remove the ObjectId field to avoid validation error
            groups.append(GoogleGroupModel(**group_data))
        
        return groups
        
    except Exception as e:
        logger.error(f"Error fetching Google Groups: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching Google Groups: {str(e)}"
        )

@router.get("/google/test")
async def test_google_groups_endpoint(
    current_user: UserModel = Depends(get_current_user)
):
    """Test endpoint to check if Google Groups functionality is working"""
    try:
        collections = await mongodb.db.list_collection_names()
        return {
            "message": "Google Groups endpoint is working",
            "collections": collections,
            "user_id": current_user.id,
            "google_groups_exists": "google_groups" in collections
        }
    except Exception as e:
        logger.error(f"Test endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test endpoint error: {str(e)}"
        )

from pydantic import BaseModel

class SyncGroupsRequest(BaseModel):
    email_account_id: str

@router.post("/google/sync")
async def sync_google_groups_to_db(
    request: SyncGroupsRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Sync Google Groups to database for a specific email account"""
    email_account_id = request.email_account_id
    if not email_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email_account_id is required"
        )
    try:
        # Get email account
        email_account = await mongodb.db["email_accounts"].find_one({
            "_id": ObjectId(email_account_id),
            "user_id": current_user.id
        })
        
        if not email_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email account not found"
            )
        
        # Sync groups
        groups_service = GoogleGroupsService()
        result = await groups_service.sync_groups_to_database(
            user_id=current_user.id,
            email_account_id=email_account_id,
            access_token=email_account.get('access_token'),
            refresh_token=email_account.get('refresh_token')
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing Google Groups: {str(e)}"
        )

@router.post("/google/save-selected")
async def save_selected_groups_to_db(
    email_account_id: str,
    selected_group_ids: List[str],
    current_user: UserModel = Depends(get_current_user)
):
    """Save selected groups for an email account (mark as connected for scanning)"""
    try:
        # Verify email account belongs to user
        email_account = await mongodb.db["email_accounts"].find_one({
            "_id": ObjectId(email_account_id),
            "user_id": current_user.id
        })
        
        if not email_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email account not found"
            )
        
        # Update group connection status
        groups_service = GoogleGroupsService()
        success = await groups_service.update_group_connection_status(
            user_id=current_user.id,
            email_account_id=email_account_id,
            selected_group_ids=selected_group_ids
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save group selection"
            )
        
        # Count connected groups
        connected_count = await mongodb.db["google_groups"].count_documents({
            "user_id": current_user.id,
            "email_account_id": email_account_id,
            "connected": True
        })
        
        total_groups = await mongodb.db["google_groups"].count_documents({
            "user_id": current_user.id,
            "email_account_id": email_account_id
        })
        
        return {
            "success": True,
            "message": f"Successfully updated {connected_count} connected groups",
            "connected_count": connected_count,
            "total_groups": total_groups
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving selected groups: {str(e)}"
        )
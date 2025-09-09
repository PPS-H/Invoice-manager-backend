from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Optional
from datetime import datetime
from bson import ObjectId
import logging

from core.database import mongodb
from models.user_vendor_preferences import (
    UserVendorPreferences, 
    UserVendorPreferencesRequest,
    CustomVendorRequest,
    VendorPreferencesResponse
)
from models.vendor import VendorModel
from models.user import UserModel
from core.jwt import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vendors", tags=["vendors"])

@router.get("/available", response_model=List[VendorModel])
async def get_available_vendors(current_user: UserModel = Depends(get_current_user)):
    """Get all available vendors (global + user's custom vendors)"""
    try:
        # Get global vendors
        global_vendors = await mongodb.db["vendors"].find({
            "is_global": True,
            "is_active": True
        }).to_list(None)
        
        # Get user's custom vendors
        custom_vendors = await mongodb.db["vendors"].find({
            "created_by": current_user.id,
            "is_global": False,
            "is_active": True
        }).to_list(None)
        
        # Combine and return
        all_vendors = global_vendors + custom_vendors
        
        # Convert ObjectIds to strings
        for vendor in all_vendors:
            vendor["_id"] = str(vendor["_id"])
        
        logger.info(f"📋 Retrieved {len(all_vendors)} available vendors for user {current_user.id}")
        return all_vendors
        
    except Exception as e:
        logger.error(f"Error getting available vendors: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving vendors: {str(e)}"
        )

@router.get("/user-preferences", response_model=VendorPreferencesResponse)
async def get_user_vendor_preferences(current_user: UserModel = Depends(get_current_user)):
    """Get user's vendor preferences"""
    try:
        preferences = await mongodb.db["user_vendor_preferences"].find_one(
            {"user_id": current_user.id},
            sort=[("updated_at", -1)]  # Get the most recent preferences
        )
        
        if not preferences:
            # Create default preferences if none exist
            preferences = {
                "user_id": current_user.id,
                "selected_vendors": [],
                "custom_vendors": [],
                "scan_settings": {
                    "days_back": 30,
                    "include_attachments": True,
                    "auto_scan_enabled": False
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await mongodb.db["user_vendor_preferences"].insert_one(preferences)
            preferences["_id"] = result.inserted_id
        
        # Convert ObjectId to string
        preferences["_id"] = str(preferences["_id"])
        
        logger.info(f"📋 Retrieved vendor preferences for user {current_user.id}")
        return VendorPreferencesResponse(
            success=True,
            message="Vendor preferences retrieved successfully",
            data=UserVendorPreferences(**preferences)
        )
        
    except Exception as e:
        logger.error(f"Error getting user vendor preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving preferences: {str(e)}"
        )

@router.post("/preferences", response_model=VendorPreferencesResponse)
async def save_user_vendor_preferences(
    preferences_request: UserVendorPreferencesRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Save user's vendor preferences"""
    try:
        # Get vendor details for selected vendors
        selected_vendors = []
        for vendor_id in preferences_request.selected_vendors:
            vendor = await mongodb.db["vendors"].find_one({"_id": ObjectId(vendor_id)})
            if vendor:
                selected_vendors.append({
                    "vendor_id": str(vendor["_id"]),
                    "vendor_name": vendor["display_name"],
                    "email_domains": vendor.get("typical_email_domains", []),
                    "is_custom": not vendor.get("is_global", True)
                })
        
        # Update or create preferences
        update_data = {
            "user_id": current_user.id,
            "selected_vendors": selected_vendors,
            "custom_vendors": preferences_request.custom_vendors,
            "scan_settings": preferences_request.scan_settings or {
                "days_back": 30,
                "include_attachments": True,
                "auto_scan_enabled": False
            },
            "updated_at": datetime.utcnow()
        }
        
        # Upsert preferences
        result = await mongodb.db["user_vendor_preferences"].update_one(
            {"user_id": current_user.id},
            {"$set": update_data},
            upsert=True
        )
        
        # Update usage count for selected vendors
        for vendor_id in preferences_request.selected_vendors:
            await mongodb.db["vendors"].update_one(
                {"_id": ObjectId(vendor_id)},
                {"$inc": {"usage_count": 1}}
            )
        
        logger.info(f"💾 Saved vendor preferences for user {current_user.id}: {len(selected_vendors)} vendors selected")
        
        return VendorPreferencesResponse(
            success=True,
            message=f"Vendor preferences saved successfully. {len(selected_vendors)} vendors selected.",
            data=UserVendorPreferences(**update_data)
        )
        
    except Exception as e:
        logger.error(f"Error saving user vendor preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving preferences: {str(e)}"
        )

@router.post("/custom", response_model=VendorPreferencesResponse)
async def add_custom_vendor(
    vendor_data: CustomVendorRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Add a custom vendor for the user"""
    try:
        # Create new vendor
        new_vendor = {
            "name": vendor_data.name.lower().replace(" ", "_"),
            "display_name": vendor_data.name,
            "category": vendor_data.category,
            "typical_email_domains": vendor_data.email_domains,
            "typical_email_addresses": [],
            "common_keywords": [],
            "is_active": True,
            "is_global": False,  # User-created vendor
            "created_by": current_user.id,
            "usage_count": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert vendor
        vendor_result = await mongodb.db["vendors"].insert_one(new_vendor)
        new_vendor["_id"] = vendor_result.inserted_id
        
        # Add to user's custom vendors
        custom_vendor = {
            "vendor_id": str(new_vendor["_id"]),
            "vendor_name": new_vendor["display_name"],
            "email_domains": new_vendor["typical_email_domains"],
            "category": new_vendor["category"],
            "is_custom": True,
            "created_at": datetime.utcnow()
        }
        
        # Update user preferences
        await mongodb.db["user_vendor_preferences"].update_one(
            {"user_id": current_user.id},
            {
                "$push": {"custom_vendors": custom_vendor},
                "$set": {"updated_at": datetime.utcnow()}
            },
            upsert=True
        )
        
        logger.info(f"➕ Added custom vendor '{vendor_data.name}' for user {current_user.id}")
        
        return VendorPreferencesResponse(
            success=True,
            message=f"Custom vendor '{vendor_data.name}' added successfully",
            data=None
        )
        
    except Exception as e:
        logger.error(f"Error adding custom vendor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding custom vendor: {str(e)}"
        )

@router.post("/scan-selected")
async def scan_selected_vendor_emails(
    current_user: UserModel = Depends(get_current_user),
    email_account_id: Optional[str] = None
):
    """Scan emails from user's selected vendors using specified email account"""
    try:
        # Get user preferences
        preferences = await mongodb.db["user_vendor_preferences"].find_one({
            "user_id": current_user.id
        })
        
        if not preferences or not preferences.get("selected_vendors"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No vendors selected. Please select vendors first."
            )
        
        # Get user's email account - either specified or default to first connected
        if email_account_id:
            # Use the specified email account
            email_account = await mongodb.db["email_accounts"].find_one({
                "_id": ObjectId(email_account_id),
                "user_id": current_user.id,
                "status": "connected"
            })
            
            if not email_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Specified email account {email_account_id} not found or not accessible"
                )
        else:
            # Get the first connected email account (backward compatibility)
            email_account = await mongodb.db["email_accounts"].find_one({
                "user_id": current_user.id,
                "status": "connected"
            })
            
            if not email_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No connected email account found. Please connect your email account first."
                )
        
        logger.info(f"🔍 Scanning vendors using email account: {email_account.get('email')}")
        logger.info(f"   Account ID: {email_account.get('_id')}")
        logger.info(f"   Provider: {email_account.get('provider')}")
        
        # Import and use invoice processor
        from services.invoice_processor import InvoiceProcessor
        invoice_processor = InvoiceProcessor()
        
        # Process user's preferred vendors
        result = await invoice_processor.process_user_preferred_vendors(
            user_id=current_user.id,
            email_account_id=str(email_account["_id"])
        )
        
        logger.info(f"🔍 Completed vendor email scan for user {current_user.id}: {result}")
        
        return {
            "success": result["success"],
            "message": result.get("message", "Email scan completed"),
            "data": result,
            "email_account_used": {
                "id": str(email_account["_id"]),
                "email": email_account["email"],
                "provider": email_account["provider"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scanning selected vendor emails: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scanning emails: {str(e)}"
        ) 
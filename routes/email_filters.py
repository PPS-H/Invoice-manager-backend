from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timedelta
import logging
from bson import ObjectId
from core.database import mongodb
from core.jwt import get_current_user
from models.user import UserModel
from models.email_filter import EmailFilterModel, VendorIgnoreModel, FilterMode
from schemas.email_filter import (
    CreateEmailFilterRequest,
    UpdateEmailFilterRequest,
    EmailFilterResponse,
    EmailFilterListResponse,
    CreateVendorIgnoreRequest,
    UpdateVendorIgnoreRequest,
    VendorIgnoreResponse,
    VendorIgnoreListResponse,
    PriorityScanRequest,
    PriorityScanResponse
)
from services.invoice_processor import InvoiceProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email-filters", tags=["email-filters"])

# Email Filter Management
@router.post("/", response_model=EmailFilterResponse)
async def create_email_filter(
    filter_data: CreateEmailFilterRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Create a new email filter for targeted scanning"""
    try:
        # Check if filter with same name exists
        existing_filter = await mongodb.db["email_filters"].find_one({
            "user_id": current_user.id,
            "name": filter_data.name
        })
        
        if existing_filter:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filter with this name already exists"
            )
        
        # Create filter
        email_filter = EmailFilterModel(
            user_id=current_user.id,
            **filter_data.dict()
        )
        
        # Insert filter
        result = await mongodb.db["email_filters"].insert_one(email_filter.dict(exclude={'id'}))
        email_filter.id = str(result.inserted_id)
        
        return EmailFilterResponse(**email_filter.dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating email filter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating email filter: {str(e)}"
        )

@router.get("/", response_model=EmailFilterListResponse)
async def get_email_filters(
    current_user: UserModel = Depends(get_current_user)
):
    """Get all email filters for the current user"""
    try:
        filters_data = await mongodb.db["email_filters"].find({
            "user_id": current_user.id
        }).to_list(length=None)
        
        filters = []
        for filter_data in filters_data:
            filter_data['id'] = str(filter_data['_id'])
            del filter_data['_id']
            filters.append(EmailFilterResponse(**filter_data))
        
        return EmailFilterListResponse(
            filters=filters,
            total=len(filters)
        )
        
    except Exception as e:
        logger.error(f"Error fetching email filters: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching email filters: {str(e)}"
        )

@router.put("/{filter_id}", response_model=EmailFilterResponse)
async def update_email_filter(
    filter_id: str,
    update_data: UpdateEmailFilterRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Update an email filter"""
    try:
        object_id = ObjectId(filter_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filter ID format"
        )
    
    # Check if filter exists and belongs to user
    existing_filter = await mongodb.db["email_filters"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not existing_filter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email filter not found"
        )
    
    # Update filter
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.utcnow()
    
    await mongodb.db["email_filters"].update_one(
        {"_id": object_id},
        {"$set": update_dict}
    )
    
    # Return updated filter
    updated_filter = await mongodb.db["email_filters"].find_one({"_id": object_id})
    updated_filter['id'] = str(updated_filter['_id'])
    del updated_filter['_id']
    
    return EmailFilterResponse(**updated_filter)

@router.delete("/{filter_id}")
async def delete_email_filter(
    filter_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Delete an email filter"""
    try:
        object_id = ObjectId(filter_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filter ID format"
        )
    
    # Check if filter exists and belongs to user
    existing_filter = await mongodb.db["email_filters"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not existing_filter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email filter not found"
        )
    
    # Delete filter
    await mongodb.db["email_filters"].delete_one({"_id": object_id})
    
    return {"message": "Email filter deleted successfully"}

# Priority Scanning
@router.post("/scan", response_model=PriorityScanResponse)
async def priority_scan_emails(
    scan_request: PriorityScanRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Run priority scanning for user's selected vendors"""
    try:
        # Get user's email account
        email_account = await mongodb.db["email_accounts"].find_one({
            "user_id": current_user.id,
            "status": "connected"
        })
        
        if not email_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No connected email account found"
            )
        
        # Create invoice processor
        invoice_processor = InvoiceProcessor()
        
        # Run user preferred vendors scanning
        result = await invoice_processor.process_user_preferred_vendors(
            user_id=current_user.id,
            email_account_id=str(email_account["_id"])
        )
        
        return PriorityScanResponse(
            success=result["success"],
            message=result.get("message", "Scanning completed"),
            processed_count=result.get("invoices_found", 0),
            total_emails=result.get("processed_count", 0),
            filter_name="User Selected Vendors"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running priority scan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running priority scan: {str(e)}"
        )

# Vendor Ignore Management
@router.post("/vendors/ignore", response_model=VendorIgnoreResponse)
async def create_vendor_ignore(
    vendor_data: CreateVendorIgnoreRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Add a vendor to the ignore list"""
    try:
        # Check if vendor already ignored
        existing_ignore = await mongodb.db["vendor_ignores"].find_one({
            "user_id": current_user.id,
            "vendor_name": vendor_data.vendor_name
        })
        
        if existing_ignore:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vendor is already in ignore list"
            )
        
        # Create vendor ignore
        vendor_ignore = VendorIgnoreModel(
            user_id=current_user.id,
            **vendor_data.dict()
        )
        
        # Insert vendor ignore
        result = await mongodb.db["vendor_ignores"].insert_one(vendor_ignore.dict(exclude={'id'}))
        vendor_ignore.id = str(result.inserted_id)
        
        return VendorIgnoreResponse(**vendor_ignore.dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vendor ignore: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating vendor ignore: {str(e)}"
        )

@router.get("/vendors/ignore", response_model=VendorIgnoreListResponse)
async def get_ignored_vendors(
    current_user: UserModel = Depends(get_current_user)
):
    """Get all ignored vendors for the current user"""
    try:
        vendors_data = await mongodb.db["vendor_ignores"].find({
            "user_id": current_user.id
        }).to_list(length=None)
        
        vendors = []
        for vendor_data in vendors_data:
            vendor_data['id'] = str(vendor_data['_id'])
            del vendor_data['_id']
            vendors.append(VendorIgnoreResponse(**vendor_data))
        
        return VendorIgnoreListResponse(
            ignored_vendors=vendors,
            total=len(vendors)
        )
        
    except Exception as e:
        logger.error(f"Error fetching ignored vendors: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching ignored vendors: {str(e)}"
        )

@router.delete("/vendors/ignore/{vendor_id}")
async def remove_vendor_ignore(
    vendor_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Remove a vendor from the ignore list"""
    try:
        object_id = ObjectId(vendor_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vendor ID format"
        )
    
    # Check if vendor ignore exists and belongs to user
    existing_ignore = await mongodb.db["vendor_ignores"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not existing_ignore:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor ignore not found"
        )
    
    # Delete vendor ignore
    await mongodb.db["vendor_ignores"].delete_one({"_id": object_id})
    
    return {"message": "Vendor removed from ignore list successfully"} 
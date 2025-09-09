from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.responses import FileResponse
from typing import List, Optional, Dict
from datetime import datetime
import os
import logging
from core.database import mongodb
from core.jwt import get_current_user
from models.user import UserModel
from models.invoice import InvoiceModel, InvoiceStatus
from schemas.invoice import (
    CreateInvoiceRequest,
    UpdateInvoiceRequest,
    InvoiceFilterRequest,
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceStatsResponse
)
from bson import ObjectId

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])

@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    invoice_data: CreateInvoiceRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Create a new invoice"""
    # Verify email account belongs to user
    email_account = await mongodb.db["email_accounts"].find_one({
        "_id": invoice_data.email_account_id,
        "user_id": current_user.id
    })
    
    if not email_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email account not found"
        )
    
    # Create invoice
    invoice = InvoiceModel(
        user_id=current_user.id,
        **invoice_data.dict()
    )
    
    result = await mongodb.db["invoices"].insert_one(invoice.dict(by_alias=True))
    invoice.id = str(result.inserted_id)
    
    return InvoiceResponse(**invoice.dict(by_alias=True))

@router.get("/", response_model=InvoiceListResponse)
@router.get("", response_model=InvoiceListResponse)
async def get_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    vendor_name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[InvoiceStatus] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    amount_min: Optional[float] = Query(None),
    amount_max: Optional[float] = Query(None),
    email_account_id: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None, description="Filter by source: 'email' or 'group'"),
    source_group_email: Optional[str] = Query(None, description="Filter by specific group email"),
    current_user: UserModel = Depends(get_current_user)
):
    """Get invoices with filtering and pagination"""
    import time
    start_time = time.time()
    logger.info(f"🚀 Starting invoice query for user {current_user.id}")
    # Build filter
    filter_query = {"user_id": current_user.id}
    
    if vendor_name:
        filter_query["vendor_name"] = {"$regex": vendor_name, "$options": "i"}
    if category:
        filter_query["category"] = category
    if status:
        filter_query["status"] = status
    if date_from or date_to:
        date_filter = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        filter_query["invoice_date"] = date_filter
    if amount_min or amount_max:
        amount_filter = {}
        if amount_min:
            amount_filter["$gte"] = amount_min
        if amount_max:
            amount_filter["$lte"] = amount_max
        filter_query["total_amount"] = amount_filter
    if email_account_id:
        filter_query["email_account_id"] = email_account_id
    if source_type:
        filter_query["source_type"] = source_type
    if source_group_email:
        filter_query["source_group_email"] = source_group_email
    
    # Get total count
    count_start = time.time()
    total = await mongodb.db["invoices"].count_documents(filter_query)
    logger.info(f"📊 Count query took: {(time.time() - count_start)*1000:.1f}ms")
    
    # Get total amount for all matching invoices (not just current page)
    total_amount_pipeline = [
        {"$match": filter_query},
        {"$group": {
            "_id": None,
            "total_amount": {"$sum": "$total_amount"}
        }}
    ]
    
    agg_start = time.time()
    total_amount_result = await mongodb.db["invoices"].aggregate(total_amount_pipeline).to_list(length=1)
    total_amount = total_amount_result[0]["total_amount"] if total_amount_result else 0.0
    logger.info(f"💰 Aggregation query took: {(time.time() - agg_start)*1000:.1f}ms")
    
    # Get paginated results
    find_start = time.time()
    skip = (page - 1) * page_size
    cursor = mongodb.db["invoices"].find(filter_query).sort("created_at", -1).skip(skip).limit(page_size)
    invoices = await cursor.to_list(length=None)
    logger.info(f"📄 Find query took: {(time.time() - find_start)*1000:.1f}ms")
    
    # Convert to response format
    invoice_responses = []
    for invoice in invoices:
        invoice["id"] = str(invoice["_id"])
        invoice_responses.append(InvoiceResponse(**invoice))
    
    total_pages = (total + page_size - 1) // page_size
    
    total_time = (time.time() - start_time) * 1000
    logger.info(f"✅ Invoice API completed in {total_time:.1f}ms (found {len(invoice_responses)} invoices)")
    
    return InvoiceListResponse(
        invoices=invoice_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        total_amount=total_amount
    )

@router.get("/hierarchy", response_model=Dict)
async def get_invoice_hierarchy(current_user: UserModel = Depends(get_current_user)):
    """Get invoices organized in hierarchical structure: Invoice Manager > Invoices > Emails > Months > Invoices"""
    try:
        # Get all invoices for the user
        invoices = await mongodb.db["invoices"].find({"user_id": current_user.id}).to_list(length=None)
        
        # Organize by email account and month
        hierarchy = {
            "invoice_manager": {
                "invoices": {}
            }
        }
        
        for invoice in invoices:
            # Get email account info
            email_account = await mongodb.db["email_accounts"].find_one({
                "_id": ObjectId(invoice.get("email_account_id"))
            })
            
            if not email_account:
                continue
                
            email_address = email_account.get("email", "unknown@example.com")
            
            # Get month name from invoice date
            invoice_date = invoice.get("invoice_date")
            if invoice_date:
                month_name = invoice_date.strftime("%B %Y")
            else:
                month_name = "Unknown Month"
            
            # Initialize structure if not exists
            if email_address not in hierarchy["invoice_manager"]["invoices"]:
                hierarchy["invoice_manager"]["invoices"][email_address] = {
                    "email": email_address,
                    "months": {}
                }
            
            if month_name not in hierarchy["invoice_manager"]["invoices"][email_address]["months"]:
                hierarchy["invoice_manager"]["invoices"][email_address]["months"][month_name] = {
                    "month": month_name,
                    "invoices": []
                }
            
            # Add invoice to the structure
            invoice_data = {
                "id": str(invoice["_id"]),
                "vendor_name": invoice.get("vendor_name", "Unknown Vendor"),
                "total_amount": invoice.get("total_amount", 0),
                "invoice_date": invoice.get("invoice_date").isoformat() if invoice.get("invoice_date") else None,
                "status": invoice.get("status", "unknown"),
                "invoice_number": invoice.get("invoice_number"),
                "category": invoice.get("category"),
                "source_type": invoice.get("source_type", "email"),
                "source_group_email": invoice.get("source_group_email"),
                "drive_view_link": invoice.get("drive_view_link"),
                "local_file_path": invoice.get("local_file_path")
            }
            
            hierarchy["invoice_manager"]["invoices"][email_address]["months"][month_name]["invoices"].append(invoice_data)
        
        # Sort invoices by date within each month
        for email in hierarchy["invoice_manager"]["invoices"]:
            for month in hierarchy["invoice_manager"]["invoices"][email]["months"]:
                hierarchy["invoice_manager"]["invoices"][email]["months"][month]["invoices"].sort(
                    key=lambda x: x["invoice_date"] or "", reverse=True
                )
        
        return hierarchy
        
    except Exception as e:
        logger.error(f"Error getting invoice hierarchy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting invoice hierarchy: {str(e)}"
        )

@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get specific invoice"""
    invoice = await mongodb.db["invoices"].find_one({
        "_id": invoice_id,
        "user_id": current_user.id
    })
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    invoice["id"] = str(invoice["_id"])
    return InvoiceResponse(**invoice)

@router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    update_data: UpdateInvoiceRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Update invoice"""
    # Check if invoice exists and belongs to user
    invoice = await mongodb.db["invoices"].find_one({
        "_id": invoice_id,
        "user_id": current_user.id
    })
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Update invoice
    update_dict = update_data.dict(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()
    
    await mongodb.db["invoices"].update_one(
        {"_id": invoice_id},
        {"$set": update_dict}
    )
    
    return {"message": "Invoice updated successfully"}

@router.get("/pending-review")
async def get_pending_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(get_current_user)
):
    """Get invoices that need review/confirmation"""
    ensure_db()
    
    skip = (page - 1) * page_size
    
    # Get invoices with low confidence or marked for review
    query = {
        "user_id": current_user.id,
        "$or": [
            {"confidence_score": {"$lt": 0.7}},
            {"needs_review": True},
            {"status": "pending_review"}
        ]
    }
    
    total = await mongodb.db["invoices"].count_documents(query)
    
    invoices = await mongodb.db["invoices"].find(query).sort(
        "created_at", -1
    ).skip(skip).limit(page_size).to_list(None)
    
    # Convert ObjectId to string
    for invoice in invoices:
        invoice["_id"] = str(invoice["_id"])
        invoice["id"] = invoice["_id"]
    
    return {
        "invoices": invoices,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.patch("/{invoice_id}/review")
async def review_invoice(
    invoice_id: str,
    review_data: Dict = Body(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Mark invoice as valid/invalid or update its details"""
    ensure_db()
    
    try:
        object_id = ObjectId(invoice_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID"
        )
    
    # Get the invoice
    invoice = await mongodb.db["invoices"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Update based on review action
    update_data = {"updated_at": datetime.utcnow()}
    
    if "is_valid" in review_data:
        if review_data["is_valid"]:
            update_data["status"] = "approved"
            update_data["needs_review"] = False
        else:
            update_data["status"] = "rejected"
            update_data["rejection_reason"] = review_data.get("reason", "Manually rejected")
    
    # Allow updating vendor name, amount, etc.
    if "vendor_name" in review_data:
        update_data["vendor_name"] = review_data["vendor_name"]
    if "total_amount" in review_data:
        update_data["total_amount"] = review_data["total_amount"]
        update_data["amount"] = review_data["total_amount"]
    if "invoice_date" in review_data:
        update_data["invoice_date"] = datetime.fromisoformat(review_data["invoice_date"])
    
    # Update the invoice
    result = await mongodb.db["invoices"].update_one(
        {"_id": object_id},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        return {"message": "Invoice updated successfully", "invoice_id": invoice_id}
    else:
        return {"message": "No changes made", "invoice_id": invoice_id}

@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Delete an invoice"""
    ensure_db()
    
    try:
        object_id = ObjectId(invoice_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID"
        )
    
    # Delete the invoice
    result = await mongodb.db["invoices"].delete_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if result.deleted_count > 0:
        return {"message": "Invoice deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

@router.get("/stats/summary", response_model=InvoiceStatsResponse)
async def get_invoice_stats(current_user: UserModel = Depends(get_current_user)):
    """Get invoice statistics"""
    import time
    start_time = time.time()
    logger.info(f"🚀 Starting stats query for user {current_user.id}")
    # Get total invoices and amount
    pipeline = [
        {"$match": {"user_id": current_user.id}},
        {"$group": {
            "_id": None,
            "total_invoices": {"$sum": 1},
            "total_amount": {"$sum": "$total_amount"}
        }}
    ]
    
    result = await mongodb.db["invoices"].aggregate(pipeline).to_list(length=1)
    
    if not result:
        return InvoiceStatsResponse(
            total_invoices=0,
            total_amount=0.0,
            currency="USD",
            monthly_totals=[],
            vendor_totals=[],
            category_totals=[]
        )
    
    stats = result[0]
    
    # Get monthly totals
    monthly_pipeline = [
        {"$match": {"user_id": current_user.id}},
        {"$group": {
            "_id": {
                "year": {"$year": "$invoice_date"},
                "month": {"$month": "$invoice_date"}
            },
            "count": {"$sum": 1},
            "amount": {"$sum": "$total_amount"}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}}
    ]
    
    monthly_totals = await mongodb.db["invoices"].aggregate(monthly_pipeline).to_list(length=None)
    
    # Get vendor totals
    vendor_pipeline = [
        {"$match": {"user_id": current_user.id}},
        {"$group": {
            "_id": "$vendor_name",
            "count": {"$sum": 1},
            "amount": {"$sum": "$total_amount"}
        }},
        {"$sort": {"amount": -1}},
        {"$limit": 10}
    ]
    
    vendor_totals = await mongodb.db["invoices"].aggregate(vendor_pipeline).to_list(length=None)
    
    # Get category totals
    category_pipeline = [
        {"$match": {"user_id": current_user.id, "category": {"$ne": None}}},
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "amount": {"$sum": "$total_amount"}
        }},
        {"$sort": {"amount": -1}},
        {"$limit": 10}
    ]
    
    category_totals = await mongodb.db["invoices"].aggregate(category_pipeline).to_list(length=None)
    
    total_time = (time.time() - start_time) * 1000
    logger.info(f"✅ Stats API completed in {total_time:.1f}ms")
    
    return InvoiceStatsResponse(
        total_invoices=stats["total_invoices"],
        total_amount=stats["total_amount"],
        currency="USD",
        monthly_totals=monthly_totals,
        vendor_totals=vendor_totals,
        category_totals=category_totals
    )

@router.get("/{invoice_id}/download")
async def download_invoice_file(
    invoice_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Download invoice file"""
    try:
        object_id = ObjectId(invoice_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID format"
        )
    
    # Get invoice
    invoice = await mongodb.db["invoices"].find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Check if file exists locally
    local_file_path = invoice.get("local_file_path")
    if not local_file_path or not os.path.exists(local_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice file not found"
        )
    
    # Return file
    filename = invoice.get("local_file_name", "invoice.pdf")
    return FileResponse(
        path=local_file_path,
        filename=filename,
        media_type="application/pdf"
    )

@router.post("/process-text-invoice")
async def process_text_based_invoice(
    request: dict,
    current_user: UserModel = Depends(get_current_user)
):
    """Process text-based invoice from email content (no PDF attachment)"""
    try:
        from services.invoice_processor import InvoiceProcessor
        
        # Extract email data from request
        email_data = {
            "subject": request.get("subject", ""),
            "body": request.get("body", ""),
            "sender": request.get("sender", ""),
            "date": request.get("date", ""),
            "message_id": request.get("message_id", ""),
            "invoice_type": "email_content"  # Mark as text-based invoice
        }
        
        # Initialize invoice processor
        processor = InvoiceProcessor()
        
        # Process the text-based invoice
        invoice_info = processor.process_text_based_invoice(email_data)
        
        if not invoice_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract invoice information from email content"
            )
        
        # Save the invoice to database
        invoice = await processor._save_gemini_invoice(
            current_user.id,
            request.get("email_account_id", ""),
            email_data,
            invoice_info,
            invoice_info.get("vendor_name", "Unknown")
        )
        
        # Also save to Google Drive if available
        if invoice and request.get("email_account_id"):
            try:
                drive_info = await processor.save_text_invoice_to_drive(
                    current_user.id,
                    request.get("email_account_id"),
                    email_data,
                    invoice_info
                )
                
                if drive_info:
                    # Update invoice with Drive information
                    await mongodb.db["invoices"].update_one(
                        {"_id": invoice["_id"]},
                        {
                            "$set": {
                                "drive_file_id": drive_info.get("drive_file_id"),
                                "drive_file_name": drive_info.get("drive_file_name"),
                                "drive_folder_id": drive_info.get("drive_folder_id")
                            }
                        }
                    )
                    logger.info(f"✅ Updated invoice with Drive information: {drive_info.get('drive_file_name')}")
                    
            except Exception as e:
                logger.error(f"Error saving to Google Drive: {str(e)}")
                # Continue even if Drive save fails
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save invoice"
            )
        
        return {
            "success": True,
            "message": "Text-based invoice processed successfully",
            "invoice": invoice
        }
        
    except Exception as e:
        logger.error(f"Error processing text-based invoice: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process text-based invoice: {str(e)}"
        ) 
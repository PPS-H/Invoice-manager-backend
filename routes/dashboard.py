from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta
from core.database import mongodb
from core.jwt import get_current_user
from models.user import UserModel

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/stats")
async def get_dashboard_stats(current_user: UserModel = Depends(get_current_user)):
    """Get dashboard statistics for current user"""
    try:
        # Get user's email accounts count
        email_accounts_count = await mongodb.db["email_accounts"].count_documents({
            "user_id": current_user.id
        })
        
        # Get user's invoices count
        invoices_count = await mongodb.db["invoices"].count_documents({
            "user_id": current_user.id
        })
        
        # Get total invoice amount
        pipeline = [
            {"$match": {"user_id": current_user.id}},
            {"$group": {
                "_id": None,
                "total_amount": {"$sum": "$total_amount"}
            }}
        ]
        
        result = await mongodb.db["invoices"].aggregate(pipeline).to_list(length=1)
        total_amount = result[0]["total_amount"] if result else 0
        
        # Get recent invoices (last 5)
        recent_invoices = await mongodb.db["invoices"].find({
            "user_id": current_user.id
        }).sort("created_at", -1).limit(5).to_list(length=None)
        
        # Get recent email accounts
        recent_email_accounts = await mongodb.db["email_accounts"].find({
            "user_id": current_user.id
        }).sort("created_at", -1).limit(3).to_list(length=None)
        
        # Convert ObjectId to string for JSON serialization
        for invoice in recent_invoices:
            invoice["id"] = str(invoice["_id"])
            del invoice["_id"]
        
        for account in recent_email_accounts:
            account["id"] = str(account["_id"])
            del account["_id"]
        
        return {
            "email_accounts_count": email_accounts_count,
            "invoices_count": invoices_count,
            "total_amount": total_amount,
            "recent_invoices": recent_invoices,
            "recent_email_accounts": recent_email_accounts,
            "currency": "USD"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )

@router.get("/activity")
async def get_recent_activity(current_user: UserModel = Depends(get_current_user)):
    """Get recent activity for current user"""
    try:
        # Get recent invoices
        recent_invoices = await mongodb.db["invoices"].find({
            "user_id": current_user.id
        }).sort("created_at", -1).limit(10).to_list(length=None)
        
        # Get recent email account syncs
        recent_syncs = await mongodb.db["email_accounts"].find({
            "user_id": current_user.id,
            "last_sync_at": {"$exists": True}
        }).sort("last_sync_at", -1).limit(5).to_list(length=None)
        
        activity = []
        
        # Add invoice activities
        for invoice in recent_invoices:
            activity.append({
                "type": "invoice",
                "id": str(invoice["_id"]),
                "title": f"Invoice from {invoice['vendor_name']}",
                "description": f"${invoice['total_amount']} - {invoice['status']}",
                "timestamp": invoice["created_at"],
                "amount": invoice["total_amount"]
            })
        
        # Add sync activities
        for sync in recent_syncs:
            activity.append({
                "type": "sync",
                "id": str(sync["_id"]),
                "title": f"Email sync: {sync['email']}",
                "description": f"Last synced: {sync['last_sync_at']}",
                "timestamp": sync["last_sync_at"],
                "email": sync["email"]
            })
        
        # Sort by timestamp
        activity.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "activity": activity[:20]  # Return last 20 activities
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent activity: {str(e)}"
        ) 
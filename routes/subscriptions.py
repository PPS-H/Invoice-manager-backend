"""
Subscription Management API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from datetime import datetime
import stripe
from core.config import settings
from core.jwt import get_current_user
from models.user import UserModel
from models.subscription import SubscriptionModel
from services.subscription_service import SubscriptionService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

@router.get("/my-subscription", response_model=Optional[SubscriptionModel])
async def get_my_subscription(current_user: UserModel = Depends(get_current_user)):
    """
    Get current user's active subscription
    """
    try:
        subscription = await SubscriptionService.get_user_subscription(current_user.id)
        return subscription
    except Exception as e:
        logger.error(f"Error getting user subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscription"
        )

@router.get("/all", response_model=List[SubscriptionModel])
async def get_all_subscriptions(
    current_user: UserModel = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, description="Filter by status (active, canceled, past_due, etc.)"),
    limit: int = Query(50, description="Maximum number of subscriptions to return")
):
    """
    Get all subscriptions (admin only - for now returns user's subscriptions)
    """
    try:
        # For now, just return user's subscriptions
        # In production, add admin role check
        from core.database import mongodb
        
        query = {"user_id": current_user.id}
        if status_filter:
            query["status"] = status_filter
        
        subscriptions = await mongodb.db["subscriptions"].find(query).limit(limit).to_list(length=None)
        
        return [SubscriptionModel(**sub) for sub in subscriptions]
        
    except Exception as e:
        logger.error(f"Error getting subscriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscriptions"
        )

@router.post("/cancel")
async def cancel_subscription(
    subscription_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Cancel a subscription
    """
    try:
        # Get user's subscription
        subscription = await SubscriptionService.get_user_subscription(current_user.id)
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        if subscription.stripe_subscription_id != subscription_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription does not belong to user"
            )
        
        # Cancel subscription in Stripe
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        # Update local database
        cancelled = await SubscriptionService.cancel_subscription(
            current_user.id, 
            subscription_id
        )
        
        if cancelled:
            return {"message": "Subscription will be cancelled at the end of the current period"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel subscription"
            )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )

@router.post("/reactivate")
async def reactivate_subscription(
    subscription_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Reactivate a cancelled subscription
    """
    try:
        # Get user's subscription
        subscription = await SubscriptionService.get_user_subscription(current_user.id)
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )
        
        if subscription.stripe_subscription_id != subscription_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription does not belong to user"
            )
        
        # Reactivate subscription in Stripe
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )
        
        # Update local database
        await SubscriptionService.create_or_update_subscription(
            user_id=subscription.user_id,
            stripe_customer_id=subscription.stripe_customer_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            price_id=subscription.price_id,
            status="active",
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            latest_invoice_id=subscription.latest_invoice_id
        )
        
        return {"message": "Subscription reactivated successfully"}
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error reactivating subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error reactivating subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate subscription"
        )

@router.get("/usage")
async def get_subscription_usage(current_user: UserModel = Depends(get_current_user)):
    """
    Get subscription usage information
    """
    try:
        subscription = await SubscriptionService.get_user_subscription(current_user.id)
        
        if not subscription:
            return {
                "has_subscription": False,
                "message": "No active subscription"
            }
        
        # Get user's email accounts count
        from core.database import mongodb
        email_accounts_count = await mongodb.db["email_accounts"].count_documents({
            "user_id": current_user.id
        })
        
        # Determine limits based on subscription
        limits = {
            "starter": 3,
            "business": 10,
            "professional": 30,
            "enterprise": float('inf')
        }
        
        # Get limit based on price_id or plan name
        limit = limits.get("starter", 3)  # Default to starter
        if "business" in subscription.price_id.lower():
            limit = limits["business"]
        elif "professional" in subscription.price_id.lower():
            limit = limits["professional"]
        elif "enterprise" in subscription.price_id.lower():
            limit = limits["enterprise"]
        
        return {
            "has_subscription": True,
            "subscription": {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "price_id": subscription.price_id
            },
            "usage": {
                "email_connections": {
                    "used": email_accounts_count,
                    "limit": limit if limit != float('inf') else "unlimited",
                    "remaining": "unlimited" if limit == float('inf') else max(0, limit - email_accounts_count)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting subscription usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscription usage"
        )

@router.post("/sync")
async def sync_subscription_from_stripe(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Sync subscription data from Stripe
    """
    try:
        if not current_user.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Stripe customer ID found"
            )
        
        # Get subscriptions from Stripe
        subscriptions = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status="all"
        )
        
        synced_count = 0
        for stripe_sub in subscriptions.data:
            # Convert timestamps
            current_period_start = datetime.fromtimestamp(stripe_sub.current_period_start)
            current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
            
            # Get price ID
            price_id = stripe_sub.items.data[0].price.id
            
            # Sync to database
            await SubscriptionService.create_or_update_subscription(
                user_id=current_user.id,
                stripe_customer_id=stripe_sub.customer,
                stripe_subscription_id=stripe_sub.id,
                price_id=price_id,
                status=stripe_sub.status,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
                latest_invoice_id=stripe_sub.latest_invoice
            )
            synced_count += 1
        
        return {
            "message": f"Synced {synced_count} subscriptions from Stripe",
            "synced_count": synced_count
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error syncing subscriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error syncing subscriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync subscriptions"
        )
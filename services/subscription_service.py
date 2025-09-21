"""
Subscription service for managing user subscriptions in MongoDB
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from core.database import mongodb
from models.subscription import SubscriptionModel
from models.user import UserModel

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Service for managing subscription operations"""
    
    @staticmethod
    async def create_or_update_subscription(
        user_id: str,
        stripe_customer_id: str,
        stripe_subscription_id: str,
        price_id: str,
        status: str,
        current_period_start: datetime,
        current_period_end: datetime,
        latest_invoice_id: Optional[str] = None
    ) -> Optional[SubscriptionModel]:
        """
        Create or update a subscription record in MongoDB
        """
        try:
            # Check if subscription already exists
            existing_subscription = await mongodb.db["subscriptions"].find_one({
                "user_id": user_id,
                "stripe_subscription_id": stripe_subscription_id
            })
            
            subscription_data = {
                "user_id": user_id,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": stripe_subscription_id,
                "price_id": price_id,
                "status": status,
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "latest_invoice_id": latest_invoice_id,
                "updated_at": datetime.utcnow()
            }
            
            if existing_subscription:
                # Update existing subscription
                result = await mongodb.db["subscriptions"].update_one(
                    {"_id": existing_subscription["_id"]},
                    {"$set": subscription_data}
                )
                if result.modified_count > 0:
                    logger.info(f"Updated subscription for user {user_id}")
                    # Return updated subscription
                    updated_subscription = await mongodb.db["subscriptions"].find_one({
                        "_id": existing_subscription["_id"]
                    })
                    return SubscriptionModel(**updated_subscription)
            else:
                # Create new subscription
                subscription_data["created_at"] = datetime.utcnow()
                result = await mongodb.db["subscriptions"].insert_one(subscription_data)
                if result.inserted_id:
                    logger.info(f"Created new subscription for user {user_id}")
                    # Return created subscription
                    created_subscription = await mongodb.db["subscriptions"].find_one({
                        "_id": result.inserted_id
                    })
                    return SubscriptionModel(**created_subscription)
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating/updating subscription: {str(e)}")
            return None
    
    @staticmethod
    async def get_user_subscription(user_id: str) -> Optional[SubscriptionModel]:
        """
        Get the active subscription for a user
        """
        try:
            subscription = await mongodb.db["subscriptions"].find_one({
                "user_id": user_id,
                "status": {"$in": ["active", "trialing"]}
            })
            
            if subscription:
                return SubscriptionModel(**subscription)
            return None
            
        except Exception as e:
            logger.error(f"Error getting user subscription: {str(e)}")
            return None
    
    @staticmethod
    async def cancel_subscription(user_id: str, stripe_subscription_id: str) -> bool:
        """
        Cancel a subscription (mark as canceled in our DB)
        """
        try:
            result = await mongodb.db["subscriptions"].update_one(
                {
                    "user_id": user_id,
                    "stripe_subscription_id": stripe_subscription_id
                },
                {
                    "$set": {
                        "status": "canceled",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Canceled subscription for user {user_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error canceling subscription: {str(e)}")
            return False
    
    @staticmethod
    async def update_user_stripe_customer_id(user_id: str, stripe_customer_id: str) -> bool:
        """
        Update user's Stripe customer ID
        """
        try:
            result = await mongodb.db["users"].update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "stripe_customer_id": stripe_customer_id,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated Stripe customer ID for user {user_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating user Stripe customer ID: {str(e)}")
            return False
    
    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[UserModel]:
        """
        Get user by ID
        """
        try:
            user = await mongodb.db["users"].find_one({"_id": user_id})
            if user:
                return UserModel(**user)
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None
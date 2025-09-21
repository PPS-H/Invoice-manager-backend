#!/usr/bin/env python3
"""
Debug script for subscription management
"""
import asyncio
import logging
from datetime import datetime
from core.database import connect_to_mongo, close_mongo_connection
from services.subscription_service import SubscriptionService
from models.subscription import SubscriptionModel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_subscription_creation():
    """Debug subscription creation process"""
    try:
        # Connect to MongoDB
        await connect_to_mongo()
        print("✅ Connected to MongoDB")
        
        # Test subscription creation
        test_user_id = "test_user_123"
        test_subscription_data = {
            "user_id": test_user_id,
            "stripe_customer_id": "cus_test_123",
            "stripe_subscription_id": "sub_test_123",
            "price_id": "price_test_123",
            "status": "active",
            "current_period_start": datetime.utcnow(),
            "current_period_end": datetime.utcnow().replace(month=datetime.utcnow().month + 1),
            "latest_invoice_id": "in_test_123"
        }
        
        print(f"🧪 Testing subscription creation for user: {test_user_id}")
        
        # Create subscription
        subscription = await SubscriptionService.create_or_update_subscription(
            user_id=test_subscription_data["user_id"],
            stripe_customer_id=test_subscription_data["stripe_customer_id"],
            stripe_subscription_id=test_subscription_data["stripe_subscription_id"],
            price_id=test_subscription_data["price_id"],
            status=test_subscription_data["status"],
            current_period_start=test_subscription_data["current_period_start"],
            current_period_end=test_subscription_data["current_period_end"],
            latest_invoice_id=test_subscription_data["latest_invoice_id"]
        )
        
        if subscription:
            print("✅ Subscription created successfully!")
            print(f"   ID: {subscription.id}")
            print(f"   User ID: {subscription.user_id}")
            print(f"   Status: {subscription.status}")
        else:
            print("❌ Failed to create subscription")
        
        # Test getting subscription
        print("\n🔍 Testing subscription retrieval...")
        retrieved_subscription = await SubscriptionService.get_user_subscription(test_user_id)
        
        if retrieved_subscription:
            print("✅ Subscription retrieved successfully!")
            print(f"   ID: {retrieved_subscription.id}")
            print(f"   Status: {retrieved_subscription.status}")
        else:
            print("❌ No subscription found")
        
        # Test subscription cancellation
        print("\n🗑️ Testing subscription cancellation...")
        cancelled = await SubscriptionService.cancel_subscription(test_user_id, "sub_test_123")
        
        if cancelled:
            print("✅ Subscription cancelled successfully!")
        else:
            print("❌ Failed to cancel subscription")
        
        # Clean up test data
        print("\n🧹 Cleaning up test data...")
        from core.database import mongodb
        await mongodb.db["subscriptions"].delete_many({"user_id": test_user_id})
        print("✅ Test data cleaned up")
        
    except Exception as e:
        logger.error(f"Debug error: {str(e)}")
        print(f"❌ Error: {str(e)}")
    finally:
        await close_mongo_connection()

async def check_existing_subscriptions():
    """Check existing subscriptions in database"""
    try:
        await connect_to_mongo()
        print("🔍 Checking existing subscriptions...")
        
        from core.database import mongodb
        subscriptions = await mongodb.db["subscriptions"].find({}).to_list(length=None)
        
        print(f"📊 Found {len(subscriptions)} subscriptions:")
        for sub in subscriptions:
            print(f"   - User: {sub.get('user_id', 'N/A')}")
            print(f"     Status: {sub.get('status', 'N/A')}")
            print(f"     Stripe ID: {sub.get('stripe_subscription_id', 'N/A')}")
            print(f"     Price ID: {sub.get('price_id', 'N/A')}")
            print(f"     Created: {sub.get('created_at', 'N/A')}")
            print("     ---")
        
    except Exception as e:
        logger.error(f"Error checking subscriptions: {str(e)}")
        print(f"❌ Error: {str(e)}")
    finally:
        await close_mongo_connection()

async def test_webhook_processing():
    """Test webhook processing with mock data"""
    try:
        await connect_to_mongo()
        print("🧪 Testing webhook processing...")
        
        # Mock checkout session completed event
        mock_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "mode": "subscription",
                    "subscription": "sub_test_123",
                    "customer": "cus_test_123",
                    "metadata": {
                        "userId": "test_user_456"
                    },
                    "client_reference_id": "test_user_456"
                }
            }
        }
        
        # Mock subscription data
        mock_subscription = {
            "id": "sub_test_123",
            "customer": "cus_test_123",
            "status": "active",
            "current_period_start": 1640995200,  # Jan 1, 2022
            "current_period_end": 1643673600,    # Feb 1, 2022
            "latest_invoice": "in_test_123",
            "items": {
                "data": [{
                    "price": {
                        "id": "price_test_123"
                    }
                }]
            },
            "metadata": {
                "userId": "test_user_456"
            }
        }
        
        print("📝 Processing mock checkout session...")
        
        # Simulate the webhook processing
        from routes.webhooks import create_subscription_record
        await create_subscription_record("test_user_456", mock_subscription)
        
        print("✅ Mock webhook processing completed")
        
        # Check if subscription was created
        subscription = await SubscriptionService.get_user_subscription("test_user_456")
        if subscription:
            print("✅ Subscription created via webhook processing!")
            print(f"   Status: {subscription.status}")
        else:
            print("❌ No subscription found after webhook processing")
        
        # Clean up
        from core.database import mongodb
        await mongodb.db["subscriptions"].delete_many({"user_id": "test_user_456"})
        print("✅ Test data cleaned up")
        
    except Exception as e:
        logger.error(f"Webhook test error: {str(e)}")
        print(f"❌ Error: {str(e)}")
    finally:
        await close_mongo_connection()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            asyncio.run(check_existing_subscriptions())
        elif sys.argv[1] == "webhook":
            asyncio.run(test_webhook_processing())
        else:
            print("Usage: python debug_subscription.py [check|webhook]")
    else:
        asyncio.run(debug_subscription_creation())
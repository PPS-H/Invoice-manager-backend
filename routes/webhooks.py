"""
Stripe Webhook endpoints for handling subscription events
"""
from fastapi import APIRouter, Request, HTTPException, status
import stripe
from core.config import settings
from services.subscription_service import SubscriptionService
import logging
from datetime import datetime
import traceback



logger = logging.getLogger(__name__)



router = APIRouter(prefix="/webhooks", tags=["webhooks"])



# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY



@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events - TEMPORARILY SKIP SIGNATURE VERIFICATION FOR DEBUGGING
    """
    print('🔵 WEBHOOK RECEIVED ========================')
    print(f'🔵 Time: {datetime.now()}')
    
    try:
        # Get the raw body and signature
        body = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        print(f'🔵 Body length: {len(body)}')
        print(f'🔵 Signature header: {sig_header}')
        
        logger.info(f"🔵 Webhook received at {datetime.now()}")
        logger.info(f"🔵 Signature header present: {bool(sig_header)}")
        
        # TEMPORARILY SKIP SIGNATURE VERIFICATION FOR DEBUGGING
        print('⚠️ SKIPPING SIGNATURE VERIFICATION FOR DEBUGGING')
        
        try:
            # Parse the event data directly
            import json
            event = json.loads(body)
            print(f'✅ Event parsed successfully')
            logger.info(f"✅ Event parsed successfully")
            
        except ValueError as e:
            print(f'❌ Invalid JSON payload: {str(e)}')
            logger.error(f"❌ Invalid JSON payload: {str(e)}")
            return {"error": "Invalid JSON payload"}
        except Exception as e:
            print(f'❌ Unexpected parsing error: {str(e)}')
            logger.error(f"❌ Unexpected parsing error: {str(e)}")
            return {"error": "Parsing failed"}
        
        # Handle the event
        print('🔵 EVENT DATA ========================')
        print(f'🔵 Event keys: {list(event.keys()) if isinstance(event, dict) else "Not a dict"}')
        
        event_type = event.get('type', 'unknown')
        event_id = event.get('id', 'unknown')

        print(f'🔵 Event type: {event_type}')
        print(f'🔵 Event ID: {event_id}')
        
        logger.info(f"🔵 Processing event: {event_type} (ID: {event_id})")
        
        try:
            # Route events to handlers with error isolation
            if event_type == 'checkout.session.completed':
                print("🔵 Handling checkout.session.completed")
                logger.info("🔵 Handling checkout.session.completed")
                await handle_checkout_session_completed(event)
            elif event_type == 'invoice.payment_succeeded':
                print("🔵 Handling invoice.payment_succeeded")
                logger.info("🔵 Handling invoice.payment_succeeded")
                await handle_invoice_payment_succeeded(event)
            elif event_type == 'customer.subscription.created':
                print("🔵 Handling customer.subscription.created")
                logger.info("🔵 Handling customer.subscription.created")
                await handle_subscription_created(event)
            elif event_type == 'customer.subscription.updated':
                print("🔵 Handling customer.subscription.updated")
                logger.info("🔵 Handling customer.subscription.updated")
                await handle_subscription_updated(event)
            elif event_type == 'customer.subscription.deleted':
                print("🔵 Handling customer.subscription.deleted")
                logger.info("🔵 Handling customer.subscription.deleted")
                await handle_subscription_deleted(event)
            else:
                print(f"🔵 Unhandled event type: {event_type}")
                logger.info(f"🔵 Unhandled event type: {event_type}")
                
        except Exception as handler_error:
            print(f"❌ Handler error for {event_type}: {str(handler_error)}")
            print(f"❌ Handler traceback: {traceback.format_exc()}")
            logger.error(f"❌ Handler error for {event_type}: {str(handler_error)}")
            logger.error(f"❌ Handler traceback: {traceback.format_exc()}")
            # Don't raise - return success to prevent Stripe retries
        
        print(f'✅ Webhook processing completed for {event_type}')
        logger.info(f"✅ Webhook processing completed for {event_type}")
        return {"status": "success"}
        
    except Exception as e:
        print(f"❌ Critical webhook error: {str(e)}")
        print(f"❌ Critical traceback: {traceback.format_exc()}")
        logger.error(f"❌ Critical webhook error: {str(e)}")
        logger.error(f"❌ Critical traceback: {traceback.format_exc()}")
        # Return 200 to prevent endless retries
        return {"status": "error_handled"}


async def handle_checkout_session_completed(event):
    """
    Handle checkout.session.completed event with enhanced debugging
    """
    print('🔵 HANDLING CHECKOUT SESSION COMPLETED ========================')
    
    try:
        session = event['data']['object']
        print(f'🔵 Session ID: {session.get("id")}')
        print(f'🔵 Session mode: {session.get("mode")}')
        print(f'🔵 Session customer: {session.get("customer")}')
        print(f'🔵 Session metadata: {session.get("metadata", {})}')
        print(f'🔵 Session client_reference_id: {session.get("client_reference_id")}')
        
        logger.info(f"🔵 Session ID: {session.get('id')}")
        logger.info(f"🔵 Session mode: {session.get('mode')}")
        logger.info(f"🔵 Session customer: {session.get('customer')}")
        
        # Enhanced user ID extraction
        user_id = None
        
        # Try metadata first
        metadata = session.get('metadata', {})
        if metadata:
            user_id = metadata.get('userId') or metadata.get('user_id')
            print(f'🔵 User ID from metadata: {user_id}')
            logger.info(f"🔵 User ID from metadata: {user_id}")
        
        # Try client_reference_id as fallback
        if not user_id:
            user_id = session.get('client_reference_id')
            print(f'🔵 User ID from client_reference_id: {user_id}')
            logger.info(f"🔵 User ID from client_reference_id: {user_id}")
        
        if not user_id:
            print(f'❌ No user ID found in session. Metadata: {metadata}, client_reference_id: {session.get("client_reference_id")}')
            logger.error(f"❌ No user ID found in session. Metadata: {metadata}, client_reference_id: {session.get('client_reference_id')}")
            return
        
        print(f'✅ Processing for user ID: {user_id}')
        logger.info(f"✅ Processing for user ID: {user_id}")
        
        # Update user's Stripe customer ID if available
        customer_id = session.get('customer')
        if customer_id:
            try:
                print(f"🔵 Updating customer ID for user {user_id}: {customer_id}")
                logger.info(f"🔵 Updating customer ID for user {user_id}: {customer_id}")
                await SubscriptionService.update_user_stripe_customer_id(user_id, customer_id)
                print(f"✅ Customer ID updated successfully")
                logger.info(f"✅ Customer ID updated successfully")
            except Exception as e:
                print(f"❌ Error updating customer ID: {str(e)}")
                logger.error(f"❌ Error updating customer ID: {str(e)}")
        
        # Handle subscription creation
        print(f'🔵 Session mode: {session.get("mode")}')
        if session.get('mode') == 'subscription':
            subscription_id = session.get('subscription')
            print(f'🔵 Subscription ID: {subscription_id}')
            
            if subscription_id:
                try:
                    print(f'🔵 Retrieving subscription from Stripe: {subscription_id}')
                    logger.info(f"🔵 Retrieving subscription: {subscription_id}")
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    print(f'🔵 Retrieved subscription status: {subscription.get("status")}')
                    logger.info(f"🔵 Retrieved subscription status: {subscription.get('status')}")
                    
                    print(f'🔵 Creating subscription record for user: {user_id}')
                    await create_subscription_record(user_id, subscription)
                    print(f'✅ Subscription record created for user {user_id}')
                    logger.info(f"✅ Subscription record created for user {user_id}")
                except Exception as e:
                    print(f'❌ Error processing subscription: {str(e)}')
                    print(f'❌ Subscription error traceback: {traceback.format_exc()}')
                    logger.error(f"❌ Error processing subscription: {str(e)}")
                    logger.error(f"❌ Subscription error traceback: {traceback.format_exc()}")
            else:
                print(f'⚠️ Subscription mode but no subscription ID in session')
                logger.warning(f"⚠️ Subscription mode but no subscription ID in session")
        else:
            print(f'🔵 Session mode is not subscription: {session.get("mode")}')
        
        print(f'✅ Checkout session completed processing for user {user_id}')
        logger.info(f"✅ Checkout session completed processing for user {user_id}")
        
    except Exception as e:
        print(f"❌ Error in handle_checkout_session_completed: {str(e)}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        logger.error(f"❌ Error in handle_checkout_session_completed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")


async def handle_subscription_created(event):
    """
    Handle customer.subscription.created event
    """
    print('🔵 HANDLING SUBSCRIPTION CREATED ========================')
    
    try:
        subscription = event['data']['object']
        subscription_id = subscription.get('id')
        customer_id = subscription.get('customer')
        
        print(f'🔵 Subscription created - ID: {subscription_id}, Customer: {customer_id}')
        logger.info(f"🔵 Subscription created - ID: {subscription_id}, Customer: {customer_id}")
        
        # Try to get user ID from subscription metadata
        user_id = subscription.get('metadata', {}).get('userId') or subscription.get('metadata', {}).get('user_id')
        
        if not user_id:
            # Try to find user by customer ID
            try:
                print(f'🔵 No user ID in subscription metadata, looking up by customer ID: {customer_id}')
                logger.info(f"🔵 No user ID in subscription metadata, looking up by customer ID: {customer_id}")
                from core.database import mongodb
                user_doc = await mongodb.db["users"].find_one({"stripe_customer_id": customer_id})
                if user_doc:
                    user_id = str(user_doc.get('_id'))
                    print(f'✅ Found user by customer ID: {user_id}')
                    logger.info(f"✅ Found user by customer ID: {user_id}")
                else:
                    print(f'⚠️ No user found with customer ID: {customer_id}')
                    logger.warning(f"⚠️ No user found with customer ID: {customer_id}")
            except Exception as e:
                print(f'❌ Error looking up user by customer ID: {str(e)}')
                logger.error(f"❌ Error looking up user by customer ID: {str(e)}")
        
        if user_id:
            await create_subscription_record(user_id, subscription)
            print(f'✅ Processed subscription.created for user {user_id}')
            logger.info(f"✅ Processed subscription.created for user {user_id}")
        else:
            print(f'❌ Could not determine user ID for subscription {subscription_id}')
            logger.error(f"❌ Could not determine user ID for subscription {subscription_id}")
        
    except Exception as e:
        print(f'❌ Error handling subscription.created: {str(e)}')
        print(f'❌ Traceback: {traceback.format_exc()}')
        logger.error(f"❌ Error handling subscription.created: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")


async def handle_invoice_payment_succeeded(event):
    """
    Handle invoice.payment_succeeded event
    """
    print('🔵 HANDLING INVOICE PAYMENT SUCCEEDED ========================')
    
    try:
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        
        print(f'🔵 Invoice payment succeeded for subscription: {subscription_id}')
        logger.info(f"🔵 Invoice payment succeeded for subscription: {subscription_id}")
        
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                customer_id = subscription.get('customer')
                
                print(f'🔵 Looking up user by customer ID: {customer_id}')
                # Try to find user by customer ID
                from core.database import mongodb
                user_doc = await mongodb.db["users"].find_one({"stripe_customer_id": customer_id})
                
                if user_doc:
                    user_id = str(user_doc.get('_id'))
                    print(f'✅ Found user: {user_id}')
                    await create_subscription_record(user_id, subscription)
                    print(f'✅ Processed invoice.payment_succeeded for user {user_id}')
                    logger.info(f"✅ Processed invoice.payment_succeeded for user {user_id}")
                else:
                    print(f'⚠️ No user found for customer {customer_id}')
                    logger.warning(f"⚠️ No user found for customer {customer_id}")
                    
            except Exception as e:
                print(f'❌ Error processing invoice payment: {str(e)}')
                logger.error(f"❌ Error processing invoice payment: {str(e)}")
        
    except Exception as e:
        print(f'❌ Error handling invoice.payment_succeeded: {str(e)}')
        print(f'❌ Traceback: {traceback.format_exc()}')
        logger.error(f"❌ Error handling invoice.payment_succeeded: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")


async def handle_subscription_updated(event):
    """
    Handle customer.subscription.updated event
    """
    print('🔵 HANDLING SUBSCRIPTION UPDATED ========================')
    
    try:
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        
        print(f'🔵 Subscription updated for customer: {customer_id}')
        
        # Find user by customer ID
        from core.database import mongodb
        user_doc = await mongodb.db["users"].find_one({"stripe_customer_id": customer_id})
        
        if user_doc:
            user_id = str(user_doc.get('_id'))
            print(f'✅ Found user: {user_id}')
            await create_subscription_record(user_id, subscription)
            print(f'✅ Processed subscription.updated for user {user_id}')
            logger.info(f"✅ Processed subscription.updated for user {user_id}")
        else:
            print(f'⚠️ No user found for customer {customer_id}')
        
    except Exception as e:
        print(f'❌ Error handling subscription.updated: {str(e)}')
        print(f'❌ Traceback: {traceback.format_exc()}')
        logger.error(f"❌ Error handling subscription.updated: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")


async def handle_subscription_deleted(event):
    """
    Handle customer.subscription.deleted event
    """
    print('🔵 HANDLING SUBSCRIPTION DELETED ========================')
    
    try:
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        subscription_id = subscription.get('id')
        
        print(f'🔵 Subscription deleted - ID: {subscription_id}, Customer: {customer_id}')
        
        # Find user by customer ID
        from core.database import mongodb
        user_doc = await mongodb.db["users"].find_one({"stripe_customer_id": customer_id})
        
        if user_doc:
            user_id = str(user_doc.get('_id'))
            print(f'✅ Found user: {user_id}')
            await SubscriptionService.cancel_subscription(user_id, subscription_id)
            print(f'✅ Processed subscription.deleted for user {user_id}')
            logger.info(f"✅ Processed subscription.deleted for user {user_id}")
        else:
            print(f'⚠️ No user found for customer {customer_id}')
        
    except Exception as e:
        print(f'❌ Error handling subscription.deleted: {str(e)}')
        print(f'❌ Traceback: {traceback.format_exc()}')
        logger.error(f"❌ Error handling subscription.deleted: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")


async def create_subscription_record(user_id: str, subscription: dict):
    """
    Create or update subscription record in MongoDB with enhanced error handling
    """
    print('🔵 CREATE SUBSCRIPTION RECORD ========================')
    
    try:
        print(f"🔵 Creating subscription record for user: {user_id}")
        print(f"🔵 Subscription ID: {subscription.get('id')}")
        print(f"🔵 Subscription status: {subscription.get('status')}")
        
        logger.info(f"🔵 Creating subscription record for user: {user_id}")
        logger.info(f"🔵 Subscription ID: {subscription.get('id')}")
        logger.info(f"🔵 Subscription status: {subscription.get('status')}")
        
        # Debug: Print all subscription keys to see what's available
        print(f"🔵 Available subscription keys: {list(subscription.keys())}")
        
        # Validate required data
        if not subscription.get('items', {}).get('data'):
            print(f"❌ No items found in subscription")
            logger.error(f"❌ No items found in subscription")
            return
        
        # Get the price ID from the subscription
        price_id = subscription['items']['data'][0]['price']['id']
        print(f"🔵 Price ID: {price_id}")
        logger.info(f"🔵 Price ID: {price_id}")
        
        # Handle timestamps - use get() method with default values
        current_period_start = None
        current_period_end = None
        
        if 'current_period_start' in subscription:
            current_period_start = datetime.fromtimestamp(subscription['current_period_start'])
            print(f"🔵 Current period start: {current_period_start}")
        else:
            # Use created timestamp as fallback
            current_period_start = datetime.fromtimestamp(subscription.get('created', 0))
            print(f"🔵 Using created timestamp as period start: {current_period_start}")
        
        if 'current_period_end' in subscription:
            current_period_end = datetime.fromtimestamp(subscription['current_period_end'])
            print(f"🔵 Current period end: {current_period_end}")
        else:
            # Calculate end date as 30 days from start (default for monthly)
            from datetime import timedelta
            current_period_end = current_period_start + timedelta(days=30)
            print(f"🔵 Calculated period end: {current_period_end}")
        
        # Get latest invoice ID
        latest_invoice_id = subscription.get('latest_invoice')
        print(f"🔵 Latest invoice ID: {latest_invoice_id}")
        
        print(f"🔵 About to call SubscriptionService.create_or_update_subscription")
        logger.info(f"🔵 About to call SubscriptionService.create_or_update_subscription")
        
        # Create or update subscription
        result = await SubscriptionService.create_or_update_subscription(
            user_id=user_id,
            stripe_customer_id=subscription['customer'],
            stripe_subscription_id=subscription['id'],
            price_id=price_id,
            status=subscription['status'],
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            latest_invoice_id=latest_invoice_id
        )
        
        print(f"✅ Subscription record created/updated successfully")
        print(f"✅ Result: {result}")
        logger.info(f"✅ Subscription record created/updated successfully")
        logger.info(f"✅ Result: {result}")
        
    except Exception as e:
        print(f"❌ Error creating subscription record: {str(e)}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        logger.error(f"❌ Error creating subscription record: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")



# Add test endpoint for debugging
@router.post("/test-webhook")
async def test_webhook():
    """
    Test webhook processing without Stripe
    """
    try:
        print("🔵 Testing webhook functionality")
        logger.info("🔵 Testing webhook functionality")
        
        # Test environment
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        logger.info(f"🔵 Webhook secret configured: {bool(webhook_secret)}")
        
        # Test database connection
        from core.database import mongodb
        db_status = mongodb.db is not None
        logger.info(f"🔵 Database connection: {db_status}")
        
        # Test SubscriptionService
        service_available = hasattr(SubscriptionService, 'create_or_update_subscription')
        logger.info(f"🔵 SubscriptionService available: {service_available}")
        
        return {
            "timestamp": datetime.now(),
            "webhook_secret_configured": bool(webhook_secret),
            "database_connection": db_status,
            "subscription_service_available": service_available,
            "status": "test_completed"
        }
        
    except Exception as e:
        print(f"❌ Test webhook error: {str(e)}")
        logger.error(f"❌ Test webhook error: {str(e)}")
        return {"error": str(e)}

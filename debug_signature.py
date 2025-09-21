#!/usr/bin/env python3
"""
Debug webhook signature verification
"""
import hmac
import hashlib
import time
import json
from core.config import settings

def create_webhook_signature(payload, secret):
    """Create a valid Stripe webhook signature"""
    timestamp = str(int(time.time()))
    message = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"

def test_signature_verification():
    """Test signature verification locally"""
    print("🧪 Testing webhook signature verification...")
    
    # Test data
    test_payload = '{"test": "data"}'
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    
    print(f"Webhook secret: {webhook_secret[:20]}...")
    print(f"Payload: {test_payload}")
    
    # Create signature
    signature = create_webhook_signature(test_payload, webhook_secret)
    print(f"Generated signature: {signature}")
    
    # Test verification
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Verify signature using WebhookSignature
        stripe.WebhookSignature.verify_header(
            test_payload.encode('utf-8'), 
            signature, 
            webhook_secret
        )
        print("✅ Signature verification successful!")
        
        # Parse event
        import json
        event = json.loads(test_payload)
        print(f"Event: {event}")
        return True
        
    except Exception as e:
        print(f"❌ Signature verification failed: {str(e)}")
        return False

def test_with_real_stripe_data():
    """Test with real Stripe webhook data format"""
    print("\n🧪 Testing with real Stripe data format...")
    
    import json
    
    # Real webhook payload format
    real_payload = json.dumps({
        "id": "evt_test_real",
        "object": "event",
        "api_version": "2025-08-27.basil",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "cs_test_real_123",
                "object": "checkout.session",
                "metadata": {
                    "userId": "test_real_user_123"
                }
            }
        },
        "type": "checkout.session.completed"
    })
    
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    signature = create_webhook_signature(real_payload, webhook_secret)
    
    print(f"Real payload: {real_payload}")
    print(f"Generated signature: {signature}")
    
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Verify signature using WebhookSignature
        stripe.WebhookSignature.verify_header(
            real_payload.encode('utf-8'), 
            signature, 
            webhook_secret
        )
        print("✅ Real data signature verification successful!")
        
        # Parse event
        import json
        event = json.loads(real_payload)
        print(f"Event type: {event.get('type')}")
        return True
        
    except Exception as e:
        print(f"❌ Real data signature verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 DEBUGGING WEBHOOK SIGNATURE VERIFICATION")
    print("=" * 50)
    
    test_signature_verification()
    test_with_real_stripe_data()
    
    print("\n" + "=" * 50)
    print("✅ Signature debugging completed!")
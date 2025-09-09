#!/usr/bin/env python3

import asyncio
import sys
sys.path.append('.')

from core.database import mongodb, connect_to_mongo

async def cleanup_payment_notifications():
    """
    Remove payment notifications that were incorrectly processed as invoices
    """
    await connect_to_mongo()
    
    print("🧹 Cleaning up payment notifications incorrectly processed as invoices...")
    
    # Keywords that indicate payment notifications, not invoices
    payment_keywords = [
        "payment received", "payment confirmation", "payment notification",
        "unsuccessful payment", "payment failed", "transaction confirmation", 
        "payment processed", "billing notification", "transfi.*payment"
    ]
    
    total_removed = 0
    
    for keyword in payment_keywords:
        # Find invoices with payment notification subjects
        payment_notifications = await mongodb.db["invoices"].find({
            "email_subject": {"$regex": keyword, "$options": "i"}
        }).to_list(None)
        
        if payment_notifications:
            print(f"\n📧 Found {len(payment_notifications)} emails with '{keyword}':")
            
            for notif in payment_notifications:
                print(f"   🗑️  Removing: {notif['vendor_name']} - {notif['invoice_number']}")
                print(f"      Subject: {notif['email_subject'][:60]}...")
                print(f"      Amount: ${notif['total_amount']}")
                
                # Remove the payment notification
                result = await mongodb.db["invoices"].delete_one({"_id": notif["_id"]})
                if result.deleted_count > 0:
                    total_removed += 1
                    print(f"      ✅ Deleted successfully")
                else:
                    print(f"      ❌ Failed to delete")
    
    print(f"\n🧹 Cleanup complete: Removed {total_removed} payment notification emails")
    
    # Show remaining invoices for verification
    remaining_invoices = await mongodb.db["invoices"].find({}).sort("created_at", -1).limit(10).to_list(None)
    
    if remaining_invoices:
        print(f"\n📋 Remaining invoices (last 10):")
        for i, inv in enumerate(remaining_invoices):
            print(f"   {i+1}. {inv['vendor_name']} - {inv['invoice_number']} - ${inv['total_amount']}")
            print(f"      Subject: {inv['email_subject'][:50]}...")
    
    print("\n✅ Payment notification cleanup complete!")

if __name__ == "__main__":
    asyncio.run(cleanup_payment_notifications()) 
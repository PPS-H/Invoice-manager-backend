#!/usr/bin/env python3

import asyncio
import sys
sys.path.append('.')

from core.database import mongodb, connect_to_mongo
from datetime import datetime

async def fix_datadog_duplicates():
    """
    Fix Datadog duplicate issues:
    1. Find invoices with same invoice number, vendor, and amount
    2. Keep the earliest one, remove duplicates
    3. Fix incorrect invoice number parsing
    """
    await connect_to_mongo()
    
    print("🔍 Analyzing Datadog invoice duplicates...")
    
    # Find potential duplicates by vendor, invoice_number, and amount
    pipeline = [
        {
            "$match": {
                "vendor_name": {"$regex": "Datadog", "$options": "i"}
            }
        },
        {
            "$group": {
                "_id": {
                    "user_id": "$user_id",
                    "vendor_name": "$vendor_name", 
                    "invoice_number": "$invoice_number",
                    "total_amount": "$total_amount"
                },
                "count": {"$sum": 1},
                "invoices": {
                    "$push": {
                        "doc_id": "$_id",
                        "invoice_date": "$invoice_date",
                        "email_subject": "$email_subject",
                        "email_message_id": "$email_message_id",
                        "created_at": "$created_at"
                    }
                }
            }
        },
        {
            "$match": {"count": {"$gt": 1}}
        }
    ]
    
    duplicates = await mongodb.db["invoices"].aggregate(pipeline).to_list(None)
    
    if not duplicates:
        print("✅ No duplicates found by vendor/number/amount combination")
    else:
        print(f"❌ Found {len(duplicates)} groups of potential duplicates:")
        
        total_removed = 0
        for i, dup_group in enumerate(duplicates):
            vendor = dup_group["_id"]["vendor_name"]
            invoice_num = dup_group["_id"]["invoice_number"] 
            amount = dup_group["_id"]["total_amount"]
            count = dup_group["count"]
            
            print(f"\n{i+1}. {vendor} - #{invoice_num} - ${amount}")
            print(f"   Found {count} duplicates")
            
            # Sort by created_at to keep the earliest
            invoices = sorted(dup_group["invoices"], key=lambda x: x["created_at"])
            
            # Keep the first (earliest), remove the rest
            to_keep = invoices[0]
            to_remove = invoices[1:]
            
            print(f"   ✅ Keeping: {to_keep['doc_id']} (created: {to_keep['created_at']})")
            
            for j, inv in enumerate(to_remove):
                print(f"   🗑️  Removing: {inv['doc_id']} (created: {inv['created_at']})")
                
                # Remove the duplicate
                result = await mongodb.db["invoices"].delete_one({"_id": inv["doc_id"]})
                if result.deleted_count > 0:
                    total_removed += 1
                    print(f"      ✅ Deleted successfully")
                else:
                    print(f"      ❌ Failed to delete")
        
        print(f"\n🧹 Cleanup complete: Removed {total_removed} duplicate invoices")
    
    # Check for potential payment notification duplicates
    print("\n🔍 Checking for payment notification vs invoice duplicates...")
    
    transfi_notifications = await mongodb.db["invoices"].find({
        "email_subject": {"$regex": "Transfi.*Datadog", "$options": "i"}
    }).to_list(None)
    
    if transfi_notifications:
        print(f"⚠️  Found {len(transfi_notifications)} Transfi payment notifications:")
        print("   These might be payment confirmations, not actual invoices")
        
        for notif in transfi_notifications[:5]:  # Show first 5
            print(f"   - {notif['invoice_number']} - ${notif['total_amount']}")
            print(f"     Subject: {notif['email_subject'][:60]}...")
    
    print("\n✅ Analysis complete!")

if __name__ == "__main__":
    asyncio.run(fix_datadog_duplicates()) 
#!/usr/bin/env python3
"""
Fix vendors with is_active: None by setting them to is_active: True
"""
import asyncio
import sys
import os
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from core.database import mongodb, connect_to_mongo

async def fix_vendor_is_active():
    """Fix vendors with is_active: None"""
    print("🔄 Connecting to MongoDB...")
    await connect_to_mongo()
    
    # Check current status
    total_vendors = await mongodb.db["vendors"].count_documents({})
    active_vendors = await mongodb.db["vendors"].count_documents({"is_active": True})
    none_vendors = await mongodb.db["vendors"].count_documents({"is_active": None})
    
    print(f"📊 Current status:")
    print(f"   • Total vendors: {total_vendors}")
    print(f"   • Active vendors (is_active: True): {active_vendors}")
    print(f"   • Vendors with is_active: None: {none_vendors}")
    
    if none_vendors > 0:
        print(f"\n🔧 Fixing {none_vendors} vendors with is_active: None...")
        
        # Update vendors with is_active: None to is_active: True
        result = await mongodb.db["vendors"].update_many(
            {"is_active": None},
            {"$set": {
                "is_active": True,
                "updated_at": datetime.utcnow()
            }}
        )
        
        print(f"✅ Updated {result.modified_count} vendors")
    
    # Verify final counts
    final_active = await mongodb.db["vendors"].count_documents({"is_active": True})
    final_global_active = await mongodb.db["vendors"].count_documents({
        "is_global": True, 
        "is_active": True
    })
    
    print(f"\n🎯 Final results:")
    print(f"   • Total active vendors: {final_active}")
    print(f"   • Global active vendors (API will return): {final_global_active}")
    
    if final_global_active == total_vendors:
        print("🎉 Success! All vendors will now be visible in the UI!")
    else:
        print(f"⚠️  Still missing {total_vendors - final_global_active} vendors")

if __name__ == "__main__":
    asyncio.run(fix_vendor_is_active()) 
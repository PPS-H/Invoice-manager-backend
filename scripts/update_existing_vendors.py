#!/usr/bin/env python3
"""
Update existing vendors in the database with new fields for the vendor preference system
"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from core.database import mongodb, connect_to_mongo
from datetime import datetime

async def update_existing_vendors():
    """Update existing vendors with new fields"""
    print("🔄 Connecting to MongoDB...")
    await connect_to_mongo()
    
    # Update all existing vendors to have the new fields
    print("📝 Updating existing vendors with new fields...")
    
    result = await mongodb.db["vendors"].update_many(
        {},  # Match all vendors
        {
            "$set": {
                "is_global": True,
                "created_by": None,
                "usage_count": 0,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    print(f"✅ Updated {result.modified_count} vendors with new fields")
    
    # Show updated vendors
    vendors = await mongodb.db["vendors"].find({}).to_list(None)
    print(f"\n📋 Current vendors in database ({len(vendors)} total):")
    
    for vendor in vendors:
        print(f"   • {vendor.get('display_name', vendor.get('name', 'Unknown'))}")
        print(f"     - Email domains: {vendor.get('typical_email_domains', [])}")
        print(f"     - Is global: {vendor.get('is_global', 'not set')}")
        print(f"     - Usage count: {vendor.get('usage_count', 'not set')}")
        print()

if __name__ == "__main__":
    asyncio.run(update_existing_vendors()) 
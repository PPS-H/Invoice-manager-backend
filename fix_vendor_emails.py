#!/usr/bin/env python3
"""Fix vendor email domains based on real patterns"""

import asyncio
from core.database import mongodb, connect_to_mongo
from bson import ObjectId

async def fix_vendor_emails():
    """Update vendor email domains to match real patterns"""
    await connect_to_mongo()
    
    # Based on the invoice in DB and common patterns
    vendor_updates = {
        "google": {
            "name": "google",
            "typical_email_domains": [
                "payments-noreply@google.com",  # From actual invoice
                "googlecloud-noreply@google.com",
                "cloud-billing@google.com",
                "noreply-billing@google.com",
                "google.com"  # Catch-all
            ],
            "typical_email_addresses": [
                "payments-noreply@google.com",
                "googlecloud-noreply@google.com"
            ]
        },
        "figma": {
            "name": "figma",
            "typical_email_domains": [
                "figma.com",  # Catch-all
                "mail.figma.com",
                "notifications@figma.com"
            ],
            "typical_email_addresses": [
                "noreply@figma.com",
                "billing@figma.com",
                "support@figma.com",
                "notifications@figma.com"
            ]
        },
        "mongodb": {
            "name": "mongodb_atlas",
            "typical_email_domains": [
                "mongodb.com",  # Catch-all for all MongoDB emails
                "mongodb-atlas-alerts@mongodb.com"
            ],
            "typical_email_addresses": [
                "mongodb-atlas-alerts@mongodb.com",
                "billing@mongodb.com",
                "noreply@mongodb.com"
            ]
        },
        "slack": {
            "name": "slack",
            "typical_email_domains": [
                "slack.com"  # Catch-all
            ],
            "typical_email_addresses": [
                "notification@slack.com",
                "billing@slack.com",
                "receipts@slack.com"
            ]
        },
        "youtube": {
            "name": "youtube_premium",
            "typical_email_domains": [
                "youtube.com",
                "noreply@youtube.com"
            ],
            "typical_email_addresses": [
                "noreply@youtube.com",
                "youtube-noreply@google.com"
            ]
        }
    }
    
    # Update each vendor
    for vendor_key, updates in vendor_updates.items():
        result = await mongodb.db["vendors"].update_one(
            {"name": updates["name"]},
            {
                "$set": {
                    "typical_email_domains": updates["typical_email_domains"],
                    "typical_email_addresses": updates["typical_email_addresses"]
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"✅ Updated {vendor_key}")
        else:
            print(f"❌ Failed to update {vendor_key} (not found or no changes)")
    
    # Add a simple search approach - just look for common invoice keywords
    print("\n\n🔍 Let's also try a simpler approach - search for invoice keywords...")
    
    # Close connection
    if mongodb.client:
        mongodb.client.close()

if __name__ == "__main__":
    print("🔧 Fixing vendor email domains...")
    asyncio.run(fix_vendor_emails()) 
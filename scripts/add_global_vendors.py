#!/usr/bin/env python3

"""
Add more global vendors to improve invoice recognition
"""

import sys
import os
import asyncio
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import mongodb, connect_to_mongo

# Additional global vendors
GLOBAL_VENDORS = [
    # Enterprise Software
    {
        "name": "oracle",
        "display_name": "Oracle",
        "category": "enterprise_software",
        "typical_email_domains": ["noreply@oracle.com", "billing@oracle.com"],
        "common_keywords": ["oracle", "invoice", "subscription", "license"],
        "website": "https://oracle.com"
    },
    {
        "name": "sap",
        "display_name": "SAP",
        "category": "enterprise_software",
        "typical_email_domains": ["noreply@sap.com", "billing@sap.com"],
        "common_keywords": ["sap", "invoice", "subscription"],
        "website": "https://sap.com"
    },
    {
        "name": "workday",
        "display_name": "Workday",
        "category": "hr_software",
        "typical_email_domains": ["noreply@workday.com", "billing@workday.com"],
        "common_keywords": ["workday", "invoice", "subscription"],
        "website": "https://workday.com"
    },
    {
        "name": "okta",
        "display_name": "Okta",
        "category": "security",
        "typical_email_domains": ["noreply@okta.com", "billing@okta.com"],
        "common_keywords": ["okta", "invoice", "subscription", "identity"],
        "website": "https://okta.com"
    },
    {
        "name": "auth0",
        "display_name": "Auth0",
        "category": "security",
        "typical_email_domains": ["noreply@auth0.com", "billing@auth0.com"],
        "common_keywords": ["auth0", "invoice", "subscription"],
        "website": "https://auth0.com"
    },
    {
        "name": "twilio",
        "display_name": "Twilio",
        "category": "communication_api",
        "typical_email_domains": ["noreply@twilio.com", "billing@twilio.com"],
        "common_keywords": ["twilio", "invoice", "usage", "api"],
        "website": "https://twilio.com"
    },
    {
        "name": "sendgrid",
        "display_name": "SendGrid",
        "category": "email_service",
        "typical_email_domains": ["noreply@sendgrid.com", "billing@sendgrid.com"],
        "common_keywords": ["sendgrid", "invoice", "email", "api"],
        "website": "https://sendgrid.com"
    },
    {
        "name": "mailchimp",
        "display_name": "Mailchimp",
        "category": "marketing",
        "typical_email_domains": ["noreply@mailchimp.com", "billing@mailchimp.com"],
        "common_keywords": ["mailchimp", "invoice", "subscription"],
        "website": "https://mailchimp.com"
    },
    {
        "name": "hubspot",
        "display_name": "HubSpot",
        "category": "marketing",
        "typical_email_domains": ["noreply@hubspot.com", "billing@hubspot.com"],
        "common_keywords": ["hubspot", "invoice", "subscription"],
        "website": "https://hubspot.com"
    },
    # Media & Content
    {
        "name": "adobe",
        "display_name": "Adobe",
        "category": "creative_software",
        "typical_email_domains": ["noreply@adobe.com", "billing@adobe.com"],
        "common_keywords": ["adobe", "creative cloud", "invoice", "subscription"],
        "website": "https://adobe.com"
    },
    {
        "name": "spotify",
        "display_name": "Spotify",
        "category": "media",
        "typical_email_domains": ["noreply@spotify.com"],
        "common_keywords": ["spotify", "premium", "invoice", "subscription"],
        "website": "https://spotify.com"
    },
    {
        "name": "netflix",
        "display_name": "Netflix",
        "category": "media",
        "typical_email_domains": ["info@netflix.com", "noreply@netflix.com"],
        "common_keywords": ["netflix", "invoice", "subscription", "billing"],
        "website": "https://netflix.com"
    },
    {
        "name": "youtube_premium",
        "display_name": "YouTube Premium",
        "category": "media",
        "typical_email_domains": ["noreply@youtube.com", "payments-noreply@google.com"],
        "common_keywords": ["youtube", "premium", "invoice", "subscription"],
        "website": "https://youtube.com"
    },
    # Travel & Transportation
    {
        "name": "airbnb",
        "display_name": "Airbnb",
        "category": "travel",
        "typical_email_domains": ["noreply@airbnb.com"],
        "common_keywords": ["airbnb", "booking", "receipt", "reservation"],
        "website": "https://airbnb.com"
    },
    {
        "name": "booking_com",
        "display_name": "Booking.com",
        "category": "travel",
        "typical_email_domains": ["noreply@booking.com"],
        "common_keywords": ["booking.com", "reservation", "invoice", "hotel"],
        "website": "https://booking.com"
    },
    {
        "name": "expedia",
        "display_name": "Expedia",
        "category": "travel",
        "typical_email_domains": ["noreply@expedia.com"],
        "common_keywords": ["expedia", "booking", "receipt", "travel"],
        "website": "https://expedia.com"
    },
    # E-commerce Platforms
    {
        "name": "bigcommerce",
        "display_name": "BigCommerce",
        "category": "ecommerce",
        "typical_email_domains": ["noreply@bigcommerce.com", "billing@bigcommerce.com"],
        "common_keywords": ["bigcommerce", "invoice", "subscription"],
        "website": "https://bigcommerce.com"
    },
    {
        "name": "squarespace",
        "display_name": "Squarespace",
        "category": "website_builder",
        "typical_email_domains": ["noreply@squarespace.com", "billing@squarespace.com"],
        "common_keywords": ["squarespace", "invoice", "subscription"],
        "website": "https://squarespace.com"
    },
    {
        "name": "wix",
        "display_name": "Wix",
        "category": "website_builder",
        "typical_email_domains": ["noreply@wix.com", "billing@wix.com"],
        "common_keywords": ["wix", "invoice", "subscription"],
        "website": "https://wix.com"
    },
    {
        "name": "wordpress_com",
        "display_name": "WordPress.com",
        "category": "website_builder",
        "typical_email_domains": ["noreply@wordpress.com", "billing@wordpress.com"],
        "common_keywords": ["wordpress", "invoice", "subscription"],
        "website": "https://wordpress.com"
    },
    # Security & Backup
    {
        "name": "1password",
        "display_name": "1Password",
        "category": "security",
        "typical_email_domains": ["noreply@1password.com", "billing@1password.com"],
        "common_keywords": ["1password", "invoice", "subscription"],
        "website": "https://1password.com"
    },
    {
        "name": "lastpass",
        "display_name": "LastPass",
        "category": "security",
        "typical_email_domains": ["noreply@lastpass.com", "billing@lastpass.com"],
        "common_keywords": ["lastpass", "invoice", "subscription"],
        "website": "https://lastpass.com"
    },
    {
        "name": "backblaze",
        "display_name": "Backblaze",
        "category": "backup",
        "typical_email_domains": ["noreply@backblaze.com", "billing@backblaze.com"],
        "common_keywords": ["backblaze", "backup", "invoice", "storage"],
        "website": "https://backblaze.com"
    },
    # Indian Banking & Financial Services
    {
        "name": "icici_bank",
        "display_name": "ICICI Bank",
        "category": "banking",
        "typical_email_domains": ["customercare@icicibank.com", "statements@icicibank.com"],
        "common_keywords": ["icici", "bank", "statement", "credit card"],
        "website": "https://icicibank.com"
    },
    {
        "name": "hdfc_bank",
        "display_name": "HDFC Bank",
        "category": "banking",
        "typical_email_domains": ["alerts@hdfcbank.com", "statements@hdfcbank.com"],
        "common_keywords": ["hdfc", "bank", "statement", "credit card"],
        "website": "https://hdfcbank.com"
    },
    {
        "name": "sbi_bank",
        "display_name": "State Bank of India",
        "category": "banking",
        "typical_email_domains": ["sbi.card@sbicard.com", "alerts@sbi.co.in"],
        "common_keywords": ["sbi", "state bank", "statement", "credit card"],
        "website": "https://sbi.co.in"
    },
    {
        "name": "axis_bank",
        "display_name": "Axis Bank",
        "category": "banking",
        "typical_email_domains": ["service@axisbank.com", "cards@axisbank.com"],
        "common_keywords": ["axis", "bank", "statement", "credit card"],
        "website": "https://axisbank.com"
    },
    # Food Delivery International
    {
        "name": "doordash",
        "display_name": "DoorDash",
        "category": "food_delivery",
        "typical_email_domains": ["noreply@doordash.com"],
        "common_keywords": ["doordash", "order", "receipt", "delivery"],
        "website": "https://doordash.com"
    },
    {
        "name": "grubhub",
        "display_name": "Grubhub",
        "category": "food_delivery",
        "typical_email_domains": ["noreply@grubhub.com"],
        "common_keywords": ["grubhub", "order", "receipt", "delivery"],
        "website": "https://grubhub.com"
    },
    # Additional Cloud Services
    {
        "name": "linode",
        "display_name": "Linode",
        "category": "cloud",
        "typical_email_domains": ["noreply@linode.com", "billing@linode.com"],
        "common_keywords": ["linode", "invoice", "cloud", "server"],
        "website": "https://linode.com"
    },
    {
        "name": "vultr",
        "display_name": "Vultr",
        "category": "cloud",
        "typical_email_domains": ["noreply@vultr.com", "billing@vultr.com"],
        "common_keywords": ["vultr", "invoice", "cloud", "server"],
        "website": "https://vultr.com"
    },
    {
        "name": "fastly",
        "display_name": "Fastly",
        "category": "cdn",
        "typical_email_domains": ["noreply@fastly.com", "billing@fastly.com"],
        "common_keywords": ["fastly", "cdn", "invoice", "bandwidth"],
        "website": "https://fastly.com"
    }
]

async def add_global_vendors():
    """Add global vendors to the database"""
    try:
        await connect_to_mongo()
        
        vendors_collection = mongodb.db["vendors"]
        
        print(f"🌍 Adding {len(GLOBAL_VENDORS)} global vendors...")
        
        inserted_count = 0
        updated_count = 0
        
        for vendor_data in GLOBAL_VENDORS:
            try:
                # Check if vendor already exists
                existing = await vendors_collection.find_one({"name": vendor_data["name"]})
                
                if existing:
                    # Update existing vendor
                    vendor_data["updated_at"] = datetime.utcnow()
                    await vendors_collection.update_one(
                        {"name": vendor_data["name"]},
                        {"$set": vendor_data}
                    )
                    updated_count += 1
                    print(f"  ✏️  Updated: {vendor_data['display_name']}")
                else:
                    # Create new vendor
                    vendor_data["created_at"] = datetime.utcnow()
                    vendor_data["updated_at"] = datetime.utcnow()
                    vendor_data["is_active"] = True
                    await vendors_collection.insert_one(vendor_data)
                    inserted_count += 1
                    print(f"  ✅ Inserted: {vendor_data['display_name']}")
                    
            except Exception as e:
                print(f"  ❌ Error processing {vendor_data['display_name']}: {str(e)}")
        
        print(f"\n🎉 Global vendor addition completed!")
        print(f"   📝 Inserted: {inserted_count} new vendors")
        print(f"   ✏️  Updated: {updated_count} existing vendors")
        
        # Get total count
        total_count = await vendors_collection.count_documents({"is_active": True})
        print(f"   📊 Total active vendors: {total_count}")
        
        # Show categories
        pipeline = [
            {"$match": {"is_active": True}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        categories = await vendors_collection.aggregate(pipeline).to_list(None)
        print(f"\n📊 Vendor categories:")
        for cat in categories:
            print(f"   • {cat['_id']}: {cat['count']} vendors")
        
    except Exception as e:
        print(f"❌ Error adding vendors: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(add_global_vendors()) 
#!/usr/bin/env python3

"""
Add more vendors to improve invoice recognition
"""

import sys
import os
import asyncio
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import mongodb, connect_to_mongo

# Additional vendors to add
ADDITIONAL_VENDORS = [
    # Indian Companies
    {
        "name": "razorpay_india",
        "display_name": "Razorpay India",
        "category": "payments",
        "typical_email_domains": ["noreply@razorpay.com", "support@razorpay.com"],
        "common_keywords": ["razorpay", "payment", "invoice", "receipt"],
        "website": "https://razorpay.com"
    },
    {
        "name": "paytm",
        "display_name": "Paytm",
        "category": "payments",
        "typical_email_domains": ["noreply@paytm.com", "care@paytm.com"],
        "common_keywords": ["paytm", "payment", "invoice", "receipt"],
        "website": "https://paytm.com"
    },
    {
        "name": "phonepe",
        "display_name": "PhonePe",
        "category": "payments",
        "typical_email_domains": ["noreply@phonepe.com", "support@phonepe.com"],
        "common_keywords": ["phonepe", "payment", "invoice"],
        "website": "https://phonepe.com"
    },
    {
        "name": "gpay_india",
        "display_name": "Google Pay India",
        "category": "payments",
        "typical_email_domains": ["noreply@payments.google.com"],
        "common_keywords": ["google pay", "gpay", "payment", "invoice"],
        "website": "https://pay.google.com"
    },
    # Cloud & Hosting
    {
        "name": "vercel",
        "display_name": "Vercel",
        "category": "hosting",
        "typical_email_domains": ["billing@vercel.com", "noreply@vercel.com"],
        "common_keywords": ["vercel", "invoice", "subscription", "billing"],
        "website": "https://vercel.com"
    },
    {
        "name": "netlify",
        "display_name": "Netlify",
        "category": "hosting",
        "typical_email_domains": ["billing@netlify.com", "noreply@netlify.com"],
        "common_keywords": ["netlify", "invoice", "subscription"],
        "website": "https://netlify.com"
    },
    {
        "name": "cloudflare",
        "display_name": "Cloudflare",
        "category": "cloud",
        "typical_email_domains": ["billing@cloudflare.com", "noreply@cloudflare.com"],
        "common_keywords": ["cloudflare", "invoice", "subscription"],
        "website": "https://cloudflare.com"
    },
    {
        "name": "heroku",
        "display_name": "Heroku",
        "category": "hosting",
        "typical_email_domains": ["noreply@heroku.com", "billing@heroku.com"],
        "common_keywords": ["heroku", "invoice", "subscription"],
        "website": "https://heroku.com"
    },
    # Development Tools
    {
        "name": "mongodb_atlas",
        "display_name": "MongoDB Atlas",
        "category": "database",
        "typical_email_domains": ["noreply@mongodb.com", "billing@mongodb.com"],
        "common_keywords": ["mongodb", "atlas", "invoice", "subscription"],
        "website": "https://mongodb.com"
    },
    {
        "name": "firebase",
        "display_name": "Firebase",
        "category": "backend_service",
        "typical_email_domains": ["firebase-noreply@google.com"],
        "common_keywords": ["firebase", "invoice", "subscription"],
        "website": "https://firebase.google.com"
    },
    {
        "name": "supabase",
        "display_name": "Supabase",
        "category": "backend_service",
        "typical_email_domains": ["noreply@supabase.com", "billing@supabase.com"],
        "common_keywords": ["supabase", "invoice", "subscription"],
        "website": "https://supabase.com"
    },
    # Design & Content
    {
        "name": "figma",
        "display_name": "Figma",
        "category": "design",
        "typical_email_domains": ["noreply@figma.com", "billing@figma.com"],
        "common_keywords": ["figma", "invoice", "subscription"],
        "website": "https://figma.com"
    },
    {
        "name": "canva",
        "display_name": "Canva",
        "category": "design",
        "typical_email_domains": ["noreply@canva.com", "billing@canva.com"],
        "common_keywords": ["canva", "invoice", "subscription"],
        "website": "https://canva.com"
    },
    # AI & Analytics
    {
        "name": "openai",
        "display_name": "OpenAI",
        "category": "ai",
        "typical_email_domains": ["noreply@openai.com", "billing@openai.com"],
        "common_keywords": ["openai", "invoice", "api", "billing"],
        "website": "https://openai.com"
    },
    {
        "name": "anthropic",
        "display_name": "Anthropic",
        "category": "ai",
        "typical_email_domains": ["noreply@anthropic.com", "billing@anthropic.com"],
        "common_keywords": ["anthropic", "claude", "invoice", "api"],
        "website": "https://anthropic.com"
    },
    {
        "name": "mixpanel",
        "display_name": "Mixpanel",
        "category": "analytics",
        "typical_email_domains": ["noreply@mixpanel.com", "billing@mixpanel.com"],
        "common_keywords": ["mixpanel", "invoice", "subscription"],
        "website": "https://mixpanel.com"
    },
    # More Communication
    {
        "name": "discord",
        "display_name": "Discord",
        "category": "communication",
        "typical_email_domains": ["noreply@discord.com"],
        "common_keywords": ["discord", "nitro", "invoice", "subscription"],
        "website": "https://discord.com"
    },
    {
        "name": "telegram",
        "display_name": "Telegram",
        "category": "communication",
        "typical_email_domains": ["noreply@telegram.org"],
        "common_keywords": ["telegram", "premium", "invoice"],
        "website": "https://telegram.org"
    },
    # E-learning
    {
        "name": "udemy",
        "display_name": "Udemy",
        "category": "education",
        "typical_email_domains": ["noreply@udemy.com", "support@udemy.com"],
        "common_keywords": ["udemy", "course", "invoice", "receipt"],
        "website": "https://udemy.com"
    },
    {
        "name": "coursera",
        "display_name": "Coursera",
        "category": "education",
        "typical_email_domains": ["noreply@coursera.org"],
        "common_keywords": ["coursera", "course", "invoice", "subscription"],
        "website": "https://coursera.org"
    },
    # Indian Services
    {
        "name": "swiggy",
        "display_name": "Swiggy",
        "category": "food_delivery",
        "typical_email_domains": ["noreply@swiggy.in", "care@swiggy.in"],
        "common_keywords": ["swiggy", "order", "invoice", "receipt"],
        "website": "https://swiggy.com"
    },
    {
        "name": "zomato",
        "display_name": "Zomato",
        "category": "food_delivery",
        "typical_email_domains": ["noreply@zomato.com", "care@zomato.com"],
        "common_keywords": ["zomato", "order", "invoice", "receipt"],
        "website": "https://zomato.com"
    },
    {
        "name": "ola",
        "display_name": "Ola",
        "category": "transportation",
        "typical_email_domains": ["noreply@olacabs.com", "support@olacabs.com"],
        "common_keywords": ["ola", "ride", "invoice", "receipt"],
        "website": "https://olacabs.com"
    },
    {
        "name": "uber_india",
        "display_name": "Uber India",
        "category": "transportation",
        "typical_email_domains": ["noreply@uber.com", "uber.india@uber.com"],
        "common_keywords": ["uber", "ride", "invoice", "receipt", "trip"],
        "website": "https://uber.com"
    }
]

async def add_vendors():
    """Add additional vendors to the database"""
    try:
        await connect_to_mongo()
        
        vendors_collection = mongodb.db["vendors"]
        
        print(f"🚀 Adding {len(ADDITIONAL_VENDORS)} additional vendors...")
        
        inserted_count = 0
        updated_count = 0
        
        for vendor_data in ADDITIONAL_VENDORS:
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
        
        print(f"\n🎉 Additional vendor addition completed!")
        print(f"   📝 Inserted: {inserted_count} new vendors")
        print(f"   ✏️  Updated: {updated_count} existing vendors")
        
        # Get total count
        total_count = await vendors_collection.count_documents({"is_active": True})
        print(f"   📊 Total active vendors: {total_count}")
        
    except Exception as e:
        print(f"❌ Error adding vendors: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(add_vendors()) 
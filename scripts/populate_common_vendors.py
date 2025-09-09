#!/usr/bin/env python3

"""
Script to populate the database with common vendors and their typical billing email addresses.
This helps with better invoice recognition and processing.
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import mongodb
from models.vendor import VendorModel

# Common vendors data provided by user
COMMON_VENDORS = [
    {
        "name": "jira",
        "display_name": "Jira (Atlassian)",
        "category": "project_management",
        "typical_email_domains": [
            "no-reply@appmail.atlassian.com",
            "billing@atlassian.com"
        ],
        "common_keywords": ["jira", "atlassian", "invoice", "subscription"],
        "website": "https://www.atlassian.com"
    },
    {
        "name": "datadog",
        "display_name": "Datadog",
        "category": "monitoring",
        "typical_email_domains": [
            "invoices@datadoghq.com",
            "noreply@datadoghq.com",
            "billing@datadoghq.com"
        ],
        "common_keywords": ["datadog", "monitoring", "invoice", "billing"],
        "website": "https://www.datadoghq.com"
    },
    {
        "name": "trello",
        "display_name": "Trello",
        "category": "project_management",
        "typical_email_domains": [
            "noreply@trello.com",
            "billing@trello.com"
        ],
        "common_keywords": ["trello", "invoice", "subscription"],
        "website": "https://trello.com"
    },
    {
        "name": "confluence",
        "display_name": "Confluence",
        "category": "collaboration",
        "typical_email_domains": [
            "no-reply@appmail.atlassian.com"
        ],
        "common_keywords": ["confluence", "atlassian", "invoice"],
        "website": "https://www.atlassian.com/software/confluence"
    },
    {
        "name": "github",
        "display_name": "GitHub",
        "category": "development",
        "typical_email_domains": [
            "billing@github.com",
            "noreply@github.com"
        ],
        "common_keywords": ["github", "invoice", "subscription", "billing"],
        "website": "https://github.com"
    },
    {
        "name": "notion",
        "display_name": "Notion",
        "category": "productivity",
        "typical_email_domains": [
            "billing@notion.so"
        ],
        "common_keywords": ["notion", "invoice", "subscription"],
        "website": "https://notion.so"
    },
    {
        "name": "asana",
        "display_name": "Asana",
        "category": "project_management",
        "typical_email_domains": [
            "billing@asana.com"
        ],
        "common_keywords": ["asana", "invoice", "subscription"],
        "website": "https://asana.com"
    },
    {
        "name": "zoom",
        "display_name": "Zoom",
        "category": "communication",
        "typical_email_domains": [
            "no-reply@zoom.us"
        ],
        "common_keywords": ["zoom", "invoice", "subscription", "meeting"],
        "website": "https://zoom.us"
    },
    {
        "name": "dropbox",
        "display_name": "Dropbox",
        "category": "storage",
        "typical_email_domains": [
            "no-reply@dropbox.com"
        ],
        "common_keywords": ["dropbox", "invoice", "subscription", "storage"],
        "website": "https://dropbox.com"
    },
    {
        "name": "salesforce",
        "display_name": "Salesforce",
        "category": "crm",
        "typical_email_domains": [
            "billing@salesforce.com"
        ],
        "common_keywords": ["salesforce", "invoice", "subscription"],
        "website": "https://salesforce.com"
    },
    {
        "name": "amazon",
        "display_name": "Amazon",
        "category": "ecommerce",
        "typical_email_domains": [
            "auto-confirm@amazon.in",
            "auto-confirm@amazon.com"
        ],
        "common_keywords": ["amazon", "order", "invoice", "receipt"],
        "website": "https://amazon.com"
    },
    {
        "name": "microsoft",
        "display_name": "Microsoft",
        "category": "software",
        "typical_email_domains": [
            "account-security-noreply@accountprotection.microsoft.com",
            "billing@microsoft.com"
        ],
        "common_keywords": ["microsoft", "invoice", "subscription", "office", "azure"],
        "website": "https://microsoft.com"
    },
    {
        "name": "google_workspace",
        "display_name": "Google Workspace",
        "category": "productivity",
        "typical_email_domains": [
            "invoices-noreply@google.com",
            "support@google.com"
        ],
        "common_keywords": ["google", "workspace", "invoice", "subscription"],
        "website": "https://workspace.google.com"
    },
    {
        "name": "aws",
        "display_name": "AWS",
        "category": "cloud",
        "typical_email_domains": [
            "no-reply-aws@amazon.com"
        ],
        "common_keywords": ["aws", "amazon web services", "invoice", "billing"],
        "website": "https://aws.amazon.com"
    },
    {
        "name": "zoho",
        "display_name": "Zoho",
        "category": "business_suite",
        "typical_email_domains": [
            "notifications@zohoaccounts.com",
            "invoices@zoho.com"
        ],
        "common_keywords": ["zoho", "invoice", "subscription"],
        "website": "https://zoho.com"
    },
    {
        "name": "quickbooks",
        "display_name": "QuickBooks",
        "category": "accounting",
        "typical_email_domains": [
            "quickbooks@intuit.com"
        ],
        "common_keywords": ["quickbooks", "intuit", "invoice", "subscription"],
        "website": "https://quickbooks.intuit.com"
    },
    {
        "name": "xero",
        "display_name": "Xero",
        "category": "accounting",
        "typical_email_domains": [
            "no-reply@xero.com"
        ],
        "common_keywords": ["xero", "invoice", "subscription", "accounting"],
        "website": "https://xero.com"
    },
    {
        "name": "freshbooks",
        "display_name": "FreshBooks",
        "category": "accounting",
        "typical_email_domains": [
            "mail@freshbooks.com"
        ],
        "common_keywords": ["freshbooks", "invoice", "subscription"],
        "website": "https://freshbooks.com"
    },
    {
        "name": "shopify",
        "display_name": "Shopify",
        "category": "ecommerce",
        "typical_email_domains": [
            "billing@shopify.com"
        ],
        "common_keywords": ["shopify", "invoice", "subscription", "billing"],
        "website": "https://shopify.com"
    },
    {
        "name": "paypal",
        "display_name": "PayPal",
        "category": "payments",
        "typical_email_domains": [
            "service@paypal.com"
        ],
        "common_keywords": ["paypal", "payment", "invoice", "receipt"],
        "website": "https://paypal.com"
    },
    {
        "name": "stripe",
        "display_name": "Stripe",
        "category": "payments",
        "typical_email_domains": [
            "receipts+randomhash@stripe.com"
        ],
        "common_keywords": ["stripe", "payment", "invoice", "receipt", "billing"],
        "website": "https://stripe.com"
    },
    {
        "name": "razorpay",
        "display_name": "Razorpay",
        "category": "payments",
        "typical_email_domains": [
            "noreply@razorpay.com"
        ],
        "common_keywords": ["razorpay", "payment", "invoice", "receipt"],
        "website": "https://razorpay.com"
    },
    {
        "name": "godaddy",
        "display_name": "GoDaddy",
        "category": "hosting",
        "typical_email_domains": [
            "billing@godaddy.com"
        ],
        "common_keywords": ["godaddy", "domain", "hosting", "invoice", "billing"],
        "website": "https://godaddy.com"
    },
    {
        "name": "digitalocean",
        "display_name": "DigitalOcean",
        "category": "cloud",
        "typical_email_domains": [
            "no-reply@billing.digitalocean.com"
        ],
        "common_keywords": ["digitalocean", "cloud", "invoice", "billing"],
        "website": "https://digitalocean.com"
    },
    {
        "name": "slack",
        "display_name": "Slack",
        "category": "communication",
        "typical_email_domains": [
            "receipts@slack.com"
        ],
        "common_keywords": ["slack", "invoice", "subscription", "billing"],
        "website": "https://slack.com"
    }
]

async def ensure_database_connection():
    """Ensure database connection is established"""
    try:
        from core.database import connect_to_mongo
        await connect_to_mongo()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        raise

async def populate_vendors():
    """Populate the database with common vendors"""
    try:
        await ensure_database_connection()
        
        vendors_collection = mongodb.db["vendors"]
        
        print(f"🚀 Starting to populate {len(COMMON_VENDORS)} vendors...")
        
        inserted_count = 0
        updated_count = 0
        
        for vendor_data in COMMON_VENDORS:
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
                    await vendors_collection.insert_one(vendor_data)
                    inserted_count += 1
                    print(f"  ✅ Inserted: {vendor_data['display_name']}")
                    
            except Exception as e:
                print(f"  ❌ Error processing {vendor_data['display_name']}: {str(e)}")
        
        print(f"\n🎉 Vendor population completed!")
        print(f"   📝 Inserted: {inserted_count} new vendors")
        print(f"   ✏️  Updated: {updated_count} existing vendors")
        print(f"   📊 Total: {inserted_count + updated_count} vendors processed")
        
        # Create index for faster lookups
        await vendors_collection.create_index("name", unique=True)
        await vendors_collection.create_index("typical_email_domains")
        print(f"   🗂️  Created database indexes")
        
    except Exception as e:
        print(f"❌ Error populating vendors: {str(e)}")
        raise

async def list_vendors():
    """List all vendors in the database"""
    try:
        await ensure_database_connection()
        
        vendors_collection = mongodb.db["vendors"]
        vendors = await vendors_collection.find({}).to_list(None)
        
        print(f"\n📋 Current vendors in database ({len(vendors)} total):")
        for vendor in vendors:
            print(f"  • {vendor['display_name']} ({vendor['name']})")
            print(f"    📧 Emails: {', '.join(vendor['typical_email_domains'])}")
            print(f"    🏷️  Category: {vendor['category']}")
            print()
            
    except Exception as e:
        print(f"❌ Error listing vendors: {str(e)}")

async def main():
    """Main function"""
    print("🏢 Common Vendors Database Populator")
    print("="*50)
    
    try:
        await populate_vendors()
        await list_vendors()
        
    except Exception as e:
        print(f"❌ Script failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    exit(exit_code) 
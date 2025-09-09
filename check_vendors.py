#!/usr/bin/env python3
"""Check vendor email configurations"""

import asyncio
from core.database import mongodb, connect_to_mongo
from bson import ObjectId
import json

async def check_vendors():
    """Check vendor email domains"""
    await connect_to_mongo()
    
    # Get a few key vendors
    key_vendors = ["Google", "Figma", "Amazon", "Microsoft", "Stripe"]
    
    for vendor_name in key_vendors:
        vendor = await mongodb.db["vendors"].find_one({
            "name": {"$regex": vendor_name, "$options": "i"}
        })
        
        if vendor:
            print(f"\n🏢 {vendor['name']}:")
            print(f"   Display name: {vendor.get('display_name', 'N/A')}")
            print(f"   Email domains: {vendor.get('typical_email_domains', [])}")
            print(f"   Email addresses: {vendor.get('typical_email_addresses', [])}")
        else:
            print(f"\n❌ {vendor_name} not found in database")
    
    # Also check the actual emails in your inbox
    print("\n\n📧 Let's check what emails are actually in your inbox...")
    
    # Get email account
    email_account = await mongodb.db["email_accounts"].find_one({
        "_id": ObjectId("687e587d3785e231ce7aa783")
    })
    
    if email_account:
        from services.email_scanner import EnhancedEmailScanner
        scanner = EnhancedEmailScanner()
        
        if scanner.authenticate(email_account.get("access_token"), email_account.get("refresh_token")):
            # Search for recent emails
            messages = scanner.service.users().messages().list(
                userId='me',
                q='after:2025/07/01',  # Last few days
                maxResults=20
            ).execute()
            
            print(f"\nFound {len(messages.get('messages', []))} recent emails")
            
            # Get sender info for each
            senders = {}
            for msg in messages.get('messages', []):
                try:
                    full_msg = scanner.service.users().messages().get(
                        userId='me',
                        id=msg['id']
                    ).execute()
                    
                    headers = full_msg['payload'].get('headers', [])
                    for header in headers:
                        if header['name'] == 'From':
                            sender = header['value']
                            domain = sender.split('@')[-1].split('>')[0] if '@' in sender else 'unknown'
                            if domain not in senders:
                                senders[domain] = []
                            senders[domain].append(sender)
                            break
                except:
                    continue
            
            print("\n📬 Email domains in your inbox:")
            for domain, emails in sorted(senders.items()):
                print(f"\n   {domain}:")
                for email in set(emails[:3]):  # Show up to 3 unique senders
                    print(f"      - {email}")
    
    # Close connection
    if mongodb.client:
        mongodb.client.close()

if __name__ == "__main__":
    asyncio.run(check_vendors()) 
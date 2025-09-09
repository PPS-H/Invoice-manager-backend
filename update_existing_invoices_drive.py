#!/usr/bin/env python3
"""
Script to update existing invoices with Drive links
"""
import asyncio
import sys
import os
sys.path.append('.')

from core.database import connect_to_mongo
from services.drive_service import DriveService
from services.inviter_service import InviterService
from bson import ObjectId

async def update_existing_invoices():
    """Update existing invoices with Drive links"""
    print("🔍 Updating existing invoices with Drive links...")
    
    # Connect to database
    await connect_to_mongo()
    from core.database import mongodb
    
    # Get all pending invoices that have local files but no Drive links
    invoices = await mongodb.db['invoices'].find({
        'status': 'pending',
        'local_file_path': {'$exists': True, '$ne': None},
        'drive_view_link': {'$exists': False}
    }).to_list(length=None)
    
    print(f"📄 Found {len(invoices)} invoices to update")
    
    if not invoices:
        print("✅ No invoices need updating")
        return
    
    # Get email accounts for authentication
    email_accounts = await mongodb.db['email_accounts'].find({
        'status': 'connected',
        'access_token': {'$exists': True, '$ne': None}
    }).to_list(length=None)
    
    if not email_accounts:
        print("❌ No email accounts with valid tokens found")
        return
    
    # Use the first email account for authentication
    email_account = email_accounts[0]
    print(f"📧 Using email account: {email_account['email']}")
    
    # Initialize Drive service
    drive_service = DriveService()
    
    # Authenticate
    auth_result = drive_service.authenticate(
        email_account['access_token'], 
        email_account.get('refresh_token')
    )
    
    if not auth_result:
        print("❌ Drive authentication failed")
        return
    
    print("✅ Drive authentication successful")
    
    # Process each invoice
    updated_count = 0
    failed_count = 0
    
    for invoice in invoices:
        try:
            print(f"\\n📄 Processing invoice: {invoice.get('vendor_name', 'Unknown')}")
            
            # Get the invoice's email account
            invoice_email_account = await mongodb.db['email_accounts'].find_one({
                '_id': ObjectId(invoice['email_account_id'])
            })
            
            if not invoice_email_account:
                print(f"❌ Email account not found for invoice {invoice['_id']}")
                failed_count += 1
                continue
            
            # Check if local file exists
            local_file_path = invoice.get('local_file_path')
            if not local_file_path or not os.path.exists(local_file_path):
                print(f"❌ Local file not found: {local_file_path}")
                failed_count += 1
                continue
            
            print(f"📄 Local file found: {local_file_path}")
            
            # Create mock email data
            mock_email_data = {
                'subject': invoice.get('email_subject', 'Invoice'),
                'sender': invoice.get('email_sender', 'vendor@example.com'),
                'date': invoice.get('email_date', '2024-01-15')
            }
            
            # Create invoice info
            invoice_info = {
                'vendor_name': invoice.get('vendor_name', 'Unknown Vendor'),
                'total_amount': invoice.get('total_amount', 0),
                'invoice_date': invoice.get('invoice_date', '2024-01-15'),
                'invoice_number': invoice.get('invoice_number', 'INV-001')
            }
            
            # Create local file info
            local_file_info = {
                'file_path': local_file_path,
                'filename': os.path.basename(local_file_path)
            }
            
            # Save to Drive
            print("🚀 Saving to Drive...")
            drive_file_info = await drive_service.save_scanned_email_invoice_new_structure(
                str(invoice['email_account_id']),
                invoice.get('vendor_name', 'Unknown Vendor'),
                mock_email_data,
                invoice_info,
                local_file_info,
                invoice_email_account.get('email')
            )
            
            if drive_file_info:
                print(f"✅ Drive storage successful")
                print(f"   📄 File ID: {drive_file_info.get('drive_file_id')}")
                print(f"   🔗 Drive Link: {drive_file_info.get('web_view_link')}")
                
                # Update the invoice in the database
                await mongodb.db['invoices'].update_one(
                    {'_id': invoice['_id']},
                    {'$set': {
                        'drive_file_id': drive_file_info.get('drive_file_id'),
                        'drive_file_name': drive_file_info.get('drive_file_name'),
                        'drive_folder_id': drive_file_info.get('drive_folder_id'),
                        'drive_view_link': drive_file_info.get('web_view_link'),
                        'status': 'processed'  # Update status to processed
                    }}
                )
                
                updated_count += 1
                print(f"✅ Invoice updated in database")
            else:
                print(f"❌ Drive storage failed")
                failed_count += 1
                
        except Exception as e:
            print(f"❌ Error processing invoice {invoice['_id']}: {e}")
            failed_count += 1
    
    print(f"\\n📊 Update Summary:")
    print(f"  ✅ Successfully updated: {updated_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  📄 Total processed: {len(invoices)}")

if __name__ == "__main__":
    asyncio.run(update_existing_invoices())
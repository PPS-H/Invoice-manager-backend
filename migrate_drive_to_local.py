#!/usr/bin/env python3
import asyncio
import os
from core.database import mongodb, connect_to_mongo
from services.drive_service import DriveService
from services.local_storage import LocalStorageService
from bson import ObjectId

async def migrate_drive_to_local():
    """Migrate existing Google Drive files to local storage"""
    await connect_to_mongo()
    db = mongodb.db
    
    # Get all invoices with drive_file_id but no local_file_path
    invoices = await db['invoices'].find({
        "drive_file_id": {"$ne": None},
        "$or": [
            {"local_file_path": None},
            {"local_file_path": {"$exists": False}}
        ]
    }).to_list(length=None)
    
    print(f"Found {len(invoices)} invoices with Google Drive files to migrate")
    
    drive_service = DriveService()
    local_storage = LocalStorageService()
    
    migrated_count = 0
    errors = []
    
    for invoice in invoices:
        try:
            print(f"Processing invoice {invoice['_id']} - {invoice.get('vendor_name', 'Unknown')}")
            
            # Get the email account for this invoice
            email_account = await db['email_accounts'].find_one({
                "_id": ObjectId(invoice['email_account_id'])
            })
            
            if not email_account:
                print(f"  Skipping - Email account not found")
                continue
            
            # Authenticate with Drive
            if not drive_service.authenticate(
                email_account["access_token"],
                email_account.get("refresh_token")
            ):
                print(f"  Skipping - Drive authentication failed")
                continue
            
            # Download file from Drive
            file_content = drive_service.download_file(invoice['drive_file_id'])
            
            if not file_content:
                print(f"  Skipping - Could not download file from Drive")
                continue
            
            # Save locally
            local_info = local_storage.save_invoice_file(
                invoice['user_id'],
                invoice['vendor_name'],
                file_content,
                invoice.get('drive_file_name', 'invoice.pdf'),
                email_account.get('email')  # Pass scanned email for folder naming
            )
            
            if local_info:
                # Update invoice with local file info
                await db['invoices'].update_one(
                    {"_id": invoice["_id"]},
                    {
                        "$set": {
                            "local_file_path": local_info['file_path'],
                            "local_file_name": local_info['filename'],
                            "local_file_size": local_info['size']
                        }
                    }
                )
                
                print(f"  ✅ Migrated successfully")
                migrated_count += 1
            else:
                print(f"  ❌ Failed to save locally")
                errors.append(f"Invoice {invoice['_id']}: Failed to save locally")
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            errors.append(f"Invoice {invoice['_id']}: {str(e)}")
    
    print(f"\nMigration complete!")
    print(f"Successfully migrated: {migrated_count}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error}")

if __name__ == "__main__":
    asyncio.run(migrate_drive_to_local()) 
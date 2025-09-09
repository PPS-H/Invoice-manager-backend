#!/usr/bin/env python3
"""
Script to clean up duplicate invoices before creating unique indexes.
This will keep the earliest invoice for each user_id + vendor_name + invoice_number combination.
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import List, Dict
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def find_and_cleanup_duplicates():
    """Find and clean up duplicate invoices"""
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB]
    collection = db["invoices"]
    
    logger.info("🔍 Finding duplicate invoices (same user_id + vendor_name + invoice_number)...")
    
    # Aggregation pipeline to find duplicates
    pipeline = [
        {
            "$match": {
                "user_id": {"$ne": None},
                "vendor_name": {"$ne": None},
                "invoice_number": {"$ne": None}
            }
        },
        {
            "$group": {
                "_id": {
                    "user_id": "$user_id",
                    "vendor_name": "$vendor_name", 
                    "invoice_number": "$invoice_number"
                },
                "count": {"$sum": 1},
                "documents": {
                    "$push": {
                        "doc_id": "$_id",
                        "created_at": "$created_at",
                        "total_amount": "$total_amount",
                        "invoice_date": "$invoice_date",
                        "email_subject": "$email_subject"
                    }
                }
            }
        },
        {
            "$match": {
                "count": {"$gt": 1}
            }
        },
        {
            "$sort": {"count": -1}
        }
    ]
    
    duplicates = []
    async for doc in collection.aggregate(pipeline):
        duplicates.append(doc)
    
    logger.info(f"📊 Found {len(duplicates)} groups of duplicate invoices")
    
    total_docs_to_delete = 0
    for group in duplicates:
        duplicate_count = group["count"] - 1  # Keep 1, delete the rest
        total_docs_to_delete += duplicate_count
        
        logger.info(f"🔄 Duplicate group:")
        logger.info(f"   User: {group['_id']['user_id']}")
        logger.info(f"   Vendor: {group['_id']['vendor_name']}")
        logger.info(f"   Invoice #: {group['_id']['invoice_number']}")
        logger.info(f"   Count: {group['count']} (will delete {duplicate_count})")
        
        # Show details of each duplicate
        for i, doc in enumerate(group["documents"]):
            status = "KEEP" if i == 0 else "DELETE"
            logger.info(f"      {status}: ID={doc['doc_id']}, Amount=${doc.get('total_amount', 'N/A')}, Date={doc.get('invoice_date', 'N/A')}")
    
    logger.info(f"📈 SUMMARY: Found {total_docs_to_delete} duplicate documents to delete")
    
    if total_docs_to_delete == 0:
        logger.info("✅ No duplicates found - database is clean!")
        await client.close()
        return
    
    # Ask for confirmation
    response = input(f"\n⚠️  Are you sure you want to delete {total_docs_to_delete} duplicate invoices? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("❌ Operation cancelled by user")
        await client.close()
        return
    
    # Perform cleanup
    logger.info("🧹 Starting cleanup process...")
    deleted_count = 0
    
    for group in duplicates:
        # Sort documents by created_at to keep the earliest one
        documents = sorted(group["documents"], key=lambda x: x.get("created_at", datetime.min))
        
        # Keep the first (earliest), delete the rest
        docs_to_delete = documents[1:]  # Skip the first one
        
        for doc in docs_to_delete:
            doc_id = doc["doc_id"]
            result = await collection.delete_one({"_id": doc_id})
            
            if result.deleted_count > 0:
                deleted_count += 1
                logger.info(f"🗑️  Deleted duplicate: {doc_id}")
            else:
                logger.warning(f"⚠️  Failed to delete: {doc_id}")
    
    logger.info(f"✅ Cleanup completed! Deleted {deleted_count} duplicate invoices")
    
    # Verify no more duplicates exist
    logger.info("🔍 Verifying cleanup...")
    remaining_duplicates = []
    async for doc in collection.aggregate(pipeline):
        remaining_duplicates.append(doc)
    
    if len(remaining_duplicates) == 0:
        logger.info("✅ Verification passed - no more duplicates found!")
    else:
        logger.warning(f"⚠️  Warning: {len(remaining_duplicates)} duplicate groups still exist")
    
    await client.close()

async def find_email_message_duplicates():
    """Find and clean up duplicate email message IDs"""
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB]
    collection = db["invoices"]
    
    logger.info("🔍 Finding duplicate email_message_id...")
    
    pipeline = [
        {
            "$match": {
                "email_message_id": {"$ne": None, "$ne": ""}
            }
        },
        {
            "$group": {
                "_id": {
                    "user_id": "$user_id",
                    "email_message_id": "$email_message_id"
                },
                "count": {"$sum": 1},
                "documents": {
                    "$push": {
                        "doc_id": "$_id",
                        "created_at": "$created_at",
                        "vendor_name": "$vendor_name",
                        "invoice_number": "$invoice_number"
                    }
                }
            }
        },
        {
            "$match": {
                "count": {"$gt": 1}
            }
        }
    ]
    
    duplicates = []
    async for doc in collection.aggregate(pipeline):
        duplicates.append(doc)
    
    logger.info(f"📊 Found {len(duplicates)} groups of duplicate email messages")
    
    if len(duplicates) == 0:
        logger.info("✅ No email message duplicates found!")
        await client.close()
        return
    
    total_docs_to_delete = 0
    for group in duplicates:
        duplicate_count = group["count"] - 1
        total_docs_to_delete += duplicate_count
        
        logger.info(f"🔄 Email duplicate group:")
        logger.info(f"   User: {group['_id']['user_id']}")
        logger.info(f"   Email ID: {group['_id']['email_message_id']}")
        logger.info(f"   Count: {group['count']} (will delete {duplicate_count})")
    
    # Ask for confirmation
    response = input(f"\n⚠️  Delete {total_docs_to_delete} email message duplicates? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("❌ Operation cancelled")
        await client.close()
        return
    
    # Delete duplicates (keep earliest)
    deleted_count = 0
    for group in duplicates:
        documents = sorted(group["documents"], key=lambda x: x.get("created_at", datetime.min))
        docs_to_delete = documents[1:]
        
        for doc in docs_to_delete:
            result = await collection.delete_one({"_id": doc["doc_id"]})
            if result.deleted_count > 0:
                deleted_count += 1
                logger.info(f"🗑️  Deleted email duplicate: {doc['doc_id']}")
    
    logger.info(f"✅ Deleted {deleted_count} email message duplicates")
    await client.close()

async def main():
    """Main cleanup process"""
    logger.info("🚀 Starting duplicate cleanup process...")
    
    # First clean up invoice number duplicates
    await find_and_cleanup_duplicates()
    
    # Then clean up email message duplicates  
    await find_email_message_duplicates()
    
    logger.info("🎉 All cleanup operations completed!")

if __name__ == "__main__":
    asyncio.run(main()) 
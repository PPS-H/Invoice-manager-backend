import asyncio
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def cleanup_duplicate_invoices():
    """Remove duplicate invoices based on email_message_id + user_id"""
    try:
        # Connect to MongoDB
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        database_name = os.getenv("DATABASE_NAME", "invoice_manager")
        
        client = AsyncIOMotorClient(mongodb_url)
        db = client[database_name]
        collection = db.invoices
        
        logger.info("Starting duplicate cleanup process...")
        
        # Find all duplicate groups by email_message_id + user_id
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "user_id": "$user_id",
                        "message_id": "$email_metadata.message_id"
                    },
                    "invoices": {"$push": {"_id": "$_id", "created_at": "$created_at"}},
                    "count": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "count": {"$gt": 1}
                }
            }
        ]
        
        duplicate_groups = await collection.aggregate(pipeline).to_list(None)
        
        logger.info(f"Found {len(duplicate_groups)} duplicate groups")
        
        total_removed = 0
        
        for group in duplicate_groups:
            user_id = group["_id"]["user_id"]
            message_id = group["_id"]["message_id"]
            invoices = group["invoices"]
            
            logger.info(f"Processing {len(invoices)} duplicates for user {user_id}, message {message_id}")
            
            # Sort by created_at (keep the latest one)
            invoices.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
            
            # Keep the first (latest) invoice, remove the rest
            invoices_to_remove = invoices[1:]
            
            for invoice in invoices_to_remove:
                result = await collection.delete_one({"_id": invoice["_id"]})
                if result.deleted_count > 0:
                    total_removed += 1
                    logger.info(f"Removed duplicate invoice {invoice['_id']}")
        
        logger.info(f"Cleanup completed. Removed {total_removed} duplicate invoices")
        
        # Now create the unique index to prevent future duplicates
        try:
            await collection.create_index(
                [
                    ("user_id", ASCENDING),
                    ("email_metadata.message_id", ASCENDING)
                ],
                unique=True,
                name="unique_user_message_idx"
            )
            logger.info("Created unique index to prevent future duplicates")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("Unique index already exists")
            else:
                logger.error(f"Error creating unique index: {str(e)}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(cleanup_duplicate_invoices()) 
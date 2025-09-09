import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

async def create_invoice_indexes(db: AsyncIOMotorDatabase):
    """Create indexes for invoice collection to prevent duplicates and improve performance"""
    try:
        collection = db.invoices
        
        # Index for preventing duplicate emails per user
        indexes_to_create = [
            # Unique compound index on user_id + email_message_id to prevent duplicates
            IndexModel(
                [("user_id", ASCENDING), ("email_message_id", ASCENDING)],
                unique=True,
                name="unique_user_email_message"
            ),
            
            # Index for user queries
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="user_created_at"
            ),
            
            # Index for email account queries
            IndexModel(
                [("email_account_id", ASCENDING), ("created_at", DESCENDING)],
                name="email_account_created_at"
            ),
            
            # Index for invoice date queries
            IndexModel(
                [("user_id", ASCENDING), ("invoice_date", DESCENDING)],
                name="user_invoice_date"
            ),
            
            # Index for vendor queries
            IndexModel(
                [("user_id", ASCENDING), ("vendor_name", ASCENDING)],
                name="user_vendor_name"
            ),
            
            # Index for status queries
            IndexModel(
                [("user_id", ASCENDING), ("status", ASCENDING)],
                name="user_status"
            ),
            
            # Index for processing status queries
            IndexModel(
                [("user_id", ASCENDING), ("processing_metadata.processing_status", ASCENDING)],
                name="user_processing_status"
            ),
            
            # Index for invoice type queries
            IndexModel(
                [("user_id", ASCENDING), ("processing_metadata.invoice_type", ASCENDING)],
                name="user_invoice_type"
            ),
            
            # Index for search keywords
            IndexModel(
                [("user_id", ASCENDING), ("search_keywords", ASCENDING)],
                name="user_search_keywords"
            ),
            
            # Index for amount range queries
            IndexModel(
                [("user_id", ASCENDING), ("total_amount", ASCENDING)],
                name="user_total_amount"
            ),
            
            # Index for category queries
            IndexModel(
                [("user_id", ASCENDING), ("category", ASCENDING)],
                name="user_category"
            ),
            
            # Index for currency queries
            IndexModel(
                [("user_id", ASCENDING), ("currency", ASCENDING)],
                name="user_currency"
            ),
            
            # CRITICAL: Duplicate prevention indexes for validation service
            IndexModel(
                [("user_id", ASCENDING), ("vendor_name", ASCENDING), ("invoice_number", ASCENDING)],
                name="user_vendor_invoice_duplicate_check",
                unique=True,
                sparse=True  # Allow null invoice_numbers
            ),
            
            IndexModel(
                [("user_id", ASCENDING), ("email_message_id", ASCENDING)],
                name="user_email_message_duplicate_check",
                unique=True,
                sparse=True  # Allow null email_message_ids
            ),
            
            # Fast lookup indexes for validation queries
            IndexModel([("vendor_name", ASCENDING)], name="vendor_name_lookup"),
            IndexModel([("invoice_number", ASCENDING)], name="invoice_number_lookup"),
            
            # Similar invoice detection (Rule 16)
            IndexModel(
                [("user_id", ASCENDING), ("vendor_name", ASCENDING), ("total_amount", ASCENDING), ("invoice_date", ASCENDING)],
                name="user_vendor_amount_date_similarity"
            ),
            
            # Text index for full-text search
            IndexModel(
                [
                    ("vendor_name", "text"),
                    ("invoice_number", "text"),
                    ("email_metadata.subject", "text"),
                    ("email_metadata.sender", "text"),
                    ("search_keywords", "text")
                ],
                name="text_search_index"
            )
        ]
        
        # Create indexes
        await collection.create_indexes(indexes_to_create)
        logger.info(f"Created {len(indexes_to_create)} indexes for invoices collection")
        
    except Exception as e:
        logger.error(f"Error creating invoice indexes: {str(e)}")
        raise

async def create_batch_processing_indexes(db: AsyncIOMotorDatabase):
    """Create indexes for batch processing collection"""
    try:
        collection = db.batch_processing
        
        indexes_to_create = [
            # Index for user batch queries
            IndexModel(
                [("user_id", ASCENDING), ("start_time", DESCENDING)],
                name="user_start_time"
            ),
            
            # Index for batch status queries
            IndexModel(
                [("user_id", ASCENDING), ("status", ASCENDING)],
                name="user_batch_status"
            ),
            
            # Unique index for batch ID
            IndexModel(
                [("batch_id", ASCENDING)],
                unique=True,
                name="unique_batch_id"
            )
        ]
        
        await collection.create_indexes(indexes_to_create)
        logger.info(f"Created {len(indexes_to_create)} indexes for batch_processing collection")
        
    except Exception as e:
        logger.error(f"Error creating batch processing indexes: {str(e)}")
        raise

async def create_pdf_processing_indexes(db: AsyncIOMotorDatabase):
    """Create indexes for PDF processing collection"""
    try:
        collection = db.pdf_processing
        
        indexes_to_create = [
            # Index for user processing queries
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="user_pdf_created_at"
            ),
            
            # Unique index for processing ID
            IndexModel(
                [("processing_id", ASCENDING)],
                unique=True,
                name="unique_processing_id"
            ),
            
            # Index for invoice ID queries
            IndexModel(
                [("invoice_id", ASCENDING)],
                name="pdf_invoice_id"
            ),
            
            # Index for status queries
            IndexModel(
                [("user_id", ASCENDING), ("status", ASCENDING)],
                name="user_pdf_status"
            )
        ]
        
        await collection.create_indexes(indexes_to_create)
        logger.info(f"Created {len(indexes_to_create)} indexes for pdf_processing collection")
        
    except Exception as e:
        logger.error(f"Error creating PDF processing indexes: {str(e)}")
        raise

async def create_scanning_task_indexes(db: AsyncIOMotorDatabase):
    """Create indexes for scanning tasks collection"""
    try:
        collection = db.scanning_tasks
        
        indexes_to_create = [
            # Index for user queries
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="user_created_at"
            ),
            
            # Index for account queries
            IndexModel(
                [("account_id", ASCENDING), ("created_at", DESCENDING)],
                name="account_created_at"
            ),
            
            # Index for task status queries
            IndexModel(
                [("status", ASCENDING), ("created_at", DESCENDING)],
                name="status_created_at"
            ),
            
            # Index for active tasks
            IndexModel(
                [("status", ASCENDING), ("account_id", ASCENDING)],
                name="active_tasks_lookup"
            ),
            
            # Unique index for task_id
            IndexModel(
                [("task_id", ASCENDING)],
                unique=True,
                name="unique_task_id"
            ),
            
            # Index for cleanup queries
            IndexModel(
                [("status", ASCENDING), ("updated_at", ASCENDING)],
                name="cleanup_index"
            ),
            
            # Index for scan type queries
            IndexModel(
                [("scan_type", ASCENDING), ("created_at", DESCENDING)],
                name="scan_type_created_at"
            )
        ]
        
        await collection.create_indexes(indexes_to_create)
        logger.info(f"Created {len(indexes_to_create)} indexes for scanning_tasks collection")
        
    except Exception as e:
        logger.error(f"Error creating scanning task indexes: {str(e)}")
        raise

async def create_all_indexes(db: AsyncIOMotorDatabase):
    """Create all database indexes"""
    try:
        logger.info("Starting database index creation...")
        
        await create_invoice_indexes(db)
        await create_batch_processing_indexes(db)
        await create_pdf_processing_indexes(db)
        await create_scanning_task_indexes(db)
        
        logger.info("Successfully created all database indexes")
        
    except Exception as e:
        logger.error(f"Error creating database indexes: {str(e)}")
        raise

async def drop_and_recreate_indexes(db: AsyncIOMotorDatabase):
    """Drop and recreate all indexes (use with caution)"""
    try:
        logger.warning("Dropping all indexes...")
        
        # Drop all indexes except _id
        collections = ['invoices', 'batch_processing', 'pdf_processing']
        
        for collection_name in collections:
            collection = db[collection_name]
            try:
                await collection.drop_indexes()
                logger.info(f"Dropped indexes for {collection_name}")
            except Exception as e:
                logger.warning(f"Error dropping indexes for {collection_name}: {str(e)}")
        
        # Recreate indexes
        await create_all_indexes(db)
        
        logger.info("Successfully recreated all indexes")
        
    except Exception as e:
        logger.error(f"Error recreating indexes: {str(e)}")
        raise 

# Critical indexes for validation service duplicate checks
("invoices", "user_vendor_invoice_duplicate_check", {
    "user_id": 1,
    "vendor_name": 1, 
    "invoice_number": 1
}, {"unique": True}),

("invoices", "user_email_message_duplicate_check", {
    "user_id": 1,
    "email_message_id": 1
}, {"unique": True}),

# Fast lookup indexes for validation queries
("invoices", "vendor_name_lookup", {"vendor_name": 1}),
("invoices", "invoice_number_lookup", {"invoice_number": 1}),

# Similar invoice detection (Rule 16)
("invoices", "user_vendor_amount_month", {
    "user_id": 1,
    "vendor_name": 1,
    "total_amount": 1,
    "invoice_date": 1
}), 
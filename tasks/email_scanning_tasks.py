"""
Celery tasks for email scanning operations
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from bson import ObjectId

from core.celery_app import celery_app
from core.database import mongodb
from services.invoice_processor import InvoiceProcessor
from services.factory import create_invoice_processor

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="scan_user_emails")
def scan_user_emails_task(self, user_id: str, account_id: str, scan_type: str = "inbox", months: int = 1):
    """
    Celery task for email scanning
    
    Args:
        user_id: User ID
        account_id: Email account ID
        scan_type: Type of scan (inbox, groups, all)
        months: Number of months to scan back
    
    Returns:
        Dict with scan results
    """
    try:
        logger.info(f"🚀 Starting Celery email scan task: {self.request.id}")
        logger.info(f"   User: {user_id}, Account: {account_id}, Type: {scan_type}, Months: {months}")
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={
                "status": "Initializing email scan",
                "user_id": user_id,
                "account_id": account_id,
                "scan_type": scan_type,
                "progress": 0,
                "started_at": datetime.utcnow().isoformat()
            }
        )
        
        # Run async function in sync context
        result = asyncio.run(_process_email_scan_async(
            self, user_id, account_id, scan_type, months
        ))
        
        # Update final status
        self.update_state(
            state="SUCCESS",
            meta={
                "status": "Email scan completed successfully",
                "result": result,
                "progress": 100,
                "completed_at": datetime.utcnow().isoformat()
            }
        )
        
        # Update database task status to DONE
        asyncio.run(_update_task_status_to_done(self.request.id, result))
        
        logger.info(f"✅ Celery email scan task completed: {self.request.id}")
        return result
        
    except Exception as exc:
        logger.error(f"❌ Celery email scan task failed: {self.request.id}, Error: {str(exc)}")
        
        # Update task status to failure
        self.update_state(
            state="FAILURE",
            meta={
                "status": "Email scan failed",
                "error": str(exc),
                "progress": 0,
                "failed_at": datetime.utcnow().isoformat()
            }
        )
        
        # Update database task status to FAILURE
        asyncio.run(_update_task_status_to_failure(self.request.id, str(exc)))
        
        raise exc

async def _process_email_scan_async(task_instance, user_id: str, account_id: str, scan_type: str, months: int) -> Dict[str, Any]:
    """
    Async function to process email scanning
    """
    try:
        # Update progress
        task_instance.update_state(
            state="PROGRESS",
            meta={
                "status": "Connecting to database",
                "progress": 5
            }
        )
        
        # Ensure database connection is established
        from core.database import connect_to_mongo
        await connect_to_mongo()
        
        # Update progress
        task_instance.update_state(
            state="PROGRESS",
            meta={
                "status": "Creating invoice processor",
                "progress": 10
            }
        )
        
        # Create invoice processor
        processor = create_invoice_processor()
        if not processor:
            raise Exception("Failed to create invoice processor")
        
        # Calculate days back
        days_back = months * 30
        
        # Update progress
        task_instance.update_state(
            state="PROGRESS",
            meta={
                "status": "Processing emails",
                "progress": 25
            }
        )
        
        # Process emails based on scan type
        if scan_type == "inbox":
            result = await processor.process_user_preferred_vendors(
                user_id=user_id,
                email_account_id=account_id,
                days_back=days_back
            )
        elif scan_type == "groups":
            result = await processor.process_user_preferred_vendors(
                user_id=user_id,
                email_account_id=account_id,
                days_back=90  # Default for groups
            )
        elif scan_type == "all":
            # Process both inbox and groups
            inbox_result = await processor.process_user_preferred_vendors(
                user_id=user_id,
                email_account_id=account_id,
                days_back=days_back
            )
            
            task_instance.update_state(
                state="PROGRESS",
                meta={
                    "status": "Processing groups",
                    "progress": 75
                }
            )
            
            groups_result = await processor.process_user_preferred_vendors(
                user_id=user_id,
                email_account_id=account_id,
                days_back=90
            )
            
            # Combine results
            result = {
                "success": inbox_result.get("success", False) and groups_result.get("success", False),
                "inbox": inbox_result,
                "groups": groups_result,
                "total_processed": inbox_result.get("processed_count", 0) + groups_result.get("processed_count", 0),
                "total_invoices": inbox_result.get("invoices_found", 0) + groups_result.get("invoices_found", 0)
            }
        else:
            raise ValueError(f"Invalid scan type: {scan_type}")
        
        # Update progress
        task_instance.update_state(
            state="PROGRESS",
            meta={
                "status": "Finalizing results",
                "progress": 90
            }
        )
        
        # Update database with results
        await _update_scan_results(user_id, account_id, result)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in async email scan processing: {str(e)}")
        raise

async def _update_scan_results(user_id: str, account_id: str, result: Dict[str, Any]):
    """
    Update database with scan results
    """
    try:
        # Ensure database connection
        from core.database import connect_to_mongo
        await connect_to_mongo()
        
        # Update email account status
        object_id = ObjectId(account_id)
        status = "connected" if result.get("success", False) else "error"
        
        await mongodb.db["email_accounts"].update_one(
            {"_id": object_id, "user_id": user_id},
            {"$set": {
                "status": status,
                "last_sync_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"Updated email account {account_id} status to {status}")
        
    except Exception as e:
        logger.error(f"Error updating scan results: {str(e)}")

async def _update_task_status_to_done(task_id: str, result: Dict[str, Any]):
    """
    Update scanning task status to DONE in database
    """
    try:
        # Ensure database connection
        from core.database import connect_to_mongo
        await connect_to_mongo()
        
        # Update scanning task status to DONE
        await mongodb.db["scanning_tasks"].update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "DONE",
                "progress": 100,
                "current_status": "Email scan completed successfully",
                "result": result,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"✅ Updated scanning task {task_id} status to DONE")
        
    except Exception as e:
        logger.error(f"Error updating task status to DONE: {str(e)}")

async def _update_task_status_to_failure(task_id: str, error_message: str):
    """
    Update scanning task status to FAILURE in database
    """
    try:
        # Ensure database connection
        from core.database import connect_to_mongo
        await connect_to_mongo()
        
        # Update scanning task status to FAILURE
        await mongodb.db["scanning_tasks"].update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "FAILURE",
                "progress": 0,
                "current_status": "Email scan failed",
                "error": error_message,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"❌ Updated scanning task {task_id} status to FAILURE")
        
    except Exception as e:
        logger.error(f"Error updating task status to FAILURE: {str(e)}")

@celery_app.task(bind=True, name="bulk_scan_emails")
def bulk_scan_emails_task(self, user_id: str, account_ids: list, scan_type: str = "inbox", months: int = 1):
    """
    Celery task for bulk email scanning
    
    Args:
        user_id: User ID
        account_ids: List of email account IDs
        scan_type: Type of scan (inbox, groups, all)
        months: Number of months to scan back
    
    Returns:
        Dict with bulk scan results
    """
    try:
        logger.info(f"🚀 Starting bulk email scan task: {self.request.id}")
        logger.info(f"   User: {user_id}, Accounts: {len(account_ids)}, Type: {scan_type}")
        
        results = []
        total_accounts = len(account_ids)
        
        for i, account_id in enumerate(account_ids):
            # Update progress
            progress = int((i / total_accounts) * 100)
            self.update_state(
                state="PROGRESS",
                meta={
                    "status": f"Scanning account {i+1}/{total_accounts}",
                    "progress": progress,
                    "current_account": account_id,
                    "completed_accounts": i
                }
            )
            
            # Start individual scan task
            individual_task = scan_user_emails_task.delay(
                user_id=user_id,
                account_id=account_id,
                scan_type=scan_type,
                months=months
            )
            
            results.append({
                "account_id": account_id,
                "task_id": individual_task.id,
                "status": "started"
            })
            
            logger.info(f"Started scan for account {account_id}: {individual_task.id}")
        
        # Update final status
        self.update_state(
            state="SUCCESS",
            meta={
                "status": "All bulk scans started",
                "results": results,
                "total_accounts": total_accounts,
                "progress": 100
            }
        )
        
        return {
            "status": "All scans started",
            "results": results,
            "total_accounts": total_accounts
        }
        
    except Exception as exc:
        logger.error(f"❌ Bulk email scan task failed: {self.request.id}, Error: {str(exc)}")
        
        self.update_state(
            state="FAILURE",
            meta={
                "status": "Bulk scan failed",
                "error": str(exc),
                "progress": 0
            }
        )
        raise exc

@celery_app.task(name="cleanup_old_tasks")
def cleanup_old_tasks():
    """
    Cleanup old completed tasks from database
    """
    try:
        # Ensure database connection
        import asyncio
        from core.database import connect_to_mongo
        
        async def _cleanup():
            await connect_to_mongo()
            
            # Clean up tasks older than 24 hours
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            result = await mongodb.db["scanning_tasks"].delete_many({
                "status": {"$in": ["SUCCESS", "FAILURE"]},
                "updated_at": {"$lt": cutoff_time}
            })
            
            logger.info(f"Cleaned up {result.deleted_count} old scanning tasks")
            return {"cleaned_count": result.deleted_count}
        
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an event loop, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _cleanup())
                return future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            return asyncio.run(_cleanup())
        
    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}")
        return {"error": str(e)}

@celery_app.task(bind=True, name="cancel_scan_task")
def cancel_scan_task(self, task_id: str):
    """
    Cancel a running scan task
    
    Args:
        task_id: Task ID to cancel
    
    Returns:
        Dict with cancellation result
    """
    try:
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        
        # Update database
        import asyncio
        from core.database import connect_to_mongo
        
        async def _cancel():
            await connect_to_mongo()
            
            await mongodb.db["scanning_tasks"].update_one(
                {"task_id": task_id},
                {"$set": {
                    "status": "CANCELLED",
                    "updated_at": datetime.utcnow()
                }}
            )
        
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an event loop, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _cancel())
                future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            asyncio.run(_cancel())
        
        logger.info(f"Cancelled scan task: {task_id}")
        return {"status": "cancelled", "task_id": task_id}
        
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {str(e)}")
        return {"error": str(e)}
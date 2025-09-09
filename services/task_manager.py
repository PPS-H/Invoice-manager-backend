"""
Task management service for Celery tasks
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from bson import ObjectId

from core.database import mongodb
from core.celery_app import celery_app
from models.scanning_task import ScanningTaskModel, TaskStatus, ScanType

logger = logging.getLogger(__name__)

class TaskManager:
    """Service for managing Celery tasks and their database records"""
    
    def __init__(self):
        self.celery_app = celery_app
    
    async def start_email_scan(
        self, 
        user_id: str, 
        account_id: str, 
        scan_type: str = "inbox", 
        months: int = 1
    ) -> Dict[str, Any]:
        """
        Start an email scan task
        
        Args:
            user_id: User ID
            account_id: Email account ID
            scan_type: Type of scan (inbox, groups, all)
            months: Number of months to scan back
            
        Returns:
            Dict with task information
        """
        try:
            # Check if there's already a running task for this user and account
            existing_task = await self.get_active_task_for_account(account_id, user_id)
            if existing_task:
                # Calculate estimated_duration for existing task
                existing_estimated_duration = existing_task.get("estimated_duration")
                if existing_estimated_duration is None or existing_estimated_duration <= 0:
                    existing_estimated_duration = self._estimate_duration(months, scan_type)
                
                return {
                    "message": "Email scan already in progress for this user",
                    "account_id": account_id,
                    "user_id": user_id,
                    "task_id": existing_task["task_id"],
                    "status": "already_running",
                    "estimated_duration": existing_estimated_duration,
                    "existing_task": existing_task
                }
            
            # Import here to avoid circular imports
            from tasks.email_scanning_tasks import scan_user_emails_task
            
            # Start Celery task
            celery_task = scan_user_emails_task.delay(
                user_id=user_id,
                account_id=account_id,
                scan_type=scan_type,
                months=months
            )
            
            # Create database record
            task_record = ScanningTaskModel(
                task_id=celery_task.id,
                user_id=user_id,
                account_id=account_id,
                scan_type=ScanType(scan_type),
                months=months,
                status=TaskStatus.PENDING,
                progress=0,
                current_status="Task queued",
                estimated_duration=self._estimate_duration(months, scan_type)
            )
            
            # Save to database
            result = await mongodb.db["scanning_tasks"].insert_one(task_record.dict())
            task_record.id = str(result.inserted_id)
            
            logger.info(f"Started email scan task: {celery_task.id} for account {account_id}")
            
            # Ensure estimated_duration is always a valid integer
            estimated_duration = task_record.estimated_duration
            if estimated_duration is None or estimated_duration <= 0:
                estimated_duration = self._estimate_duration(months, scan_type)
            
            return {
                "message": f"Email scan started for {months} month{'s' if months > 1 else ''}",
                "account_id": account_id,
                "task_id": celery_task.id,
                "status": "started",
                "estimated_duration": estimated_duration,
                "scan_type": scan_type
            }
            
        except Exception as e:
            logger.error(f"Error starting email scan: {str(e)}")
            logger.error(f"Error details - user_id: {user_id}, account_id: {account_id}, scan_type: {scan_type}, months: {months}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to start email scan: {str(e)}")
    
    async def start_bulk_email_scan(
        self, 
        user_id: str, 
        account_ids: List[str], 
        scan_type: str = "inbox", 
        months: int = 1
    ) -> Dict[str, Any]:
        """
        Start bulk email scan for multiple accounts
        
        Args:
            user_id: User ID
            account_ids: List of email account IDs
            scan_type: Type of scan
            months: Number of months to scan back
            
        Returns:
            Dict with bulk task information
        """
        try:
            # Import here to avoid circular imports
            from tasks.email_scanning_tasks import bulk_scan_emails_task
            
            # Start Celery bulk task
            celery_task = bulk_scan_emails_task.delay(
                user_id=user_id,
                account_ids=account_ids,
                scan_type=scan_type,
                months=months
            )
            
            # Create database record for bulk task
            task_record = ScanningTaskModel(
                task_id=celery_task.id,
                user_id=user_id,
                account_id="bulk",  # Special identifier for bulk tasks
                scan_type=ScanType(scan_type),
                months=months,
                status=TaskStatus.PENDING,
                progress=0,
                current_status="Bulk scan queued",
                estimated_duration=self._estimate_duration(months, scan_type) * len(account_ids)
            )
            
            # Save to database
            result = await mongodb.db["scanning_tasks"].insert_one(task_record.dict())
            task_record.id = str(result.inserted_id)
            
            logger.info(f"Started bulk email scan task: {celery_task.id} for {len(account_ids)} accounts")
            
            # Ensure estimated_duration is always a valid integer
            estimated_duration = task_record.estimated_duration
            if estimated_duration is None or estimated_duration <= 0:
                estimated_duration = self._estimate_duration(months, scan_type) * len(account_ids)
            
            return {
                "message": f"Bulk email scan started for {len(account_ids)} accounts",
                "task_id": celery_task.id,
                "status": "started",
                "account_count": len(account_ids),
                "estimated_duration": estimated_duration
            }
            
        except Exception as e:
            logger.error(f"Error starting bulk email scan: {str(e)}")
            raise Exception(f"Failed to start bulk email scan: {str(e)}")
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a specific task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Dict with task status information
        """
        try:
            # Get task from database
            task_record = await mongodb.db["scanning_tasks"].find_one({"task_id": task_id})
            if not task_record:
                return {"error": "Task not found"}
            
            # Get real-time status from Celery
            celery_result = self.celery_app.AsyncResult(task_id)
            
            # Update database record with latest status
            updated_record = await self._update_task_from_celery(task_record, celery_result)
            
            return {
                "task_id": task_id,
                "status": updated_record["status"],
                "progress": updated_record["progress"],
                "current_status": updated_record["current_status"],
                "result": updated_record.get("result"),
                "error": updated_record.get("error"),
                "created_at": updated_record["created_at"],
                "updated_at": updated_record["updated_at"],
                "estimated_duration": updated_record.get("estimated_duration"),
                "actual_duration": updated_record.get("actual_duration")
            }
            
        except Exception as e:
            logger.error(f"Error getting task status: {str(e)}")
            return {"error": str(e)}
    
    async def get_active_task_for_account(self, account_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get active task for a specific account and user
        
        Args:
            account_id: Email account ID
            user_id: User ID (optional, for user-specific checks)
            
        Returns:
            Active task record or None
        """
        try:
            # Build query - check for active tasks for this specific user and account
            query = {
                "account_id": account_id,
                "status": {"$in": ["PENDING", "PROGRESS"]}
            }
            
            # If user_id is provided, only check for that user's tasks
            if user_id:
                query["user_id"] = user_id
            
            task_record = await mongodb.db["scanning_tasks"].find_one(query)
            return task_record
        except Exception as e:
            logger.error(f"Error getting active task for account {account_id}, user {user_id}: {str(e)}")
            return None
    
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a running task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Dict with cancellation result
        """
        try:
            # Revoke the Celery task
            self.celery_app.control.revoke(task_id, terminate=True)
            
            # Update database record
            await mongodb.db["scanning_tasks"].update_one(
                {"task_id": task_id},
                {"$set": {
                    "status": TaskStatus.CANCELLED,
                    "current_status": "Task cancelled",
                    "updated_at": datetime.utcnow()
                }}
            )
            
            logger.info(f"Cancelled task: {task_id}")
            return {"status": "cancelled", "task_id": task_id}
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}")
            return {"error": str(e)}
    
    async def get_user_tasks(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent tasks for a user
        
        Args:
            user_id: User ID
            limit: Maximum number of tasks to return
            
        Returns:
            List of task records
        """
        try:
            tasks = await mongodb.db["scanning_tasks"].find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(limit).to_list(length=limit)
            
            return tasks
        except Exception as e:
            logger.error(f"Error getting user tasks: {str(e)}")
            return []
    
    async def _update_task_from_celery(self, task_record: Dict, celery_result) -> Dict[str, Any]:
        """
        Update task record with latest Celery status
        """
        try:
            # Ensure database connection
            from core.database import connect_to_mongo
            await connect_to_mongo()
            
            # Get Celery task state and info
            celery_state = celery_result.state
            celery_info = celery_result.info if celery_result.info else {}
            
            # Map Celery states to our status
            status_mapping = {
                "PENDING": TaskStatus.PENDING,
                "PROGRESS": TaskStatus.PROGRESS,
                "SUCCESS": TaskStatus.DONE,  # Map SUCCESS to DONE
                "FAILURE": TaskStatus.FAILURE,
                "REVOKED": TaskStatus.CANCELLED
            }
            
            new_status = status_mapping.get(celery_state, TaskStatus.PENDING)
            
            # Prepare update data
            update_data = {
                "status": new_status,
                "updated_at": datetime.utcnow()
            }
            
            if celery_state == "PROGRESS" and isinstance(celery_info, dict):
                update_data.update({
                    "progress": celery_info.get("progress", task_record.get("progress", 0)),
                    "current_status": celery_info.get("status", task_record.get("current_status", ""))
                })
            elif celery_state == "SUCCESS":
                update_data.update({
                    "progress": 100,
                    "current_status": "Task completed successfully",
                    "result": celery_info,
                    "completed_at": datetime.utcnow()
                })
            elif celery_state == "FAILURE":
                update_data.update({
                    "current_status": "Task failed",
                    "error": str(celery_info),
                    "completed_at": datetime.utcnow()
                })
            
            # Calculate actual duration if completed
            if new_status in [TaskStatus.DONE, TaskStatus.FAILURE, TaskStatus.CANCELLED]:
                if task_record.get("started_at"):
                    started_at = task_record["started_at"]
                    if isinstance(started_at, str):
                        started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    duration = (datetime.utcnow() - started_at).total_seconds() / 60
                    update_data["actual_duration"] = round(duration, 2)
            
            # Update database
            await mongodb.db["scanning_tasks"].update_one(
                {"task_id": task_record["task_id"]},
                {"$set": update_data}
            )
            
            # Return updated record
            task_record.update(update_data)
            return task_record
            
        except Exception as e:
            logger.error(f"Error updating task from Celery: {str(e)}")
            return task_record
    
    def _estimate_duration(self, months: int, scan_type: str) -> int:
        """
        Estimate task duration in minutes
        """
        base_duration = months * 2  # 2 minutes per month base
        
        if scan_type == "groups":
            base_duration += 5  # Groups take longer
        elif scan_type == "all":
            base_duration *= 1.5  # Both inbox and groups
        
        return max(base_duration, 1)  # Minimum 1 minute

# Global task manager instance
task_manager = TaskManager()
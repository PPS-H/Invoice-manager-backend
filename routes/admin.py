"""
Admin routes for monitoring Celery tasks and system health
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from core.jwt import get_current_user
from core.database import mongodb
from core.celery_app import celery_app
from services.task_manager import task_manager
from models.user import UserModel
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/scanning-stats")
async def get_scanning_stats(
    current_user: UserModel = Depends(get_current_user)
):
    """Get scanning statistics for admin monitoring"""
    try:
        # Get task statistics by status
        stats = await mongodb.db["scanning_tasks"].aggregate([
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]).to_list(length=None)
        
        # Get recent tasks
        recent_tasks = await mongodb.db["scanning_tasks"].find(
            {},
            {"task_id": 1, "user_id": 1, "account_id": 1, "status": 1, "created_at": 1, "scan_type": 1}
        ).sort("created_at", -1).limit(20).to_list(length=20)
        
        # Get active workers info
        active_workers = celery_app.control.inspect().active()
        scheduled_tasks = celery_app.control.inspect().scheduled()
        
        return {
            "task_stats": stats,
            "recent_tasks": recent_tasks,
            "active_workers": active_workers,
            "scheduled_tasks": scheduled_tasks,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting scanning stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scanning stats: {str(e)}"
        )

@router.get("/active-tasks")
async def get_active_tasks(
    current_user: UserModel = Depends(get_current_user)
):
    """Get all currently active tasks"""
    try:
        active_tasks = await mongodb.db["scanning_tasks"].find({
            "status": {"$in": ["PENDING", "PROGRESS"]}
        }).sort("created_at", -1).to_list(length=None)
        
        return {
            "active_tasks": active_tasks,
            "count": len(active_tasks),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting active tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active tasks: {str(e)}"
        )

@router.get("/task-queue-status")
async def get_task_queue_status(
    current_user: UserModel = Depends(get_current_user)
):
    """Get Celery task queue status"""
    try:
        # Get queue info from Celery
        inspect = celery_app.control.inspect()
        
        queue_info = {
            "active": inspect.active(),
            "scheduled": inspect.scheduled(),
            "reserved": inspect.reserved(),
            "stats": inspect.stats(),
            "registered": inspect.registered()
        }
        
        return {
            "queue_info": queue_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )

@router.post("/cancel-all-tasks")
async def cancel_all_tasks(
    current_user: UserModel = Depends(get_current_user)
):
    """Cancel all active tasks (admin only)"""
    try:
        # Get all active tasks
        active_tasks = await mongodb.db["scanning_tasks"].find({
            "status": {"$in": ["PENDING", "PROGRESS"]}
        }).to_list(length=None)
        
        cancelled_count = 0
        for task in active_tasks:
            try:
                # Revoke the Celery task
                celery_app.control.revoke(task["task_id"], terminate=True)
                
                # Update database
                await mongodb.db["scanning_tasks"].update_one(
                    {"task_id": task["task_id"]},
                    {"$set": {
                        "status": "CANCELLED",
                        "current_status": "Cancelled by admin",
                        "updated_at": datetime.utcnow()
                    }}
                )
                
                cancelled_count += 1
                
            except Exception as e:
                logger.error(f"Error cancelling task {task['task_id']}: {str(e)}")
        
        return {
            "message": f"Cancelled {cancelled_count} active tasks",
            "cancelled_count": cancelled_count,
            "total_active": len(active_tasks)
        }
        
    except Exception as e:
        logger.error(f"Error cancelling all tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel tasks: {str(e)}"
        )

@router.get("/system-health")
async def get_system_health(
    current_user: UserModel = Depends(get_current_user)
):
    """Get overall system health status"""
    try:
        # Check database connection
        db_status = "healthy"
        try:
            await mongodb.db.command("ping")
        except Exception:
            db_status = "unhealthy"
        
        # Check Redis connection
        redis_status = "healthy"
        try:
            celery_app.control.inspect().ping()
        except Exception:
            redis_status = "unhealthy"
        
        # Get task statistics
        task_stats = await mongodb.db["scanning_tasks"].aggregate([
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]).to_list(length=None)
        
        # Get failed tasks in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        failed_tasks = await mongodb.db["scanning_tasks"].count_documents({
            "status": "FAILURE",
            "updated_at": {"$gte": one_hour_ago}
        })
        
        return {
            "overall_status": "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
            "database": db_status,
            "redis": redis_status,
            "celery": redis_status,  # Redis and Celery are connected
            "task_stats": task_stats,
            "failed_tasks_last_hour": failed_tasks,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}"
        )

@router.get("/user-tasks/{user_id}")
async def get_user_tasks_admin(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_user)
):
    """Get all tasks for a specific user (admin only)"""
    try:
        # Get user's tasks
        tasks = await mongodb.db["scanning_tasks"].find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
        
        return {
            "user_id": user_id,
            "tasks": tasks,
            "total": len(tasks)
        }
        
    except Exception as e:
        logger.error(f"Error getting user tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user tasks: {str(e)}"
        )

@router.delete("/cleanup-old-tasks")
async def cleanup_old_tasks(
    days: int = Query(7, ge=1, le=30),
    current_user: UserModel = Depends(get_current_user)
):
    """Clean up old completed tasks (admin only)"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        result = await mongodb.db["scanning_tasks"].delete_many({
            "status": {"$in": ["SUCCESS", "FAILURE", "CANCELLED"]},
            "updated_at": {"$lt": cutoff_time}
        })
        
        return {
            "message": f"Cleaned up {result.deleted_count} old tasks",
            "deleted_count": result.deleted_count,
            "cutoff_days": days
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup tasks: {str(e)}"
        )
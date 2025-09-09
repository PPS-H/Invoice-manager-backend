#!/usr/bin/env python3
"""
Log viewer for email scanning tasks
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.database import connect_to_mongo, mongodb

async def view_recent_tasks():
    """View recent email scanning tasks"""
    try:
        await connect_to_mongo()
        
        print("🔍 Recent Email Scanning Tasks")
        print("=" * 60)
        
        # Get recent tasks
        recent_tasks = await mongodb.db["scanning_tasks"].find(
            {}
        ).sort("created_at", -1).limit(10).to_list(length=10)
        
        if not recent_tasks:
            print("No tasks found in database.")
            return
        
        for task in recent_tasks:
            print(f"\n📋 Task ID: {task['task_id']}")
            print(f"   User: {task['user_id']}")
            print(f"   Account: {task['account_id']}")
            print(f"   Type: {task['scan_type']}")
            print(f"   Status: {task['status']}")
            print(f"   Progress: {task.get('progress', 0)}%")
            print(f"   Created: {task['created_at']}")
            print(f"   Updated: {task['updated_at']}")
            
            if task.get('current_status'):
                print(f"   Current: {task['current_status']}")
            
            if task.get('error'):
                print(f"   ❌ Error: {task['error']}")
            
            if task.get('result'):
                result = task['result']
                if isinstance(result, dict):
                    print(f"   ✅ Result: {result.get('invoices_found', 0)} invoices found")
                    print(f"      Processed: {result.get('processed_count', 0)} emails")
        
    except Exception as e:
        print(f"❌ Error viewing tasks: {e}")

async def view_active_tasks():
    """View currently active tasks"""
    try:
        await connect_to_mongo()
        
        print("\n🚀 Currently Active Tasks")
        print("=" * 60)
        
        # Get active tasks
        active_tasks = await mongodb.db["scanning_tasks"].find({
            "status": {"$in": ["PENDING", "PROGRESS"]}
        }).sort("created_at", -1).to_list(length=None)
        
        if not active_tasks:
            print("No active tasks found.")
            return
        
        for task in active_tasks:
            print(f"\n🔄 Active Task: {task['task_id']}")
            print(f"   User: {task['user_id']}")
            print(f"   Account: {task['account_id']}")
            print(f"   Status: {task['status']}")
            print(f"   Progress: {task.get('progress', 0)}%")
            print(f"   Started: {task['created_at']}")
            
            if task.get('current_status'):
                print(f"   Current: {task['current_status']}")
            
            if task.get('estimated_duration'):
                print(f"   Estimated: {task['estimated_duration']} minutes")
    
    except Exception as e:
        print(f"❌ Error viewing active tasks: {e}")

async def view_task_stats():
    """View task statistics"""
    try:
        await connect_to_mongo()
        
        print("\n📊 Task Statistics")
        print("=" * 60)
        
        # Get task statistics
        stats = await mongodb.db["scanning_tasks"].aggregate([
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]).to_list(length=None)
        
        for stat in stats:
            status = stat["_id"]
            count = stat["count"]
            emoji = {
                "PENDING": "⏳",
                "PROGRESS": "🔄", 
                "SUCCESS": "✅",
                "FAILURE": "❌",
                "CANCELLED": "🚫"
            }.get(status, "📋")
            
            print(f"{emoji} {status}: {count} tasks")
        
        # Get recent activity
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = await mongodb.db["scanning_tasks"].count_documents({
            "created_at": {"$gte": one_hour_ago}
        })
        
        print(f"\n📈 Recent Activity (last hour): {recent_count} tasks")
    
    except Exception as e:
        print(f"❌ Error viewing stats: {e}")

async def main():
    """Main log viewer"""
    print("📋 Email Scanning Log Viewer")
    print("=" * 60)
    
    await view_recent_tasks()
    await view_active_tasks()
    await view_task_stats()
    
    print("\n" + "=" * 60)
    print("💡 To see real-time logs:")
    print("   1. Celery Worker: Check the terminal where you started 'python3 start_celery_worker.py'")
    print("   2. FastAPI Server: Check the terminal where you started 'python3 main.py'")
    print("   3. Database Logs: Run this script again to see updated task status")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Log viewer stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
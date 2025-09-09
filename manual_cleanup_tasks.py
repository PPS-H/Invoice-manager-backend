#!/usr/bin/env python3
"""
Manual cleanup script for old scanning tasks
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.database import connect_to_mongo, mongodb
from tasks.email_scanning_tasks import cleanup_old_tasks

async def manual_cleanup_old_tasks(days: int = 7):
    """Manually clean up old tasks"""
    try:
        print(f"🧹 Manual Cleanup of Tasks Older Than {days} Days")
        print("=" * 50)
        
        # Connect to database
        await connect_to_mongo()
        
        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        print(f"📅 Cutoff time: {cutoff_time}")
        
        # Count tasks before cleanup
        total_tasks = await mongodb.db["scanning_tasks"].count_documents({})
        old_tasks = await mongodb.db["scanning_tasks"].count_documents({
            "status": {"$in": ["SUCCESS", "FAILURE", "CANCELLED"]},
            "updated_at": {"$lt": cutoff_time}
        })
        
        print(f"📊 Current task statistics:")
        print(f"   📋 Total tasks: {total_tasks}")
        print(f"   🗑️  Old tasks to delete: {old_tasks}")
        
        if old_tasks == 0:
            print("✅ No old tasks to clean up!")
            return
        
        # Perform cleanup
        print(f"\n🧹 Cleaning up {old_tasks} old tasks...")
        result = await mongodb.db["scanning_tasks"].delete_many({
            "status": {"$in": ["SUCCESS", "FAILURE", "CANCELLED"]},
            "updated_at": {"$lt": cutoff_time}
        })
        
        print(f"✅ Cleanup completed!")
        print(f"   🗑️  Deleted: {result.deleted_count} tasks")
        
        # Show remaining tasks
        remaining_tasks = await mongodb.db["scanning_tasks"].count_documents({})
        print(f"   📋 Remaining: {remaining_tasks} tasks")
        
        # Show task status breakdown
        status_counts = {}
        async for task in mongodb.db["scanning_tasks"].aggregate([
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]):
            status_counts[task["_id"]] = task["count"]
        
        print(f"\n📊 Remaining tasks by status:")
        for status, count in status_counts.items():
            print(f"   {status}: {count}")
        
        return result.deleted_count
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        return 0

async def test_automatic_cleanup():
    """Test the automatic cleanup task"""
    try:
        print("\n🤖 Testing Automatic Cleanup Task")
        print("=" * 50)
        
        # Call the Celery cleanup task directly
        result = cleanup_old_tasks()
        print(f"✅ Automatic cleanup result: {result}")
        
        return result
        
    except Exception as e:
        print(f"❌ Automatic cleanup test failed: {e}")
        return None

async def show_task_statistics():
    """Show current task statistics"""
    try:
        print("\n📊 Current Task Statistics")
        print("=" * 50)
        
        await connect_to_mongo()
        
        # Total tasks
        total_tasks = await mongodb.db["scanning_tasks"].count_documents({})
        print(f"📋 Total tasks: {total_tasks}")
        
        # Tasks by status
        status_counts = {}
        async for task in mongodb.db["scanning_tasks"].aggregate([
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]):
            status_counts[task["_id"]] = task["count"]
        
        print(f"\n📊 Tasks by status:")
        for status, count in status_counts.items():
            print(f"   {status}: {count}")
        
        # Recent tasks
        recent_tasks = await mongodb.db["scanning_tasks"].find(
            {},
            {"task_id": 1, "user_id": 1, "status": 1, "created_at": 1}
        ).sort("created_at", -1).limit(5).to_list(5)
        
        print(f"\n🕒 Recent tasks (last 5):")
        for task in recent_tasks:
            print(f"   📋 {task['task_id'][:8]}... - {task['status']} - {task['created_at']}")
        
        # Old tasks
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        old_tasks = await mongodb.db["scanning_tasks"].count_documents({
            "status": {"$in": ["SUCCESS", "FAILURE", "CANCELLED"]},
            "updated_at": {"$lt": cutoff_24h}
        })
        
        print(f"\n🗑️  Tasks older than 24h: {old_tasks}")
        
    except Exception as e:
        print(f"❌ Failed to get statistics: {e}")

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manual cleanup of old scanning tasks")
    parser.add_argument("--days", type=int, default=7, help="Days to keep (default: 7)")
    parser.add_argument("--test-auto", action="store_true", help="Test automatic cleanup")
    parser.add_argument("--stats", action="store_true", help="Show task statistics")
    parser.add_argument("--cleanup", action="store_true", help="Perform manual cleanup")
    
    args = parser.parse_args()
    
    if args.stats:
        await show_task_statistics()
    
    if args.test_auto:
        await test_automatic_cleanup()
    
    if args.cleanup:
        await manual_cleanup_old_tasks(args.days)
    
    if not any([args.stats, args.test_auto, args.cleanup]):
        # Default: show stats and cleanup
        await show_task_statistics()
        await manual_cleanup_old_tasks(args.days)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Cleanup interrupted by user")
    except Exception as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)
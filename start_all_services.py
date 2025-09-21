#!/usr/bin/env python3
"""
Script to start all required services for the invoice processing system
"""
import subprocess
import sys
import time
import os
from pathlib import Path


def start_service(name, command, background=True):
    """Start a service with the given command"""
    try:
        print(f"🚀 Starting {name}...")
        if background:
            process = subprocess.Popen(command, shell=True)
            print(f"✅ {name} started with PID: {process.pid}")
            return process
        else:
            subprocess.run(command, shell=True, check=True)
            print(f"✅ {name} completed")
            return None
    except Exception as e:
        print(f"❌ Failed to start {name}: {e}")
        return None

def check_service_running(service_name):
    """Check if a service is running"""
    try:
        result = subprocess.run(f"ps aux | grep -v grep | grep '{service_name}'", 
                              shell=True, capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except:
        return False

def main():
    """Main function to start all services"""
    print("🎯 Starting All Invoice Processing Services")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("core/celery_app.py").exists():
        print("❌ Please run this script from the backend directory")
        sys.exit(1)
    
    services = []
    
    # 1. Check Redis
    print("\n1️⃣ Checking Redis...")
    if check_service_running("redis-server"):
        print("✅ Redis is already running")
    else:
        print("⚠️  Redis not running. Please start it with: sudo systemctl start redis-server")
    
    # 2. Start Celery Worker
    print("\n2️⃣ Starting Celery Worker...")
    if check_service_running("celery.*worker"):
        print("✅ Celery Worker is already running")
    else:
        worker_process = start_service("Celery Worker", "python3 start_celery_worker.py")
        if worker_process:
            services.append(("Celery Worker", worker_process))
        time.sleep(2)
    
    # 3. Start Celery Beat (for automatic cleanup)
    print("\n3️⃣ Starting Celery Beat...")
    if check_service_running("celery.*beat"):
        print("✅ Celery Beat is already running")
    else:
        beat_process = start_service("Celery Beat", "python3 -m celery -A core.celery_app beat --loglevel=info")
        if beat_process:
            services.append(("Celery Beat", beat_process))
        time.sleep(2)
    
    # 4. Start FastAPI Server
    print("\n4️⃣ Starting FastAPI Server...")
    if check_service_running("python.*main.py"):
        print("✅ FastAPI Server is already running")
    else:
        server_process = start_service("FastAPI Server", "python3 main.py")
        if server_process:
            services.append(("FastAPI Server", server_process))
    
    # 5. Verify services
    print("\n5️⃣ Verifying Services...")
    time.sleep(3)
    
    redis_running = check_service_running("redis-server")
    worker_running = check_service_running("celery.*worker")
    beat_running = check_service_running("celery.*beat")
    server_running = check_service_running("python.*main.py")
    
    print(f"📊 Service Status:")
    print(f"   Redis: {'✅ Running' if redis_running else '❌ Not Running'}")
    print(f"   Celery Worker: {'✅ Running' if worker_running else '❌ Not Running'}")
    print(f"   Celery Beat: {'✅ Running' if beat_running else '❌ Not Running'}")
    print(f"   FastAPI Server: {'✅ Running' if server_running else '❌ Not Running'}")
    
    # 6. Test automatic cleanup
    if beat_running:
        print("\n6️⃣ Testing Automatic Cleanup...")
        try:
            from tasks.email_scanning_tasks import cleanup_old_tasks
            result = cleanup_old_tasks()
            print(f"✅ Automatic cleanup test: {result}")
        except Exception as e:
            print(f"❌ Automatic cleanup test failed: {e}")
    
    # 7. Show usage instructions
    print("\n" + "=" * 50)
    print("🎉 Services Started Successfully!")
    print("\n📋 Available Commands:")
    print("   • View task logs: python3 view_logs.py")
    print("   • Manual cleanup: python3 manual_cleanup_tasks.py --cleanup")
    print("   • Task statistics: python3 manual_cleanup_tasks.py --stats")
    print("   • Test multiple users: python3 test_celery_multiple_users.py")
    
    print("\n🌐 API Endpoints:")
    print("   • Health check: http://localhost:8000/api/admin/health")
    print("   • Task cleanup: DELETE http://localhost:8000/api/admin/cleanup-old-tasks")
    print("   • Email scan: POST http://localhost:8000/api/email-accounts/{id}/sync-inbox")
    
    print("\n⏰ Automatic Cleanup:")
    if beat_running:
        print("   ✅ Automatic cleanup is ENABLED (runs every hour)")
        print("   🗑️  Cleans up tasks older than 24 hours")
    else:
        print("   ⚠️  Automatic cleanup is DISABLED (Celery Beat not running)")
        print("   🔧 Use manual cleanup: python3 manual_cleanup_tasks.py --cleanup")
    
    print("\n🛑 To stop services:")
    print("   • Press Ctrl+C to stop this script")
    print("   • Or kill processes manually: pkill -f celery")
    
    # Keep script running
    try:
        print("\n⏳ Services are running... Press Ctrl+C to stop")
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        for name, process in services:
            if process and process.poll() is None:
                print(f"   Stopping {name}...")
                process.terminate()
        print("👋 All services stopped")

if __name__ == "__main__":
    main()
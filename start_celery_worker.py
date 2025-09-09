#!/usr/bin/env python3
"""
Start Celery worker for email scanning tasks
"""
import os
import sys
import subprocess
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def start_celery_worker():
    """Start Celery worker with proper configuration"""
    
    # Set environment variables
    env = os.environ.copy()
    env['PYTHONPATH'] = str(backend_dir)
    
    # Celery worker command
    cmd = [
        'celery',
        '-A', 'core.celery_app',
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--queues=email_scanning',
        '--hostname=worker@%h',
        '--pool=prefork',
        '--max-tasks-per-child=50',
        '--time-limit=1800',  # 30 minutes
        '--soft-time-limit=1500'  # 25 minutes
    ]
    
    print("🚀 Starting Celery worker for email scanning...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 50)
    
    try:
        # Start the worker
        subprocess.run(cmd, env=env, cwd=backend_dir)
    except KeyboardInterrupt:
        print("\n🛑 Celery worker stopped by user")
    except Exception as e:
        print(f"❌ Error starting Celery worker: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_celery_worker()
#!/usr/bin/env python3
"""
Start Celery beat scheduler for periodic tasks
"""
import os
import sys
import subprocess
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def start_celery_beat():
    """Start Celery beat scheduler"""
    
    # Set environment variables
    env = os.environ.copy()
    env['PYTHONPATH'] = str(backend_dir)
    
    # Celery beat command
    cmd = [
        'celery',
        '-A', 'core.celery_app',
        'beat',
        '--loglevel=info',
        '--scheduler=celery.beat:PersistentScheduler'
    ]
    
    print("⏰ Starting Celery beat scheduler...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 50)
    
    try:
        # Start the beat scheduler
        subprocess.run(cmd, env=env, cwd=backend_dir)
    except KeyboardInterrupt:
        print("\n🛑 Celery beat stopped by user")
    except Exception as e:
        print(f"❌ Error starting Celery beat: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_celery_beat()
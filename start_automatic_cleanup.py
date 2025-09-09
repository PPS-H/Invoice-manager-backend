#!/usr/bin/env python3
"""
Simple script to start automatic cleanup (Celery Beat)
"""
import subprocess
import sys
import time
import signal
import os

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\n🛑 Stopping automatic cleanup...')
    sys.exit(0)

def main():
    """Start Celery Beat for automatic cleanup"""
    print("🕒 Starting Automatic Task Cleanup")
    print("=" * 40)
    print("✅ This will run cleanup every hour")
    print("🗑️  Cleans up tasks older than 24 hours")
    print("⏹️  Press Ctrl+C to stop")
    print("=" * 40)
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start Celery Beat
        print("🚀 Starting Celery Beat...")
        process = subprocess.Popen([
            sys.executable, "-m", "celery", 
            "-A", "core.celery_app", 
            "beat", 
            "--loglevel=info"
        ])
        
        print(f"✅ Celery Beat started with PID: {process.pid}")
        print("🔄 Automatic cleanup is now running every hour")
        
        # Wait for the process
        process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping automatic cleanup...")
        if 'process' in locals():
            process.terminate()
    except Exception as e:
        print(f"❌ Error starting automatic cleanup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
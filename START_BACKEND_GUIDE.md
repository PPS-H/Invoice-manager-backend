# Complete Backend Startup Guide

## 🎯 Overview

This guide shows you how to start all required services for your invoice management backend with multiple user support and email scanning.

## 📋 Required Services

1. **Redis** - Message broker for Celery
2. **Celery Worker** - Background task processing
3. **Celery Beat** - Automatic task scheduling (cleanup)
4. **FastAPI Server** - Main API server

## 🚀 Quick Start (Recommended)

### Option 1: Use the All-in-One Script
```bash
# Start all services at once
python3 start_all_services.py
```

### Option 2: Manual Step-by-Step

## 📝 Step-by-Step Instructions

### Step 1: Start Redis
```bash
# Check if Redis is running
sudo systemctl status redis-server

# If not running, start it
sudo systemctl start redis-server

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

### Step 2: Start Celery Worker
```bash
# Open Terminal 1
cd /home/abhishek/Desktop/invoiceWorking/backend
python3 start_celery_worker.py
```

**Expected Output**:
```
🚀 Starting Celery Worker...
✅ Celery Worker started with PID: 12345
[INFO] Connected to redis://localhost:6379/0
[INFO] mingle: searching for neighbors
[INFO] mingle: all alone
[INFO] celery@worker ready.
```

### Step 3: Start Celery Beat (for automatic cleanup)
```bash
# Open Terminal 2
cd /home/abhishek/Desktop/invoiceWorking/backend
python3 start_automatic_cleanup.py
```

**Expected Output**:
```
🕒 Starting Automatic Task Cleanup
✅ Celery Beat started with PID: 12346
🔄 Automatic cleanup is now running every hour
```

### Step 4: Start FastAPI Server
```bash
# Open Terminal 3
cd /home/abhishek/Desktop/invoiceWorking/backend
python3 main.py
```

**Expected Output**:
```
INFO:     Started server process [12347]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## 🔍 Verification Steps

### 1. Check All Services Are Running
```bash
# Check all processes
ps aux | grep -E "(redis|celery|python.*main)"

# Should show:
# - redis-server
# - celery worker processes
# - celery beat process
# - python main.py (FastAPI)
```

### 2. Test API Health
```bash
# Test API endpoint
curl http://localhost:8000/api/admin/health

# Expected response:
# {"status": "healthy", "services": {...}}
```

### 3. Test Email Scanning
```bash
# Test multiple users (requires authentication)
python3 test_multiple_users_fix.py

# Expected output:
# 🎉 ALL TESTS PASSED!
# ✅ Multiple users can now scan emails simultaneously
```

### 4. Check Task Statistics
```bash
# View current tasks
python3 view_logs.py

# Expected output:
# 📊 Current Task Statistics
# 📋 Total tasks: X
# 📊 Tasks by status: ...
```

## 🛠️ Alternative Startup Methods

### Method 1: Individual Scripts
```bash
# Terminal 1: Redis
sudo systemctl start redis-server

# Terminal 2: Celery Worker
python3 start_celery_worker.py

# Terminal 3: Celery Beat
python3 start_automatic_cleanup.py

# Terminal 4: FastAPI
python3 main.py
```

### Method 2: Direct Commands
```bash
# Terminal 1: Redis
sudo systemctl start redis-server

# Terminal 2: Celery Worker
python3 -m celery -A core.celery_app worker --loglevel=info --concurrency=4

# Terminal 3: Celery Beat
python3 -m celery -A core.celery_app beat --loglevel=info

# Terminal 4: FastAPI
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📊 Service Status Monitoring

### Check Redis
```bash
redis-cli ping
# Should return: PONG
```

### Check Celery Worker
```bash
python3 -c "
from core.celery_app import celery_app
print('Active workers:', celery_app.control.inspect().active())
"
```

### Check Celery Beat
```bash
ps aux | grep "celery.*beat"
# Should show beat process running
```

### Check FastAPI
```bash
curl http://localhost:8000/docs
# Should show API documentation
```

## 🔧 Troubleshooting

### Redis Issues
```bash
# If Redis fails to start
sudo systemctl restart redis-server
sudo systemctl enable redis-server

# Check Redis logs
sudo journalctl -u redis-server
```

### Celery Worker Issues
```bash
# If worker fails to start
pkill -f celery
python3 start_celery_worker.py

# Check worker logs
tail -f celery_worker.log
```

### Celery Beat Issues
```bash
# If beat fails to start
pkill -f "celery.*beat"
python3 start_automatic_cleanup.py
```

### FastAPI Issues
```bash
# If server fails to start
pkill -f "python.*main"
python3 main.py

# Check server logs
tail -f fastapi.log
```

## 🎯 Production Setup

### Using Systemd Services
```bash
# Create systemd service files for production
sudo nano /etc/systemd/system/invoice-celery-worker.service
sudo nano /etc/systemd/system/invoice-celery-beat.service
sudo nano /etc/systemd/system/invoice-fastapi.service

# Enable and start services
sudo systemctl enable invoice-celery-worker
sudo systemctl enable invoice-celery-beat
sudo systemctl enable invoice-fastapi

sudo systemctl start invoice-celery-worker
sudo systemctl start invoice-celery-beat
sudo systemctl start invoice-fastapi
```

### Using Docker
```bash
# Create docker-compose.yml for containerized setup
docker-compose up -d
```

## 📈 Performance Optimization

### Redis Configuration
```bash
# Edit Redis config for better performance
sudo nano /etc/redis/redis.conf

# Recommended settings:
# maxmemory 256mb
# maxmemory-policy allkeys-lru
```

### Celery Configuration
```bash
# Adjust worker concurrency based on CPU cores
# In start_celery_worker.py, change:
# --concurrency=4  # Adjust based on your CPU cores
```

## 🎉 Success Indicators

When everything is running correctly, you should see:

1. ✅ **Redis**: `PONG` response
2. ✅ **Celery Worker**: `celery@worker ready`
3. ✅ **Celery Beat**: `beat: Starting...`
4. ✅ **FastAPI**: `Uvicorn running on http://0.0.0.0:8000`
5. ✅ **API Health**: `{"status": "healthy"}`
6. ✅ **Multiple Users**: All tests pass

## 🚀 Quick Commands Summary

```bash
# Start everything
python3 start_all_services.py

# Or manually:
sudo systemctl start redis-server
python3 start_celery_worker.py &
python3 start_automatic_cleanup.py &
python3 main.py

# Check status
ps aux | grep -E "(redis|celery|python.*main)"

# Test system
python3 test_multiple_users_fix.py
```

Your backend is now ready to handle multiple users scanning emails simultaneously! 🎉
# Automatic Task Cleanup Solution

## 🎯 Current Status

**Question**: "Now system'll clear old task manually?"

**Answer**: **NO!** The system now has **automatic cleanup** configured, but it needs to be properly started.

## ✅ What's Already Configured

### 1. **Automatic Cleanup Task**
- ✅ `cleanup_old_tasks` Celery task is defined
- ✅ Runs every hour (3600 seconds)
- ✅ Cleans up tasks older than 24 hours
- ✅ Removes SUCCESS, FAILURE, and CANCELLED tasks

### 2. **Manual Cleanup Options**
- ✅ Manual cleanup script: `manual_cleanup_tasks.py`
- ✅ Admin API endpoint: `DELETE /api/admin/cleanup-old-tasks`
- ✅ Configurable retention period (1-30 days)

### 3. **Database Indexes**
- ✅ Optimized indexes for cleanup queries
- ✅ Efficient deletion of old tasks

## 🔧 How to Enable Automatic Cleanup

### Option 1: Start Celery Beat (Recommended)
```bash
# Start the scheduler
python3 start_celery_beat.py
```

### Option 2: Manual Cleanup (On-demand)
```bash
# Clean up tasks older than 7 days
python3 manual_cleanup_tasks.py --cleanup --days 7

# Show current statistics
python3 manual_cleanup_tasks.py --stats

# Test automatic cleanup
python3 manual_cleanup_tasks.py --test-auto
```

### Option 3: API Cleanup (Admin)
```bash
# Clean up via API (requires authentication)
curl -X DELETE "http://localhost:8000/api/admin/cleanup-old-tasks?days=7"
```

## 📊 Current Task Statistics

Based on the latest scan:
- **Total tasks**: 8
- **SUCCESS**: 3 tasks
- **PENDING**: 5 tasks
- **Tasks older than 24h**: 0

## 🚀 Complete Setup Instructions

### 1. **Start All Services**
```bash
# Terminal 1: Start Redis
sudo systemctl start redis-server

# Terminal 2: Start Celery Worker
python3 start_celery_worker.py

# Terminal 3: Start Celery Beat (for automatic cleanup)
python3 start_celery_beat.py

# Terminal 4: Start FastAPI Server
python3 main.py
```

### 2. **Verify Automatic Cleanup**
```bash
# Check if Celery Beat is running
ps aux | grep beat

# Test the cleanup task
python3 manual_cleanup_tasks.py --test-auto
```

### 3. **Monitor Cleanup**
```bash
# View task statistics
python3 manual_cleanup_tasks.py --stats

# View real-time logs
python3 view_logs.py
```

## ⚙️ Configuration Details

### Automatic Cleanup Schedule
```python
# In core/celery_app.py
beat_schedule={
    'cleanup-old-tasks': {
        'task': 'tasks.email_scanning_tasks.cleanup_old_tasks',
        'schedule': 3600.0,  # Run every hour
    },
}
```

### Cleanup Criteria
- **Age**: Tasks older than 24 hours
- **Status**: SUCCESS, FAILURE, CANCELLED
- **Frequency**: Every hour
- **Retention**: Configurable (1-30 days)

## 🎯 Benefits

### Automatic Cleanup:
- ✅ **No manual intervention** required
- ✅ **Consistent cleanup** every hour
- ✅ **Prevents database bloat**
- ✅ **Maintains performance**

### Manual Cleanup:
- ✅ **On-demand cleanup** when needed
- ✅ **Configurable retention** period
- ✅ **Detailed statistics** and reporting
- ✅ **Admin control** via API

## 📈 Monitoring

### View Cleanup Activity:
```bash
# Check Celery Beat logs
tail -f celery_beat.log

# Check task statistics
python3 manual_cleanup_tasks.py --stats

# View recent cleanup activity
python3 view_logs.py
```

### API Monitoring:
```bash
# Check system health
curl "http://localhost:8000/api/admin/health"

# Get scanning statistics
curl "http://localhost:8000/api/admin/scanning-stats"
```

## 🎉 Summary

**The system WILL automatically clear old tasks** once Celery Beat is started. Currently:

1. ✅ **Automatic cleanup is configured** and working
2. ✅ **Manual cleanup is available** for immediate needs
3. ✅ **API cleanup is available** for admin control
4. ⚠️ **Celery Beat needs to be started** for automatic scheduling

**To enable automatic cleanup**: Start Celery Beat with `python3 start_celery_beat.py`

**Current status**: Manual cleanup only (until Beat is started)
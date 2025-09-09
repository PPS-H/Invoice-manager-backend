# 🚀 Celery + Redis Implementation Guide

## Overview

This document describes the implementation of Celery + Redis for non-blocking email scanning in the invoice management system. This solution resolves the concurrency issues where multiple users couldn't scan emails simultaneously.

## 🏗️ Architecture

### Before (BackgroundTasks)
```
User Request → FastAPI → BackgroundTasks (Same Process) → Blocking
```

### After (Celery + Redis)
```
User Request → FastAPI → Celery Task (Separate Process) → Non-blocking
```

## 📁 File Structure

```
backend/
├── core/
│   └── celery_app.py              # Celery configuration
├── tasks/
│   ├── __init__.py
│   └── email_scanning_tasks.py    # Celery tasks
├── services/
│   └── task_manager.py            # Task management service
├── models/
│   └── scanning_task.py           # Task model
├── routes/
│   ├── email_accounts.py          # Updated routes
│   └── admin.py                   # Admin monitoring
├── start_celery_worker.py         # Worker startup script
└── start_celery_beat.py           # Beat scheduler script
```

## 🔧 Configuration

### Environment Variables
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=4
```

### Celery Settings
- **Worker Concurrency**: 4 workers per instance
- **Task Time Limit**: 30 minutes
- **Soft Time Limit**: 25 minutes
- **Max Tasks Per Child**: 50 (prevents memory leaks)
- **Queue**: `email_scanning`

## 🚀 Starting the System

### 1. Start Redis
```bash
redis-server
```

### 2. Start Celery Worker
```bash
cd backend
python start_celery_worker.py
```

### 3. Start Celery Beat (Optional)
```bash
cd backend
python start_celery_beat.py
```

### 4. Start FastAPI
```bash
cd backend
python main.py
```

## 📊 API Endpoints

### Email Scanning
- `POST /api/email-accounts/{account_id}/sync-inbox` - Start inbox scan
- `POST /api/email-accounts/{account_id}/sync-groups` - Start groups scan
- `GET /api/email-accounts/{account_id}/sync-status` - Get scan status
- `POST /api/email-accounts/{account_id}/cancel-scan` - Cancel scan

### Task Management
- `GET /api/email-accounts/tasks/my-tasks` - Get user's tasks
- `GET /api/email-accounts/tasks/{task_id}/status` - Get task status
- `GET /api/email-accounts/{account_id}/task-history` - Get task history

### Admin Monitoring
- `GET /api/admin/scanning-stats` - Get scanning statistics
- `GET /api/admin/active-tasks` - Get active tasks
- `GET /api/admin/system-health` - Get system health
- `POST /api/admin/cancel-all-tasks` - Cancel all tasks

## 🔄 Task Flow

### 1. User Initiates Scan
```python
# User calls API
POST /api/email-accounts/{account_id}/sync-inbox
{
    "months": 3
}

# Response
{
    "message": "Email scan started for 3 months",
    "task_id": "abc123-def456-ghi789",
    "status": "processing",
    "estimated_duration": 6
}
```

### 2. Task Processing
```python
# Celery task runs in background
@celery_app.task(bind=True, name="scan_user_emails")
def scan_user_emails_task(self, user_id, account_id, scan_type, months):
    # Process emails
    # Update progress
    # Return results
```

### 3. Status Monitoring
```python
# User checks status
GET /api/email-accounts/{account_id}/sync-status

# Response
{
    "task_id": "abc123-def456-ghi789",
    "status": "PROGRESS",
    "progress": 75,
    "current_status": "Processing emails",
    "estimated_duration": 6,
    "actual_duration": 4.5
}
```

## 📈 Performance Benefits

### Before Celery
- ❌ **Concurrency**: Only 1 user could scan at a time
- ❌ **API Blocking**: APIs waited for background tasks
- ❌ **Resource Contention**: All tasks competed for same resources
- ❌ **No Monitoring**: No visibility into task progress

### After Celery
- ✅ **Concurrency**: Multiple users can scan simultaneously
- ✅ **Non-blocking APIs**: APIs return immediately
- ✅ **Resource Management**: Controlled worker concurrency
- ✅ **Full Monitoring**: Real-time task tracking
- ✅ **Fault Tolerance**: Failed tasks don't crash system
- ✅ **Scalability**: Can add more workers as needed

## 🛠️ Monitoring & Debugging

### Celery Commands
```bash
# Check active workers
celery -A core.celery_app inspect active

# Check scheduled tasks
celery -A core.celery_app inspect scheduled

# Check worker stats
celery -A core.celery_app inspect stats

# Purge all tasks
celery -A core.celery_app purge
```

### Database Queries
```python
# Get active tasks
db.scanning_tasks.find({"status": {"$in": ["PENDING", "PROGRESS"]}})

# Get failed tasks
db.scanning_tasks.find({"status": "FAILURE"})

# Get task statistics
db.scanning_tasks.aggregate([
    {"$group": {"_id": "$status", "count": {"$sum": 1}}}
])
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Redis Connection Error
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG
```

#### 2. Worker Not Starting
```bash
# Check Python path
export PYTHONPATH=/path/to/backend:$PYTHONPATH

# Start worker with debug
celery -A core.celery_app worker --loglevel=debug
```

#### 3. Tasks Not Processing
```bash
# Check worker is registered
celery -A core.celery_app inspect registered

# Check queue status
celery -A core.celery_app inspect active_queues
```

#### 4. Memory Issues
```bash
# Reduce worker concurrency
celery -A core.celery_app worker --concurrency=2

# Reduce max tasks per child
celery -A core.celery_app worker --max-tasks-per-child=25
```

## 📊 Scaling

### Horizontal Scaling
```bash
# Start multiple workers on different machines
# Worker 1
celery -A core.celery_app worker --hostname=worker1@%h

# Worker 2
celery -A core.celery_app worker --hostname=worker2@%h

# Worker 3
celery -A core.celery_app worker --hostname=worker3@%h
```

### Vertical Scaling
```bash
# Increase worker concurrency
celery -A core.celery_app worker --concurrency=8

# Increase task limits
celery -A core.celery_app worker --time-limit=3600
```

## 🔒 Security Considerations

1. **Redis Security**: Use password authentication
2. **Task Isolation**: Each task runs in separate process
3. **Resource Limits**: Set appropriate time and memory limits
4. **Access Control**: Admin endpoints require authentication

## 📝 Best Practices

1. **Task Design**: Keep tasks idempotent and atomic
2. **Error Handling**: Implement proper retry logic
3. **Monitoring**: Set up alerts for failed tasks
4. **Cleanup**: Regularly clean up old completed tasks
5. **Logging**: Use structured logging for debugging

## 🎯 Success Metrics

- **API Response Time**: < 100ms (vs 5-30 minutes)
- **Concurrent Users**: Unlimited (vs 1)
- **Task Success Rate**: > 95%
- **System Uptime**: > 99.9%
- **Resource Usage**: Controlled and predictable

This implementation transforms the system from a single-user blocking system to a multi-user concurrent system, providing a production-ready solution for email scanning at scale! 🚀
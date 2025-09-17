"""
Celery configuration for background task processing
"""
from celery import Celery
from core.config import settings
import os
import redis

# Redis configuration
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://default:email@redis-17402.c84.us-east-1-2.ec2.redns.redis-cloud.com:17402/0"
)

# ✅ Setup Redis Connection Pool (Limits total open connections)
# This prevents creating too many Redis connections (which hits max_clients)
redis_pool = redis.ConnectionPool.from_url(
    REDIS_URL,
    max_connections=10,  # Limit max connections to Redis (adjust as needed)
    decode_responses=True
)

# ✅ Create Celery app
celery_app = Celery(
    "invoice_processor",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.email_scanning_tasks"]
)

# ✅ Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task configuration
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,

    # ✅ Lower concurrency to avoid too many open Redis connections
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", 2)),

    # Task routing
    task_routes={
        "tasks.email_scanning_tasks.*": {"queue": "email_scanning"},
    },
    task_default_queue="email_scanning",

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Beat schedule (for periodic tasks)
    beat_schedule={
        'cleanup-old-tasks': {
            'task': 'tasks.email_scanning_tasks.cleanup_old_tasks',
            'schedule': 3600.0,  # Run every hour
        },
    },
)

# Optional: Configure logging
celery_app.conf.update(
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

if __name__ == '__main__':
    celery_app.start()

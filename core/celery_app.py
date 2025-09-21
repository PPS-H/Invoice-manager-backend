"""
Celery configuration for background task processing with Redis error handling
"""
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, task_failure
from core.config import settings
import os
import redis
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://default:email@redis-17402.c84.us-east-1-2.ec2.redns.redis-cloud.com:17402/0"
)

def create_redis_pool():
    """Create Redis connection pool with error handling"""
    try:
        pool = redis.ConnectionPool.from_url(
            REDIS_URL,
            max_connections=3,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Test connection
        test_redis = redis.Redis(connection_pool=pool)
        test_redis.ping()
        logger.info("✅ Redis connection pool created and tested successfully")
        return pool
        
    except redis.ConnectionError as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.error(f"Redis URL: {REDIS_URL}")
        raise
    except redis.TimeoutError as e:
        logger.error(f"❌ Redis connection timeout: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected Redis error: {e}")
        raise

# Create connection pool
redis_pool = create_redis_pool()

# Create Celery app
try:
    celery_app = Celery(
        "invoice_processor",
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=["tasks.email_scanning_tasks"]
    )
    logger.info("✅ Celery app initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Celery app: {e}")
    raise

# Enhanced Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task configuration
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", 1)),

    # Broker connection settings
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_heartbeat=30,
    broker_pool_limit=1,
    
    # Task handling
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,

    # Task routing
    task_routes={
        "tasks.email_scanning_tasks.*": {"queue": "email_scanning"},
    },
    task_default_queue="email_scanning",

    # Result backend settings
    result_expires=3600,
    result_backend_transport_options={
        'retry_policy': {
            'timeout': 5.0
        }
    },

    # Beat schedule
    beat_schedule={
        'cleanup-old-tasks': {
            'task': 'tasks.email_scanning_tasks.cleanup_old_tasks',
            'schedule': 3600.0,
        },
    },
)

# Signal handlers for monitoring
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    logger.info("✅ Celery worker ready and connected to Redis")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    logger.info("🔄 Celery worker shutting down")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    if isinstance(exception, (redis.ConnectionError, redis.TimeoutError)):
        logger.error(f"❌ Task {task_id} failed due to Redis connection issue: {exception}")

# Configure Celery logging
celery_app.conf.update(
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

if __name__ == '__main__':
    celery_app.start()

from celery import Celery

# Initialize Celery with Redis backend
celery_app = Celery(
    'playmoretcg',
    broker='rediss://:AbWDAAIjcDFkZTYzZmU4NzZhNjg0YTNhYjkwMzk2NTNiNTQ5YjE1MHAxMA@adapting-panther-46467.upstash.io:6379',
    backend='rediss://:AbWDAAIjcDFkZTYzZmU4NzZhNjg0YTNhYjkwMzk2NTNiNTQ5YjE1MHAxMA@adapting-panther-46467.upstash.io:6379'
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    redis_backend_use_ssl={
        'ssl_cert_reqs': None
    }
)
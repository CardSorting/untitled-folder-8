from celery import Celery

import ssl

# Redis URL with SSL configuration
REDIS_URL = 'rediss://:AbWDAAIjcDFkZTYzZmU4NzZhNjg0YTNhYjkwMzk2NTNiNTQ5YjE1MHAxMA@adapting-panther-46467.upstash.io:6379'

# SSL Context configuration
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Initialize Celery with Redis backend
celery_app = Celery(
    'playmoretcg',
    broker=REDIS_URL,
    backend=REDIS_URL
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
        'ssl_cert_reqs': None,
        'ssl_ca_certs': None
    },
    broker_use_ssl={
        'ssl_cert_reqs': None,
        'ssl_ca_certs': None
    }
)
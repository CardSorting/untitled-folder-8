from celery import Celery
import ssl

# Redis URL with SSL configuration (for credits)
REDIS_URL = 'rediss://:AbWDAAIjcDFkZTYzZmU4NzZhNjg0YTNhYjkwMzk2NTNiNTQ5YjE1MHAxMA@adapting-panther-46467.upstash.io:6379?ssl_cert_reqs=CERT_NONE'

# LavinMQ URL (for card operations)
LAVINMQ_URL = 'amqps://wfnozibh:4T_jdMaK65ElpLne0WeKkrzWW0v3BARP@possum.lmq.cloudamqp.com/wfnozibh'

# Initialize Celery with LavinMQ broker and Redis backend
celery_app = Celery(
    'playmoretcg',
    broker=LAVINMQ_URL,
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
        'ssl_cert_reqs': ssl.CERT_NONE,
        'ssl_ca_certs': None
    },
    broker_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE,
        'ssl_ca_certs': None,
        'cert_reqs': ssl.CERT_NONE
    },
    task_routes={
        'tasks.create_card_task': {'queue': 'card_creation'},
        'tasks.process_pack_opening': {'queue': 'pack_opening'},
        'tasks.get_credit_balance': {'queue': 'credits'},
        'tasks.claim_daily_credits': {'queue': 'credits'}
    }
)
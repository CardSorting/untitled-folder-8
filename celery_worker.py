#!/usr/bin/env python
import ssl
from celery_config import celery_app
from tasks import (
    process_pack_opening,
    spend_credits,
    claim_daily_credits,
    get_credit_balance,
    create_card_task
)

if __name__ == '__main__':
    # Configure SSL context for LavinMQ
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    celery_app.conf.update(
        broker_use_ssl={
            'ssl_cert_reqs': ssl.CERT_NONE,
            'ssl_ca_certs': None,
            'cert_reqs': ssl.CERT_NONE
        }
    )
    
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '-Q', 'card_creation,pack_opening,credits'  # Specify queues to listen to
    ])
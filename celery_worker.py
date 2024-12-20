#!/usr/bin/env python
from celery_config import celery_app
from tasks import process_pack_opening, spend_credits, claim_daily_credits, get_credit_balance

if __name__ == '__main__':
    celery_app.worker_main(['worker', '--loglevel=info'])
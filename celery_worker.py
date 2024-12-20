#!/usr/bin/env python
from celery_config import celery_app
from tasks import process_pack_opening, spend_credits

if __name__ == '__main__':
    celery_app.worker_main(['worker', '--loglevel=info'])
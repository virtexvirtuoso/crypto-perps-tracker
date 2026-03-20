#!/bin/bash
cd /home/linuxuser/crypto-perps-tracker
export $(grep 'DISCORD.*WEBHOOK_URL' .env | xargs)
/home/linuxuser/crypto-perps-tracker/venv/bin/python3 scripts/log_historical_data.py >> logs/historical_logger.log 2>&1

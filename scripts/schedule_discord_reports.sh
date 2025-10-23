#!/bin/bash

# Discord Report Scheduler
# Run this script to send market reports to Discord on a schedule
# Configured interval: 12 hours (adjustable in config/config.yaml)

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Log file
LOG_FILE="data/discord_reports.log"

# Create data directory if it doesn't exist
mkdir -p data

# Function to send report with logging
send_report() {
    echo "===========================================================================" >> "$LOG_FILE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting Discord report generation" >> "$LOG_FILE"
    echo "===========================================================================" >> "$LOG_FILE"

    # Run the Discord report script
    python3 scripts/send_discord_report.py >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ✅ Report sent successfully" >> "$LOG_FILE"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ❌ Report failed to send" >> "$LOG_FILE"
    fi

    echo "" >> "$LOG_FILE"
}

# Send the report
send_report

# Exit with success
exit 0

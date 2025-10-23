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

# Function to send reports with logging
send_reports() {
    echo "===========================================================================" >> "$LOG_FILE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting Discord reports generation" >> "$LOG_FILE"
    echo "===========================================================================" >> "$LOG_FILE"

    # Run the Market Report
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Generating Market Report..." >> "$LOG_FILE"
    python3 scripts/send_discord_report.py >> "$LOG_FILE" 2>&1
    MARKET_STATUS=$?

    if [ $MARKET_STATUS -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ✅ Market Report sent successfully" >> "$LOG_FILE"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ❌ Market Report failed to send" >> "$LOG_FILE"
    fi

    echo "" >> "$LOG_FILE"

    # Run the Symbol Report
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Generating Symbol Report..." >> "$LOG_FILE"
    python3 scripts/generate_symbol_report.py >> "$LOG_FILE" 2>&1
    SYMBOL_STATUS=$?

    if [ $SYMBOL_STATUS -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ✅ Symbol Report sent successfully" >> "$LOG_FILE"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ❌ Symbol Report failed to send" >> "$LOG_FILE"
    fi

    echo "" >> "$LOG_FILE"

    # Return success only if both succeeded
    if [ $MARKET_STATUS -eq 0 ] && [ $SYMBOL_STATUS -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# Send both reports
send_reports

# Exit with success
exit 0

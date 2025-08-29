#!/bin/bash

# Master File Comparison Helper Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/compare_master_files.py"

case "$1" in
    "auto"|"latest")
        echo "Comparing latest two master files..."
        python3 "$PYTHON_SCRIPT" --auto
        ;;
    "yesterday")
        YESTERDAY=$(date -d "yesterday" +%Y%m%d)
        echo "Comparing today with $YESTERDAY..."
        python3 "$PYTHON_SCRIPT" --date $(date +%Y%m%d)
        ;;
    "date")
        if [ -z "$2" ]; then
            echo "Usage: $0 date YYYYMMDD"
            exit 1
        fi
        echo "Comparing $2 with previous day..."
        python3 "$PYTHON_SCRIPT" --date "$2"
        ;;
    *)
        echo "Usage: $0 {auto|latest|yesterday|date YYYYMMDD}"
        echo "  auto/latest  - Compare the two most recent master files"
        echo "  yesterday    - Compare today's file with yesterday's"
        echo "  date YYYYMMDD - Compare specified date with previous day"
        exit 1
        ;;
esac
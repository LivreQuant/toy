#!/bin/bash
"""
run_all_analysis.sh - Master execution script with data quality validation
"""

set -e  # Exit on any error

TODAY=$(date +%Y%m%d)
YESTERDAY=$(date -d "yesterday" +%Y%m%d)

echo "🔍 MASTER SYMBOLOGY ANALYSIS WITH DATA QUALITY VALIDATION"
echo "========================================================"
echo "Analysis Period: $YESTERDAY -> $TODAY"
echo "Started: $(date)"
echo ""

# Set directories - adjust paths as needed
DATA_DIR="../master_symbology/data"
CA_DIR="../corporate_actions/data"

echo "Step 1: Analyzing new symbols..."
python3 new_symbols_analyzer.py --yesterday $YESTERDAY --today $TODAY --data-dir "$DATA_DIR" --ca-dir "$CA_DIR"

echo ""
echo "Step 2: Analyzing disappeared symbols..."
python3 disappeared_symbols_analyzer.py --yesterday $YESTERDAY --today $TODAY --data-dir "$DATA_DIR" --ca-dir "$CA_DIR"

echo ""
echo "Step 3: Analyzing data changes in existing symbols..."
python3 data_changes_analyzer.py --yesterday $YESTERDAY --today $TODAY --data-dir "$DATA_DIR" --ca-dir "$CA_DIR"

echo ""
echo "Step 4: Generating comprehensive summary report..."
python3 generate_summary_report.py --date $TODAY --ca-dir "$CA_DIR"

echo ""
echo "✅ ANALYSIS COMPLETE!"
echo "📄 Check symbology_summary_${TODAY}.txt for comprehensive overview"
echo "📊 Individual CSV files contain detailed breakdowns"
echo ""
echo "Finished: $(date)"
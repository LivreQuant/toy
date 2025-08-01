#!/bin/bash

echo "========================================"
echo "DATABASE POPULATION SCRIPT"
echo "========================================"

# Get today's date in YYYY-MM-DD format
TODAY=$(date +%Y-%m-%d)
echo "Today's date: $TODAY"

# Find postgres pod
echo "Finding postgres pod..."
POSTGRES_POD=$(kubectl get pods -l app=postgres -o jsonpath="{.items[0].metadata.name}")

if [ -z "$POSTGRES_POD" ]; then
    echo "ERROR: No postgres pod found!"
    exit 1
fi

echo "Found postgres pod: $POSTGRES_POD"

# Clear existing data
echo ""
echo "Clearing existing data..."
kubectl exec -it $POSTGRES_POD -- psql -U opentp -d opentp -c \
"TRUNCATE TABLE exch_us_equity.return_data CASCADE;
 TRUNCATE TABLE exch_us_equity.trade_data CASCADE;
 TRUNCATE TABLE exch_us_equity.order_data CASCADE;
 TRUNCATE TABLE exch_us_equity.impact_data CASCADE;
 TRUNCATE TABLE exch_us_equity.portfolio_risk_data CASCADE;
 TRUNCATE TABLE exch_us_equity.cash_flow_data CASCADE;
 TRUNCATE TABLE exch_us_equity.account_data CASCADE;
 TRUNCATE TABLE exch_us_equity.portfolio_data CASCADE;
 TRUNCATE TABLE exch_us_equity.users CASCADE;
 TRUNCATE TABLE exch_us_equity.fx_data CASCADE;
 TRUNCATE TABLE exch_us_equity.equity_data CASCADE;
 TRUNCATE TABLE exch_us_equity.risk_factor_data CASCADE;
 TRUNCATE TABLE exch_us_equity.risk_symbol_data CASCADE;
 TRUNCATE TABLE exch_us_equity.universe_data CASCADE;
 TRUNCATE TABLE exch_us_equity.metadata CASCADE;"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to clear data!"
    exit 1
fi
echo "Data cleared successfully!"

# Update SQL files with today's date and copy to pod
echo ""
echo "Updating SQL files with today's date and copying to pod..."

# Update global_static_data.sql
sed "s/2024-01-09/$TODAY/g" global_static_data.sql > temp_global_static_data.sql
kubectl cp temp_global_static_data.sql $POSTGRES_POD:/tmp/global_static_data.sql

# Update user_sample_data.sql
sed "s/2024-01-09/$TODAY/g" user_sample_data.sql > temp_user_sample_data.sql
kubectl cp temp_user_sample_data.sql $POSTGRES_POD:/tmp/user_sample_data.sql

# Execute SQL files
echo ""
echo "Executing global static data..."
kubectl exec -it $POSTGRES_POD -- psql -U opentp -d opentp -f /tmp/global_static_data.sql

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to execute global static data!"
    rm -f temp_*.sql
    exit 1
fi

echo ""
echo "Executing user sample data..."
kubectl exec -it $POSTGRES_POD -- psql -U opentp -d opentp -f /tmp/user_sample_data.sql

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to execute user sample data!"
    rm -f temp_*.sql
    exit 1
fi

# Verify data
echo ""
echo "Verifying data..."
kubectl exec -it $POSTGRES_POD -- psql -U opentp -d opentp -c \
"SELECT 'metadata' as table_name, count(*) as records FROM exch_us_equity.metadata
 UNION ALL SELECT 'universe_data', count(*) FROM exch_us_equity.universe_data
 UNION ALL SELECT 'users', count(*) FROM exch_us_equity.users
 UNION ALL SELECT 'portfolio_data', count(*) FROM exch_us_equity.portfolio_data
 ORDER BY table_name;"

echo ""
echo "========================================"
echo "DATABASE POPULATION COMPLETED!"
echo "========================================"

# Clean up temp files
rm -f temp_*.sql
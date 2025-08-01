#!/bin/bash

echo "========================================"
echo "DATABASE POPULATION SCRIPT"
echo "========================================"

# Parse command line arguments
CREATE_USER=false
if [ "$1" = "--create-user" ]; then
    CREATE_USER=true
fi

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

# Create fake user if requested
if [ "$CREATE_USER" = true ]; then
    echo ""
    echo "Creating fake auth user..."
    
    # Create fake user SQL with proper UUID
    cat > temp_create_user.sql << 'EOF'
-- Create fake user in auth schema with proper UUID
INSERT INTO auth.users (
    user_id,
    username,
    email,
    password_hash,
    email_verified,
    is_active,
    user_role,
    created_at
) VALUES (
    '00000000-0000-0000-0000-000000000001'::UUID,
    'testuser',
    'test@example.com',
    '$2b$12$dummy.hash.for.testing.purposes.only',
    true,
    true,
    'user',
    CURRENT_TIMESTAMP
) ON CONFLICT (user_id) DO UPDATE SET
    username = EXCLUDED.username,
    email = EXCLUDED.email,
    is_active = EXCLUDED.is_active;

SELECT 'Fake user created/updated successfully!' as status;
EOF

    # Copy and execute user creation SQL
    kubectl cp temp_create_user.sql $POSTGRES_POD:/tmp/create_user.sql
    kubectl exec -it $POSTGRES_POD -- psql -U opentp -d opentp -f /tmp/create_user.sql
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create fake user!"
        rm -f temp_create_user.sql
        exit 1
    fi
    
    echo "Fake user created successfully!"
    rm -f temp_create_user.sql
    
    # If we're only creating user, exit here
    if [ $# -eq 1 ]; then
        echo "User creation completed. Run without --create-user to populate exchange data."
        exit 0
    fi
fi

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
"SELECT 'auth.users' as table_name, count(*) as records FROM auth.users
UNION ALL SELECT 'metadata', count(*) FROM exch_us_equity.metadata
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
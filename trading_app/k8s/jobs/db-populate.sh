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
-- Create fake user in auth schema with proper UUID (testuser: Test123!)
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
    '4f6694d10ede2bb286a0559638ac04a5d27e181aa3d83a17be4cb238a30c29d4',
    true,
    true,
    'user',
    CURRENT_TIMESTAMP
);


-- Create fund for the test user
INSERT INTO fund.funds (
    user_id,
    fund_id,
    active_at
) VALUES (
    '00000000-0000-0000-0000-000000000001'::UUID,
    '0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID,
    CURRENT_TIMESTAMP
);

-- Insert fund properties
INSERT INTO fund.fund_properties (fund_id, category, subcategory, value, active_at, expire_at) VALUES
('0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID, 'property', 'name', 'Test Fund', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID, 'property', 'legal_structure', 'Personal Account', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID, 'property', 'state_country', 'Newark, NJ', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID, 'property', 'year_established', '2025', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID, 'metadata', 'aum', 'Under $1M', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID, 'metadata', 'purpose', '["raise_capital", "track_record"]', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID, 'metadata', 'thesis', 'Test this thing out.', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00');

-- Create team member
INSERT INTO fund.team_members (
    team_member_id,
    fund_id,
    active_at,
    expire_at
) VALUES (
    '6e46e336-766c-4f05-a96b-21f9359dda61'::UUID,
    '0ae5453f-2d9e-4c6a-ade0-df9f66726ad1'::UUID,
    CURRENT_TIMESTAMP,
    '2999-01-01 00:00:00+00'
);

-- Insert team member properties
INSERT INTO fund.team_member_properties (member_id, category, subcategory, value, active_at, expire_at) VALUES
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'personal', 'order', '0', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'personal', 'firstName', 'Sergio', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'personal', 'lastName', 'Amaral', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'personal', 'birthDate', '1984-05-19', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'professional', 'role', 'Portfolio Manager', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'professional', 'yearsExperience', '2', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'professional', 'currentEmployment', 'Citadel Shit', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'professional', 'investmentExpertise', 'Quantitative', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'social', 'linkedin', 'https://google.com', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00'),
('6e46e336-766c-4f05-a96b-21f9359dda61'::UUID, 'education', 'education', 'MIT', CURRENT_TIMESTAMP, '2999-01-01 00:00:00+00');

SELECT 'Fake user and fund created/updated successfully!' as status;
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
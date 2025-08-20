#!/bin/bash
# Database population script with user data deletion option

echo "========================================"
echo "DATABASE POPULATION SCRIPT"
echo "========================================"

# Parse command line arguments
CREATE_USER=false
DELETE_USER_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --create-user)
            CREATE_USER=true
            shift
            ;;
        --delete-user-data)
            DELETE_USER_DATA=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--create-user] [--delete-user-data]"
            echo "  --create-user      Create fake user and fund data"
            echo "  --delete-user-data Delete specific user tables to test fund service creation"
            exit 1
            ;;
    esac
done

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

# Handle delete user data option
if [ "$DELETE_USER_DATA" = true ]; then
    echo ""
    echo "🗑️  DELETING SPECIFIC USER DATA..."
    echo "This will only delete:"
    echo "  - exch_us_equity.metadata (exchange metadata)"
    echo "  - exch_us_equity.users (exchange user data)"  
    echo "  - exch_us_equity.account_data (user account data)"
    echo ""
    
    read -p "Delete these 3 tables? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Operation cancelled."
        exit 0
    fi
    
    echo "Deleting specific user data..."
    
    kubectl exec -it $POSTGRES_POD -- psql -U opentp -d opentp -c \
    "DELETE FROM exch_us_equity.account_data;
     DELETE FROM exch_us_equity.users; 
     DELETE FROM exch_us_equity.metadata;
     
     SELECT 'Deleted specific user data successfully!' as status;
     
     SELECT 'Remaining records:' as info;
     SELECT 'metadata' as table_name, count(*) as records FROM exch_us_equity.metadata
     UNION ALL SELECT 'users', count(*) FROM exch_us_equity.users  
     UNION ALL SELECT 'account_data', count(*) FROM exch_us_equity.account_data;"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to delete user data!"
        exit 1
    fi
    
    echo "✅ Only the 3 specified tables cleared!"
    echo "Now you can test if fund service creates them properly."
    exit 0
fi

# Create fake user if requested
if [ "$CREATE_USER" = true ]; then
    echo ""
    echo "Creating fake auth user..."
    
    # Create fake user SQL with proper UUID
    cat > temp_create_user.sql << 'EOF'
-- Create/update user in auth schema (using your actual data)
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
    '16615527-c536-4018-8d79-fb22e51718a5'::UUID,
    'testuser',
    'sergio.daniel.marques.amaral@gmail.com',
    '4f6694d10ede2bb286a0559638ac04a5d27e181aa3d83a17be4cb238a30c29d4',
    true,
    true,
    'user',
    '2025-08-20 19:14:04.187409+00'::TIMESTAMP WITH TIME ZONE
) ON CONFLICT (user_id) DO UPDATE SET
    username = EXCLUDED.username,
    email = EXCLUDED.email,
    email_verified = EXCLUDED.email_verified,
    is_active = EXCLUDED.is_active;

-- Create fund for the test user (using your actual data)
INSERT INTO fund.funds (
    user_id,
    fund_id,
    active_at
) VALUES (
    '16615527-c536-4018-8d79-fb22e51718a5'::UUID,
    '7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID,
    '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE
) ON CONFLICT (fund_id) DO UPDATE SET
    active_at = EXCLUDED.active_at;

-- Insert fund properties (using your actual data)
INSERT INTO fund.fund_properties (fund_id, category, subcategory, value, active_at, expire_at) VALUES
('7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID, 'property', 'name', 'Sergio''s Fund', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID, 'property', 'legal_structure', 'Personal Account', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID, 'property', 'state_country', 'Newark, NJ', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID, 'property', 'year_established', '2025', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID, 'metadata', 'aum', 'Under $1M', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID, 'metadata', 'purpose', '["raise_capital"]', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID, 'metadata', 'thesis', 'This is dope.', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00')
ON CONFLICT (fund_id, category, subcategory) DO UPDATE SET
    value = EXCLUDED.value,
    active_at = EXCLUDED.active_at;

-- Create team member (using your actual data)
INSERT INTO fund.team_members (
    team_member_id,
    fund_id,
    active_at,
    expire_at
) VALUES (
    '69530c0c-0daa-477e-bec4-2bc711158c73'::UUID,
    '7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID,
    '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE,
    '2999-01-01 00:00:00+00'
) ON CONFLICT (team_member_id) DO UPDATE SET
    active_at = EXCLUDED.active_at;

-- Insert team member properties (using your actual data)
INSERT INTO fund.team_member_properties (member_id, category, subcategory, value, active_at, expire_at) VALUES
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'personal', 'order', '0', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'personal', 'firstName', 'Sergio', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'personal', 'lastName', 'Amaral', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'personal', 'birthDate', '1984-05-19', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'professional', 'role', 'PM', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'professional', 'yearsExperience', '1', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'professional', 'currentEmployment', 'Citadel Shit', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'professional', 'investmentExpertise', 'Quant', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'social', 'linkedin', 'https://google.com', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00'),
('69530c0c-0daa-477e-bec4-2bc711158c73'::UUID, 'education', 'education', 'MIT', '2025-08-20 19:15:42.345176+00'::TIMESTAMP WITH TIME ZONE, '2999-01-01 00:00:00+00')
ON CONFLICT (member_id, category, subcategory) DO UPDATE SET
    value = EXCLUDED.value,
    active_at = EXCLUDED.active_at;

-- Create crypto wallet (using your actual data)
INSERT INTO crypto.wallets (
    user_id,
    fund_id,
    address,
    mnemonic,
    mnemonic_salt,
    active_at,
    expire_at
) VALUES (
    '16615527-c536-4018-8d79-fb22e51718a5'::UUID,
    '7421c696-bd33-4367-944b-fd37fb6fc2fd'::UUID,
    'U34GNHVFKR2OE3GMLSD53MRJDK7MUNVTHIMRZXOFG6XAXULQ3J4HTJKMVA',
    'Z0FBQUFBQm9waDdmaDNNdm9BRGNoQ19Nb1M3UXVqLTVmZG1EM3ZqNVlKM2dRcXJseXNCd0htWDQ4ZDRZajFWeG9qcVVzTDAxZXFEdlh0QVprVnNjRC13d3gxaGtibmctN2dkaTNaYnNzY1Bxc1UxbnlXd1BhRmM3Nk1hbkk1T3U4WTVlWi1kbFlWMjdTWjl1NkN0TmxJblNJZHZQWTYtbjRFblQ5X2l4MmJOVkdRQV9vS3hpWWJhc0dwaUZKQzVCc1Jxdk53YkwydE10LW5UTjhPUlFYUkNpOHMyZDdmelZNYklZQUhWOFEzSnRobXFOTnVGaTM0QUQ4ZkhLT2RYZnhObEZnYXhSQkxRZzFRZlBhMVJhcjZvUVRaYjEzMGV0dE1UWXlRTG50SDV0ODQxUlJSMXJuYUk9',
    '480nQOX9r7EJourSu+EdUQ==',
    '2025-08-20 19:15:45.452+00'::TIMESTAMP WITH TIME ZONE,
    '2999-01-01 00:00:00+00'
) ON CONFLICT (user_id, fund_id) DO UPDATE SET
    address = EXCLUDED.address,
    active_at = EXCLUDED.active_at;

SELECT 'User, fund, team member, and crypto wallet created/updated successfully!' as status;

-- Show what was created
SELECT 'DATA SUMMARY:' as info;
SELECT 'auth.users' as table_name, count(*) as records FROM auth.users WHERE user_id = '16615527-c536-4018-8d79-fb22e51718a5'
UNION ALL SELECT 'fund.funds', count(*) FROM fund.funds WHERE fund_id = '7421c696-bd33-4367-944b-fd37fb6fc2fd'
UNION ALL SELECT 'fund.fund_properties', count(*) FROM fund.fund_properties WHERE fund_id = '7421c696-bd33-4367-944b-fd37fb6fc2fd'
UNION ALL SELECT 'fund.team_members', count(*) FROM fund.team_members WHERE team_member_id = '69530c0c-0daa-477e-bec4-2bc711158c73'
UNION ALL SELECT 'fund.team_member_properties', count(*) FROM fund.team_member_properties WHERE member_id = '69530c0c-0daa-477e-bec4-2bc711158c73'
UNION ALL SELECT 'crypto.wallets', count(*) FROM crypto.wallets WHERE user_id = '16615527-c536-4018-8d79-fb22e51718a5'
ORDER BY table_name;
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
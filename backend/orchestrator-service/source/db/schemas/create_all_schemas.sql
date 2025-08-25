-- db/schemas/create_all_schemas.sql
-- Master script to create all database schemas and tables

-- Create UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types
DO $$ 
BEGIN
    CREATE TYPE trade_side AS ENUM ('BUY', 'SELL');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ 
BEGIN
    CREATE TYPE settlement_status AS ENUM ('PENDING', 'MATCHED', 'SETTLED', 'FAILED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ 
BEGIN
    CREATE TYPE workflow_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Create all schemas
CREATE SCHEMA IF NOT EXISTS positions;
CREATE SCHEMA IF NOT EXISTS settlement;
CREATE SCHEMA IF NOT EXISTS pnl;
CREATE SCHEMA IF NOT EXISTS risk_model;
CREATE SCHEMA IF NOT EXISTS risk_metrics;
CREATE SCHEMA IF NOT EXISTS attribution;
CREATE SCHEMA IF NOT EXISTS reference_data;
CREATE SCHEMA IF NOT EXISTS universe;
CREATE SCHEMA IF NOT EXISTS corporate_actions;
CREATE SCHEMA IF NOT EXISTS reconciliation;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS archival;
CREATE SCHEMA IF NOT EXISTS workflows;
CREATE SCHEMA IF NOT EXISTS exch_us_equity;
CREATE SCHEMA IF NOT EXISTS system_config;

-- Load schema files in order
\echo 'Creating core schemas...'
\i db/schemas/core/positions.sql
\i db/schemas/core/trades.sql
\i db/schemas/core/pnl.sql
\i db/schemas/core/risk_model.sql

\echo 'Creating reference data schemas...'
\i db/schemas/reference/securities.sql
\i db/schemas/reference/exchanges.sql
\i db/schemas/reference/universe.sql
\i db/schemas/reference/corporate_actions.sql

\echo 'Creating operational schemas...'
\i db/schemas/operations/system.sql

\echo 'Creating reconciliation schemas...'
\i db/schemas/reconciliation/position_recon.sql
\i db/schemas/reconciliation/cash_recon.sql
\i db/schemas/reconciliation/breaks.sql

\echo 'Creating reporting schemas...'
\i db/schemas/reporting/reports.sql
\i db/schemas/reporting/archival.sql

\echo 'Creating risk schemas...'
\i db/schemas/risk/attribution.sql

\echo 'Creating views...'
\i db/schemas/views/portfolio_views.sql

\echo 'Creating indexes...'
\i db/schemas/create_indexes.sql

\echo 'Inserting reference data...'
\i db/schemas/insert_reference_data.sql

\echo 'Schema creation complete!'
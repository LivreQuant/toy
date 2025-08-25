-- db/schemas/create_all_schemas.sql
-- Master script to create all database schemas and tables
-- Run this to initialize a fresh database

-- Create all schemas first
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

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types
DO $$ 
BEGIN
    -- Trade side enum
    CREATE TYPE trade_side AS ENUM ('BUY', 'SELL');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ 
BEGIN
    -- Settlement status enum
    CREATE TYPE settlement_status AS ENUM ('PENDING', 'MATCHED', 'SETTLED', 'FAILED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ 
BEGIN
    -- Workflow status enum
    CREATE TYPE workflow_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Load all schema files in dependency order
\i db/schemas/core/positions.sql
\i db/schemas/core/trades.sql
\i db/schemas/core/pnl.sql
\i db/schemas/core/workflows.sql
\i db/schemas/risk/risk_model.sql
\i db/schemas/risk/risk_metrics.sql
\i db/schemas/risk/attribution.sql
\i db/schemas/reference/securities.sql
\i db/schemas/reference/exchanges.sql
\i db/schemas/reference/corporate_actions.sql
\i db/schemas/reference/universe.sql
\i db/schemas/reconciliation/position_recon.sql
\i db/schemas/reconciliation/cash_recon.sql
\i db/schemas/reconciliation/breaks.sql
\i db/schemas/reporting/reports.sql
\i db/schemas/reporting/archival.sql
\i db/schemas/operations/exchanges.sql
\i db/schemas/operations/system.sql
\i db/schemas/views/portfolio_views.sql
\i db/schemas/views/risk_views.sql
\i db/schemas/views/reporting_views.sql

-- Create indexes after all tables
\i db/schemas/create_indexes.sql

-- Insert reference data
\i db/schemas/insert_reference_data.sql

COMMIT;
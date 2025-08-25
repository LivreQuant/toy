-- db/schemas/__init__.sql
-- Schema initialization script with proper extension and type setup

-- Create UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom enums
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
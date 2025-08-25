-- db/schemas/reporting/archival.sql
-- Data archival and retention tables

CREATE TABLE IF NOT EXISTS archival.archive_catalog (
    archive_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    data_type VARCHAR(100) NOT NULL,
    archive_date DATE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    storage_tier VARCHAR(50) NOT NULL,
    compression_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    record_count INTEGER NOT NULL,
    checksum VARCHAR(128),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS archival.archive_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(50) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    target_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    records_archived INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS archival.retention_policies (
    policy_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    data_type VARCHAR(100) NOT NULL UNIQUE,
    retention_days INTEGER NOT NULL,
    storage_tier VARCHAR(50) NOT NULL,
    compression_type VARCHAR(50) NOT NULL,
    archival_frequency VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE archival.archive_catalog IS 'Catalog of all archived data';
COMMENT ON TABLE archival.archive_jobs IS 'Archival job execution tracking';
COMMENT ON TABLE archival.retention_policies IS 'Data retention and archival policies';
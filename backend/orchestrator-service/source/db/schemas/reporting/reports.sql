-- db/schemas/reporting/reports.sql
-- Reporting framework tables

CREATE TABLE IF NOT EXISTS reporting.report_catalog (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_name VARCHAR(200) NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    account_id VARCHAR(50),
    report_date DATE NOT NULL,
    file_path VARCHAR(500),
    file_size_bytes BIGINT,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Report schedules
CREATE TABLE IF NOT EXISTS reporting.report_schedules (
    schedule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_name VARCHAR(200) NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    schedule_frequency VARCHAR(50) NOT NULL,
    schedule_time TIME NOT NULL,
    recipients TEXT[],
    parameters JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Report templates
CREATE TABLE IF NOT EXISTS reporting.report_templates (
    template_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name VARCHAR(200) NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    template_content JSONB NOT NULL,
    template_version VARCHAR(20) DEFAULT '1.0',
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE reporting.report_catalog IS 'Catalog of all generated reports';
COMMENT ON TABLE reporting.report_schedules IS 'Automated report generation schedules';
COMMENT ON TABLE reporting.report_templates IS 'Report templates and layouts';
-- db/schemas/operations/system.sql
-- System configuration and operational data

CREATE TABLE IF NOT EXISTS system_config.configuration (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) NOT NULL DEFAULT 'STRING' CHECK (config_type IN ('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'JSON')),
    description TEXT,
    is_sensitive BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System audit log
CREATE TABLE IF NOT EXISTS system_config.audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(20) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    record_id VARCHAR(100),
    old_values JSONB,
    new_values JSONB,
    user_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflow tables
CREATE TABLE IF NOT EXISTS workflows.workflow_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_name VARCHAR(200) NOT NULL,
    workflow_type VARCHAR(100) NOT NULL,
    execution_date DATE NOT NULL,
    workflow_status workflow_status DEFAULT 'PENDING',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    execution_context JSONB,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS workflows.workflow_tasks (
    task_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_execution_id UUID REFERENCES workflows.workflow_executions(execution_id),
    task_name VARCHAR(200) NOT NULL,
    task_order INTEGER NOT NULL,
    task_status workflow_status DEFAULT 'PENDING',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    task_result JSONB,
    error_message TEXT
);

COMMENT ON TABLE system_config.configuration IS 'System configuration parameters';
COMMENT ON TABLE system_config.audit_log IS 'Audit trail for all database changes';
COMMENT ON TABLE workflows.workflow_executions IS 'Workflow execution tracking';
COMMENT ON TABLE workflows.workflow_tasks IS 'Individual workflow task tracking';
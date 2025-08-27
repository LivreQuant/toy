-- db/schemas/reconciliation/breaks.sql
-- Reconciliation breaks and exceptions

CREATE TABLE IF NOT EXISTS reconciliation.recon_breaks (
   break_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
   recon_date DATE NOT NULL,
   account_id VARCHAR(50) NOT NULL,
   symbol VARCHAR(20),
   break_type VARCHAR(50) NOT NULL,
   break_description TEXT NOT NULL,
   impact_amount DECIMAL(20,2),
   resolution_status VARCHAR(20) DEFAULT 'OPEN',
   assigned_to VARCHAR(100),
   resolution_notes TEXT,
   resolved_at TIMESTAMP WITH TIME ZONE,
   created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Break resolution workflow
CREATE TABLE IF NOT EXISTS reconciliation.break_resolutions (
   resolution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
   break_id UUID REFERENCES reconciliation.recon_breaks(break_id),
   resolution_type VARCHAR(50) NOT NULL,
   resolution_action TEXT NOT NULL,
   authorized_by VARCHAR(100) NOT NULL,
   resolution_date DATE NOT NULL,
   impact_on_pnl DECIMAL(20,2),
   created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE reconciliation.recon_breaks IS 'Reconciliation breaks requiring resolution';
COMMENT ON TABLE reconciliation.break_resolutions IS 'Actions taken to resolve reconciliation breaks';
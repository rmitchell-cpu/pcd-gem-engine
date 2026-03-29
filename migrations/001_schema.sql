-- ============================================================
-- PCD GEM Engine — Supabase Schema Migration 001
-- ============================================================
-- Run this once against the Supabase Postgres database.
-- Safe to re-run: uses IF NOT EXISTS / OR REPLACE throughout.
-- ============================================================

-- Drop the old empty table (user confirmed it's empty and disposable)
DROP TABLE IF EXISTS gp_pipeline CASCADE;


-- ============================================================
-- 1. gp_pipeline  (central GP record — one row per fund manager)
-- ============================================================
CREATE TABLE IF NOT EXISTS gp_pipeline (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    -- GP identity
    gp_name             text NOT NULL,
    contact_first_name  text,
    contact_last_name   text,
    contact_email       text,
    contact_phone       text,

    -- Account
    account_owner       text NOT NULL DEFAULT 'Randy Mitchell',
    start_date          date,

    -- Financials
    sub_price_usd       numeric,
    fund_ii_net_irr     numeric,
    payment_status      text NOT NULL DEFAULT 'Pending'
                        CHECK (payment_status IN ('Pending', 'Verified')),

    -- Travel
    travel_dates        jsonb DEFAULT '[]'::jsonb,
    -- Format: [{"city": "NYC", "start_date": "2026-04-10", "end_date": "2026-04-12"}, ...]

    -- GEM pipeline summary (denormalized for fast reads)
    gatekeeper_score    integer,
    gatekeeper_class    text,
    pipeline_state      text,
    latest_job_id       text,

    -- Storage
    deck_pdf_path       text
);

COMMENT ON TABLE gp_pipeline IS 'Central GP record — one row per fund manager. Source of truth for contact info, financials, travel, and latest pipeline state.';
COMMENT ON COLUMN gp_pipeline.travel_dates IS 'JSON array: [{"city":"NYC","start_date":"2026-04-10","end_date":"2026-04-12"}]';
COMMENT ON COLUMN gp_pipeline.payment_status IS 'Pending or Verified';


-- ============================================================
-- 2. gem_jobs  (one row per pipeline execution)
-- ============================================================
CREATE TABLE IF NOT EXISTS gem_jobs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          text UNIQUE NOT NULL,
    gp_id           uuid REFERENCES gp_pipeline(id) ON DELETE SET NULL,
    fund_name       text,
    deck_filename   text,
    deck_storage_path text,
    state           text NOT NULL DEFAULT 'uploaded',
    gatekeeper_score integer,
    gatekeeper_class text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gem_jobs_gp_id ON gem_jobs(gp_id);
CREATE INDEX IF NOT EXISTS idx_gem_jobs_state ON gem_jobs(state);
CREATE INDEX IF NOT EXISTS idx_gem_jobs_created ON gem_jobs(created_at DESC);

COMMENT ON TABLE gem_jobs IS 'One row per GEM pipeline execution. Links back to gp_pipeline via gp_id.';


-- ============================================================
-- 3. gem_artifacts  (one row per stage output per job)
-- ============================================================
CREATE TABLE IF NOT EXISTS gem_artifacts (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      text NOT NULL REFERENCES gem_jobs(job_id) ON DELETE CASCADE,
    stage_name  text NOT NULL,
    data        jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),

    UNIQUE(job_id, stage_name)
);

CREATE INDEX IF NOT EXISTS idx_gem_artifacts_job ON gem_artifacts(job_id);

COMMENT ON TABLE gem_artifacts IS 'Raw stage JSON outputs from the GEM pipeline. One row per stage per job.';


-- ============================================================
-- 4. gem_status_log  (append-only audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS gem_status_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          text NOT NULL REFERENCES gem_jobs(job_id) ON DELETE CASCADE,
    stage_name      text NOT NULL,
    from_state      text,
    to_state        text NOT NULL,
    result          text NOT NULL,
    notes           text,
    model_version   text,
    prompt_version  text,
    token_usage     jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gem_log_job ON gem_status_log(job_id);
CREATE INDEX IF NOT EXISTS idx_gem_log_created ON gem_status_log(created_at DESC);

COMMENT ON TABLE gem_status_log IS 'Append-only pipeline transition audit trail.';


-- ============================================================
-- 5. Auto-update timestamps
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_gp_pipeline_updated ON gp_pipeline;
CREATE TRIGGER trg_gp_pipeline_updated
    BEFORE UPDATE ON gp_pipeline
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_gem_jobs_updated ON gem_jobs;
CREATE TRIGGER trg_gem_jobs_updated
    BEFORE UPDATE ON gem_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ============================================================
-- 6. Row-Level Security
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE gp_pipeline ENABLE ROW LEVEL SECURITY;
ALTER TABLE gem_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE gem_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE gem_status_log ENABLE ROW LEVEL SECURITY;

-- Anon key: read-only access to all tables
CREATE POLICY "anon_read_gp_pipeline" ON gp_pipeline
    FOR SELECT USING (true);

CREATE POLICY "anon_read_gem_jobs" ON gem_jobs
    FOR SELECT USING (true);

CREATE POLICY "anon_read_gem_artifacts" ON gem_artifacts
    FOR SELECT USING (true);

CREATE POLICY "anon_read_gem_status_log" ON gem_status_log
    FOR SELECT USING (true);

-- Service role: full access (bypasses RLS by default, but explicit for clarity)
CREATE POLICY "service_all_gp_pipeline" ON gp_pipeline
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_all_gem_jobs" ON gem_jobs
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_all_gem_artifacts" ON gem_artifacts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_all_gem_status_log" ON gem_status_log
    FOR ALL USING (auth.role() = 'service_role');


-- ============================================================
-- 7. Ensure gp_decks storage bucket exists (idempotent)
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('gp_decks', 'gp_decks', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policy: anon can read, service_role can write
CREATE POLICY "public_read_gp_decks" ON storage.objects
    FOR SELECT USING (bucket_id = 'gp_decks');

CREATE POLICY "service_write_gp_decks" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'gp_decks' AND auth.role() = 'service_role');


-- ============================================================
-- Done
-- ============================================================

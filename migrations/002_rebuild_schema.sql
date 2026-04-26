-- Migration 002: Rebuild Concierge schema
-- Applied directly to Supabase project opqnmrjnnafswbkawdii on 25/04/2026
-- This file documents the change for repository history.
-- Replaces the gem_* table naming from 001_schema.sql with pipeline_* naming
-- and renames gatekeeper_* columns to prescreen_* on gp_pipeline.
-- ============================================================
-- Tables retired (already dropped from production):
--   gem_jobs, gem_artifacts, gem_status_log
-- ============================================================
-- Renamed columns on gp_pipeline:
--   gatekeeper_score → prescreen_score
--   gatekeeper_class → prescreen_class
-- Tier column added: gp_pipeline.tier
--   CHECK constraint: native | high_potential_aspiring | challenging
-- ============================================================
-- New pipeline tables (already created in production):
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id TEXT UNIQUE NOT NULL,
  gp_id UUID REFERENCES gp_pipeline(id) ON DELETE CASCADE,
  fund_name TEXT,
  deck_filename TEXT,
  deck_storage_path TEXT,
  state TEXT NOT NULL DEFAULT 'uploaded',
  prescreen_score INTEGER,
  prescreen_class TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  CONSTRAINT pipeline_jobs_prescreen_class_check
    CHECK (prescreen_class IS NULL OR prescreen_class IN
      ('native', 'high_potential_aspiring', 'challenging'))
);
CREATE TABLE IF NOT EXISTS pipeline_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id TEXT NOT NULL REFERENCES pipeline_jobs(job_id) ON DELETE CASCADE,
  stage_name TEXT NOT NULL,
  data JSONB NOT NULL,
  prompt_version TEXT,
  model_version TEXT,
  token_usage JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (job_id, stage_name)
);
CREATE TABLE IF NOT EXISTS pipeline_status_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id TEXT NOT NULL REFERENCES pipeline_jobs(job_id) ON DELETE CASCADE,
  stage_name TEXT NOT NULL,
  from_state TEXT,
  to_state TEXT NOT NULL,
  result TEXT,
  notes TEXT,
  model_version TEXT,
  prompt_version TEXT,
  token_usage JSONB,
  duration_ms INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Canonical stage_name values used in pipeline_artifacts:
--   prescreen
--   01_fund_extract
--   02_deck_analysis
--   03_angle_brief
--   04_preqin_taxonomy
--   05_deal_card
--   06_lp_emails
--   eval_voice
--   eval_cross_stage

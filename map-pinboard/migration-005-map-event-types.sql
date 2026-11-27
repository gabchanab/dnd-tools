-- ============================================================================
-- Migration 005 — a type for map events
--
-- Run ONCE in the Supabase SQL editor on a database set up before this change.
-- Fresh installs using the current schema.sql do NOT need this file.
--
-- Adds map_events.event_type (optional). The values are the same keys the
-- timeline page uses: cosmic, geological, settlement, origins, conflict,
-- societal. Nothing is dropped or rewritten. Safe to re-run.
-- ============================================================================

alter table public.map_events
  add column if not exists event_type text;

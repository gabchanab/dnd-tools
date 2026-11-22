-- ============================================================================
-- Migration 003 — "still exists" flag for the current-year view (Phase 3b)
--
-- Run ONCE in the Supabase SQL editor on a database set up before this change.
-- Fresh installs using the current schema.sql do NOT need this file.
--
-- Adds a single column. Nothing is dropped or rewritten, and every existing pin
-- gets the default (true = "still exists after its latest event"), so nothing
-- changes visually until you turn on the Year view on a map.
-- Safe to re-run.
-- ============================================================================

alter table public.map_pins
  add column if not exists still_exists boolean not null default true;

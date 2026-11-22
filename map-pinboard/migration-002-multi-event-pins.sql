-- ============================================================================
-- Migration 002 — let a pin link to MANY timeline events (was: one)
--
-- Run this ONCE in the Supabase SQL editor, in a database that was set up with
-- the original schema.sql (which had map_pins.timeline_event_id).
-- Fresh installs using the current schema.sql do NOT need this file.
--
-- What it does:
--   1. creates the map_pin_events join table (+ RLS policy)
--   2. copies every existing pin -> event link into it (nothing is lost)
--   3. leaves the old map_pins.timeline_event_id column in place and unused.
--      Dropping it is optional and is the last, commented-out step below.
--
-- Safe to re-run: every step is idempotent (the copy skips rows that exist).
-- The "drop policy if exists" line only removes a policy of this table's own
-- name so the script can be re-run; it can't touch any data.
-- ============================================================================

-- 1) join table ---------------------------------------------------------------
create table if not exists public.map_pin_events (
  pin_id     uuid not null references public.map_pins(id) on delete cascade,
  event_id   uuid not null references public.timeline_events(id) on delete cascade,
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (pin_id, event_id)
);

create index if not exists map_pin_events_event_idx on public.map_pin_events (event_id);

alter table public.map_pin_events enable row level security;

drop policy if exists "map_pin_events: owner all" on public.map_pin_events;
create policy "map_pin_events: owner all" on public.map_pin_events
  for all to authenticated
  using (user_id = auth.uid())
  with check (
    user_id = auth.uid()
    and exists (select 1 from public.map_pins p where p.id = pin_id and p.user_id = auth.uid())
  );

-- 2) copy existing single links across ---------------------------------------
insert into public.map_pin_events (pin_id, event_id, user_id)
select id, timeline_event_id, user_id
from public.map_pins
where timeline_event_id is not null
on conflict (pin_id, event_id) do nothing;

-- 3) check: both numbers should match -----------------------------------------
select
  (select count(*) from public.map_pins where timeline_event_id is not null) as old_links,
  (select count(*) from public.map_pin_events)                               as new_links;

-- 4) OPTIONAL, LATER — only after you've confirmed everything works on the live
--    site. This permanently removes the old single-event column. Leave it
--    commented out until then (the app no longer reads or writes it).
--
-- alter table public.map_pins drop column timeline_event_id;

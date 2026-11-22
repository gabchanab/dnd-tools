-- ============================================================================
-- Migration 004 — pin start/end years + per-map events (Year view redesign)
--
-- Run ONCE in the Supabase SQL editor on a database set up before this change.
-- Fresh installs using the current schema.sql do NOT need this file.
--
-- What it adds (nothing is dropped or rewritten):
--   1. map_pins.start_year / end_year  — when the place/thing existed (absolute
--      years). NULL start = "always existed", NULL end = "still exists today".
--   2. map_events                      — things that happen in the world, shown in
--      the key on the map. Each has a start and end year and can optionally point
--      at a timeline event.
--   3. map_event_pins                  — which pins belong to which map event.
--
-- The old map_pins.still_exists column (migration 003) is no longer used by the
-- page. It is harmless; drop it whenever you like with:
--   alter table public.map_pins drop column still_exists;
-- Safe to re-run.
-- ============================================================================

-- ── 1. pin existence range ──────────────────────────────────────────────────
alter table public.map_pins
  add column if not exists start_year integer,
  add column if not exists end_year   integer;

alter table public.map_pins drop constraint if exists map_pins_year_order;
alter table public.map_pins
  add constraint map_pins_year_order
  check (start_year is null or end_year is null or end_year >= start_year);

-- ── 2. map_events ───────────────────────────────────────────────────────────
create table if not exists public.map_events (
  id          uuid primary key default gen_random_uuid(),
  map_id      uuid not null references public.maps(id) on delete cascade,
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,

  title       text not null,
  description text,

  -- Absolute years, same scale as timeline_events.year. A one-year event has
  -- end_year = start_year.
  start_year  integer not null,
  end_year    integer not null,
  check (end_year >= start_year),

  -- Optional reference to a timeline event (just a link; dates are stored here).
  timeline_event_id uuid references public.timeline_events(id) on delete set null,

  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists map_events_map_idx on public.map_events (map_id);

drop trigger if exists map_events_set_updated_at on public.map_events;
create trigger map_events_set_updated_at before update on public.map_events
  for each row execute function public.set_updated_at();

-- ── 3. map_event_pins (many-to-many) ────────────────────────────────────────
create table if not exists public.map_event_pins (
  event_id   uuid not null references public.map_events(id) on delete cascade,
  pin_id     uuid not null references public.map_pins(id)   on delete cascade,
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (event_id, pin_id)
);

create index if not exists map_event_pins_pin_idx on public.map_event_pins (pin_id);

-- ── Row-level security: owner only ──────────────────────────────────────────
alter table public.map_events     enable row level security;
alter table public.map_event_pins enable row level security;

drop policy if exists "map_events: owner all" on public.map_events;
create policy "map_events: owner all" on public.map_events
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- A link row must belong to you AND join one of your own events to one of your own pins.
drop policy if exists "map_event_pins: owner all" on public.map_event_pins;
create policy "map_event_pins: owner all" on public.map_event_pins
  for all to authenticated
  using (user_id = auth.uid())
  with check (
    user_id = auth.uid()
    and exists (select 1 from public.map_events e where e.id = event_id and e.user_id = auth.uid())
    and exists (select 1 from public.map_pins   p where p.id = pin_id   and p.user_id = auth.uid())
  );

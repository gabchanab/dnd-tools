-- ============================================================================
-- Map Pinboard — Supabase schema (first sketch)
-- Run in the Supabase SQL editor. Safe to re-run top to bottom on a fresh DB.
--
-- ASSUMPTION TO VERIFY: timeline_events.id is a uuid. If it is bigint/int,
-- change `timeline_event_id uuid` below to match before running.
-- ============================================================================

-- ── maps ────────────────────────────────────────────────────────────────────
create table if not exists public.maps (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,

  name          text not null,
  description   text,

  -- Images live in Storage; we store only the paths (bucket: "maps").
  -- image_path      = the plain map (required, the base layer)
  -- grid_image_path = the same map with the hex grid baked in (optional overlay,
  --                   must be pixel-aligned/same size as the base image)
  image_path        text not null,
  grid_image_path   text,
  image_width       integer not null,   -- natural pixel size of the base image
  image_height      integer not null,   -- (Leaflet needs this to build its bounds)

  -- Hex grid calibration (used for measuring; the grid *look* comes from
  -- grid_image_path). All pixel values are in base-image pixels.
  grid_enabled      boolean not null default false,
  grid_orientation  text    check (grid_orientation in ('pointy', 'flat')),
  grid_hex_size_px  numeric check (grid_hex_size_px > 0),  -- centre-to-corner
  grid_origin_x_px  numeric,                               -- centre of a known hex
  grid_origin_y_px  numeric,
  distance_per_hex  numeric check (distance_per_hex > 0),  -- e.g. 6 (miles)
  distance_unit     text not null default 'miles',

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists maps_user_idx on public.maps (user_id);

-- ── map_pins ────────────────────────────────────────────────────────────────
create table if not exists public.map_pins (
  id            uuid primary key default gen_random_uuid(),
  map_id        uuid not null references public.maps(id) on delete cascade,
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,

  -- Position as a FRACTION of the image (0..1), origin top-left.
  -- Resolution-independent: survives re-uploading a higher-res version.
  x             double precision not null check (x between 0 and 1),
  y             double precision not null check (y between 0 and 1),

  title         text not null,
  pin_type      text not null default 'landmark'
                check (pin_type in ('city','town','village','dungeon','landmark','ruin','region','port','other')),
  description   text,

  -- Optional link: opens a nested map. (Timeline events are many-to-many and live
  -- in map_pin_events below, so one pin can carry several events over the years.)
  child_map_id      uuid references public.maps(id) on delete set null,

  -- "Current year" view: a pin's active range runs from its earliest to its latest
  -- linked timeline event. If still_exists is true (the default) it stays active
  -- after the latest event (a city); if false it ends there (a one-off battle).
  -- Pins with no linked events are timeless.
  still_exists      boolean not null default true,

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists map_pins_map_idx   on public.map_pins (map_id);
create index if not exists map_pins_child_idx on public.map_pins (child_map_id);

-- ── map_pin_events: which timeline events happened at which pin (many-to-many) ──
create table if not exists public.map_pin_events (
  pin_id     uuid not null references public.map_pins(id) on delete cascade,
  event_id   uuid not null references public.timeline_events(id) on delete cascade,
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (pin_id, event_id)
);

create index if not exists map_pin_events_event_idx on public.map_pin_events (event_id);

-- ── updated_at trigger ──────────────────────────────────────────────────────
create or replace function public.set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists maps_set_updated_at on public.maps;
create trigger maps_set_updated_at before update on public.maps
  for each row execute function public.set_updated_at();

drop trigger if exists map_pins_set_updated_at on public.map_pins;
create trigger map_pins_set_updated_at before update on public.map_pins
  for each row execute function public.set_updated_at();

-- ── Row-level security: owner only ──────────────────────────────────────────
alter table public.maps           enable row level security;
alter table public.map_pins       enable row level security;
alter table public.map_pin_events enable row level security;

drop policy if exists "maps: owner all" on public.maps;
create policy "maps: owner all" on public.maps
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

drop policy if exists "map_pins: owner all" on public.map_pins;
create policy "map_pins: owner all" on public.map_pins
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- A link row must belong to you AND point at one of your own pins.
drop policy if exists "map_pin_events: owner all" on public.map_pin_events;
create policy "map_pin_events: owner all" on public.map_pin_events
  for all to authenticated
  using (user_id = auth.uid())
  with check (
    user_id = auth.uid()
    and exists (select 1 from public.map_pins p where p.id = pin_id and p.user_id = auth.uid())
  );

-- ── Storage: private "maps" bucket ──────────────────────────────────────────
-- Object path convention:  <user_id>/<map_id>/base.<ext>
--                          <user_id>/<map_id>/grid.<ext>
-- The first folder is the owner's user id, which the policies below check.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('maps', 'maps', false, 26214400,  -- 25 MB
        array['image/png', 'image/jpeg', 'image/webp'])
on conflict (id) do nothing;

drop policy if exists "maps bucket: owner read"   on storage.objects;
drop policy if exists "maps bucket: owner insert" on storage.objects;
drop policy if exists "maps bucket: owner update" on storage.objects;
drop policy if exists "maps bucket: owner delete" on storage.objects;

create policy "maps bucket: owner read" on storage.objects
  for select to authenticated
  using (bucket_id = 'maps' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "maps bucket: owner insert" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'maps' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "maps bucket: owner update" on storage.objects
  for update to authenticated
  using (bucket_id = 'maps' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "maps bucket: owner delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'maps' and (storage.foldername(name))[1] = auth.uid()::text);

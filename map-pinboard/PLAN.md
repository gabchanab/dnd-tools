# Map Pinboard — Plan

A world-map reference tool for the D&D Tools hub. Upload a map image, drop
labelled pins, link pins to timeline events, nest maps (continent → city), and
(later) overlay a hex grid with a real distance-measuring tool.

**Not a VTT.** No tokens, combat, fog or real-time sync. It's a browsable
reference map.

## Decisions (from the brainstorm)

| Question | Decision |
|---|---|
| Sharing | Owner-only for now (RLS on `user_id`). Revisit for player share links later. |
| Map structure | Several maps, with nesting: a pin can open a child map. |
| Pin links | Timeline events — **many per pin** (one place, many things over the years) via the `map_pin_events` join table. |
| Hex grid | Yes, later. Gridded reference image is pixel-aligned with the plain one. |
| Grid features | Visual overlay **and** a real distance tool (miles per hex). |
| Rendering | Leaflet.js with `L.CRS.Simple` (image map mode), loaded from CDN. |

## Stack / conventions

Same as the rest of the hub: single-file `map-pinboard/index.html`, vanilla JS,
`js/auth.js` + `js/supabase-client.js` copied like the other tool folders,
styling from `character builder/static/css/sheet.css`. New: Leaflet (CDN) and
Supabase **Storage** (first use).

## Data model

See [`schema.sql`](schema.sql) for the full, runnable version.

- **`maps`** — name, `image_path`, optional `grid_image_path`, natural
  `image_width`/`image_height`, and grid calibration columns (`grid_orientation`,
  `grid_hex_size_px`, `grid_origin_x_px/y_px`, `distance_per_hex`,
  `distance_unit`).
- **`map_pins`** — `map_id`, `x`/`y`, `title`, `pin_type`, `description`,
  `child_map_id`.
- **`map_pin_events`** — join table `(pin_id, event_id)` (primary key on the
  pair, both cascade-delete) linking a pin to any number of timeline events.
  Existing databases get it from
  [`migration-002-multi-event-pins.sql`](migration-002-multi-event-pins.sql),
  which also copies over the old single `map_pins.timeline_event_id` links.
- **Storage bucket `maps`** (private). Paths: `<user_id>/<map_id>/base.<ext>`
  and `<user_id>/<map_id>/grid.<ext>`. Policies check that the first folder
  equals `auth.uid()`.

### Key design choices

1. **Pin position is a fraction (0–1) of the image**, not pixels. Swapping in a
   higher-res image later doesn't move any pin.
2. **Image dimensions are stored on the map.** Leaflet needs them to build
   bounds without loading the image first.
3. **Private bucket + signed URLs.** The page calls
   `supabase.storage.from('maps').createSignedUrl(path, 3600)` and hands that
   URL to Leaflet.
4. **Grid "look" and grid "maths" are separate.** The look is the gridded
   image (exact match to your reference, zero drawing code). The maths
   (distance) uses the calibration columns. Both can coexist.
5. **Nesting:** the parent link lives on the pin (`child_map_id`), so a map can
   be reached from a pin without needing a parent column on `maps`.

## Leaflet mapping

```js
const map = L.map('map', { crs: L.CRS.Simple, minZoom: -3, maxZoom: 2, zoomSnap: 0.25 });
const bounds = [[0, 0], [H, W]];            // [lat, lng] = [y, x], y grows upward
L.imageOverlay(baseUrl, bounds).addTo(map);
if (gridUrl) gridLayer = L.imageOverlay(gridUrl, bounds); // toggle with addTo/remove
map.fitBounds(bounds);

// DB fraction (x, y from top-left)  →  Leaflet latlng
const toLatLng = p => [(1 - p.y) * H, p.x * W];
// Leaflet click latlng              →  DB fraction
const toFrac   = ll => ({ x: ll.lng / W, y: 1 - ll.lat / H });
```

Pins are `L.marker` with `L.divIcon` (icon per `pin_type`), `draggable: true`
for repositioning (save on `dragend`). Leaflet keeps markers a constant screen
size on zoom, so no counter-scaling code is needed.

## Hex grid layer (phase 3)

- **Look:** a toggle button adds/removes the gridded `imageOverlay`. Because the
  two images are the same size, it lines up exactly.
- **Calibration (one-time per map):** the user picks orientation (pointy/flat),
  clicks the centres of two adjacent hexes (gives size and rotation-free
  origin), and enters "1 hex = N miles". Saved to the `grid_*` columns.
- **Measure tool:** click point A, click point B. Convert each pixel position to
  hex cube coordinates, then `distance = max(|dq|, |dr|, |ds|)` hexes, times
  `distance_per_hex`. Show a line plus a "4 hexes ≈ 24 miles" label.
- **Optional:** highlight the hex under the cursor (draw one hexagon polygon
  from the calibration maths) to confirm calibration is correct.

## Pin years & "current year" view (Phase 3b, TODO)

Goal: pins can say *when* they existed; the map has a "current year" control
that fades pins that did not exist (or had not happened) in the selected year.

**Decisions (from the brainstorm):**

| Question | Decision |
|---|---|
| Year model | Optional **From year** and **To year**. Blank To = ongoing (a city that still stands). A one-off event sets both to the same year. No years at all = timeless, always shown normally. |
| Linking to a timeline event | Originally: linking auto-fills the pin's year from the event. **Needs revisiting now that a pin can have many events** — see open points. |
| Entering years | Same as the timeline: pick an **Age**, then a year relative to it (e.g. "120 PAA"). From and To may be in different Ages. |
| Default state | Control is **off**: all pins show normally until an Age + year is chosen. A "Show all" button switches it off again. |

**Data:** add two nullable columns to `map_pins`, stored as **absolute** years,
the same convention `timeline_events.year` already uses:

```sql
alter table public.map_pins
  add column if not exists year_start integer,
  add column if not exists year_end   integer,
  add constraint map_pins_year_order check (year_end is null or year_start is null or year_end >= year_start);
```

The Age is *derived* from the absolute year (the Age whose `start_year`..
`end_year` range contains it; `end_year` null = ongoing), so nothing about Ages
is duplicated onto the pin. Display uses the Age abbreviation the same way
`formatEventYear` does on the timeline page.

**Pin form:** "When" section with From (Age select + year-in-Age input) and To
(same, plus an "Ongoing" option). Shows the computed absolute year as a hint,
like the timeline form does.

**Map control:** a bar above the map: Age select (names and periods read from
`timeline_ages`) + year-in-Age input + "Show all". On change, for each pin:

- active in selected year (`year_start` null or ≤ Y, and `year_end` null or ≥ Y) → normal
- otherwise → faded (~25–30% opacity, still slightly visible), still clickable
- the side panel marks faded pins ("not yet founded" / "ended in 340 PAA")

**Open points to settle when building:**

- **How linked events interact with the pin's years.** A pin can now have
  several events (e.g. a city: founded 120, sacked 840, rebuilt 900), so "auto-fill
  the year from the event" is ambiguous. Options: (a) the pin's From/To stay
  hand-entered and independent; (b) the pin's *active range* is derived from its
  events (earliest → latest, or ongoing); (c) the map's current-year view also
  highlights which of the pin's events had happened by the selected year, e.g.
  "2 of 3 events so far". Pick one before building 3b.
- whether faded pins should also be dimmed in the side-panel list;
- what to do when the selected year is outside every Age (probably fall back to
  an absolute-year input).

## Phases

1. **Foundation** — run `schema.sql`; confirm `timeline_events.id` type; create
   `map-pinboard/` with the shared js files; add the hub card to `index.html`.
2. **MVP** — maps list, upload (base image + read dimensions), Leaflet view,
   add / edit / drag / delete pins, pin type icons, side panel with description.
3. **Links** — ✅ done (events many-to-many per pin). Timeline event picker on pins (grouped by Age); "📍"
   chips on timeline event cards that open the map focused on the pin
   (`#map=<id>&pin=<id>`); "View on timeline" back-link (`#event=<id>`); nested
   maps via a pin's "Opens map" (↳ badge on the pin, breadcrumbs back up).
3b. **Pin years & "current year" view** — see the section below. Needs the
   timeline's Ages, so do it alongside or just after Phase 3.
4. **Hex grid** — optional gridded image upload, overlay toggle, calibration
   flow, measure tool.
5. **Later ideas** — pin type filters, routes/paths with travel time, secret
   pins + player share link (`is_public` / `is_secret`), more link types
   (NPCs, factions), image tiling if maps get very large.

## Open items / risks

- Confirm `timeline_events.id` type before running the schema.
- Large images (>25 MB or >8k px) will be slow in the browser; the bucket caps
  uploads at 25 MB. Tiling is the later fix if needed.
- Signed URLs expire (1 h in the sketch); refresh on load, not stored.
- Deleting a map should also delete its Storage objects (the DB cascade does
  not touch Storage) — handle in the delete function.

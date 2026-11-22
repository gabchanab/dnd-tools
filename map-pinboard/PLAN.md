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
- **`map_events`** / **`map_event_pins`** — per-map events with start/end years
  and their many-to-many links to pins (see the Year view section).
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

## Pin dates, map events & "Year view" (Phase 3b, ✅ done — redesigned)

Locations/items on the map and things that *happen* in the world are different
things, so they are modelled separately. The first version derived a pin's
lifetime from its timeline events, which blurred the two.

- **Pins** are places/things. Each has its own optional **start year** and **end
  year** (`map_pins.start_year/end_year`, absolute). Blank start = always
  existed; blank end = still exists today. Outside the range the pin fades in
  the Year view. Linking a pin to timeline events stays as a plain reference.
- **Map events** (`map_events`, per map) are things that happen: a title,
  description, **start and end year** (blank end = single year) and an optional
  link to a timeline event (just a reference; picking one fills an empty title
  and start year). They live in an **Events key**, a bubble in the top-right
  corner of the map, listed oldest first.
- **Pin ↔ event links** (`map_event_pins`, many-to-many) can be edited from the
  pin form or the event form.

**Decisions:**

| Question | Decision |
|---|---|
| Where events live | Per map (new `map_events` table), optional timeline link. |
| Entering years | Age + year within the Age (or an absolute year); stored as absolute years. |
| Old event-derived range / "Still exists" | Replaced by the pin's own start/end. `still_exists` is no longer used. |
| Clicking an event in the key | Shows its pins, fades the rest. Independent of the Year view (the event selection wins while it is active). Click again or Esc to clear. |
| Default state | Year view **off**: every pin and event normal. |

**Behaviour:**

- With a year selected, a pin is `before` if Y < start, `after` if Y > end, else
  active; pins with neither date are "undated" and always shown. Faded pins are
  ~28% opacity (65% when selected), still clickable.
- Key rows: bold with a gold edge when the selected year is inside the event's
  range, dimmed when outside, all normal when the Year view is off. Each row
  shows its range and pin count; the header collapses the list and has a **+**.
- Pin panel shows "Exists: …" and its state in the selected year, plus the map
  events it belongs to (click one to highlight it). Event panel shows its
  range, state, linked pins (click to focus) and timeline reference.
- The selected year carries over when you open a nested map; it resets on reload.

**Data:** [`migration-004-pin-dates-and-map-events.sql`](migration-004-pin-dates-and-map-events.sql)
(also folded into `schema.sql`). It does not copy any old derived ranges across,
so existing pins start undated.

**Not built (ideas):** a slider to scrub the year; remembering the year across
reloads or putting it in the URL; map events shared across maps; showing events
on the timeline page.

## Phases

1. **Foundation** — run `schema.sql`; confirm `timeline_events.id` type; create
   `map-pinboard/` with the shared js files; add the hub card to `index.html`.
2. **MVP** — maps list, upload (base image + read dimensions), Leaflet view,
   add / edit / drag / delete pins, pin type icons, side panel with description.
3. **Links** — ✅ done (events many-to-many per pin). Timeline event picker on pins (grouped by Age); "📍"
   chips on timeline event cards that open the map focused on the pin
   (`#map=<id>&pin=<id>`); "View on timeline" back-link (`#event=<id>`); nested
   maps via a pin's "Opens map" (↳ badge on the pin, breadcrumbs back up).
3b. **Pin dates, map events & Year view** — ✅ done, see the section above.
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

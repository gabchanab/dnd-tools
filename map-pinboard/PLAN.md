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
| Pin links (v1) | Timeline events only (`timeline_event_id`). |
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
  `timeline_event_id`, `child_map_id`.
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

## Phases

1. **Foundation** — run `schema.sql`; confirm `timeline_events.id` type; create
   `map-pinboard/` with the shared js files; add the hub card to `index.html`.
2. **MVP** — maps list, upload (base image + read dimensions), Leaflet view,
   add / edit / drag / delete pins, pin type icons, side panel with description.
3. **Links** — timeline event picker on pins; "📍 Show on map" button on the
   timeline page that opens the map centred on the pin; nested maps (pin →
   child map, breadcrumb back to parent).
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

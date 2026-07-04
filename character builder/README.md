# D&D 2024 Character Builder

A Flask web app for building and managing D&D 2024 characters. Pulls live data from the [Open5e v2 API](https://api.open5e.com/v2), generates interactive character sheets, and supports homebrew content via local JSON files.

---

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

---

## How it works

### Flow
1. **`/`** — Character Vault landing page. Shows saved characters and a "New Character" card.
2. **`/build`** — Multi-step character creation wizard. Fetches class, species, background, and spell data from Open5e client-side, then submits everything to Flask.
3. **`/sheet`** — Interactive character sheet rendered from the submitted data. Supports dice rolling, spell accordions, HP tracking, death saves, spell slot toggles, and more.
4. **`/load/<filename>`** — Loads a saved character JSON from `my_characters/` and redirects to the sheet.

### Saving characters
Click **Save JSON** in the sheet footer. The file is written to `my_characters/<CharacterName>.json` and appears on the vault page next time you visit `/`.

---

## Project structure

```
character builder/
│
├── app.py                      # Flask server — all routes, API calls, character context builder
├── character_model.py          # Data structures and helpers for character fields
├── requirements.txt            # Python dependencies (flask, requests, matplotlib, …)
├── README.md                   # This file
│
├── templates/                  # Jinja2 HTML templates (filled with data by Flask)
│   ├── index.html              # Vault landing page — lists saved characters
│   ├── builder.html            # Multi-step character creation wizard
│   └── sheet.html              # Interactive character sheet
│
├── static/
│   ├── css/sheet.css           # Base styles: layout, panels, colours, fonts
│   └── js/                     # (Reserved for standalone JS files)
│
├── sigil_creator/              # Polar-plot sigil generator module
│   ├── __init__.py             # Makes the folder a Python package
│   └── alphabet_coordinates.py # Maps letters → polar coords, draws sigil PNGs via matplotlib
│
├── homebrew/                   # Your custom content — edit these JSON files to add options
│   ├── subclasses.json         # Custom subclasses
│   ├── backgrounds.json        # Custom backgrounds
│   ├── species.json            # Custom species
│   └── feats.json              # Custom feats / origin feats
│
├── my_characters/              # Saved character sheets (written by the Save JSON button)
│   └── <CharacterName>.json
│
└── dnd_spellbook/              # Standalone legacy spellbook app (not connected to main app)
    ├── app.py
    └── templates/index.html
```

---

## Homebrew content

Add custom options by editing the JSON files in `homebrew/`. Each file is fetched by the builder at `/api/homebrew` and merged with the official Open5e data.

**`subclasses.json`** — array of subclass objects:
```json
[
  {
    "name": "School of Shadows",
    "class": "wizard",
    "_hbData": {
      "features": {
        "3": [{ "name": "Shadow Step", "description": "You can teleport…" }],
        "7": [{ "name": "Umbral Form", "description": "As a bonus action…" }]
      }
    }
  }
]
```

**`backgrounds.json`**, **`species.json`**, **`feats.json`** — follow the same pattern as Open5e objects. See the existing files for examples.

---

## API endpoints

| Route | Method | Description |
|---|---|---|
| `/` | GET | Vault landing page |
| `/build` | GET | Character builder wizard |
| `/sheet` | GET | Rendered character sheet |
| `/load/<filename>` | GET | Load a saved character and redirect to sheet |
| `/api/build` | POST | Receives builder JSON, builds character context |
| `/api/character` | GET | Returns current character as raw JSON |
| `/api/character/save` | POST | Saves character to `my_characters/` |
| `/api/spells/search` | GET | Proxies Open5e spell search |
| `/api/spells/<index>` | GET | Proxies single spell detail |
| `/api/sigil` | GET | Generates a sigil PNG for a spell name + school |
| `/api/open5e/<path>` | GET | General Open5e proxy |
| `/api/homebrew` | GET | Returns merged homebrew content |

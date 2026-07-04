"""
D&D Character Sheet — Flask App
  GET  /              → character builder wizard
  GET  /sheet         → parchment character sheet
  GET  /api/homebrew  → serves your homebrew/ JSON files to the builder
  POST /api/build     → receives builder JSON (with pre-fetched API data), builds sheet
"""

from flask import Flask, render_template, request, jsonify, session, send_file, redirect, url_for
import json, os, re, io, threading, requests as http

# Set non-interactive backend BEFORE any matplotlib.pyplot import
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as _plt

import sys
sys.path.insert(0, os.path.dirname(__file__))
from sigil_creator.alphabet_coordinates import plot_word_with_connection as _plot_word_with_connection

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Server-side character store — avoids cookie size limits
import uuid
_CHARACTER_STORE: dict = {}

# ---------------------------------------------------------------------------
# Homebrew API  —  reads your homebrew/ folder and returns it as JSON
# ---------------------------------------------------------------------------

HOMEBREW_DIR  = os.path.join(os.path.dirname(__file__), "homebrew")
OPEN5E_BASE   = "https://api.open5e.com/v2"
_PROXY_CACHE  = {}   # url+params → (response_bytes, status_code); cleared on restart

# ---------------------------------------------------------------------------
# Sigil generator
# ---------------------------------------------------------------------------

# School overlay patterns (mirrors alphabet_coordinates.py __main__ block)
_SPELL_SCHOOLS_SIGIL = {
    'ABJURATION':    [(1.0, 0.0, 0.0, 0.5), ['KAF','straight'], ['CAH','straight'], ['TUVW','arc']],
    'CONJURATION':   [(0.0, 1.0, 1.0, 0.5), ['MQNROSPM','straight']],
    'DIVINATION':    [(0.5, 0.5, 0.5, 0.5), ['AEI','straight'], ['KCG','straight']],
    'ENCHANTMENT':   [(0.5, 0.0, 0.5, 0.5), ['AGI','arc'], ['TUVW','arc'], ['XYZ','arc'],
                                        ['CXE','straight'], ['KXI','straight'], ['PXQ','straight']],
    'EVOCATION':     [(1.0, 0.5, 0.0, 0.5), ['AEI','straight'], ['TIE','straight'],
                                        ['UJL','straight'], ['WDB','straight']],
    'ILLUSION':      [(0.0, 0.0, 1.0, 0.5), ['TVD','straight'], ['WUA','straight'],
                                        ['TVJ','straight'], ['WUG','straight']],
    'NECROMANCY':    [(1.0, 0.0, 1.0, 0.5), ['AJGD','straight'], ['PMQ','straight'], ['LBG','straight']],
    'TRANSMUTATION': [(0.0, 0.5, 0.0, 0.5), ['MQN','arc'], ['NPSQN','straight']],
}

_SIGIL_LOCK  = threading.Lock()
_SIGIL_CACHE: dict = {}   # keyed by "NAME:SCHOOL" → PNG bytes; cleared on server restart


@app.route("/api/sigil")
def spell_sigil_route():
    name   = request.args.get('name', '').strip().upper()
    school = request.args.get('school', 'evocation').strip().upper()

    if not name:
        return jsonify({'error': 'name is required'}), 400

    cache_key = f"{name}:{school}"
    if cache_key in _SIGIL_CACHE:
        return send_file(io.BytesIO(_SIGIL_CACHE[cache_key]), mimetype='image/png')

    sc = school if school in _SPELL_SCHOOLS_SIGIL else 'EVOCATION'
    school_color = _SPELL_SCHOOLS_SIGIL[sc][0]

    word_configs = [
        {'word': _SPELL_SCHOOLS_SIGIL[sc][x][0],
         'connection': _SPELL_SCHOOLS_SIGIL[sc][x][1],
         'line_color': school_color,
         'close': True}
        for x in range(1, len(_SPELL_SCHOOLS_SIGIL[sc]))
    ] + [
        {'word': name, 'connection': 'both',
         'line_color': (0.827, 0.686, 0.216), 'line_width': 2.5}
    ]

    buf = io.BytesIO()
    with _SIGIL_LOCK:
        _plt.rcParams['figure.figsize'] = [4, 4]
        _plot_word_with_connection(
            word_configs,
            filename=buf,
            title=None,
            show_title=False,
            normalize=False,
            scale_min_frac=0.3,
            scale_max_frac=0.8,
        )
        _plt.close('all')

    buf.seek(0)
    img_bytes = buf.read()
    _SIGIL_CACHE[cache_key] = img_bytes
    return send_file(io.BytesIO(img_bytes), mimetype='image/png')


# ---------------------------------------------------------------------------
# Open5e proxy  —  keeps all external API calls server-side
# ---------------------------------------------------------------------------

@app.route("/api/open5e/<path:endpoint>")
def open5e_proxy(endpoint):
    params = request.args.to_dict()
    cache_key = endpoint + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    if cache_key in _PROXY_CACHE:
        content, status = _PROXY_CACHE[cache_key]
        return (content, status, {"Content-Type": "application/json"})
    url = f"{OPEN5E_BASE}/{endpoint}/"
    try:
        r = http.get(url, params=params, timeout=30,
                     headers={"Accept": "application/json"})
        _PROXY_CACHE[cache_key] = (r.content, r.status_code)
        return (r.content, r.status_code, {"Content-Type": "application/json"})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.route("/api/homebrew")
def homebrew_content():
    result = {"subclasses": [], "backgrounds": [], "species": [], "feats": [], "classes": []}
    if not os.path.isdir(HOMEBREW_DIR):
        return jsonify(result)
    for filename, key in [
        ("subclasses.json",  "subclasses"),
        ("backgrounds.json", "backgrounds"),
        ("species.json",     "species"),
        ("feats.json",       "feats"),
        ("classes.json",     "classes"),
    ]:
        path = os.path.join(HOMEBREW_DIR, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    result[key] = json.load(f)
            except Exception as e:
                result[key + "_error"] = str(e)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Builder page
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    files = []
    if os.path.isdir(MY_CHARACTERS_DIR):
        for fname in sorted(os.listdir(MY_CHARACTERS_DIR)):
            if fname.endswith(".json"):
                path = os.path.join(MY_CHARACTERS_DIR, fname)
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    files.append({
                        "filename":      fname,
                        "char_name":     data.get("char_name", fname[:-5]),
                        "class_name":    data.get("class_name", ""),
                        "subclass_name": data.get("subclass_name", ""),
                        "species_name":  data.get("species_name", ""),
                        "level":         data.get("level", ""),
                        "alignment":     data.get("alignment", ""),
                        "background_name": data.get("background_name", ""),
                    })
                except Exception:
                    files.append({"filename": fname, "char_name": fname[:-5],
                                  "class_name": "", "subclass_name": "",
                                  "species_name": "", "level": "",
                                  "alignment": "", "background_name": ""})
    return render_template("index.html", characters=files)


@app.route("/build")
def builder():
    return render_template("builder.html")


# ---------------------------------------------------------------------------
# Spell search  —  proxies Open5e /spells/ with level/school/class/name filters
# ---------------------------------------------------------------------------

@app.route("/api/spells/search")
def spells_search():
    level      = request.args.get("level", "")
    school     = request.args.get("school", "")
    cls        = request.args.get("class", "")
    name_query = request.args.get("name", "").strip().lower()

    params = {"document__key": "srd-2024", "limit": 1000}
    if level != "":
        params["level"] = level
    try:
        r = http.get(f"{OPEN5E_BASE}/spells/", params=params, timeout=15,
                     headers={"Accept": "application/json"})
        r.raise_for_status()
        spells = r.json().get("results", [])
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    for s in spells:
        if "index" not in s:
            s["index"] = s.get("key", "")
        sch = s.get("school")
        if isinstance(sch, dict):
            s["school"] = sch.get("key", "")

    if school:
        spells = [s for s in spells if s.get("school", "").lower() == school.lower()]

    if cls:
        cls_lower = cls.lower()
        def has_class(s):
            for c in s.get("classes", []):
                if cls_lower in (c.get("name","").lower(), c.get("key","").lower().split("_")[-1]):
                    return True
            return False
        spells = [s for s in spells if has_class(s)]

    if name_query:
        spells = [s for s in spells if name_query in s.get("name", "").lower()]

    return jsonify({"count": len(spells), "results": spells})


@app.route("/api/spells/<spell_index>")
def spell_detail(spell_index):
    try:
        r = http.get(f"{OPEN5E_BASE}/spells/{spell_index}/", timeout=15,
                     headers={"Accept": "application/json"})
        r.raise_for_status()
        s = r.json()
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    comps = []
    if s.get("verbal"):   comps.append("V")
    if s.get("somatic"):  comps.append("S")
    if s.get("material"): comps.append("M")

    desc = s.get("desc", [])
    if isinstance(desc, str): desc = [desc] if desc else []
    hl = s.get("higher_level", [])
    if isinstance(hl, str): hl = [hl] if hl else []

    return jsonify({
        "index":        spell_index,
        "name":         s.get("name", "Unknown"),
        "level":        s.get("level", 0),
        "school_index": s.get("school", {}).get("key", ""),
        "school_name":  s.get("school", {}).get("name", ""),
        "casting_time": s.get("casting_time", ""),
        "range":        s.get("range_text", s.get("range", "")),
        "duration":     s.get("duration", ""),
        "components":   ", ".join(comps),
        "material":     s.get("material_specified", ""),
        "ritual":       s.get("ritual", False),
        "concentration":s.get("concentration", False),
        "desc":         desc,
        "higher_level": hl,
        "classes":      [c.get("name", "") for c in s.get("classes", [])],
    })


# ---------------------------------------------------------------------------
# Build → Sheet
# The builder JS pre-fetches all Open5e data client-side and sends it in the
# payload as JSON strings, so Flask never needs to call Open5e directly.
# ---------------------------------------------------------------------------

@app.route("/api/build", methods=["POST"])
def build():
    f = request.get_json(force=True)

    # Unpack pre-fetched API data sent by the browser
    def parse_data(key):
        raw = f.get(key)
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except Exception:
            return {}
            

    sp  = parse_data("species_data")
    cls = parse_data("class_data")
    bg  = parse_data("bg_data")
    sub = parse_data("subclass_data")

    # Fall back to name fields if no data was sent
    sc = {
        "strength":     int(f.get("str", 10)),
        "dexterity":    int(f.get("dex", 10)),
        "constitution": int(f.get("con", 10)),
        "intelligence": int(f.get("int", 10)),
        "wisdom":       int(f.get("wis", 10)),
        "charisma":     int(f.get("cha", 10)),
    }

    def mod(s): return (s - 10) // 2
    def fmt(n): return f"+{n}" if n >= 0 else str(n)

    level = int(f.get("level", 1))
    prof  = max(2, (level - 1) // 4 + 2)

    # HP — respect builder overrides (custom die selection, rolled HP)
    hit_die_override = f.get("hit_die_override")
    if hit_die_override:
        hit_die = max(4, int(hit_die_override))
    else:
        hit_die_str = (cls.get("hit_points") or {}).get("hit_dice", "D8")
        hit_die = int("".join(c for c in hit_die_str if c.isdigit()) or "8")

    hp_rolled = f.get("hp_rolled")
    if hp_rolled and int(hp_rolled) > 0:
        hp_max = max(1, int(hp_rolled))
    else:
        hp_max = hit_die + mod(sc["constitution"]) + (level - 1) * (hit_die // 2 + 1 + mod(sc["constitution"]))
        hp_max = max(1, hp_max)
    hp_temp = 0

    # Skills
    SKILL_AB = {
        "Acrobatics": "dexterity", "Animal Handling": "wisdom", "Arcana": "intelligence",
        "Athletics": "strength", "Deception": "charisma", "History": "intelligence",
        "Insight": "wisdom", "Intimidation": "charisma", "Investigation": "intelligence",
        "Medicine": "wisdom", "Nature": "intelligence", "Perception": "wisdom",
        "Performance": "charisma", "Persuasion": "charisma", "Religion": "intelligence",
        "Sleight of Hand": "dexterity", "Stealth": "dexterity", "Survival": "wisdom",
    }
    chosen = [s.lower() for s in f.get("skills", [])]
    skills_out = []
    for sk, ab in SKILL_AB.items():
        base = mod(sc[ab])
        ip = sk.lower() in chosen
        skills_out.append({
            "name": sk, "ability": ab[:3].upper(),
            "base_mod": base,
            "bonus": base + (prof if ip else 0),
            "proficiency": "proficient" if ip else "none",
        })

    # Saving throws
    raw_saves = cls.get("saving_throws") or []
    save_profs = []
    for s in raw_saves:
        if isinstance(s, dict): save_profs.append(s.get("name", "").lower())
        elif isinstance(s, str): save_profs.append(s.lower())

    ABS = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    abilities_out = []
    for ab in ABS:
        score = sc[ab]; m = mod(score)
        isp = ab in save_profs or ab[:3] in save_profs
        abilities_out.append({
            "key": ab, "label": ab[:3].upper(), "score": score,
            "modifier": m, "save": m + (prof if isp else 0), "save_prof": isp,
        })

    passive_perc = 10 + next((s["bonus"] for s in skills_out if s["name"] == "Perception"), mod(sc["wisdom"]))

    # Speed from species traits
    speed_val = 30
    for t in (sp.get("traits") or []):
        if isinstance(t, dict) and t.get("type") == "SPEED":
            m = re.search(r"\d+", t.get("desc", "30"))
            if m:
                speed_val = int(m.group())
                break

    # Spell slots
    SLOTS = {
        "full": {1:[2],2:[3],3:[4,2],4:[4,3],5:[4,3,2],6:[4,3,3],7:[4,3,3,1],
                 8:[4,3,3,2],9:[4,3,3,3,1],10:[4,3,3,3,2],11:[4,3,3,3,2,1],
                 12:[4,3,3,3,2,1],13:[4,3,3,3,2,1,1],14:[4,3,3,3,2,1,1],
                 15:[4,3,3,3,2,1,1,1],16:[4,3,3,3,2,1,1,1],17:[4,3,3,3,2,1,1,1,1],
                 18:[4,3,3,3,3,1,1,1,1],19:[4,3,3,3,3,2,1,1,1],20:[4,3,3,3,3,2,2,1,1]},
        "half": {1:[2],2:[2],3:[3],4:[3],5:[4,2],6:[4,2],7:[4,3],
                 8:[4,3],9:[4,3,2],10:[4,3,2],11:[4,3,3],
                 12:[4,3,3],13:[4,3,3,1],14:[4,3,3,1],
                 15:[4,3,3,2],16:[4,3,3,2],17:[4,3,3,3,1],
                 18:[4,3,3,3,1],19:[4,3,3,3,2],20:[4,3,3,3,2]},
        "pact": {1:[1],2:[2],3:[0,2],4:[0,2],5:[0,0,2],6:[0,0,2],7:[0,0,0,2],
                 8:[0,0,0,2],9:[0,0,0,0,2],10:[0,0,0,0,2],11:[0,0,0,0,3],
                 12:[0,0,0,0,3],13:[0,0,0,0,3],14:[0,0,0,0,3],
                 15:[0,0,0,0,3],16:[0,0,0,0,3],17:[0,0,0,0,4],
                 18:[0,0,0,0,4],19:[0,0,0,0,4],20:[0,0,0,0,4]},
    }
    ct = (cls.get("caster_type") or "NONE").lower()
    slot_list = SLOTS.get("full" if ct == "full" else "half" if ct == "half" else "pact" if ct == "pact" else "", {}).get(level, [])
    spell_slots = [{"level": i+1, "max": n, "used": 0, "available": n} for i, n in enumerate(slot_list) if n > 0]

    # Spellcasting stats — derived from "Spellcasting" or "Pact Magic" feature description
    spell_mod_display = None
    spell_attack_display = None
    spell_save_dc = None
    spell_ability_abbr = ""
    if ct in ("full", "half", "pact"):
        for feat in (cls.get("features") or []):
            if feat.get("name") in ("Spellcasting", "Pact Magic"):
                m = re.search(
                    r'(Intelligence|Wisdom|Charisma) is (?:your |the )?spellcasting ability',
                    feat.get("desc", ""), re.I
                )
                if m:
                    ability = m.group(1).lower()
                    spell_ability_abbr = ability[:3].upper()
                    sc_mod = mod(sc[ability])
                    spell_mod_display    = fmt(sc_mod)
                    spell_attack_display = fmt(sc_mod + prof)
                    spell_save_dc        = 8 + sc_mod + prof
                break

    # Species traits
    traits_out = [{"name": t.get("name", ""), "desc": t.get("desc", "")}
                  for t in (sp.get("traits") or []) if isinstance(t, dict) and t.get("name")]

    # Class features — exclude spellcasting mechanics (handled by spell step)
    SKIP_FEAT_NAMES = {"Spellcasting"}
    class_features = []
    for feat in (cls.get("features") or []):
        gained = feat.get("gained_at") or []
        levels = [g["level"] for g in gained if isinstance(g, dict)]
        ft = feat.get("feature_type", "")
        name = feat.get("name", "")
        if name in SKIP_FEAT_NAMES or name.endswith("Spell List"):
            continue
        if ft in ("CLASS_LEVEL_FEATURE", "PROFICIENCIES") and (not levels or any(l <= level for l in levels)):
            d = feat.get("desc", "")
            class_features.append({"name": name, "desc": d})
    # (no cap — homebrew classes can have many features)

    # Subclass features (level-gated)
    subclass_features = []
    if sub:
        hb_data = sub.get("_hbData")
        if hb_data:
            # Homebrew JSON: features dict keyed by level string e.g. {"3": [...], "7": [...]}
            for level_str, feats in sorted((hb_data.get("features") or {}).items(), key=lambda x: int(x[0])):
                if int(level_str) <= level:
                    for feat in (feats or []):
                        d = feat.get("description", "")
                        subclass_features.append({
                            "name": feat.get("name", ""),
                            "desc": d,
                        })
        else:
            # Open5e: features list with gained_at
            for feat in (sub.get("features") or []):
                gained = feat.get("gained_at") or []
                levels = [g["level"] for g in gained if isinstance(g, dict)]
                if levels and any(l <= level for l in levels):
                    d = feat.get("desc", "")
                    subclass_features.append({
                        "name": feat.get("name", ""),
                        "desc": d,
                    })
    # (no cap — homebrew subclasses can have many features)

    # Parse CORE_TRAITS_TABLE rows for class proficiencies and equipment
    class_equipment = ""
    armor_proficiencies = ""
    weapon_proficiencies = ""
    core_traits = next((feat for feat in (cls.get("features") or [])
                        if feat.get("feature_type") == "CORE_TRAITS_TABLE"), None)
    if core_traits:
        for row in core_traits.get("desc", "").split("\n"):
            cells = [c.strip() for c in row.split("|") if c.strip()]
            if len(cells) < 2:
                continue
            label = cells[0].lower()
            if label == "starting equipment":
                class_equipment = cells[1]
            elif label == "armor training":
                armor_proficiencies = cells[1]
            elif label == "weapon proficiencies":
                weapon_proficiencies = cells[1]

    # Background benefits — equipment, tool proficiency, languages
    bg_equipment = ""
    bg_tool_proficiency = ""
    bg_languages = ""
    bg_trait_name = ""
    bg_trait_desc = ""
    bg_ofeat_name = ""
    bg_ofeat_desc = ""
    bg_benefits = bg.get("benefits") or []
    if bg_benefits:
        for b in bg_benefits:
            t = b.get("type", "")
            if t == "equipment"        and not bg_equipment:        bg_equipment        = b.get("desc", "")
            if t == "tool_proficiency" and not bg_tool_proficiency: bg_tool_proficiency = b.get("desc", "")
            if t == "language"         and not bg_languages:        bg_languages        = b.get("desc", "")
            if t == "trait"            and not bg_trait_name:
                bg_trait_name = b.get("name", "") #or b.get("desc", "")
                bg_trait_desc = b.get("desc", "")
            if t == "feat"      and not bg_ofeat_name:
                bg_ofeat_name = b.get("name", "") #or b.get("desc", "")
                bg_ofeat_desc = b.get("desc", "")
    else:
        flat = bg.get("starting_equipment") or []
        if flat:
            bg_equipment = ", ".join(flat)
        bg_tool_proficiency = bg.get("tool_proficiency") or ""
        bg_languages        = bg.get("languages") or ""
        bg_trait_name       = (bg.get("trait") or {}).get("name", "") #if isinstance(bg.get("trait"), dict) else (bg.get("trait") or "")
        bg_trait_desc       = (bg.get("trait") or {}).get("desc", "") #if isinstance(bg.get("trait"), dict) else ""
        bg_ofeat_name       = (bg.get("feat") or {}).get("name", "") #if isinstance(bg.get("feat"), dict) else (bg.get("feat") or "")
        bg_ofeat_desc       = (bg.get("feat") or {}).get("desc", "") #if isinstance(bg.get("feat"), dict) else ""

    ctx = {
        "char_name":        f.get("name", "Unnamed Hero"),
        "player_name":      f.get("player_name", ""),
        "alignment":        f.get("alignment", "True Neutral"),
        "species_name":     sp.get("name") or f.get("species_name", ""),
        "class_name":       cls.get("name") or f.get("class_name", ""),
        "subclass_name":    f.get("subclass_name", ""),
        "subclass_homebrew": f.get("subclass_homebrew", False),
        "background_name":  bg.get("name") or f.get("background_name", ""),
        "level":            level,
        "proficiency_bonus": prof,
        "passive_perception": passive_perc,
        "hp_max":           hp_max,
        "hp_current":       hp_max,
        "hp_temp":          hp_temp,
        "hp_pct":           100,
        "hit_dice_display": f"{level}d{hit_die}",
        "armor_class":      10 + mod(sc["dexterity"]),
        "speed":            speed_val,
        "initiative":       fmt(mod(sc["dexterity"])),
        "inspiration":      True,
        "spell_mod":        spell_mod_display,
        "spell_attack":     spell_attack_display,
        "spell_save_dc":    spell_save_dc,
        "spell_ability":    spell_ability_abbr,
        "abilities":        abilities_out,
        "skills":           skills_out,
        "spell_slots":      spell_slots,
        "traits":           traits_out,
        "class_features":     class_features,
        "subclass_features":  subclass_features,
        "resources":        [],
        "prepared_spells":  sorted(
            [{"name": s["name"], "level": s.get("level"), "index": s.get("index")} if isinstance(s, dict) else {"name": s, "level": None, "index": None}
             for s in f.get("spells", [])],
            key=lambda x: (x["level"] if x["level"] is not None else 99)
        ),
        "cantrips":         f.get("cantrips", []),
        "notes":            f.get("notes", ""),
        "backstory":        f.get("backstory", ""),
        "gold":             float(f.get("gold", 0)),
        "class_equipment":      class_equipment,
        "bg_equipment":         bg_equipment,
        "armor_proficiencies":  armor_proficiencies,
        "weapon_proficiencies": weapon_proficiencies,
        "bg_tool_proficiency":  bg_tool_proficiency,
        "bg_languages":         bg_languages,
        "bg_trait_name":        bg_trait_name,
        "bg_trait_desc":        bg_trait_desc,
        "bg_ofeat_name":        bg_ofeat_name,
        "bg_ofeat_desc":        bg_ofeat_desc,
    }
    char_id = str(uuid.uuid4())
    _CHARACTER_STORE[char_id] = ctx
    ctx['_raw'] = dict(f)          # preserve builder payload for the edit-character flow
    session["char_id"] = char_id
    return jsonify({"ok": True})


@app.route("/sheet")
def sheet():
    char_id = session.get("char_id")
    ctx = _CHARACTER_STORE.get(char_id) if char_id else None
    if not ctx:
        return "<h2 style='font-family:serif;padding:2rem'>No character found. <a href='/'>Back to builder</a></h2>"
    return render_template("sheet.html", **ctx)


@app.route("/api/character/builder-data")
def builder_data():
    """Return the raw builder payload so the wizard can be pre-filled for editing.
    Falls back to reconstructing a usable payload from the processed context when
    _raw is absent (characters built before edit-mode was added, or loaded from
    JSON files that predate this feature).
    """
    char_id = session.get("char_id")
    ctx = _CHARACTER_STORE.get(char_id) if char_id else None
    if not ctx:
        return jsonify({}), 404

    raw = ctx.get("_raw")
    if raw:
        return jsonify(raw)

    # ── reconstruct a partial payload from the processed context ────────────
    # Ability scores — stored as [{"key": "strength", "score": 15, ...}, ...]
    ab_map = {a["key"][:3]: a["score"] for a in (ctx.get("abilities") or [])}

    # Skills — return any that are not 'none' (proficient / half / expert)
    chosen_skills = [
        s["name"] for s in (ctx.get("skills") or [])
        if s.get("proficiency", "none") != "none"
    ]

    reconstructed = {
        "name":              ctx.get("char_name", ""),
        "player_name":       ctx.get("player_name", ""),
        "alignment":         ctx.get("alignment", ""),
        "level":             ctx.get("level", 1),
        "gold":              ctx.get("gold", 0),
        "backstory":         ctx.get("backstory", ""),
        "notes":             ctx.get("notes", ""),
        "species_name":      ctx.get("species_name", ""),
        "class_name":        ctx.get("class_name", ""),
        "subclass_name":     ctx.get("subclass_name", ""),
        "subclass_homebrew": ctx.get("subclass_homebrew", False),
        "background_name":   ctx.get("background_name", ""),
        "str": ab_map.get("str", 10),
        "dex": ab_map.get("dex", 10),
        "con": ab_map.get("con", 10),
        "int": ab_map.get("int", 10),
        "wis": ab_map.get("wis", 10),
        "cha": ab_map.get("cha", 10),
        "skills": chosen_skills,
        "spells": ctx.get("prepared_spells") or [],
    }
    return jsonify(reconstructed)


@app.route("/api/character")
def api_character():
    char_id = session.get("char_id")
    return jsonify(_CHARACTER_STORE.get(char_id, {}) if char_id else {})


MY_CHARACTERS_DIR = os.path.join(os.path.dirname(__file__), "my_characters")

@app.route("/api/character/save", methods=["POST"])
def save_character():
    char_id = session.get("char_id")
    ctx = _CHARACTER_STORE.get(char_id) if char_id else None
    if not ctx:
        return jsonify({"error": "No character found"}), 404

    os.makedirs(MY_CHARACTERS_DIR, exist_ok=True)

    # Sanitise the character name for use as a filename
    raw_name = ctx.get("char_name", "character")
    safe_name = re.sub(r'[^\w\s-]', '', raw_name).strip().replace(' ', '_') or "character"
    filename = f"{safe_name}.json"
    filepath = os.path.join(MY_CHARACTERS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False)

    return jsonify({"ok": True, "filename": filename})


@app.route("/edit/<filename>")
def edit_character(filename):
    """Load a saved character into the session then redirect to the builder in edit mode."""
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        return "Invalid filename", 400
    path = os.path.join(MY_CHARACTERS_DIR, filename)
    if not os.path.exists(path):
        return "Character file not found", 404
    with open(path, encoding="utf-8") as f:
        ctx = json.load(f)
    char_id = str(uuid.uuid4())
    _CHARACTER_STORE[char_id] = ctx
    session["char_id"] = char_id
    return redirect(url_for("builder") + "?edit=1")


@app.route("/load/<filename>")
def load_character(filename):
    # Prevent path traversal — only allow plain filenames with no slashes
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        return "Invalid filename", 400
    path = os.path.join(MY_CHARACTERS_DIR, filename)
    if not os.path.exists(path):
        return "Character file not found", 404
    with open(path, encoding="utf-8") as f:
        ctx = json.load(f)
    char_id = str(uuid.uuid4())
    _CHARACTER_STORE[char_id] = ctx
    session["char_id"] = char_id
    return redirect(url_for("sheet"))


if __name__ == "__main__":
    app.run(debug=True)

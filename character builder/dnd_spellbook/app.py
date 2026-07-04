# app.py — A small Flask web app that looks up D&D 5e spells.
#
# WHAT IS FLASK?
# Flask is a "web framework" for Python. It lets you write Python functions
# that run when someone visits a URL in their browser. We attach a function
# to a URL using a "decorator" (the @app.route(...) line above each function).
#
# HOW THE APP WORKS, IN PLAIN ENGLISH:
#   1. The user opens the page in a browser. Their browser asks our server
#      for "/" — we respond with the HTML page (the form + empty results area).
#   2. The user picks filters (level, school, class) and clicks "Search".
#      The page's JavaScript calls our own URL "/api/search" — that's still
#      OUR server, written in Python below.
#   3. Our Python code then calls the *real* D&D API (dnd5eapi.co), reformats
#      the data a bit, and sends it back to the browser as JSON.
#   4. The browser uses that JSON to draw the spell list / spell card.
#
# WHY ROUTE THROUGH PYTHON INSTEAD OF CALLING THE API DIRECTLY FROM JS?
#   - This is the whole point of doing it in Python: the *Python code* is
#     where the work happens. We can clean up the data, add caching, log
#     things, etc. The HTML page is just the front door.
#   - It also avoids any browser cross-origin (CORS) hassle — the browser
#     only ever talks to our own server.

# ---------------------------------------------------------------------------
# IMPORTS — bringing in code that other people have already written.
# ---------------------------------------------------------------------------

# `Flask` is the web framework itself.
# `render_template` finds an HTML file in the `templates/` folder and returns it.
# `jsonify` turns a Python dict into a proper JSON HTTP response.
# `request` lets us read query-string parameters like ?level=3 from the URL.
from flask import Flask, render_template, jsonify, request

# `requests` is the standard Python library for making HTTP calls.
# Don't confuse it with Flask's `request` above — different things, similar name.
# (Flask's `request` = the incoming request from the user's browser.
#  `requests` = the library WE use to call OTHER websites, like the D&D API.)
import requests


# ---------------------------------------------------------------------------
# CONFIG — values we want to set once and reuse.
# ---------------------------------------------------------------------------

# The base URL of the Open5e API. We use SRD 2024 content only.
API_BASE = "https://api.open5e.com/v2"
DOCUMENT_KEY = "srd-2024"

# How long to wait for the Open5e API before giving up. Always set a timeout
# on requests calls — without one, a slow server can hang your app forever.
TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# CREATE THE FLASK APP.
# ---------------------------------------------------------------------------

# `__name__` is a built-in Python variable. When you run this file directly,
# it equals "__main__"; when imported, it equals the module name. Flask uses
# it to figure out where to look for templates and static files. You'll see
# this exact line in nearly every Flask app — don't overthink it.
app = Flask(__name__)


# ---------------------------------------------------------------------------
# ROUTE 1 — the home page.
# ---------------------------------------------------------------------------

# `@app.route("/")` means: "when a browser asks for the root URL, run this
# function". The "/" is the path part of the URL (e.g. for localhost:5000/
# the path is just "/").
@app.route("/")
def home():
    # `render_template` looks inside the `templates/` folder for the file
    # named "index.html" and returns its contents. Flask is opinionated:
    # templates MUST live in a folder called `templates` next to this file.
    return render_template("index.html")


# ---------------------------------------------------------------------------
# ROUTE 2 — search for spells (called by the page's JavaScript).
# ---------------------------------------------------------------------------

@app.route("/api/search")
def api_search():
    # `request.args` is a dict-like object holding URL query-string params.
    # If the browser asked for /api/search?level=3&school=evocation
    # then request.args["level"] == "3" and request.args["school"] == "evocation".
    #
    # `.get("level", "")` means "give me the 'level' parameter, or an empty
    # string if it isn't there". This is safer than request.args["level"],
    # which would crash with a KeyError if the param were missing.
    level = request.args.get("level", "")
    school = request.args.get("school", "")
    cls = request.args.get("class", "")
    name_query = request.args.get("name", "").strip().lower()

    # Open5e only exposes spells through /spells/. We request the SRD-2024
    # documents and apply any additional filtering locally.
    url = f"{API_BASE}/spells/"
    params = {"document__key": DOCUMENT_KEY, "limit": 1000}
    if level != "":
        params["level"] = level
    # Note: School filtering is done locally below, as the API may not support it reliably.

    # `try` / `except` lets us handle errors gracefully. If anything goes
    # wrong inside the try block (network down, API returns garbage, etc.)
    # Python jumps to the matching `except` instead of crashing.
    try:
        # Make the HTTP GET request. `params=...` automatically builds the
        # ?key=value&key=value bit of the URL for us — no manual stringing.
        response = requests.get(url, params=params, timeout=TIMEOUT)

        # `raise_for_status()` raises an exception if the response was an
        # HTTP error (4xx or 5xx). Without this, a 500 from the API would
        # silently look like a successful empty response.
        response.raise_for_status()

        # `.json()` parses the response body as JSON and gives us a Python
        # dict (or list). The Open5e list endpoint returns {"count": N,
        # "results": [...]}.
        data = response.json()
    except requests.RequestException as err:
        # `RequestException` is the parent of all `requests` library errors
        # (timeouts, connection failures, bad status codes, etc.). Catching
        # the parent class catches all of them in one go.
        #
        # We send back a JSON error and HTTP status 502 ("Bad Gateway") —
        # which means "I'm a server, and the upstream server I depend on
        # gave me a bad response". The JS in the browser checks for this.
        return jsonify({"error": f"Open5e API request failed: {err}"}), 502

    # `data.get("results", [])` — same pattern as before: use a default of
    # an empty list if the key isn't there, so the rest of the code doesn't
    # explode trying to iterate over None.
    spells = data.get("results", [])

    # Normalize Open5e list results for the existing frontend.
    for spell_summary in spells:
        if "index" not in spell_summary:
            spell_summary["index"] = spell_summary.get("key", "")
        school_obj = spell_summary.get("school")
        if isinstance(school_obj, dict):
            spell_summary["school"] = school_obj.get("key", "")

    # Filter by school locally.
    if school:
        school_lower = school.lower()
        spells = [s for s in spells if s.get("school", "").lower() == school_lower]

    # Filter by class locally, since Open5e doesn't expose the old /classes/<cls>/spells
    # endpoint semantics in the same way.
    if cls:
        cls_lower = cls.lower()
        def has_class(spell):
            for c in spell.get("classes", []):
                name = c.get("name", "").lower()
                key = c.get("key", "").lower().split("_")[-1]
                if cls_lower == name or cls_lower == key:
                    return True
            return False
        spells = [s for s in spells if has_class(s)]

    # Filter by name substring if the user typed one.
    if name_query:
        spells = [s for s in spells if name_query in s.get("name", "").lower()]

    return jsonify({"count": len(spells), "results": spells})


# ---------------------------------------------------------------------------
# ROUTE 3 — fetch the full details for a single spell.
# ---------------------------------------------------------------------------

# `<spell_index>` in the route is a *URL parameter* (also called a "path
# variable"). Whatever the user puts there gets passed into our function
# as the argument with the same name. So /api/spell/fireball -> spell_index="fireball".
@app.route("/api/spell/<spell_index>")
def api_spell(spell_index):
    try:
        response = requests.get(
            f"{API_BASE}/spells/{spell_index}/", timeout=TIMEOUT
        )
        response.raise_for_status()
        spell = response.json()
    except requests.RequestException as err:
        return jsonify({"error": f"Failed to fetch spell: {err}"}), 502

    # Open5e returns a slightly different spell shape than the old API.
    # Normalize it for the frontend.
    components = []
    if spell.get("verbal"):
        components.append("V")
    if spell.get("somatic"):
        components.append("S")
    if spell.get("material"):
        components.append("M")

    desc = spell.get("desc", [])
    if isinstance(desc, str):
        desc = [desc] if desc else []

    higher_level = spell.get("higher_level", [])
    if isinstance(higher_level, str):
        higher_level = [higher_level] if higher_level else []

    formatted = {
        "index": spell_index,
        "name": spell.get("name", "Unknown"),
        "level": spell.get("level", 0),
        "school_index": spell.get("school", {}).get("key", ""),
        "school_name": spell.get("school", {}).get("name", ""),
        "casting_time": spell.get("casting_time", ""),
        "range": spell.get("range_text", spell.get("range", "")),
        "duration": spell.get("duration", ""),
        "components": ", ".join(components),
        "material": spell.get("material_specified", ""),
        "ritual": spell.get("ritual", False),
        "concentration": spell.get("concentration", False),
        "desc": desc,
        "higher_level": higher_level,
        "classes": [c.get("name", "") for c in spell.get("classes", [])],
    }

    return jsonify(formatted)


# ---------------------------------------------------------------------------
# RUN THE APP — only when this file is run directly, not when imported.
# ---------------------------------------------------------------------------

# `if __name__ == "__main__":` is a Python idiom. It's True when you run
# this file directly (`python app.py`) and False when another file imports
# from this one. The block only runs in the first case — useful so we
# don't accidentally start a web server during tests or imports.
if __name__ == "__main__":
    # `debug=True` enables auto-reload (the server restarts when you save
    # the file) and shows a nice error page in the browser. Turn it OFF
    # in production — the debug console can let attackers run code.
    #
    # `port=5000` is the default. Visit http://localhost:5001 in a browser.
    app.run(debug=True, port=5002)

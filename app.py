"""LearnGeo -- a world-knowledge quiz show.

    python scripts/fetch_data.py     # once, builds the dataset
    python app.py                    # then open http://127.0.0.1:5000
"""
import os
import json
import random
import time
import uuid
from urllib.parse import quote_plus

from flask import Flask, jsonify, redirect, render_template, request, url_for, g


def _load_env(path=".env"):
    """Read .env if it is there, without adding a dependency.

    Anything already in the real environment wins, which is what makes this
    safe on a host: Railway sets its variables properly and this changes
    nothing there.
    """
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except IOError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env()

from learngeo import matching, provenance, questions, store, supplement
from learngeo.data import TOPIC_FIELDS, ent_name, slug, world
from learngeo.data_util import wiki_url

app = Flask(__name__)
# Nothing about a run rides in a cookie any more -- answer keys, scores and
# pending questions live in the database, keyed by run id -- so this only
# signs whatever Flask itself needs. Set LEARNGEO_SECRET on a real host.
app.secret_key = os.environ.get("LEARNGEO_SECRET", "learngeo-local-dev-key")

RUN_LENGTH = 12       # questions in a standard run
STARTING_LIVES = 3
BASE_POINTS = 100

PLAYER_COOKIE = "learngeo_player"
LEARN_COOKIE = "learngeo_learning"
COOKIE_YEAR = 365 * 24 * 3600

# A two-option question is one coin toss away from being answered by someone
# who knows nothing, so it cannot be worth what a four-option one is. Driving
# side and "is it in NATO" are the two-option ones; a map click, with 197
# countries to choose between, is worth more than either.
CHOICE_WEIGHT = {0: 1.25, 2: 0.5, 4: 1.0}

# How long an unanswered question can sit before its elapsed time stops
# counting towards the speed bonus. A refresh restarts the browser's clock, so
# the server keeps its own and takes whichever is shorter.
SPEED_WINDOW_MS = 12000


def player_id():
    """Who is playing, with no account and no sign-up.

    A random id in a year-long cookie. It scopes every row in the progress
    database, so two people on the same deployed copy do not share a score,
    and clearing your cookies is how you start over. Nothing about a person is
    stored: the id is the only thing that identifies the browser, and it is
    generated here, not derived from anything.
    """
    if hasattr(g, "player_id"):
        return g.player_id
    pid = request.cookies.get(PLAYER_COOKIE)
    if pid and 8 <= len(pid) <= 40 and pid.isalnum():
        g.player_id = pid
    else:
        g.player_id = uuid.uuid4().hex[:24]
    return g.player_id


def learning_on():
    """Whether answers train the picker. Off means questions come at random
    and nothing is written down."""
    return request.cookies.get(LEARN_COOKIE) != "off"


def with_player(response):
    """Refresh the cookies on the way out, so a year is a rolling year."""
    pid = player_id()
    response.set_cookie(PLAYER_COOKIE, pid, max_age=COOKIE_YEAR,
                        samesite="Lax", httponly=True)
    return response


# --------------------------------------------------------------------------
# Runs, one per tab
# --------------------------------------------------------------------------
# Persistence used to be keyed by browser: one active run, whichever tab
# touched it last. Open a second tab, pick a different game, and the first
# tab's run was gone -- and refreshing the first tab resumed the second tab's
# game. A run now has an id of its own, it lives in the URL, and every API
# call names the run it means. Two tabs are two runs.

def load_run(run_id):
    """Fetch a run and remember the version it was at, for the save."""
    if not run_id:
        return None
    state, version = store.load_run(player_id(), run_id)
    if state is not None:
        g.run_version = version
    return state


def save_run(run):
    """Write a run back, refusing to flatten a newer write from another tab."""
    version = store.save_run(player_id(), run["id"], run,
                             getattr(g, "run_version", 0))
    if version is None:
        return False
    g.run_version = version
    return True


def requested_run_id():
    """The run this request is about: a query parameter or a JSON field."""
    rid = request.args.get("run")
    if not rid and request.is_json:
        rid = (request.get_json(silent=True) or {}).get("run")
    return rid if rid and rid.isalnum() and len(rid) <= 40 else None


@app.after_request
def _keep_player(response):
    if request.endpoint and request.endpoint != "static":
        with_player(response)
        response.headers["Cache-Control"] = "no-store"
    return response


# Stale runs are swept once in a while rather than on a timer: there is no
# scheduler here, and a fortnight-old run costs nothing until somebody asks
# the database a question anyway.
_LAST_SWEEP = [0.0]
SWEEP_EVERY = 3600.0


def maybe_sweep():
    now = time.time()
    if now - _LAST_SWEEP[0] < SWEEP_EVERY:
        return
    _LAST_SWEEP[0] = now
    try:
        store.cleanup_stale()
    except Exception:
        pass          # a failed tidy-up is never worth a failed request


# --------------------------------------------------------------------------
# Fact cards -- the payload shown after every answer. This is the part that
# actually teaches, so it gets a photo and real detail, not just "correct!".
# --------------------------------------------------------------------------

def speaker_count(n):
    """215424000 -> '215.4M'. Speaker numbers are census figures; showing them
    to the digit implies a precision they do not have."""
    if not n:
        return None
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000.0)
    if n >= 1_000:
        return "%.0fk" % (n / 1000.0)
    return str(n)


def language_rows(c, limit=3):
    """The languages of a country, with the share of people who speak each.

    At least three where the data has three, and more than three whenever the
    ones beyond it are still spoken by a fifth of the country -- a rule that
    keeps Switzerland's four and Canada's two both looking right.
    """
    langs = [l for l in (c.get("languages") or []) if isinstance(l, dict)]
    out = []
    for i, lang in enumerate(langs):
        if i >= limit and (lang.get("share") or 0) < 20 and not lang.get("status"):
            continue
        out.append({
            "name": lang["name"],
            "share": lang.get("share"),
            "official": bool(lang.get("official")),
            "status": lang.get("status"),
            "speakers": speaker_count(lang.get("speakers")),
            "wiki": lang.get("wiki"),
            "kind": "language",
            "key": lang.get("qid") or slug(lang["name"]),
        })
    return out


def language_line(c):
    """The same list as one line of text, for the fact-card bullet."""
    bits = []
    for lang in language_rows(c):
        if lang["share"]:
            bits.append("%s %g%%" % (lang["name"], lang["share"]))
        elif lang["speakers"]:
            bits.append("%s %s" % (lang["name"], lang["speakers"]))
        else:
            bits.append(lang["name"])
    return ", ".join(bits)


def leader_rows(c, limit=4):
    """Current leaders, with the two offices merged when one person holds both.

    Presidential systems put the same person in both chairs, and the card was
    printing them twice -- Guatemala showed Bernardo Arevalo next to Bernardo
    Arevalo.
    """
    ROLES = {"head_of_state": "Head of state",
             "head_of_government": "Head of government"}
    out = []
    for p in (c.get("leaders") or []):
        if not p.get("name"):
            continue
        same = next((x for x in out if x["name"] == p["name"]), None)
        role = ROLES.get(p.get("role"), "Leader")
        if same:
            if role not in same["roles"]:
                same["roles"].append(role)
            continue
        out.append({"name": p["name"], "roles": [role], "image": p.get("image"),
                    "wiki": p.get("wiki"), "party": p.get("party"),
                    "start": p.get("start")})
    for p in out:
        p["role"] = " and ".join(p["roles"]).replace("Head of state and Head of "
                                                     "government", "Head of state and government")
    return out[:limit]


def economy_lines(c):
    """The two or three economy facts worth a strip on the card."""
    e = c.get("economy") or {}
    out = []
    if e.get("exports"):
        out.append(("Sells", ", ".join(e["exports"][:4])))
    if e.get("export_partners"):
        out.append(("Sells to", ", ".join(
            "%s%s" % (p["name"], " %g%%" % p["share"] if p.get("share") else "")
            for p in e["export_partners"][:3])))
    if e.get("resources"):
        out.append(("Natural resources", ", ".join(e["resources"][:5])))
    if e.get("gdp_per_capita"):
        out.append(("GDP per head", e["gdp_per_capita"]))
    return out


def fact_card(iso2):
    w = world()
    c = w.get(iso2)
    if not c:
        return None
    neighbours = [{"iso2": n, "name": w.name(n), "flag": w.get(n)["flag_thumb"]}
                  for n in w.neighbours(iso2, 8)]
    leaders = leader_rows(c, 3)
    bullets = []
    if c.get("drives_on"):
        bullets.append(("Driving side", c["drives_on"].capitalize()))
    if c.get("calling_code"):
        bullets.append(("Calling code", c["calling_code"]))
    if c.get("capitals"):
        bullets.append(("Capital", ", ".join(
            ent_name(x) for x in c["capitals"][:2])))
    if c.get("population"):
        bullets.append(("Population", "{:,}".format(c["population"])))
    if c.get("area"):
        bullets.append(("Area", "{:,} km2".format(int(c["area"]))))
    if c.get("climate_zone"):
        bullets.append(("Climate", c["climate_zone"]))
    if c.get("government_type") or c.get("government"):
        bullets.append(("Government", c.get("government_type")
                        or ent_name(c["government"][0])))
    if c.get("currencies"):
        bullets.append(("Currency", ent_name(c["currencies"][0])))
    langs = language_line(c)
    if langs:
        bullets.append(("Languages", langs))
    if c.get("national_languages"):
        bullets.append(("National language", ", ".join(c["national_languages"])))
        bullets.append(("Working languages", ", ".join(c["working_languages"])))
    for label, value in economy_lines(c)[:2]:
        bullets.append((label, value))
    all_neighbours = w.neighbours(iso2)
    if all_neighbours:
        bullets.append(("Land borders", "%d: %s" % (
            len(all_neighbours),
            ", ".join(n["name"] for n in neighbours[:4]) +
            (" ..." if len(all_neighbours) > 4 else ""))))
    else:
        bullets.append(("Land borders", "None"))
    return {
        "iso2": iso2,
        "iso3": c.get("iso3"),
        "name": c["name"],
        "flag": c["flag_url"],
        "emoji": c.get("flag_emoji"),
        "blurb": w.summary_line(iso2),
        "bullets": bullets,
        "neighbours": neighbours,
        "leaders": leaders,
        "figures": (c.get("key_figures") or [])[:4],
        "economy": economy_lines(c),
        "geometry": w.shape(iso2),
        "wiki_url": c.get("wiki_url"),
        "news_url": news_url(c["name"]),
        "cities": (c.get("cities") or [])[:5],
        "wars": [dict(x, kind="war", key=x.get("qid") or slug(x["name"]))
                 for x in (c.get("wars") or [])[:5]],
        "languages": language_rows(c, 4),
        "links": [x for f in ("government", "currencies", "religions")
                  for x in w.topics_for(iso2, f)][:6],
    }


def news_url(name):
    """Today's headlines for a country. Google News rather than a news API:
    no key, no quota, and it is where the reader would have gone anyway."""
    return ("https://news.google.com/search?q=%s&hl=en-US&gl=US&ceid=US:en"
            % quote_plus(name))


# --------------------------------------------------------------------------
# Focus cards -- what a wrong answer should actually put in front of you
# --------------------------------------------------------------------------
# "Which country did Gaddafi lead?" is a question about Gaddafi, and answering
# it wrong used to raise a page about Libya with him four screens down. The
# question says what it was about (its `highlight`), and that decides which
# card comes up. The country card is still there, one button away, because
# sometimes the country is the interesting part.

ROLE_LABEL = {"head_of_state": "Head of state",
              "head_of_government": "Head of government"}


def person_card(name, iso2):
    w = world()
    p = w.person(name)
    if not p:
        return None
    bio = supplement.summary_for(name)
    home = w.get(p.get("iso2") or iso2)
    lines = []
    if p.get("role"):
        role = ROLE_LABEL.get(p["role"], "Leader")
        span = " to ".join(x for x in (p.get("start"), p.get("end")) if x)
        lines.append((role, span or "in office"))
    if p.get("party"):
        lines.append(("Party", p["party"]))
    if p.get("occupations"):
        lines.append(("Known as", ", ".join(p["occupations"][:3])))
    if p.get("born") or p.get("died"):
        lines.append(("Lived", "%s to %s" % (p.get("born") or "?",
                                             p.get("died") or "now")))
    if p.get("note"):
        lines.append(("Why they matter", p["note"]))
    return {
        "kind": "person",
        "title": name,
        "subtitle": home["name"] if home else None,
        "image": p.get("image") or bio.get("image"),
        "blurb": bio.get("summary"),
        "facts": lines,
        "wiki_url": p.get("wiki") or bio.get("wiki") or wiki_url(name),
        "iso2": p.get("iso2") or iso2,
        "flag": home["flag_thumb"] if home else None,
    }


def city_card(name, iso2):
    w = world()
    c = w.get(iso2)
    if not c:
        return None
    cities = c.get("cities") or []
    row = next((x for x in cities if x.get("name") == name), None)
    if not row:
        return None
    rank = cities.index(row) + 1
    ordinal = ["largest", "second largest", "third largest", "fourth largest",
               "fifth largest"][rank - 1] if rank <= 5 else "%dth largest" % rank
    facts = [("Country", c["name"]), ("Size", "The %s city" % ordinal)]
    if row.get("population"):
        facts.append(("Population", "{:,}".format(row["population"])))
    if c.get("capitals") and ent_name(c["capitals"][0]) == name:
        facts.append(("Also", "The capital"))
    others = [x["name"] for x in cities if x["name"] != name][:4]
    if others:
        facts.append(("Other cities", ", ".join(others)))
    return {
        "kind": "city",
        "title": name,
        "subtitle": c["name"],
        "image": None,
        "blurb": None,
        "facts": facts,
        "wiki_url": row.get("wiki") or wiki_url(name),
        "iso2": iso2,
        "flag": c["flag_thumb"],
    }


def focus_card(highlight, iso2):
    """The card for the thing a question was about, or None for the country."""
    if not highlight:
        return None
    kind, value = highlight[0], highlight[1]
    if kind == "person":
        return person_card(value, iso2)
    if kind == "city":
        return city_card(value, iso2)
    return None          # "fact" highlights mark a line on the country card


# --------------------------------------------------------------------------
# Run state, persisted in SQLite and scoped to the browser cookie
# --------------------------------------------------------------------------

def new_run(category, endless=False, challenge=False, country=None):
    run = {
        "id": uuid.uuid4().hex,
        "country": country,
        "category": category,
        "endless": endless,
        # Challenge mode takes the four options away: you type the answer, or
        # for anything whose answer is a country, click it on the map.
        "challenge": challenge,
        "score": 0,
        "streak": 0,
        "best_streak": 0,
        "asked": 0,
        "correct": 0,
        "lives": STARTING_LIVES,
        "lifelines": {"fifty": 1, "peek": 1, "skip": 1},
        "recent": [],
        # How often each question type has come up, so a run spreads itself
        # over the topics instead of over the dice. See questions.balanced_mode.
        "mode_counts": {},
        "pending": {},
        "over": False,
        "started_at": time.time(),
    }
    g.run_version = 0
    store.save_run(player_id(), run["id"], run, 0)
    g.run_version = 1
    return run


def modes_for(category):
    modes = questions.CATEGORY_MODES.get(category)
    return list(modes) if modes else list(questions.MODES)


def public(run):
    out = {k: run.get(k) for k in
           ("id", "country", "category", "endless", "challenge", "score",
            "streak", "best_streak", "asked", "correct", "lives", "lifelines",
            "over")}
    # The browser keeps its own score history and can only report what it is
    # told. Sending the distinct countries a run has covered lets it show
    # what was learned alongside what was scored.
    out["countries_seen"] = sorted({pair[0] for pair in run.get("recent") or []})
    return out


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

@app.route("/")
def home():
    w = world()
    stats = store.overview(w, player_id())
    # The flag wall: every country, ordered so the world reads west to east,
    # dim until you have shown you know it.
    wall = []
    for iso in sorted(w.all_isos, key=lambda i: (w.get(i).get("lon") or 0)):
        c = w.get(iso)
        wall.append((iso, {"flag": c["flag_thumb"], "name": c["name"],
                           "level": stats["mastery"].get(iso, {}).get("level", 0)}))
    stats["mastery_wall"] = wall
    return render_template("index.html", categories=questions.CATEGORIES, stats=stats)


@app.route("/games")
def games():
    """Every game in one place, each offered both ways round: a scored run of
    twelve with three lives, or casual practice that never ends.

    Country practice was only reachable from a country's own page, which meant
    finding the country first and knowing the button was there. It is offered
    here too, as a list of every country in the dataset.
    """
    w = world()
    countries = sorted(((w.name(i), i) for i in w.all_isos))
    return render_template("games.html", categories=questions.CATEGORIES,
                           countries=countries,
                           stats=store.overview(w, player_id()))


@app.route("/map")
def world_map():
    """The atlas as a map rather than a list: click a country, read about it.

    The panel is filled from a lookup the page already has, so hovering and
    clicking cost nothing; only the link out to the full dossier is a page
    load.
    """
    w = world()
    stats = store.overview(w, player_id())
    # Keyed by ISO3 because that is the id on every GeoJSON feature.
    info = {}
    for iso in w.all_isos:
        c = w.get(iso)
        if not c.get("iso3"):
            continue
        info[c["iso3"]] = {
            "iso2": iso, "name": c["name"], "flag": c["flag_thumb"],
            "capital": ent_name((c.get("capitals") or [None])[0]),
            "continent": w.continent_of(iso),
            "population": c.get("population"),
            "area": int(c["area"]) if c.get("area") else None,
            "languages": [l["name"] for l in language_rows(c, 3)],
            "government": c.get("government_type"),
            "currency": ent_name((c.get("currencies") or [None])[0]),
            "blurb": w.summary_line(iso),
            "level": stats["mastery"].get(iso, {}).get("level", 0),
        }
    return render_template("map.html", info=info, stats=stats)


@app.route("/sources")
def sources():
    w = world()
    counts = {
        "countries": len(w.all_isos),
        "languages": len(w.topics.get("language") or {}),
        "wars": len(w.topics.get("war") or {}),
        "people": sum(1 for r in w.search_rows if r["kind"] == "person"),
        "cities": sum(len(w.get(i).get("cities") or []) for i in w.all_isos),
        "economy": sum(1 for i in w.all_isos if w.get(i).get("economy")),
    }
    return render_template("sources.html", counts=counts,
                           conventions=sorted(provenance.CONVENTIONS.items()))


@app.route("/play/<category>")
def play(category):
    """The stage. Always lands on a URL naming the run it is showing.

    Arriving without one resumes the newest run of this exact shape, or starts
    a fresh one, and then redirects so the id is in the address bar. That
    redirect is what makes refresh, back, bookmarking and a second tab all
    behave: the tab's own run is written down where only that tab can see it.
    """
    if category not in questions.CATEGORY_MODES:
        return redirect(url_for("home"))
    maybe_sweep()
    endless = request.args.get("endless") == "1"
    challenge = request.args.get("challenge") == "1"
    country = request.args.get("country", "").upper() or None
    if country and not world().get(country):
        return redirect(url_for("games"))
    shape = {"category": category, "endless": endless,
             "challenge": challenge, "country": country}

    requested = requested_run_id()
    run = load_run(requested)
    # A run id in the URL that will not load is the interesting case: it means
    # the browser is not returning its cookie, so every redirect would mint a
    # fresh run and bounce again -- an endless loop, not a game. One hop is
    # all this is allowed, so a browser that blocks cookies gets a playable
    # run with a stale id in the address bar rather than an error page.
    unowned = bool(requested) and run is None
    if run and any(run.get(k) != v for k, v in shape.items()):
        # The settings in the URL win over the run named in it: a link to the
        # endless version of a game has to start the endless version.
        run = None
    if run is None and not unowned:
        run, version = store.latest_run(player_id(), shape)
        if run and not run.get("over"):
            g.run_version = version
        else:
            run = None
    if run is None:
        run = new_run(category, endless, challenge, country)
    if requested != run["id"] and not unowned:
        args = dict(request.args, run=run["id"])
        return redirect(url_for("play", category=category, **args))

    title = next((n for k, n, _, _ in questions.CATEGORIES if k == category),
                 "Quiz")
    # What this country simply has no data for, said out loud rather than
    # quietly never asked about.
    gaps = {}
    if country:
        gaps = questions.missing_topics(
            world(), country, sorted(questions.COUNTRY_STUDY_MODES))
    return render_template("play.html", category=category, title=title,
                           endless=endless, challenge=challenge,
                           run_length=RUN_LENGTH, country=country,
                           run_id=run["id"], gaps=gaps)


@app.route("/atlas")
def atlas():
    w = world()
    stats = store.overview(w, player_id())
    rows = []
    for iso in w.all_isos:
        c = w.get(iso)
        m = stats["mastery"].get(iso, {})
        rows.append({
            "iso2": iso, "name": c["name"], "flag": c["flag_thumb"],
            "continent": w.continent_of(iso),
            "population": c.get("population") or 0,
            "area": int(c.get("area") or 0),
            "level": m.get("level", 0), "seen": m.get("seen", 0),
        })
    rows.sort(key=lambda r: r["name"])
    continents = sorted({r["continent"] for r in rows})
    return render_template("atlas.html", rows=rows, continents=continents, stats=stats)


@app.route("/country/<iso2>")
def country(iso2):
    iso2 = iso2.upper()
    w = world()
    c = w.get(iso2)
    if not c:
        return redirect(url_for("atlas"))
    stats = store.overview(w, player_id())
    linked = {f: w.topics_for(iso2, f) for f in TOPIC_FIELDS}
    return render_template("country.html", c=c, card=fact_card(iso2),
                           mastery=stats["mastery"].get(iso2),
                           linked=linked,
                           # Which facts on this page have a source behind
                           # them, and what that source actually says.
                           provenance=sorted(w.provenance(iso2).items()),
                           practice_gaps=questions.missing_topics(
                               w, iso2, sorted(questions.COUNTRY_STUDY_MODES)),
                           languages=language_rows(c, 5),
                           leaders=leader_rows(c),
                           economy=c.get("economy") or {},
                           news_url=news_url(c["name"]),
                           neighbours=[w.get(n) for n in w.neighbours(iso2)])


@app.route("/topics")
def topics_index():
    w = world()
    kinds = []
    for field, (kind, label, _) in TOPIC_FIELDS.items():
        nodes = w.topic_list(kind)
        kinds.append({"kind": kind, "label": label, "count": len(nodes),
                      "top": nodes[:8]})
    kinds.sort(key=lambda k: -k["count"])
    return render_template("topics.html", kinds=kinds)


@app.route("/topic/<kind>")
def topic_kind(kind):
    w = world()
    label = next((lbl for _, (k, lbl, _) in TOPIC_FIELDS.items() if k == kind), None)
    if not label:
        return redirect(url_for("topics_index"))
    return render_template("topic_list.html", kind=kind, label=label,
                           nodes=w.topic_list(kind))


@app.route("/topic/<kind>/<key>")
def topic(kind, key):
    w = world()
    node = w.topic(kind, key)
    if not node:
        return redirect(url_for("topic_kind", kind=kind))
    rows = []
    for r in node["countries"]:
        c = w.get(r["iso2"])
        if not c:
            continue
        rows.append({"iso2": r["iso2"], "name": c["name"], "flag": c["flag_thumb"],
                     "detail": r["detail"]})
    label = next((lbl for _, (k, lbl, _) in TOPIC_FIELDS.items() if k == kind), kind)
    return render_template("topic.html", node=node, rows=rows, kind=kind,
                           label=label)


@app.route("/progress")
def progress():
    w = world()
    stats = store.overview(w, player_id())
    weak = []
    for row in stats["weak"]:
        weak.append({
            "name": w.name(row["iso2"]), "iso2": row["iso2"],
            "mode": questions.MODES.get(row["mode"], ("", row["mode"], None))[1],
            "seen": row["seen"], "correct": row["correct"],
        })
    by_mode = []
    for row in stats["by_mode"]:
        label = questions.MODES.get(row["mode"], (row["mode"], row["mode"], None))[1]
        by_mode.append({"label": label, "seen": row["seen"],
                        "correct": row["correct"] or 0,
                        "pct": round(100 * (row["correct"] or 0) / row["seen"]) if row["seen"] else 0})
    return render_template("progress.html", stats=stats, weak=weak, by_mode=by_mode)


# --------------------------------------------------------------------------
# Quiz API
# --------------------------------------------------------------------------

@app.route("/api/next")
def api_next():
    w = world()
    run = load_run(requested_run_id())
    if run is None:
        return jsonify({"error": "That run has expired. Start a new one.",
                        "expired": True}), 409

    if run.get("last_response") and request.args.get("advance") != "1":
        return jsonify(dict(run["current_payload"],
                            restored_answer=run["last_response"]))
    if run.get("pending") and run.get("current_payload"):
        return jsonify(dict(run["current_payload"], run=public(run)))
    if run["over"]:
        return jsonify({"done": True, "run": public(run)})

    run.pop("last_response", None)
    modes = modes_for(run["category"])
    typed_only = False
    if run.get("challenge"):
        typed = [m for m in modes if m not in questions.CHOICE_REQUIRED]
        # Some games have nothing that can be typed: every Alliances question
        # is a yes or no, and "yes" typed blind is a coin toss. Rather than
        # refuse to start, the run plays as multiple choice and says so.
        typed_only = not typed
        modes = typed if typed else modes
    if run.get("country"):
        modes = [m for m in modes if m in questions.COUNTRY_STUDY_MODES]
        # Only what this country can actually be asked about. Retrying a
        # generator forty times in the hope that Tuvalu grows a land border
        # is not a plan.
        modes = questions.supported_modes(w, run["country"], modes)
    if not modes:
        return jsonify({"error": "No questions for this combination. "
                                 "Choose Grand Tour for country practice."}), 400

    rng = random
    q = None
    avoid = [tuple(x) for x in run["recent"][-14:]]
    counts = run.setdefault("mode_counts", {})
    for _ in range(40):
        if run.get("country"):
            iso = run["country"]
            mode = questions.balanced_mode(rng, modes, counts)
        else:
            iso, mode = store.pick(w, modes, rng, avoid=avoid,
                                   player=player_id(), adaptive=learning_on())
        gen = questions.MODES[mode][2]
        try:
            q = gen(w, iso, rng)
        except Exception:
            q = None
        if q:
            break
    if not q:
        return jsonify({"error": "Could not build a question. "
                                 "Is the dataset built?"}), 500

    kind = q.get("answer_kind") or "text"
    challenge = bool(run.get("challenge")) and kind != "map" and not typed_only

    qid = uuid.uuid4().hex[:12]
    run["pending"] = {qid: {"answer": q["answer"], "mode": q["mode"],
                            "subject": q["subject"],
                            "highlight": q.get("highlight"),
                            "answer_kind": kind,
                            "also": q.get("also") or [],
                            "choice_count": len(q.get("choices") or []),
                            # The server's own clock on this question. A
                            # refresh restarts the browser's, and the speed
                            # bonus should not be a reward for refreshing.
                            "asked_at": time.time(),
                            "challenge": challenge}}
    run["recent"] = (run["recent"] + [[q["subject"], q["mode"]]])[-18:]
    counts[q["mode"]] = counts.get(q["mode"], 0) + 1

    payload = {k: q[k] for k in ("mode", "prompt", "hint", "media", "choices")}
    payload["qid"] = qid
    payload["category_label"] = questions.MODES[q["mode"]][0]
    payload["run"] = public(run)
    payload["question_no"] = run["asked"] + 1
    payload["run_length"] = None if run["endless"] else RUN_LENGTH
    payload["answer_kind"] = kind
    payload["challenge"] = challenge
    # What the answer is measured against, where that is a convention rather
    # than a fact. Shown under the question: "largest city" means nothing
    # until you say whether you mean the city or the conurbation.
    payload["definition"] = q.get("definition")
    if typed_only:
        payload["note"] = ("This game has no typed answers -- every question "
                           "is a yes or no -- so it is played with options.")
    if challenge:
        # No options to choose between, so they are not sent at all -- and a
        # country answer gets the map as a second way in, since pointing at
        # Chad is a fair way to prove you know where Chad is.
        payload["choices"] = []
        payload["input"] = "text"
        if kind == "country" and not q["media"]:
            payload["media"] = {"type": "map"}
            payload["input"] = "text+map"
    run["current_payload"] = payload
    if not save_run(run):
        return jsonify({"error": "This run was changed in another tab. "
                                 "Refresh to pick it up.", "conflict": True}), 409
    return jsonify(payload)


@app.route("/api/answer", methods=["POST"])
def api_answer():
    """Score one answer, as a single transaction, exactly once.

    The four writes an answer causes -- the mastery card, the answer log, the
    finished-run row and the run state itself -- now land together or not at
    all, and the question id is the idempotency key: submit the same answer
    twice and the second submission gets the first one's response back rather
    than a second score. See store.commit_answer.
    """
    body = request.get_json(force=True) or {}
    run = load_run(requested_run_id())
    if run is None:
        return jsonify({"error": "That run has expired. Start a new one.",
                        "expired": True}), 409
    qid = body.get("qid")

    already = store.stored_answer(player_id(), run["id"], qid)
    if already is not None:
        return jsonify(already)

    pending = run.get("pending", {}).get(qid)
    if not pending:
        return jsonify({"error": "That question expired -- start a new one."}), 400

    given = body.get("choice")
    typed = body.get("text")
    ms = elapsed_ms(pending, body.get("ms"))
    skipped = bool(body.get("skipped"))
    if skipped:
        if run["lifelines"]["skip"] <= 0:
            return jsonify({"error": "No skips remaining."}), 400
        run["lifelines"]["skip"] -= 1
        run["streak"] = 0
        correct = False
    elif typed is not None:
        # Challenge mode: judged on meaning, not spelling. See matching.py.
        correct = matching.judge(world(), typed, pending)
    elif pending.get("answer_kind") in ("country", "map"):
        correct = matching.judge(world(), str(given or ""), pending)
    else:
        correct = str(given) == str(pending["answer"])

    run["asked"] += 1
    if correct:
        run["correct"] += 1
        run["streak"] += 1
        run["best_streak"] = max(run["best_streak"], run["streak"])
        run["score"] += award(run, pending, ms)
    elif not skipped:
        run["streak"] = 0
        # Casual runs have no lives to lose: they are practice, and being
        # thrown out after three mistakes is the opposite of practice.
        if not run["endless"]:
            run["lives"] -= 1

    finished = run["lives"] <= 0 or (not run["endless"]
                                     and run["asked"] >= RUN_LENGTH)
    if finished:
        run["over"] = True
    run["pending"] = {}

    highlight = pending.get("highlight")
    answer = pending["answer"]
    # In challenge mode there is no winning button to light up, so the answer
    # has to arrive as words.
    answer_text = answer
    c = None
    if pending.get("answer_kind") in ("country", "map"):
        iso = answer if len(str(answer)) == 2 else None
        c = world().by_iso3.get(answer) if iso is None else world().get(answer)
        answer_text = c["name"] if c else answer
    response = {
        "qid": qid,
        "points": run["score"] - run["current_payload"]["run"]["score"],
        "correct": correct,
        "skipped": skipped,
        "answer": answer,
        "answer_text": answer_text,
        "answer_iso3": (c.get("iso3") if c else None)
                       if pending.get("answer_kind") in ("country", "map") else None,
        "subject": pending["subject"],
        "mode": pending["mode"],
        "card": fact_card(pending["subject"]),
        # What the question was actually about: a person or a city gets its
        # own card, and anything else marks a line on the country's.
        "focus": focus_card(highlight, pending["subject"]),
        "highlight": highlight,
        "run": public(run),
        "finished": finished,
    }
    run["last_response"] = response

    learning = learning_on() and not skipped
    version, stored = store.commit_answer(
        player_id(), run["id"], qid, response, run,
        getattr(g, "run_version", 0),
        mastery=(pending["subject"], pending["mode"], correct, ms)
                if learning else None,
        finished_run=(run["category"], run["score"], run["asked"],
                      run["correct"], run["best_streak"])
                     if finished and learning_on() else None)
    if version is None:
        return jsonify({"error": "This run was changed in another tab. "
                                 "Refresh to pick it up.", "conflict": True}), 409
    g.run_version = version
    return jsonify(stored)


def elapsed_ms(pending, reported):
    """How long the question was on screen, believing whichever is longer.

    The browser's clock restarts on a refresh, so "refresh, then answer"
    reports a second and earns the full speed bonus for a question that has
    been open for a minute. The server's clock is set when the question is
    handed out and does not restart, so it is never an understatement --
    taking the larger of the two makes the bonus impossible to refresh into
    existence. It costs an honest player a little on a slow connection, which
    is the right side to be wrong on for a bonus nobody is ranked by.
    """
    server = None
    if pending.get("asked_at"):
        server = int((time.time() - pending["asked_at"]) * 1000)
    if not isinstance(reported, int) or reported < 0:
        return server
    return reported if server is None else max(reported, server)


def award(run, pending, ms):
    """Points for one correct answer.

    Three multipliers, and a fourth that stops a coin toss paying what real
    recall pays: a two-option question is worth half a four-option one, and a
    bare map click -- 197 countries, no options at all -- is worth more.
    """
    speed = 1.0
    if isinstance(ms, int) and 0 <= ms < SPEED_WINDOW_MS:
        speed = 1.0 + (SPEED_WINDOW_MS - ms) / (SPEED_WINDOW_MS * 2.0)
    streak = min(4, 1 + run["streak"] // 3)
    # No four options to guess between, so it is worth half as much again.
    hard = 1.5 if pending.get("challenge") else 1.0
    width = CHOICE_WEIGHT.get(pending.get("choice_count"), 1.0)
    return int(BASE_POINTS * streak * speed * hard * width)


@app.route("/api/lifeline", methods=["POST"])
def api_lifeline():
    body = request.get_json(force=True) or {}
    kind = body.get("kind")
    qid = body.get("qid")
    run = load_run(requested_run_id())
    if run is None:
        return jsonify({"error": "That run has expired.", "expired": True}), 409
    pending = run.get("pending", {}).get(qid)
    if kind not in ("fifty", "peek") or not pending or run["lifelines"].get(kind, 0) <= 0:
        return jsonify({"error": "Not available"}), 400
    run["lifelines"][kind] -= 1

    out = {"run": public(run)}
    if kind == "fifty":
        keys = body.get("keys") or []
        wrong = [k for k in keys if str(k) != str(pending["answer"])]
        random.shuffle(wrong)
        out["remove"] = wrong[:max(0, len(wrong) - 1)]
        run["current_payload"]["removed"] = out["remove"]
    elif kind == "peek":
        out["peek"] = world().summary_line(pending["subject"])
        run["current_payload"]["hint"] = out["peek"]
    out["run"] = public(run)
    if not save_run(run):
        return jsonify({"error": "This run was changed in another tab. "
                                 "Refresh to pick it up.", "conflict": True}), 409
    return jsonify(out)


@app.route("/api/geo")
def api_geo():
    """The quiz map: polygons, plus a point for every country without one.

    Twenty-six countries have no shape in this GeoJSON -- Singapore, Malta,
    Bahrain, every Pacific and Caribbean microstate -- and on a polygon-only
    map they are not merely hard to click, they are not there. Asked to find
    Tuvalu, you could not. Each gets a marker at its recorded centre instead,
    so it is a real target with a real name rather than an absence.
    """
    w = world()
    geo = w.geojson
    features = [f for f in geo["features"] if f.get("id") != "ATA"]
    have = {f.get("id") for f in features}
    points = []
    for iso in w.all_isos:
        c = w.get(iso)
        if c.get("iso3") in have or c.get("lat") is None or c.get("lon") is None:
            continue
        points.append({"id": c.get("iso3") or iso, "iso2": iso,
                       "name": c["name"], "lat": c["lat"], "lon": c["lon"]})
    return jsonify(dict(geo, features=features, points=points))


# Which set of names the challenge box should offer for each question type.
SUGGEST_DOMAIN = {
    "landmark_to_country": "country",
    "flag_to_country": "country", "country_to_flag": "country",
    "outline": "country", "capital_to_country": "country",
    "which_borders_both": "country", "border_odd_one_out": "country",
    "leader_photo": "country", "past_leader": "country",
    "famous_person": "country", "higher_lower": "country",
    "city_to_country": "country", "map_click": "country",
    "capital_of": "capital", "currency_of": "currency",
    "language_of": "language", "continent_of": "continent",
    "climate_of": "climate", "government_of": "govtype",
    "leader_name": "person", "city_in_country": "city",
    "biggest_city": "city",
}


@app.route("/api/suggest")
def api_suggest():
    """Type-ahead for challenge mode.

    Offering the names it will accept turns a spelling test back into a
    geography one. It is scoped to the kind of answer the question wants, so
    a capitals question suggests capitals, not all 197 countries.
    """
    mode = request.args.get("mode", "")
    kind = SUGGEST_DOMAIN.get(mode)
    if not kind:
        return jsonify({"results": []})
    return jsonify({"results": world().suggest(kind, request.args.get("q", ""))})


@app.route("/api/search")
def api_search():
    """Type-ahead for the box in the header: countries, topics and people."""
    return jsonify({"results": world().search(request.args.get("q", ""), 10)})


@app.route("/search")
def search_page():
    """Where Enter lands: the same matches, but a page of them."""
    q = request.args.get("q", "")
    results = world().search(q, 60)
    if len(results) == 1:
        return redirect(results[0]["url"])
    return render_template("search.html", q=q, results=results)


@app.route("/api/learning", methods=["POST"])
def api_learning():
    """Turn adaptation on or off, and optionally wipe what it has learned."""
    body = request.get_json(force=True) or {}
    on = bool(body.get("on"))
    if body.get("forget"):
        store.forget(player_id())
    resp = jsonify({"learning": on})
    resp.set_cookie(LEARN_COOKIE, "on" if on else "off",
                    max_age=COOKIE_YEAR, samesite="Lax")
    return resp


@app.route("/api/forget", methods=["POST"])
def api_forget():
    """Erase some named part of what the server holds for this browser.

    "Forget everything" used to mean mastery, the answer log and finished
    runs, and leave the game in progress sitting there to be resumed. The
    scopes are named now, and the page offers them one at a time, because a
    reset that quietly does three-quarters of the job is worse than one that
    says what it does. Scores kept in the browser are cleared by the browser;
    the page says which button does which.
    """
    body = request.get_json(force=True) or {}
    scopes = body.get("scopes")
    if scopes is not None and not isinstance(scopes, list):
        return jsonify({"error": "scopes must be a list"}), 400
    cleared = store.forget(player_id(), scopes)
    return jsonify({"cleared": cleared,
                    "scopes": sorted(store.FORGET_SCOPES)})


@app.route("/api/progress/export")
def api_export():
    """Everything the server holds for this browser, as a file to keep."""
    blob = store.export_data(player_id())
    resp = jsonify(blob)
    resp.headers["Content-Disposition"] = (
        "attachment; filename=learngeo-progress.json")
    return resp


@app.route("/api/progress/import", methods=["POST"])
def api_import():
    body = request.get_json(force=True, silent=True)
    if body is None:
        return jsonify({"error": "That file is not JSON."}), 400
    blob = body.get("data") if isinstance(body, dict) and "data" in body else body
    try:
        counts = store.import_data(player_id(), blob,
                                   replace=bool(isinstance(body, dict)
                                                and body.get("replace")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"imported": counts})


@app.route("/api/restart", methods=["POST"])
def api_restart():
    """Start a fresh run, leaving the old one to be swept in its own time."""
    body = request.get_json(force=True) or {}
    old = requested_run_id()
    run = new_run(body.get("category", "grand_tour"), bool(body.get("endless")),
                  bool(body.get("challenge")), body.get("country"))
    if old and old != run["id"]:
        store.drop_run(player_id(), old)
    return jsonify({"run": public(run)})


@app.route("/api/run/abandon", methods=["POST"])
def api_abandon():
    """Leave a run for good. What the in-game Exit button does."""
    rid = requested_run_id()
    if rid:
        store.drop_run(player_id(), rid)
    return jsonify({"abandoned": bool(rid)})


@app.template_filter("commas")
def commas(n):
    try:
        return "{:,}".format(int(n))
    except (TypeError, ValueError):
        return "-"


if __name__ == "__main__":
    # PORT is what every host hands you, Railway included. In production the
    # Procfile puts gunicorn in front of this and __main__ never runs.
    # A missing dataset is reported by learngeo.data, which both paths hit.
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

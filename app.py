"""LearnGeo -- a world-knowledge quiz show.

    python scripts/fetch_data.py     # once, builds the dataset
    python app.py                    # then open http://127.0.0.1:5000
"""
import os
import random
import uuid
from urllib.parse import quote_plus

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from learngeo import questions, store
from learngeo.data import TOPIC_FIELDS, ent_name, slug, world

app = Flask(__name__)
# Only guards the local session cookie (score, current answer key). Override
# with LEARNGEO_SECRET if you ever put this on a network.
app.secret_key = os.environ.get("LEARNGEO_SECRET", "learngeo-local-dev-key")

RUN_LENGTH = 12       # questions in a standard run
STARTING_LIVES = 3
BASE_POINTS = 100


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
        if i >= limit and (lang.get("share") or 0) < 20:
            break
        out.append({
            "name": lang["name"],
            "share": lang.get("share"),
            "official": bool(lang.get("official")),
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
# Run state, kept in the session cookie
# --------------------------------------------------------------------------

def new_run(category, endless=False):
    session["run"] = {
        "category": category,
        "endless": endless,
        "score": 0,
        "streak": 0,
        "best_streak": 0,
        "asked": 0,
        "correct": 0,
        "lives": STARTING_LIVES,
        "lifelines": {"fifty": 1, "peek": 1, "skip": 1},
        "recent": [],
        "pending": {},
        "over": False,
    }
    session.modified = True
    return session["run"]


def run_state():
    r = session.get("run")
    if not r:
        r = new_run("grand_tour")
    return r


def modes_for(category):
    modes = questions.CATEGORY_MODES.get(category)
    return list(modes) if modes else list(questions.MODES)


def public(run):
    return {k: run[k] for k in
            ("category", "endless", "score", "streak", "best_streak", "asked",
             "correct", "lives", "lifelines", "over")}


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

@app.route("/")
def home():
    w = world()
    stats = store.overview(w)
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
    twelve with three lives, or casual practice that never ends."""
    return render_template("games.html", categories=questions.CATEGORIES,
                           stats=store.overview(world()))


@app.route("/map")
def world_map():
    """The atlas as a map rather than a list: click a country, read about it.

    The panel is filled from a lookup the page already has, so hovering and
    clicking cost nothing; only the link out to the full dossier is a page
    load.
    """
    w = world()
    stats = store.overview(w)
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
    return render_template("sources.html", counts=counts)


@app.route("/play/<category>")
def play(category):
    if category not in questions.CATEGORY_MODES:
        return redirect(url_for("home"))
    endless = request.args.get("endless") == "1"
    new_run(category, endless)
    title = next((n for k, n, _, _ in questions.CATEGORIES if k == category), "Quiz")
    return render_template("play.html", category=category, title=title,
                           endless=endless, run_length=RUN_LENGTH)


@app.route("/atlas")
def atlas():
    w = world()
    stats = store.overview(w)
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
    stats = store.overview(w)
    linked = {f: w.topics_for(iso2, f) for f in TOPIC_FIELDS}
    return render_template("country.html", c=c, card=fact_card(iso2),
                           mastery=stats["mastery"].get(iso2),
                           linked=linked,
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
    return render_template("topic.html", node=node, rows=rows, kind=kind)


@app.route("/progress")
def progress():
    w = world()
    stats = store.overview(w)
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
    run = run_state()
    if run["over"]:
        return jsonify({"done": True, "run": public(run)})

    modes = modes_for(run["category"])
    rng = random
    q = None
    avoid = [tuple(x) for x in run["recent"][-8:]]
    for _ in range(40):
        iso, mode = store.pick(w, modes, rng, avoid=avoid)
        gen = questions.MODES[mode][2]
        try:
            q = gen(w, iso, rng)
        except Exception:
            q = None
        if q:
            break
    if not q:
        return jsonify({"error": "Could not build a question. Is the dataset built?"}), 500

    qid = uuid.uuid4().hex[:12]
    run["pending"] = {qid: {"answer": q["answer"], "mode": q["mode"],
                            "subject": q["subject"]}}
    run["recent"] = (run["recent"] + [[q["subject"], q["mode"]]])[-10:]
    session.modified = True

    payload = {k: q[k] for k in ("mode", "prompt", "hint", "media", "choices")}
    payload["qid"] = qid
    payload["category_label"] = questions.MODES[q["mode"]][0]
    payload["run"] = public(run)
    payload["question_no"] = run["asked"] + 1
    payload["run_length"] = None if run["endless"] else RUN_LENGTH
    return jsonify(payload)


@app.route("/api/answer", methods=["POST"])
def api_answer():
    body = request.get_json(force=True) or {}
    run = run_state()
    qid = body.get("qid")
    pending = run.get("pending", {}).get(qid)
    if not pending:
        return jsonify({"error": "That question expired -- start a new one."}), 400

    given = body.get("choice")
    ms = body.get("ms")
    skipped = bool(body.get("skipped"))
    correct = (not skipped) and str(given) == str(pending["answer"])

    if not skipped:
        store.record(pending["subject"], pending["mode"], correct, ms)

    run["asked"] += 1
    if correct:
        run["correct"] += 1
        run["streak"] += 1
        run["best_streak"] = max(run["best_streak"], run["streak"])
        speed = 1.0
        if isinstance(ms, int) and ms < 12000:
            speed = 1.0 + (12000 - ms) / 24000.0     # up to +50% for fast answers
        multiplier = min(4, 1 + run["streak"] // 3)
        run["score"] += int(BASE_POINTS * multiplier * speed)
    elif not skipped:
        run["streak"] = 0
        # Casual runs have no lives to lose: they are practice, and being
        # thrown out after three mistakes is the opposite of practice.
        if not run["endless"]:
            run["lives"] -= 1

    finished = run["lives"] <= 0 or (not run["endless"] and run["asked"] >= RUN_LENGTH)
    if finished:
        run["over"] = True
        store.record_run(run["category"], run["score"], run["asked"],
                         run["correct"], run["best_streak"])
    run["pending"] = {}
    session.modified = True

    return jsonify({
        "correct": correct,
        "skipped": skipped,
        "answer": pending["answer"],
        "card": fact_card(pending["subject"]),
        "run": public(run),
        "finished": finished,
    })


@app.route("/api/lifeline", methods=["POST"])
def api_lifeline():
    body = request.get_json(force=True) or {}
    kind = body.get("kind")
    qid = body.get("qid")
    run = run_state()
    pending = run.get("pending", {}).get(qid)
    if not pending or run["lifelines"].get(kind, 0) <= 0:
        return jsonify({"error": "Not available"}), 400
    run["lifelines"][kind] -= 1
    session.modified = True

    out = {"run": public(run)}
    if kind == "fifty":
        keys = body.get("keys") or []
        wrong = [k for k in keys if str(k) != str(pending["answer"])]
        random.shuffle(wrong)
        out["remove"] = wrong[:max(0, len(wrong) - 1)]
    elif kind == "peek":
        out["peek"] = world().summary_line(pending["subject"])
    return jsonify(out)


@app.route("/api/geo")
def api_geo():
    return jsonify(world().geojson)


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


@app.route("/api/restart", methods=["POST"])
def api_restart():
    body = request.get_json(force=True) or {}
    run = new_run(body.get("category", "grand_tour"), bool(body.get("endless")))
    return jsonify({"run": public(run)})


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

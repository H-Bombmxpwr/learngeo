"""General-knowledge study area. Original prompts; no runtime scraping or AI calls.

The one runtime lookup is /trivia/thumbs: a picture and a one-line description
from Wikipedia for names in the answer suggestions, cached on disk and never
needed for studying to work."""
import json
import gzip
import os
import threading
from functools import lru_cache
from pathlib import Path
import uuid

import requests
from flask import Blueprint, Response, jsonify, render_template, request

from . import store
from .trivia_bank import cards, TOPICS

trivia = Blueprint("trivia", __name__, url_prefix="/trivia")


@trivia.get("/")
def home():
    return render_template("trivia.html")


@trivia.get("/bank")
def bank():
    data = graph()
    if request.accept_encodings["gzip"] > 0:
        return compressed("bank")
    return jsonify(version=1, topics=TOPICS, cards=all_cards(),
                   manifest=data.get("manifest", {}), countries=dossiers())


# Progress is kept on the server, in progress.db on the deploy's volume, under
# the same anonymous player cookie as the geography wing's scores. The browser
# keeps a copy too, so studying still works offline; the client merges the two.
PLAYER_COOKIE = "learngeo_player"  # app.PLAYER_COOKIE
STATE_LIMIT = 8 * 1024 * 1024


def _player():
    pid = request.cookies.get(PLAYER_COOKIE)
    return pid if pid and 8 <= len(pid) <= 40 and pid.isalnum() else None


def _with_player(response, pid):
    response.set_cookie(PLAYER_COOKIE, pid, max_age=365 * 24 * 3600, samesite="Lax", httponly=True)
    return response


@trivia.get("/state")
def load_state():
    pid = _player() or uuid.uuid4().hex[:24]
    saved = store.studio_state(pid)
    response = Response(saved or "null", mimetype="application/json",
                        headers={"Cache-Control": "no-store"})
    return _with_player(response, pid)


@trivia.put("/state")
def save_state():
    pid = _player() or uuid.uuid4().hex[:24]
    if (request.content_length or 0) > STATE_LIMIT:
        return jsonify(error="Progress is larger than the server keeps."), 413
    data = request.get_json(silent=True)
    # The browser validates the detail (trivia-core.js validateBackup) on the
    # way back in; here only the shape is checked, so junk is not stored.
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("progress"), dict):
        return jsonify(error="Not a Commonplace v1 state."), 400
    store.save_studio_state(pid, json.dumps(data, separators=(",", ":")))
    return _with_player(jsonify(ok=True), pid)


@lru_cache(maxsize=1)
def graph():
    path = Path(__file__).resolve().parents[1] / "data" / "trivia_graph.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@lru_cache(maxsize=1)
def all_cards():
    """Curated cards, then the generated ones, each generated card carrying a
    Wikipedia article for every entity it is about -- the Wikidata link proves
    the fact, the article is what you actually want to read afterwards."""
    nodes = graph().get("entities", {})
    out = list(cards())
    for card in graph().get("cards", []):
        reading = [{"name": nodes[q]["name"], "url": nodes[q]["article"]}
                   for q in card.get("entities", []) if nodes.get(q, {}).get("article")]
        out.append(dict(card, reading=reading) if reading else card)
    return out


@trivia.get("/graph")
def graph_data():
    if request.accept_encodings["gzip"] > 0:
        return compressed("graph")
    return jsonify(entities=graph().get("entities", {}))


@lru_cache(maxsize=2)
def compressed_bytes(kind):
    data = graph()
    payload = {"entities": data.get("entities", {})} if kind == "graph" else {
        "version": 1, "topics": TOPICS, "cards": all_cards(),
        "manifest": data.get("manifest", {}), "countries": dossiers()}
    return gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def compressed(kind):
    return Response(compressed_bytes(kind), mimetype="application/json",
                    headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})


# The two halves meet at countries: a country is both a dossier in the
# geography wing and a node in the studio's graph, under the same Wikidata id.
@lru_cache(maxsize=1)
def dossiers():
    """Wikidata id -> the geography wing's country, for every country the
    studio's graph also knows, so a rabbit hole can open the dossier."""
    from .data import world
    nodes = graph().get("entities", {})
    return {c["qid"]: {"iso2": iso, "name": c["name"], "flag": c.get("flag_thumb", "")}
            for iso, c in world().countries.items() if c.get("qid") in nodes}


def connections(qid, per_topic=8):
    """What the studio's graph links to a country -- its mountains, rivers,
    dishes -- grouped by subject, best-known first. Empty when the country
    is not in the graph."""
    data = graph()
    node = data.get("entities", {}).get(qid)
    if not node:
        return []
    level = _card_levels()
    names = {t["id"]: t["name"] for t in TOPICS}
    groups = {}
    for link in node.get("links", []):
        for target in link["targets"]:
            other = data["entities"].get(target)
            if other:
                topic = other["topics"][0] if other.get("topics") else "geography"
                groups.setdefault(topic, {})[target] = (level.get(link.get("card"), 3), other["name"], other)
    out = []
    for topic, found in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        ranked = sorted(found.values(), key=lambda r: (r[0], r[1].lower()))
        out.append({"topic": names.get(topic, topic), "total": len(ranked),
                    "nodes": [{"id": n["id"], "name": n["name"], "description": n.get("description", "")}
                              for _, _, n in ranked[:per_topic]]})
    return out


@lru_cache(maxsize=1)
def _card_levels():
    return {c["id"]: c["level"] for c in graph().get("cards", [])}


# --------------------------------------------------------------------------
# Pictures for answer suggestions: Wikipedia page images, looked up by title.
# --------------------------------------------------------------------------

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_HEADERS = {"User-Agent": "CommonplaceStudy/1.0 (personal educational study app; thumbnails for answer suggestions)"}
THUMBS_MAX = 24
_thumbs = None
_thumbs_lock = threading.Lock()


def _thumbs_path():
    return Path(store.DATA_DIR) / "trivia-cache" / "wiki-thumbs.json"


def _thumb_cache():
    global _thumbs
    if _thumbs is None:
        try:
            _thumbs = json.loads(_thumbs_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _thumbs = {}
    return _thumbs


def fetch_thumbs(titles):
    """Title -> {"thumb", "description"} or None, straight from Wikipedia.
    Follows normalisation and redirects so "Cervantes" finds the page it
    points at. Raises on a network failure so nothing wrong gets cached."""
    response = requests.get(WIKI_API, headers=WIKI_HEADERS, timeout=6, params={
        "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
        "prop": "pageimages|description", "piprop": "thumbnail", "pithumbsize": "160",
        "titles": "|".join(titles)})
    response.raise_for_status()
    query = response.json().get("query", {})
    hop = {r["from"]: r["to"] for r in query.get("normalized", []) + query.get("redirects", [])}
    pages = {p["title"]: p for p in query.get("pages", []) if not p.get("missing")}
    out = {}
    for title in titles:
        name = title
        for _ in range(3):
            name = hop.get(name, name)
        page = pages.get(name)
        if page and (page.get("thumbnail") or page.get("description")):
            out[title] = {"thumb": page.get("thumbnail", {}).get("source", ""),
                          "description": page.get("description", "")[:160]}
        else:
            out[title] = None
    return out


@trivia.get("/thumbs")
def thumbs():
    wanted = []
    for title in request.args.getlist("t"):
        title = " ".join(title.split())[:200]
        if title and "|" not in title and title not in wanted:
            wanted.append(title)
    wanted = wanted[:THUMBS_MAX]
    cache = _thumb_cache()
    missing = [t for t in wanted if t not in cache]
    if missing and not os.environ.get("COMMONPLACE_OFFLINE"):
        try:
            found = fetch_thumbs(missing)
        except (requests.RequestException, ValueError, KeyError):
            found = {}
        if found:
            with _thumbs_lock:
                cache.update(found)
                try:
                    path = _thumbs_path()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                    tmp.replace(path)
                except OSError:
                    pass  # an unwritable disk only costs a repeat lookup
    response = jsonify({t: cache.get(t) for t in wanted})
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response

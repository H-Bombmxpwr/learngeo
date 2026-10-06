"""General-knowledge study area. Original prompts; no runtime scraping or AI calls."""
import json
import gzip
from functools import lru_cache
from pathlib import Path
import uuid
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

"""General-knowledge study area. Original prompts; no runtime scraping or AI calls."""
import json
import gzip
from functools import lru_cache
from pathlib import Path
from flask import Blueprint, Response, jsonify, render_template, request

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
    return jsonify(version=1, topics=TOPICS, cards=cards() + data.get("cards", []),
                   manifest=data.get("manifest", {}))


@lru_cache(maxsize=1)
def graph():
    path = Path(__file__).resolve().parents[1] / "data" / "trivia_graph.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@trivia.get("/graph")
def graph_data():
    if request.accept_encodings["gzip"] > 0:
        return compressed("graph")
    return jsonify(entities=graph().get("entities", {}))


@lru_cache(maxsize=2)
def compressed_bytes(kind):
    data = graph()
    payload = {"entities": data.get("entities", {})} if kind == "graph" else {
        "version": 1, "topics": TOPICS, "cards": cards() + data.get("cards", []),
        "manifest": data.get("manifest", {})}
    return gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def compressed(kind):
    return Response(compressed_bytes(kind), mimetype="application/json",
                    headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})

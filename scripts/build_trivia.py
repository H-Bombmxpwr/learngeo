"""Build an offline CC0 trivia graph from bounded Wikidata queries.

    .venv/Scripts/python scripts/build_trivia.py --limit 1000

Completed slices are cached; rerunning resumes. --refresh replaces the cache.
The app never calls the network. Only named entity relationships become cards.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "trivia-cache"
OUTPUT = ROOT / "data" / "trivia_graph.json"
ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "CommonplaceStudy/1.0 (personal educational CC0 dataset builder; Python requests)",
           "Accept": "application/sparql-results+json"}
# slice, topic, class, property, relationship, prompt, minimum sitelinks
SLICES = [
    ("novels", "literature", "Q8261", "P50", "author", "Name an author of {name}.", 8),
    ("plays", "literature", "Q25379", "P50", "author", "Who wrote the play {name}?", 5),
    ("poems", "literature", "Q482", "P50", "author", "Name a poet credited with {name}.", 4),
    ("paintings", "art", "Q3305213", "P170", "creator", "Name an artist credited with the painting {name}.", 5),
    ("sculptures", "art", "Q860861", "P170", "creator", "Name a sculptor credited with {name}.", 4),
    ("operas", "music", "Q1344", "P86", "composer", "Name a composer of the opera {name}.", 5),
    ("albums", "music", "Q482994", "P175", "performer", "Name a credited performer on the album {name}.", 10),
    ("films", "screen", "Q11424", "P57", "director", "Name a director of the film {name}.", 15),
    ("television", "screen", "Q5398426", "P170", "creator", "Name a creator of the television series {name}.", 10),
    ("elements", "science", "Q11344", "P61", "discoverer", "Name a person credited with discovering the element {name}.", 10),
    ("moons", "science", "Q2537", "P397", "parent body", "Which celestial body does {name} orbit?", 8),
    ("mountains", "geography", "Q8502", "P17", "country", "Name a country in which the mountain {name} is located.", 10),
    ("rivers", "geography", "Q4022", "P403", "mouth", "Into which named body of water does the river {name} flow?", 10),
    ("battles", "history", "Q178561", "P361", "part of", "Name a conflict or campaign of which {name} was a part.", 8),
    ("inventions", "technology", "Q184197", "P61", "inventor or discoverer", "Name an inventor or discoverer credited with {name}.", 5),
    ("cheeses", "food", "Q10943", "P495", "country of origin", "Name a country associated with the origin of {name} cheese.", 5),
    ("dishes", "food", "Q746549", "P495", "country of origin", "Name a country associated with the origin of the dish {name}.", 8),
    ("languages", "words", "Q34770", "P282", "writing system", "Name a writing system used for {name}.", 15),
    ("deities", "mythology", "Q178885", "P361", "mythological grouping", "Name a mythological grouping or tradition to which {name} belongs.", 8),
    ("sports-events", "sport", "Q16510064", "P641", "sport", "Which sport is contested in {name}?", 8),
    ("programming", "technology", "Q9143", "P178", "developer", "Name a developer credited with the programming language {name}.", 10),
    ("film-adaptations", "screen", "Q11424", "P144", "based on", "Name a work or source on which the film {name} is based.", 15),
    ("art-movements", "art", "Q3305213", "P135", "movement", "Name an art movement associated with the painting {name}.", 5),
    ("literary-genres", "literature", "Q8261", "P136", "genre", "Name a literary genre associated with {name}.", 8),
]


def query(spec, items):
    _, _, cls, prop, *_rest, minimum = spec
    values = " ".join("wd:" + qid(item["item"]["value"]) for item in items)
    return f'''SELECT ?item ?itemLabel ?itemDescription ?object ?objectLabel
        ?objectDescription ?article ?links ?objectAlias WHERE {{
      hint:Query hint:optimizer "None".
      VALUES ?item {{ {values} }}
      ?item wikibase:sitelinks ?links.
      ?item wdt:{prop} ?object.
      ?item rdfs:label ?itemLabel. FILTER(LANG(?itemLabel) = "en")
      ?object rdfs:label ?objectLabel. FILTER(LANG(?objectLabel) = "en")
      OPTIONAL {{ ?item schema:description ?itemDescription. FILTER(LANG(?itemDescription) = "en") }}
      OPTIONAL {{ ?object schema:description ?objectDescription. FILTER(LANG(?objectDescription) = "en") }}
      OPTIONAL {{ ?object skos:altLabel ?objectAlias. FILTER(LANG(?objectAlias) = "en") }}
      OPTIONAL {{ ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }}
    }}'''


def fetch(spec, limit, refresh=False, offline=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    revision = "-satellite-v4" if spec[0] == "moons" else "-form-v2" if spec[2] in {"Q8261", "Q25379", "Q482", "Q1344"} else ""
    path = CACHE / f"{spec[0]}-{limit}{revision}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        # A changed classifier can still reuse the last complete snapshot while
        # offline. Its original retrieval timestamp remains visible in the manifest.
        candidates = sorted((p for p in CACHE.glob(f"{spec[0]}-{limit}*.json")
                             if "-batch-" not in p.name), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return {**json.loads(candidates[0].read_text(encoding="utf-8")), "fallback_cache": candidates[0].name}
        raise FileNotFoundError("No completed cached slice: " + spec[0])
    def run(sparql):
        for attempt in range(3):
            try:
                response = requests.get(ENDPOINT, params={"query": sparql, "format": "json"},
                                        headers=HEADERS, timeout=65)
                response.raise_for_status()
                return response.json()["results"]["bindings"]
            except (requests.RequestException, ValueError, KeyError) as exc:
                print(f"  attempt {attempt + 1}: {exc}", flush=True)
                if attempt == 2:
                    raise
                time.sleep(min(10 * (attempt + 1), 30))
    # Separate candidate discovery from label/alias joins. This bounds the expensive
    # multilingual joins and avoids a query planner explosion in the monolithic query.
    classifier = "wdt:P31/wdt:P279*" if spec[0] == "moons" else "(wdt:P31|wdt:P7937)" if revision else "wdt:P31"
    candidates = run(f'''SELECT DISTINCT ?item ?links WHERE {{
      hint:Query hint:optimizer "None".
      ?item {classifier} wd:{spec[2]}.
      ?item wikibase:sitelinks ?links. FILTER(?links >= {spec[-1]})
    }} ORDER BY DESC(?links) ?item LIMIT {limit}''')
    print(f"  {len(candidates)} candidates", flush=True)
    rows = []
    for start in range(0, len(candidates), 60):
        batch_path = CACHE / f"{spec[0]}-{limit}{revision}-batch-{start}.json"
        if batch_path.exists() and not refresh:
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
        else:
            batch = run(query(spec, candidates[start:start + 60]))
            batch_path.write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
            time.sleep(.5)
        rows.extend(batch)
    payload = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "rows": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def qid(value):
    return value.rsplit("/", 1)[-1]


def build(slices):
    entities, grouped, dates = {}, {}, {}
    for spec, payload in slices:
        key, topic, _cls, prop, relation, template, _minimum = spec
        dates[key] = payload["retrieved_at"]
        for row in payload["rows"]:
            v = {k: val["value"] for k, val in row.items()}
            a, b = qid(v["item"]), qid(v["object"])
            if not re.fullmatch(r"Q\d+", a) or not re.fullmatch(r"Q\d+", b):
                continue
            name, answer = v["itemLabel"].strip(), v["objectLabel"].strip()
            if name.casefold() == answer.casefold() or len(name) > 180 or len(answer) > 100:
                continue
            for ident, label, description in [(a, name, v.get("itemDescription", "")),
                                               (b, answer, v.get("objectDescription", ""))]:
                entity = entities.setdefault(ident, {"id": ident, "name": label,
                    "description": description, "topics": [], "aliases": [], "links": []})
                if topic not in entity["topics"]:
                    entity["topics"].append(topic)
            if v.get("article"):
                entities[a]["article"] = v["article"]
            alias = v.get("objectAlias", "").strip()
            if alias and len(alias) <= 100 and alias not in entities[b]["aliases"]:
                entities[b]["aliases"].append(alias)
            group = grouped.setdefault((a, prop), {"topic": topic, "template": template,
                "relation": relation, "objects": set(), "popularity": int(v["links"]), "slice": key})
            group["objects"].add(b)
    result = []
    for (a, prop), group in grouped.items():
        answers = sorted(group["objects"])
        subject = entities[a]
        names = [entities[b]["name"] for b in answers]
        # A film and its source book often share a title. Keep that useful graph edge
        # even though the forward question would give its answer away.
        usable = len(answers) <= 6 and not any(name.casefold() in subject["name"].casefold() for name in names)
        card_id = f"wd-{a}-{prop}" if usable else None
        edge_source = f"https://www.wikidata.org/wiki/{a}#{prop}"
        subject["links"].append({"relation": group["relation"], "targets": answers,
                                  "card": card_id, "source": edge_source})
        inverse = {"author": "wrote", "creator": "created", "composer": "composed",
                   "performer": "performed on", "director": "directed", "discoverer": "discovered",
                   "parent body": "orbited by", "country": "contains", "mouth": "receives this river",
                   "part of": "includes", "inventor or discoverer": "invented or discovered",
                   "country of origin": "associated foods", "writing system": "used to write",
                   "mythological grouping": "includes", "sport": "contested at", "developer": "developed",
                   "based on": "adapted into", "movement": "associated works", "genre": "works in this genre"}
        for b in answers:
            entities[b]["links"].append({"relation": inverse[group["relation"]], "targets": [a],
                                          "card": card_id, "source": edge_source})
        if not usable:
            continue
        prompt = group["template"].format(name=subject["name"])
        if len(answers) > 1 and not prompt.startswith("Name "):
            prompt = f"Name one {group['relation']} associated with {subject['name']}."
        aliases = sorted({alias for b in answers for alias in
                          [entities[b]["name"], *entities[b]["aliases"]]})
        # Full names and explicit Wikidata aliases are accepted. No broad fuzzy matching.
        explanation = f"{subject['name']} → {group['relation']} → {'; '.join(names)}."
        if subject["description"]:
            explanation += " About the subject: " + subject["description"] + "."
        target_desc = entities[answers[0]]["description"]
        if target_desc:
            explanation += f" {names[0]}: {target_desc}."
        result.append({"id": card_id, "topic": group["topic"],
            "level": 1 if group["popularity"] >= 65 else 2 if group["popularity"] >= 25 else 3,
            "prompt": prompt, "answer": " / ".join(names), "aliases": aliases,
            "explanation": explanation, "hook": f"Connect {subject['name']} with {'; '.join(names)}.",
            "source": f"https://www.wikidata.org/wiki/{a}#{prop}",
            "source_label": f"Wikidata · {a} / {prop}", "generated": True,
            "entities": [a, *answers], "relation": group["relation"], "slice": group["slice"]})
    used = {ident for ident, node in entities.items() if node["links"]}
    return {"version": 1, "manifest": {
        "source": "Wikidata", "license": "CC0-1.0", "license_url": "https://www.wikidata.org/wiki/Wikidata:Licensing",
        "built_at": datetime.now(timezone.utc).isoformat(), "slice_dates": dates,
        "cards": len(result), "entities": len(used), "topics": dict(Counter(c["topic"] for c in result)),
        "note": "Generated from community-maintained structured data. Difficulty estimates use sitelink counts; facts are not individually human-verified.",
        "empty_slices": [spec[0] for spec, payload in slices if not payload["rows"]]},
        "cards": result, "entities": {k: v for k, v in entities.items() if k in used}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--slices", nargs="*")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Rebuild using completed local snapshots only")
    parser.add_argument("--diagnose", action="store_true", help="Inspect literary classifications with a small query")
    args = parser.parse_args()
    if args.diagnose:
        sparql = '''SELECT ?item ?itemLabel ?kind ?kindLabel ?genre ?genreLabel WHERE {
          VALUES ?item { wd:Q174596 wd:Q131252 wd:Q208460 wd:Q8337 wd:Q483732 }
          OPTIONAL { ?item wdt:P31 ?kind. }
          OPTIONAL { ?item wdt:P136 ?genre. }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }'''
        response = requests.get(ENDPOINT, params={"query": sparql, "format": "json"}, headers=HEADERS, timeout=30)
        response.raise_for_status()
        for row in response.json()["results"]["bindings"]:
            print({k: v["value"] for k, v in row.items()}, flush=True)
        return
    if not 1 <= args.limit <= 3000:
        parser.error("--limit must be between 1 and 3000")
    selected = [s for s in SLICES if not args.slices or s[0] in args.slices]
    if not selected:
        parser.error("No matching slices")
    collected, failures = [], []
    for spec in selected:
        print("Fetching " + spec[0], flush=True)
        try:
            payload = fetch(spec, args.limit, args.refresh, args.offline)
            collected.append((spec, payload))
            print(f"  {len(payload['rows'])} bindings", flush=True)
        except (requests.RequestException, ValueError, KeyError, FileNotFoundError) as exc:
            failures.append(spec[0])
            print(f"  FAILED: {exc}", flush=True)
    data = build(collected)
    data["manifest"]["failed_slices"] = failures
    # A partial refresh must never replace a larger valid dataset.
    old_count = 0
    if OUTPUT.exists():
        old_count = len(json.loads(OUTPUT.read_text(encoding="utf-8"))["cards"])
    if not data["cards"] or len(data["cards"]) < old_count:
        raise SystemExit(f"Kept existing dataset: built {len(data['cards'])}, existing {old_count}")
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temp.replace(OUTPUT)
    print(json.dumps(data["manifest"], indent=2), flush=True)


if __name__ == "__main__":
    main()

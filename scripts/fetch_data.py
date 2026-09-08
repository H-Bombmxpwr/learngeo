"""Build the LearnGeo dataset from Wikidata + Wikipedia.

Run once (takes roughly 5-10 minutes):

    python scripts/fetch_data.py

Writes data/countries.json, which the Flask app loads at startup. Nothing in
here runs at request time, so once this has finished the app works offline.
Re-run it whenever you want fresh leaders or populations.
"""
import json
import os
import re
import sys
import time

import requests

UA = "LearnGeoQuiz/1.0 (personal learning project)"
SPARQL_URL = "https://query.wikidata.org/sparql"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "countries.json")

S = requests.Session()
S.headers.update({"User-Agent": UA})

# Wikidata's sovereign-state definition, reused by every query. P31 = instance
# of, Q3624078 = sovereign state; P576 = dissolved, which excludes states that
# no longer exist (USSR, Yugoslavia and friends).
# Denmark (Q35) and Vatican City (Q237) are not typed as "sovereign state" in
# Wikidata -- Denmark is a constituent country of the Kingdom of Denmark, and
# the Vatican is modelled separately from the Holy See -- so both fell out of
# the country list entirely. They are added back by hand.
BASE = """
  { ?c wdt:P31 wd:Q3624078 } UNION { VALUES ?c { wd:Q35 wd:Q237 } }
  ?c wdt:P297 ?iso2 .
  FILTER NOT EXISTS { ?c wdt:P576 ?dissolved }
"""


def sparql(query, tries=4):
    last = None
    for i in range(tries):
        try:
            r = S.get(SPARQL_URL, params={"query": query},
                      headers={"Accept": "application/sparql-results+json"},
                      timeout=240)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            last = "HTTP %s: %s" % (r.status_code, r.text[:180])
        except Exception as e:          # network hiccup or read timeout
            last = repr(e)
        time.sleep(6 * (i + 1))
    raise RuntimeError("SPARQL failed after %d tries: %s" % (tries, last))


def v(b, k, d=None):
    return b[k]["value"] if k in b else d


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def iso_values(isos):
    return " ".join('"%s"' % i for i in isos)


def en_label(var, out):
    # Explicit rdfs:label rather than the label service: the service silently
    # leaves Q-ids unresolved inside subqueries that use ORDER BY / LIMIT.
    return '?%s rdfs:label ?%s . FILTER(LANG(?%s) = "en")' % (var, out, out)


# --------------------------------------------------------------------------
# Individual fetches. Each merges into the same {iso2: {...}} dict.
# --------------------------------------------------------------------------

def fetch_core():
    print("[1/9] core facts")
    q = """
SELECT ?iso2 (SAMPLE(?iso3) AS ?a_iso3) (SAMPLE(?nm) AS ?a_nm) (SAMPLE(?qid) AS ?a_qid)
       (MAX(?pop) AS ?a_pop) (SAMPLE(?area) AS ?a_area) (SAMPLE(?coord) AS ?a_coord)
       (SAMPLE(?emoji) AS ?a_emoji) (SAMPLE(?locmap) AS ?a_locmap)
       (SAMPLE(?drive) AS ?a_drive) (SAMPLE(?call) AS ?a_call) (SAMPLE(?born) AS ?a_born)
       (SAMPLE(?wp) AS ?a_wp)
WHERE {
  %s
  BIND(STRAFTER(STR(?c), "entity/") AS ?qid)
  OPTIONAL { ?c wdt:P298 ?iso3 }
  OPTIONAL { ?c rdfs:label ?nm FILTER(LANG(?nm) = "en") }
  OPTIONAL { ?c wdt:P1082 ?pop }
  OPTIONAL { ?c wdt:P2046 ?area }
  OPTIONAL { ?c wdt:P625 ?coord }
  OPTIONAL { ?c wdt:P487 ?emoji }
  OPTIONAL { ?c wdt:P242 ?locmap }
  OPTIONAL { ?c wdt:P1622 ?d . ?d rdfs:label ?drive FILTER(LANG(?drive) = "en") }
  OPTIONAL { ?c wdt:P474 ?call }
  OPTIONAL { ?c wdt:P571 ?born }
  OPTIONAL { ?wp schema:about ?c ; schema:isPartOf <https://en.wikipedia.org/> }
}
GROUP BY ?iso2
""" % BASE
    out = {}
    for b in sparql(q):
        iso = v(b, "iso2")
        lat = lon = None
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", v(b, "a_coord") or "")
        if m:
            lon, lat = float(m.group(1)), float(m.group(2))
        out[iso] = {
            "iso2": iso,
            "iso3": v(b, "a_iso3"),
            "name": v(b, "a_nm"),
            "qid": v(b, "a_qid"),
            "population": int(float(v(b, "a_pop"))) if v(b, "a_pop") else None,
            "area": float(v(b, "a_area")) if v(b, "a_area") else None,
            "lat": lat,
            "lon": lon,
            "flag_emoji": v(b, "a_emoji"),
            "locator_map": v(b, "a_locmap"),
            "drives_on": v(b, "a_drive"),
            "calling_code": v(b, "a_call"),
            "founded": (v(b, "a_born") or "")[:4] or None,
            "wiki_url": v(b, "a_wp"),
        }
    print("      %d sovereign states" % len(out))
    return out


# Everything the app can link to is stored as an "entity", not a bare string:
# a name, its Wikidata QID and its English Wikipedia URL, plus the years the
# statement applied where that matters. That is what lets a language, a war or
# a form of government become its own page listing every country involved.

ENTITY_Q = """
SELECT ?iso2 ?lbl ?qid ?wp ?start ?ended WHERE {
  %s
  %s
  BIND(STRAFTER(STR(?o), "entity/") AS ?qid)
  OPTIONAL { ?wp schema:about ?o ; schema:isPartOf <https://en.wikipedia.org/> }
  %s
  OPTIONAL { ?st pq:P580 ?start }
  OPTIONAL { ?st pq:P582 ?ended }
}
"""


def fetch_entities(countries, prop, key, cap=None, current_only=False,
                   with_time=False):
    stmt = "?c p:%s ?st . ?st ps:%s ?o ." % (prop, prop)
    if current_only:
        stmt += " FILTER NOT EXISTS { ?st pq:P582 ?e }"
    q = ENTITY_Q % (BASE, stmt, en_label("o", "lbl"))
    for b in sparql(q):
        iso = v(b, "iso2")
        if iso not in countries:
            continue
        bucket = countries[iso].setdefault(key, [])
        name = v(b, "lbl")
        if not name:
            continue
        entry = {"name": name, "qid": v(b, "qid"), "wiki": v(b, "wp")}
        if with_time:
            entry["start"] = (v(b, "start") or "")[:4] or None
            entry["end"] = (v(b, "ended") or "")[:4] or None
        already = any(x["name"] == name and
                      (not with_time or x.get("start") == entry.get("start"))
                      for x in bucket)
        if not already and (cap is None or len(bucket) < cap):
            bucket.append(entry)
    return countries


def fetch_capitals(countries):
    print("[2/9] capitals")
    return fetch_entities(countries, "P36", "capitals", cap=3, current_only=True)


def fetch_politics(countries):
    print("[3/9] currencies, government, continent, religion, memberships")
    fetch_entities(countries, "P37", "official_languages", cap=5)
    fetch_entities(countries, "P38", "currencies", cap=3, current_only=True)
    # Government keeps its dates: that is the timeline on the topic page.
    fetch_entities(countries, "P122", "government", cap=8, with_time=True)
    fetch_entities(countries, "P30", "continents", cap=3)
    fetch_entities(countries, "P140", "religions", cap=5)
    fetch_entities(countries, "P463", "member_of", cap=40)
    fetch_entities(countries, "P610", "highest_point", cap=1)
    return countries


# GeoNames files New York's boroughs as PPLA2, the same feature code it gives
# Los Angeles, because each is a county seat. Nothing in the data separates
# them from real cities, so they are named here: without this the five largest
# US cities come back as New York, Los Angeles, Brooklyn, Chicago, Queens.
NOT_REALLY_CITIES = {
    ("US", "Brooklyn"), ("US", "Queens"), ("US", "Manhattan"),
    ("US", "The Bronx"), ("US", "Bronx"), ("US", "Staten Island"),
}


def fetch_cities(countries):
    """Five largest cities per country, from GeoNames.

    Wikidata cannot do this: asking it for a country's cities by population
    either times out or, with an optimizer hint, quietly returns the wrong
    ones (France came back led by Angers, with Paris missing). GeoNames
    publishes a 3MB dump of every city over 15,000 people, keyed by ISO2, which
    is both faster and correct."""
    print("[4c/9] largest cities")
    import io as _io
    import zipfile
    url = "https://download.geonames.org/export/dump/cities15000.zip"
    cache = os.path.join(ROOT, "data", "cities15000.zip")
    if not os.path.exists(cache):
        r = S.get(url, timeout=120)
        r.raise_for_status()
        with open(cache, "wb") as f:
            f.write(r.content)
    biggest = {}
    with zipfile.ZipFile(cache) as z:
        raw = z.read("cities15000.txt").decode("utf-8")
    for line in raw.splitlines():
        parts = line.split("	")
        if len(parts) < 15:
            continue
        name, feature, iso2, pop = parts[1], parts[7], parts[8], parts[14]
        if feature == "PPLX" or iso2 not in countries or not pop.isdigit():
            continue
        if (iso2, name) in NOT_REALLY_CITIES:
            continue
        biggest.setdefault(iso2, []).append((int(pop), name))
    for iso, c in countries.items():
        rows = sorted(biggest.get(iso, []), reverse=True)[:5]
        c["cities"] = [{"name": n, "population": p,
                        "wiki": "https://en.wikipedia.org/wiki/" + n.replace(" ", "_")}
                       for p, n in rows]
    print("      %d countries have cities" % sum(1 for c in countries.values() if c.get("cities")))
    return countries


def fetch_wars(countries):
    """Wars and armed conflicts the country took part in, most notable first.

    Q198 is 'war'; the subclass walk picks up civil wars, invasions and the
    like. P710 is 'participant'."""
    print("[4b/9] wars and conflicts")
    isos = sorted(countries)
    for n, iso in enumerate(isos):
        q = """
SELECT ?lbl ?qid ?wp ?start ?ended ?sl WHERE {
  ?c wdt:P297 "%s" .
  ?war wdt:P31/wdt:P279* wd:Q198 ; wdt:P710 ?c ; wikibase:sitelinks ?sl .
  BIND(STRAFTER(STR(?war), "entity/") AS ?qid)
  OPTIONAL { ?wp schema:about ?war ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?war wdt:P580 ?start }
  OPTIONAL { ?war wdt:P582 ?ended }
  %s
}
ORDER BY DESC(?sl)
LIMIT 40
""" % (iso, en_label("war", "lbl"))
        try:
            rows = sparql(q, tries=2)
        except RuntimeError:
            print("      %s failed, skipping" % iso)
            rows = []
        seen = {}
        for b in rows:
            name = v(b, "lbl")
            if not name or name in seen:
                continue
            seen[name] = {
                "name": name, "qid": v(b, "qid"), "wiki": v(b, "wp"),
                "start": (v(b, "start") or "")[:4] or None,
                "end": (v(b, "ended") or "")[:4] or None,
                "fame": int(v(b, "sl", "0")),
            }
        countries[iso]["wars"] = sorted(seen.values(), key=lambda x: -x["fame"])[:12]
        if n and n % 25 == 0:
            print("      %d/%d" % (n, len(isos)))
            save_progress(countries)
    return countries


# Wikidata's P47 "shares border with" counts MARITIME boundaries, which is why
# the United States came back bordering Japan, Tonga and the Marshall Islands.
# Every candidate pair is checked against the real polygons: outlines within
# ~2km of each other share land, the rest do not. Verified against 14 known
# pairs, including US-Russia across the Bering Strait (correctly rejected).
BORDER_TOLERANCE_DEG = 0.02      # ~2 km

# The 28 countries with no polygon in countries.geo.json cannot be checked
# geometrically. Almost all are islands with no land border at all; these five
# are the exceptions, so they are stated outright rather than guessed.
MICROSTATE_BORDERS = {
    "AD": ["ES", "FR"],
    "VA": ["IT"],
    "MC": ["FR"],
    "SM": ["IT"],
    "LI": ["CH", "AT"],
    "XK": ["MK", "AL", "ME", "RS"],
}


def _load_shapes():
    from shapely.geometry import shape
    path = os.path.join(ROOT, "data", "countries.geo.json")
    with open(path, encoding="utf-8") as f:
        geo = json.load(f)
    return {f["id"]: shape(f["geometry"]) for f in geo["features"] if f.get("id")}


def fetch_borders(countries):
    print("[4/9] land borders")
    q = """
SELECT ?iso2 ?niso WHERE {
  %s
  ?c p:P47 ?st . ?st ps:P47 ?n .
  FILTER NOT EXISTS { ?st pq:P582 ?e }
  ?n wdt:P297 ?niso .
}
""" % BASE
    candidates = {}
    for b in sparql(q):
        iso, niso = v(b, "iso2"), v(b, "niso")
        if iso not in countries or niso == iso:
            continue
        candidates.setdefault(iso, set()).add(niso)
    # P47 is not symmetric in Wikidata; make it so before filtering.
    for iso, ns in list(candidates.items()):
        for n in ns:
            if n in countries:
                candidates.setdefault(n, set()).add(iso)

    shapes = _load_shapes()
    kept = dropped = 0
    for iso, c in countries.items():
        if iso in MICROSTATE_BORDERS:
            c["borders"] = [x for x in MICROSTATE_BORDERS[iso] if x in countries]
            continue
        mine = shapes.get(c.get("iso3"))
        if mine is None:
            # No polygon and not a known exception: an island with no land border.
            c["borders"] = []
            continue
        real = []
        for n in sorted(candidates.get(iso, ())):
            if n in MICROSTATE_BORDERS:
                if iso in MICROSTATE_BORDERS[n]:
                    real.append(n)
                continue
            theirs = shapes.get((countries.get(n) or {}).get("iso3"))
            if theirs is None:
                dropped += 1
                continue
            if mine.distance(theirs) < BORDER_TOLERANCE_DEG:
                real.append(n)
                kept += 1
            else:
                dropped += 1
        c["borders"] = real
    # Re-symmetrise after filtering, so "does X border Y" never contradicts itself.
    for iso, c in countries.items():
        for n in list(c["borders"]):
            if n in countries and iso not in countries[n]["borders"]:
                countries[n]["borders"].append(iso)
    for c in countries.values():
        c["borders"].sort()
    print("      kept %d land borders, dropped %d maritime ones" % (kept, dropped))
    return countries


def fetch_languages(countries):
    """Most-spoken languages, ranked by speakers inside that country.

    P37 (official language) was wrong for this: the United States has no
    federal official language, so Wikidata returned Hawaiian, Samoan and
    Chamorro and no English at all. P2936 ("language used") carries a
    'number of speakers' qualifier, which is what people actually mean by
    'most spoken'."""
    print("[3b/9] most-spoken languages")
    isos = sorted(countries)
    for n, iso in enumerate(isos):
        q = """
SELECT ?llbl ?qid ?wp ?num WHERE {
  ?c wdt:P297 "%s" .
  ?c p:P2936 ?st . ?st ps:P2936 ?lang .
  BIND(STRAFTER(STR(?lang), "entity/") AS ?qid)
  OPTIONAL { ?wp schema:about ?lang ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?st pq:P1098 ?num }
  %s
}
LIMIT 400
""" % (iso, en_label("lang", "llbl"))
        try:
            rows = sparql(q, tries=2)
        except RuntimeError:
            print("      %s failed, skipping" % iso)
            rows = []
        best = {}
        for b in rows:
            name = v(b, "llbl")
            if not name:
                continue
            num = v(b, "num")
            num = int(float(num)) if num else None
            # A language can be listed several times with counts from different
            # censuses; keep the largest.
            if name not in best or (num or 0) > (best[name]["speakers"] or 0):
                best[name] = {"name": name, "qid": v(b, "qid"),
                              "wiki": v(b, "wp"), "speakers": num}
        counted = [x for x in best.values() if x["speakers"]]
        counted.sort(key=lambda x: -x["speakers"])
        if counted:
            langs = counted[:3]
        else:
            # No speaker counts recorded: fall back to the official languages.
            langs = [dict(x, speakers=None)
                     for x in (countries[iso].get("official_languages") or [])[:3]]
        countries[iso]["languages"] = langs
        if n and n % 25 == 0:
            print("      %d/%d" % (n, len(isos)))
            save_progress(countries)
    return countries


# The person queries need care. Two things bite:
#
#  * "current leader" cannot be expressed as "statement has no end date" --
#    Wikidata often records a scheduled end for a sitting president, so France
#    came back empty. Instead pull every P35/P6 statement and decide in Python
#    by comparing the end date to today.
#  * Asking for the citizens of a large country makes Blazegraph pick a plan
#    that scans every human first and times out (504). The optimizer hint below
#    forces country -> citizen -> image -> sitelinks, which returns in seconds.

TODAY = time.strftime("%Y-%m-%d")
HINT = "PREFIX hint: <http://www.bigdata.com/queryHints#>"


def _leader_statements(iso, prop):
    q = """
SELECT ?plbl ?img ?start ?ended ?sl WHERE {
  ?c wdt:P297 "%s" .
  ?c p:%s ?st . ?st ps:%s ?person .
  ?person wikibase:sitelinks ?sl .
  %s
  OPTIONAL { ?person wdt:P18 ?img }
  OPTIONAL { ?st pq:P580 ?start }
  OPTIONAL { ?st pq:P582 ?ended }
}
LIMIT 120
""" % (iso, prop, prop, en_label("person", "plbl"))
    return sparql(q, tries=2)


def fetch_leaders(countries):
    print("[5/9] leaders, current and past")
    isos = sorted(countries)
    for n, iso in enumerate(isos):
        current, past = [], []
        for prop, role in (("P35", "head_of_state"), ("P6", "head_of_government")):
            try:
                rows = _leader_statements(iso, prop)
            except RuntimeError:
                print("      %s %s failed, skipping" % (iso, prop))
                continue
            for b in rows:
                name = v(b, "plbl")
                if not name:
                    continue
                ended = v(b, "ended")
                entry = {
                    "name": name,
                    "role": role,
                    "image": v(b, "img"),
                    "start": (v(b, "start") or "")[:4] or None,
                    "end": (ended or "")[:4] or None,
                    "fame": int(v(b, "sl", "0")),
                }
                # Still in office if there is no end date, or it has not
                # arrived yet.
                bucket = current if (not ended or ended[:10] > TODAY) else past
                dup = any(x["name"] == entry["name"] and x["role"] == role
                          and x["start"] == entry["start"] for x in bucket)
                if not dup:
                    bucket.append(entry)
        current.sort(key=lambda x: -(x["fame"]))
        past.sort(key=lambda x: (-x["fame"], x["name"]))
        countries[iso]["leaders"] = current[:4]
        countries[iso]["past_leaders"] = past[:12]
        if n and n % 25 == 0:
            print("      %d/%d" % (n, len(isos)))
            save_progress(countries)
    return countries


def fetch_famous(countries):
    print("[7/9] famous people")
    isos = sorted(countries)
    for n, iso in enumerate(isos):
        # No ORDER BY: sorting the whole citizen set is what times out. Pull a
        # generous unordered slice above a fame floor and rank it here.
        q = """%s
SELECT ?plbl ?img ?occlbl ?born ?died ?sl WHERE {
  hint:Query hint:optimizer "None" .
  ?c wdt:P297 "%s" .
  ?person wdt:P27 ?c .
  ?person wdt:P18 ?img .
  ?person wikibase:sitelinks ?sl .
  FILTER(?sl > 90)
  %s
  OPTIONAL { ?person wdt:P106 ?occ . %s }
  OPTIONAL { ?person wdt:P569 ?born }
  OPTIONAL { ?person wdt:P570 ?died }
}
LIMIT 400
""" % (HINT, iso, en_label("person", "plbl"), en_label("occ", "occlbl"))
        try:
            rows = sparql(q, tries=2)
        except RuntimeError:
            print("      %s failed, skipping" % iso)
            rows = []
        seen = {}
        for b in rows:
            nm = v(b, "plbl")
            if not nm:
                continue
            if nm not in seen:
                seen[nm] = {
                    "name": nm,
                    "image": v(b, "img"),
                    "occupations": [],
                    "born": (v(b, "born") or "")[:4] or None,
                    "died": (v(b, "died") or "")[:4] or None,
                    "fame": int(v(b, "sl", "0")),
                }
            occ = v(b, "occlbl")
            if occ and len(seen[nm]["occupations"]) < 4 and occ not in seen[nm]["occupations"]:
                seen[nm]["occupations"].append(occ)
        countries[iso]["famous"] = sorted(seen.values(), key=lambda x: -x["fame"])[:14]
        if n and n % 25 == 0:
            print("      %d/%d" % (n, len(isos)))
            save_progress(countries)
    return countries


def fetch_wikipedia(countries):
    print("[8/9] Wikipedia blurbs (this is the slow one)")
    items = sorted(countries.items())
    for i, (iso, c) in enumerate(items):
        if not c.get("name"):
            continue
        for title, field in ((c["name"], "summary"),
                             ("Climate of " + c["name"], "climate_text")):
            try:
                r = S.get(WIKI_SUMMARY + title.replace(" ", "_"), timeout=25)
                if r.status_code != 200:
                    continue
                d = r.json()
                if "disambiguation" in (d.get("type") or ""):
                    continue
                text = d.get("extract")
                if text:
                    c[field] = text
                if field == "summary":
                    urls = d.get("content_urls") or {}
                    c["wiki_url"] = (urls.get("desktop") or {}).get("page")
            except Exception:
                pass
            time.sleep(0.1)
        if i and i % 25 == 0:
            print("      %d/%d" % (i, len(items)))
            save_progress(countries)
    return countries


# --------------------------------------------------------------------------
# Derived fields the quiz needs but no single Wikidata property provides.
# --------------------------------------------------------------------------

# Latitude bands give a defensible first-order climate zone. A handful of
# countries are famous exceptions (deserts astride temperate latitudes,
# highland climates on the equator), so those are named explicitly.
CLIMATE_OVERRIDES = {
    "EG": "Desert", "LY": "Desert", "DZ": "Desert", "SA": "Desert",
    "AE": "Desert", "QA": "Desert", "KW": "Desert", "BH": "Desert",
    "OM": "Desert", "MR": "Desert", "TD": "Desert", "NE": "Desert",
    "ML": "Desert", "SD": "Desert", "TM": "Desert", "UZ": "Desert",
    "MN": "Cold desert / steppe", "KZ": "Cold desert / steppe",
    "IS": "Subpolar oceanic", "GL": "Polar", "NO": "Subpolar to temperate",
    "NP": "Highland / alpine", "BT": "Highland / alpine", "CH": "Alpine temperate",
    "BO": "Highland / alpine", "PE": "Highland to desert coast",
    "CL": "Everything from desert to polar", "ES": "Mediterranean",
    "IT": "Mediterranean", "GR": "Mediterranean", "PT": "Mediterranean",
    "TR": "Mediterranean to continental", "MA": "Mediterranean to desert",
    "AU": "Mostly arid, temperate south", "IN": "Tropical monsoon",
    "BD": "Tropical monsoon", "VN": "Tropical monsoon", "TH": "Tropical monsoon",
    "RU": "Continental to subarctic", "CA": "Continental to subarctic",
}


def climate_zone(c):
    if c["iso2"] in CLIMATE_OVERRIDES:
        return CLIMATE_OVERRIDES[c["iso2"]]
    lat = c.get("lat")
    if lat is None:
        return None
    a = abs(lat)
    if a < 10:
        return "Equatorial tropical"
    if a < 23.5:
        return "Tropical"
    if a < 35:
        return "Subtropical"
    if a < 55:
        return "Temperate"
    if a < 66.5:
        return "Subpolar"
    return "Polar"


def add_derived(countries, geo_ids):
    print("[9/9] derived fields")
    pops = sorted((c["population"] for c in countries.values() if c["population"]),
                  reverse=True)
    for c in countries.values():
        c["climate_zone"] = climate_zone(c)
        c["hemisphere"] = ("Northern" if (c.get("lat") or 0) >= 0 else "Southern")
        c["landlocked"] = len(c.get("borders", [])) > 0 and c["iso2"] in LANDLOCKED
        c["has_shape"] = c.get("iso3") in geo_ids
        c["flag_url"] = "https://flagcdn.com/w640/%s.png" % c["iso2"].lower()
        c["flag_thumb"] = "https://flagcdn.com/w160/%s.png" % c["iso2"].lower()

        # Difficulty tier drives the adaptive ladder: tier 1 is France and
        # Japan, tier 4 is Eswatini and Suriname. Fame proxy = population rank
        # plus how many people we found notable enough to have a photo.
        pop = c.get("population") or 0
        rank = pops.index(pop) if pop in pops else len(pops)
        notable = len(c.get("famous", []))
        score = rank + (60 if notable < 3 else 0) + (30 if notable < 8 else 0)
        c["tier"] = 1 if score < 40 else 2 if score < 90 else 3 if score < 150 else 4
    return countries


LANDLOCKED = {
    "AF", "AD", "AM", "AT", "AZ", "BY", "BT", "BO", "BW", "BF", "BI", "CF",
    "TD", "CZ", "SZ", "ET", "HU", "KZ", "XK", "KG", "LA", "LS", "LI", "LU",
    "MW", "ML", "MD", "MN", "NP", "NE", "MK", "PY", "RW", "SM", "RS", "SK",
    "SI", "SS", "CH", "TJ", "TM", "UG", "UZ", "VA", "ZM", "ZW",
}


CKPT = os.path.join(ROOT, "data", "_checkpoint.json")
_STAGES_DONE = set()


def save_progress(countries):
    """Mid-stage checkpoint, so a long pass can be resumed part-way."""
    checkpoint(countries, _STAGES_DONE)


def checkpoint(countries, done):
    """Save progress after every stage. The Wikidata and Wikipedia passes take
    minutes and the odd chunk times out, so a rerun should resume rather than
    start the whole pull again. Delete data/_checkpoint.json to force a rebuild."""
    with open(CKPT, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(done), "countries": countries}, f, ensure_ascii=False)


def load_checkpoint():
    if not os.path.exists(CKPT):
        return None, set()
    with open(CKPT, encoding="utf-8") as f:
        d = json.load(f)
    print("resuming; already done: %s" % ", ".join(d["done"]))
    return d["countries"], set(d["done"])


def main():
    geo_path = os.path.join(ROOT, "data", "countries.geo.json")
    with open(geo_path, encoding="utf-8") as f:
        geo_ids = {feat.get("id") for feat in json.load(f)["features"]}

    countries, done = load_checkpoint()
    stages = [
        ("core",     lambda c: fetch_core()),
        ("capitals", fetch_capitals),
        ("politics", fetch_politics),
        ("borders",  fetch_borders),
        ("languages", fetch_languages),
        ("cities",   fetch_cities),
        ("wars",     fetch_wars),
        ("leaders",  fetch_leaders),
        ("famous",   fetch_famous),
        ("wikipedia", fetch_wikipedia),
    ]
    _STAGES_DONE.update(done)
    for name, fn in stages:
        if name in done:
            continue
        result = fn(countries)
        countries = result if result is not None else countries
        done.add(name)
        _STAGES_DONE.add(name)
        checkpoint(countries, done)

    add_derived(countries, geo_ids)

    # Drop anything too thin to build a question from.
    usable = {k: c for k, c in countries.items() if c.get("name") and c.get("iso3")}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(usable, f, ensure_ascii=False, indent=1)

    n = len(usable)
    print("\nwrote %s" % OUT)
    print("  %d countries" % n)
    for field in ("capitals", "borders", "languages", "cities", "wars", "leaders", "past_leaders",
                  "famous", "summary", "climate_text", "government", "currencies",
                  "wiki_url"):
        have = sum(1 for c in usable.values() if c.get(field))
        print("  %-14s %3d/%d" % (field, have, n))


if __name__ == "__main__":
    sys.exit(main())

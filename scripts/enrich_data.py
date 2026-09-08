"""Fill the holes the Wikidata pull leaves behind.

`fetch_data.py` builds the dataset; this script improves the fields it is bad
at, and it can be rerun on its own without repeating the 10-minute pull:

  * **Languages.** Wikidata's speaker counts exist for a handful of countries
    and nowhere else -- 167 of 197 countries came back with fewer than three
    languages, Guatemala came back with one, and Sweden did not list Swedish.
    The CIA World Factbook publishes a language *breakdown* with percentages
    and official status for almost every country, mirrored as JSON at
    github.com/factbook/factbook.json.
  * **Economy.** Nothing in the Wikidata pull said what a country sells or
    who to. The Factbook has exports, imports, partners, GDP per head and
    natural resources for the same countries.
  * **Wikipedia links on people.** The person queries kept a name and a photo
    but no identifier, so nobody on a fact card was clickable. Every distinct
    name is looked up again in one batched query.
  * **Famous faces.** The original query needed more than 90 Wikidata
    sitelinks, a bar 80 countries never cleared. The floor drops per country
    until something comes back.

    python scripts/enrich_data.py                    # everything
    python scripts/enrich_data.py languages economy  # or named stages
"""
import json
import os
import re
import sys
import time
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "countries.json")
FACTBOOK_ZIP = os.path.join(DATA, "factbook.zip")
FACTBOOK_URL = "https://codeload.github.com/factbook/factbook.json/zip/refs/heads/master"
SPARQL_URL = "https://query.wikidata.org/sparql"

S = requests.Session()
S.headers.update({"User-Agent": "LearnGeoQuiz/1.0 (personal learning project)"})


FAILED = object()      # told apart from "the query ran and found nothing"


def sparql(query, tries=3):
    """A failed query returns FAILED, not an empty list.

    The two are very different to a caller that is about to overwrite a field:
    a country whose query times out should keep the leaders it already has,
    not lose them. The endpoint answers 429 when asked several hundred
    questions in a row, so each attempt waits longer than the last.
    """
    last = None
    for i in range(tries):
        try:
            r = S.get(SPARQL_URL, params={"query": query},
                      headers={"Accept": "application/sparql-results+json"},
                      timeout=180)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            last = "HTTP %s" % r.status_code
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After") or 30))
        except Exception as e:
            last = repr(e)
        time.sleep(5 * (i + 1))
    print("      query failed (%s)" % last)
    return FAILED


def rows_of(result):
    return [] if result is FAILED else result


def v(b, k, d=None):
    return b[k]["value"] if k in b else d


def _norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _clean(text):
    """Factbook text carries HTML entities and the odd <strong> tag."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(a, b)
    text = re.sub(r"&[a-z]{1,8}acute;", lambda m: m.group(0)[1], text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# The World Factbook mirror, shared by the language and economy stages
# --------------------------------------------------------------------------

# Factbook files are named with FIPS codes, not ISO ones, so countries are
# matched on their English name. These six are filed under a different name.
FACTBOOK_ALIASES = {
    "MM": "Burma", "CI": "Cote d'Ivoire", "CV": "Cabo Verde",
    "ST": "Sao Tome and Principe", "VA": "Holy See (Vatican City)",
    "PS": "West Bank",
}

_INDEX = None


def factbook_index():
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    if not os.path.exists(FACTBOOK_ZIP):
        print("      downloading the World Factbook mirror")
        r = S.get(FACTBOOK_URL, timeout=300)
        r.raise_for_status()
        with open(FACTBOOK_ZIP, "wb") as f:
            f.write(r.content)
    z = zipfile.ZipFile(FACTBOOK_ZIP)
    _INDEX = {}
    for entry in z.namelist():
        if not entry.endswith(".json") or entry.count("/") != 2 or "/meta/" in entry:
            continue
        try:
            d = json.loads(z.read(entry))
        except ValueError:
            continue
        cn = (d.get("Government") or {}).get("Country name") or {}
        for form in ("conventional short form", "conventional long form"):
            nm = ((cn.get(form) or {}).get("text") or "").strip()
            if nm:
                _INDEX.setdefault(_norm(nm), d)
    return _INDEX


def factbook_for(iso, country):
    return factbook_index().get(_norm(FACTBOOK_ALIASES.get(iso) or country["name"]))


def field_text(section, *path):
    node = section
    for k in path:
        node = (node or {}).get(k) or {}
    return node.get("text") if isinstance(node, dict) else None


def _split_top_level(text):
    """Split on commas that are not inside brackets: the Factbook nests a
    family's members in parentheses (Maya languages 29.7% (Q'eqchi' 8.3%,
    ...)) and those inner commas must not break the row apart."""
    out, depth, buf = [], 0, ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    return out


# --------------------------------------------------------------------------
# 1. Languages, with percentages and official status
# --------------------------------------------------------------------------

# Rows that are a residual, not a language.
NOT_A_LANGUAGE = re.compile(
    r"^(other|others|unspecified|none|no response|not stated|various|"
    r"all are|note|minority|foreign|major-language|includes)", re.I)

DROP_WORDS = re.compile(
    r"\b(only|official|co-official|national|de facto|widely spoken|"
    r"lingua franca|shared|languages spoken|spoken|nationwide)\b", re.I)


def parse_languages(text):
    """Spanish (official) 69.9%, Maya languages 29.7% (...)  ->
       [{"name": "Spanish", "share": 69.9, "official": True}, ...]"""
    text = _clean(text)
    if not text:
        return []
    text = re.sub(r"\((\d{4})[^)]*\)", " ", text)          # (2018 est.)
    out = []
    for part in _split_top_level(text):
        part = part.strip().strip(";")
        if not part:
            continue
        m = re.search(r"([\d.]+)\s*%", part)
        share = None
        if m:
            try:
                share = float(m.group(1))
            except ValueError:
                share = None
        name = part[:m.start()] if m else part
        official = bool(re.search(r"\bofficial\b", name, re.I))
        name = re.sub(r"\([^)]*\)", " ", name)             # (official), notes
        name = DROP_WORDS.sub(" ", name)
        name = re.sub(r"\s+", " ", name).strip(" .;:-")
        if not name or NOT_A_LANGUAGE.match(name) or len(name) > 44:
            continue
        if share is None and out and not official:
            continue          # trailing prose after the real list
        out.append({"name": name[0].upper() + name[1:], "share": share,
                    "official": official})
    return out


def _wiki_guess(language_name):
    """Language articles are titled "X language" far more often than "X"."""
    return "https://en.wikipedia.org/wiki/%s_language" % language_name.replace(" ", "_")


def stage_languages(countries):
    print("[languages] shares from the World Factbook")
    # One name -> QID map for the whole world, not one per country. Sweden's
    # Factbook entry has no Wikidata id of its own, so "Swedish" in Sweden
    # became a different topic node from "Swedish" in Finland, and the Swedish
    # language page listed one country: Finland.
    global_ids = {}
    for c in countries.values():
        for old in (c.get("languages") or []) + (c.get("official_languages") or []):
            if isinstance(old, dict) and old.get("name") and old.get("qid"):
                global_ids.setdefault(old["name"].lower(),
                                      (old["qid"], old.get("wiki")))
    filled = missed = 0
    for iso, c in sorted(countries.items()):
        d = factbook_for(iso, c)
        node = ((d or {}).get("People and Society") or {}).get("Languages") or {}
        text = node.get("text") or ((node.get("Languages") or {}).get("text"))
        rows = parse_languages(text)
        if not rows:
            missed += 1
            continue
        # Keep what Wikidata knew -- QIDs, Wikipedia links, speaker counts --
        # and layer the shares on top, matching on name. P37 (official
        # language) is a second source for official status: the Factbook
        # sometimes states it in a note the parser cannot see.
        known = {}
        for old in c.get("languages") or []:
            if isinstance(old, dict) and old.get("name"):
                known[old["name"].lower()] = old
        official_names = {(x.get("name") or "").lower()
                          for x in (c.get("official_languages") or [])
                          if isinstance(x, dict)}
        merged = []
        for row in rows[:6]:
            old = known.get(row["name"].lower(), {})
            qid, wiki = global_ids.get(row["name"].lower(), (None, None))
            merged.append({
                "name": row["name"],
                "qid": old.get("qid") or qid,
                "wiki": old.get("wiki") or wiki or _wiki_guess(row["name"]),
                "speakers": old.get("speakers"),
                "share": row["share"],
                "official": row["official"] or row["name"].lower() in official_names,
            })
        c["languages"] = merged
        filled += 1
    print("      %d countries now have a language breakdown, %d unmatched"
          % (filled, missed))
    return countries


# --------------------------------------------------------------------------
# 2. Economy: what a country sells, buys, and to whom
# --------------------------------------------------------------------------

def _money(text):
    """$2.567 trillion (2023 est.)  ->  $2.567 trillion"""
    text = _clean(text)
    if not text:
        return None
    text = re.sub(r"\((?:\d{4}|note)[^)]*\)", "", text)
    text = text.split(";")[0]
    return text.strip(" .,") or None


def _list_of(text, cap=6):
    """Turn a Factbook comma list into at most `cap` short items."""
    text = _clean(text)
    if not text:
        return []
    text = re.sub(r"\((\d{4})[^)]*\)", " ", text)
    out = []
    for part in _split_top_level(text):
        part = re.sub(r"\([^)]*\)", " ", part)
        part = re.sub(r"\s+\d[\d.]*%", "", part)
        part = re.sub(r"\s+", " ", part).strip(" .;:-")
        if part and len(part) < 44 and not NOT_A_LANGUAGE.match(part):
            out.append(part)
        if len(out) >= cap:
            break
    return out


def _partners(text, cap=5):
    """US 16%, China 12%, ...  ->  [{"name": "US", "share": 16.0}, ...]"""
    text = _clean(text)
    if not text:
        return []
    text = re.sub(r"\((\d{4})[^)]*\)", " ", text)
    out = []
    for part in _split_top_level(text):
        m = re.search(r"([\d.]+)\s*%", part)
        name = re.sub(r"\([^)]*\)", " ", part[:m.start()] if m else part)
        name = re.sub(r"\s+", " ", name).strip(" .;:-")
        if not name or len(name) > 40:
            continue
        out.append({"name": name, "share": float(m.group(1)) if m else None})
        if len(out) >= cap:
            break
    return out


def stage_economy(countries):
    print("[economy] exports, imports and resources from the World Factbook")
    got = 0
    for iso, c in sorted(countries.items()):
        d = factbook_for(iso, c)
        if not d:
            continue
        econ = d.get("Economy") or {}
        geo = d.get("Geography") or {}
        e = {
            "gdp_per_capita": _money(field_text(econ, "Real GDP per capita")),
            "gdp": _money(field_text(econ, "Real GDP (purchasing power parity)")),
            "exports_value": _money(field_text(econ, "Exports")),
            "imports_value": _money(field_text(econ, "Imports")),
            "exports": _list_of(field_text(econ, "Exports - commodities")),
            "imports": _list_of(field_text(econ, "Imports - commodities")),
            "export_partners": _partners(field_text(econ, "Exports - partners")),
            "import_partners": _partners(field_text(econ, "Imports - partners")),
            "industries": _list_of(field_text(econ, "Industries")),
            "agriculture": _list_of(field_text(econ, "Agricultural products")),
            "resources": _list_of(field_text(geo, "Natural resources")),
            "unemployment": _money(field_text(econ, "Unemployment rate")),
        }
        e = {k: val for k, val in e.items() if val}
        if e:
            c["economy"] = e
            got += 1
    print("      %d countries have economy data" % got)
    return countries


# --------------------------------------------------------------------------
# 3. Wikipedia links for every person on a fact card
# --------------------------------------------------------------------------

PEOPLE_FIELDS = ("leaders", "past_leaders", "famous")


def stage_people(countries):
    print("[people] Wikipedia links for people")
    names = set()
    for c in countries.values():
        for field in PEOPLE_FIELDS:
            for p in c.get(field) or []:
                if p.get("name") and not p.get("wiki"):
                    names.add(p["name"])
    names = sorted(names)
    print("      %d distinct people to look up" % len(names))
    found = {}
    for i in range(0, len(names), 120):
        batch = names[i:i + 120]
        values = " ".join('"%s"@en' % n.replace("\\", "").replace('"', '')
                          for n in batch)
        q = """
SELECT ?lbl ?qid ?wp ?sl WHERE {
  VALUES ?lbl { %s }
  ?p rdfs:label ?lbl ; wdt:P31 wd:Q5 ; wikibase:sitelinks ?sl .
  ?wp schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> .
  BIND(STRAFTER(STR(?p), "entity/") AS ?qid)
}
""" % values
        for b in rows_of(sparql(q)):
            lbl, sl = v(b, "lbl"), int(v(b, "sl", "0"))
            # A name can belong to several people; the famous one wins, which
            # is the one the dataset meant in every case checked.
            if lbl not in found or sl > found[lbl][2]:
                found[lbl] = (v(b, "qid"), v(b, "wp"), sl)
        print("      %d/%d" % (min(i + 120, len(names)), len(names)))
    linked = 0
    for c in countries.values():
        for field in PEOPLE_FIELDS:
            for p in c.get(field) or []:
                hit = found.get(p.get("name"))
                if hit and not p.get("wiki"):
                    p["qid"], p["wiki"] = hit[0], hit[1]
                    linked += 1
    print("      linked %d person entries (%d names resolved)"
          % (linked, len(found)))
    return countries


# --------------------------------------------------------------------------
# 4. Leaders: current, past, and which party they belong to
# --------------------------------------------------------------------------
# The original pull read P35 (head of state) and P6 (head of government) off
# the country item, and that misses people. India's Q668 still lists Manmohan
# Singh as the last head of government, so Narendra Modi -- who has held the
# office since 2014 -- appeared nowhere. The office itself is the reliable
# route: find the position whose jurisdiction (P1001) is this country and
# which is a kind of head of state (Q48352) or head of government (Q2285706),
# then ask who holds it with no end date.

TODAY = time.strftime("%Y-%m-%d")


def _country_statements(iso):
    return """
SELECT ?role ?plbl ?qid ?wp ?img ?start ?ended ?sl WHERE {
  ?c wdt:P297 "%s" .
  { ?c p:P35 ?st . ?st ps:P35 ?person . BIND("head_of_state" AS ?role) }
  UNION
  { ?c p:P6 ?st . ?st ps:P6 ?person . BIND("head_of_government" AS ?role) }
  ?person rdfs:label ?plbl . FILTER(LANG(?plbl) = "en")
  ?person wikibase:sitelinks ?sl .
  BIND(STRAFTER(STR(?person), "entity/") AS ?qid)
  OPTIONAL { ?wp schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?person wdt:P18 ?img }
  OPTIONAL { ?st pq:P580 ?start }
  OPTIONAL { ?st pq:P582 ?ended }
}
LIMIT 200
""" % iso


def _office_holders(iso):
    return """
SELECT ?role ?plbl ?qid ?wp ?img ?start ?sl WHERE {
  ?c wdt:P297 "%s" .
  { ?off wdt:P279* wd:Q48352 . BIND("head_of_state" AS ?role) }
  UNION
  { ?off wdt:P279* wd:Q2285706 . BIND("head_of_government" AS ?role) }
  ?off wdt:P1001 ?c .
  ?person p:P39 ?st . ?st ps:P39 ?off .
  FILTER NOT EXISTS { ?st pq:P582 ?e }
  ?person rdfs:label ?plbl . FILTER(LANG(?plbl) = "en")
  ?person wikibase:sitelinks ?sl .
  BIND(STRAFTER(STR(?person), "entity/") AS ?qid)
  OPTIONAL { ?wp schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?person wdt:P18 ?img }
  OPTIONAL { ?st pq:P580 ?start }
}
LIMIT 40
""" % iso


def _entry(b, ended=None):
    return {
        "name": v(b, "plbl"), "qid": v(b, "qid"), "wiki": v(b, "wp"),
        "role": v(b, "role"), "image": v(b, "img"),
        "start": (v(b, "start") or "")[:4] or None,
        "end": (ended or "")[:4] or None,
        "fame": int(v(b, "sl", "0")),
    }


def _merge_person(bucket, entry):
    for x in bucket:
        if x["name"] == entry["name"] and x["role"] == entry["role"] \
                and x.get("start") == entry.get("start"):
            for k, val in entry.items():        # fill the gaps, keep the rest
                if val and not x.get(k):
                    x[k] = val
            return
    bucket.append(entry)


def stage_leaders(countries):
    print("[leaders] current and past, with parties")
    isos = sorted(countries)
    for n, iso in enumerate(isos):
        current, past = [], []
        a = sparql(_country_statements(iso), tries=3)
        for b in rows_of(a):
            if not v(b, "plbl"):
                continue
            ended = v(b, "ended")
            entry = _entry(b, ended)
            # Still in office if there is no end date, or it has not arrived
            # yet: Wikidata records scheduled ends for sitting leaders.
            _merge_person(current if (not ended or ended[:10] > TODAY) else past,
                          entry)
        time.sleep(0.5)                 # the endpoint starts answering 429
        bq = sparql(_office_holders(iso), tries=3)
        for b in rows_of(bq):
            if v(b, "plbl"):
                _merge_person(current, _entry(b))
        time.sleep(0.5)
        if a is FAILED and bq is FAILED:
            print("      %s: both queries failed, keeping what we had" % iso)
            continue
        # Merge with what is already on disk rather than replacing it: a
        # partial answer should add leaders, never remove them.
        for old in countries[iso].get("leaders") or []:
            if old.get("name"):
                _merge_person(current, dict(old))
        for old in countries[iso].get("past_leaders") or []:
            if old.get("name"):
                _merge_person(past, dict(old))
        current.sort(key=lambda x: (-(x["fame"]), x["name"]))
        past.sort(key=lambda x: (-(x["fame"]), x["name"]))
        # One person can hold both offices (most presidential systems); keep
        # the pair, but never the same office twice.
        seen = set()
        keep = []
        for p in current:
            if p["role"] in seen and p["name"] not in {k["name"] for k in keep}:
                continue
            if (p["name"], p["role"]) in {(k["name"], k["role"]) for k in keep}:
                continue
            seen.add(p["role"])
            keep.append(p)
        countries[iso]["leaders"] = keep[:4]
        countries[iso]["past_leaders"] = past[:12]
        if n % 20 == 0:
            print("      %d/%d (%s: %d current, %d past)"
                  % (n, len(isos), iso, len(keep), len(past)))
            save(countries)
    return stage_parties(countries)


def stage_parties(countries):
    """Political party for everyone currently in office, in batches."""
    print("[parties] party membership for sitting leaders")
    qids = sorted({p["qid"] for c in countries.values()
                   for p in c.get("leaders") or [] if p.get("qid")})
    parties = {}
    for i in range(0, len(qids), 100):
        values = " ".join("wd:%s" % q for q in qids[i:i + 100])
        q = """
SELECT ?qid ?partylbl WHERE {
  VALUES ?p { %s }
  ?p wdt:P102 ?party .
  ?party rdfs:label ?partylbl . FILTER(LANG(?partylbl) = "en")
  BIND(STRAFTER(STR(?p), "entity/") AS ?qid)
}
""" % values
        for b in rows_of(sparql(q, tries=2)):
            parties.setdefault(v(b, "qid"), v(b, "partylbl"))
    got = 0
    for c in countries.values():
        for p in c.get("leaders") or []:
            if parties.get(p.get("qid")):
                p["party"] = parties[p["qid"]]
                got += 1
    print("      %d leaders have a party" % got)
    return countries


# --------------------------------------------------------------------------
# 5. Famous faces for the countries that came back empty
# --------------------------------------------------------------------------

HINT = "PREFIX hint: <http://www.bigdata.com/queryHints#>"


def _famous_query(iso, floor):
    return """%s
SELECT ?plbl ?qid ?wp ?img ?occlbl ?born ?died ?sl WHERE {
  hint:Query hint:optimizer "None" .
  ?c wdt:P297 "%s" .
  ?person wdt:P27 ?c .
  ?person wdt:P18 ?img .
  ?person wikibase:sitelinks ?sl .
  FILTER(?sl > %d)
  ?person rdfs:label ?plbl . FILTER(LANG(?plbl) = "en")
  BIND(STRAFTER(STR(?person), "entity/") AS ?qid)
  OPTIONAL { ?wp schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?person wdt:P106 ?occ . ?occ rdfs:label ?occlbl . FILTER(LANG(?occlbl) = "en") }
  OPTIONAL { ?person wdt:P569 ?born }
  OPTIONAL { ?person wdt:P570 ?died }
}
LIMIT 400
""" % (HINT, iso, floor)


def stage_famous(countries, want=6):
    print("[famous] faces for the thin countries")
    thin = sorted(iso for iso, c in countries.items()
                  if len(c.get("famous") or []) < want)
    print("      %d countries below %d faces" % (len(thin), want))
    for n, iso in enumerate(thin):
        rows = []
        for floor in (40, 12, 3):           # drop the bar until something lands
            rows = rows_of(sparql(_famous_query(iso, floor), tries=2))
            time.sleep(0.4)
            if len(rows) > 4:
                break
        seen = {}
        for b in rows:
            nm = v(b, "plbl")
            if not nm:
                continue
            if nm not in seen:
                seen[nm] = {"name": nm, "qid": v(b, "qid"), "wiki": v(b, "wp"),
                            "image": v(b, "img"), "occupations": [],
                            "born": (v(b, "born") or "")[:4] or None,
                            "died": (v(b, "died") or "")[:4] or None,
                            "fame": int(v(b, "sl", "0"))}
            occ = v(b, "occlbl")
            if occ and occ not in seen[nm]["occupations"] and len(seen[nm]["occupations"]) < 4:
                seen[nm]["occupations"].append(occ)
        have = {p["name"] for p in countries[iso].get("famous") or []}
        extra = [p for p in sorted(seen.values(), key=lambda x: -x["fame"])
                 if p["name"] not in have]
        countries[iso]["famous"] = ((countries[iso].get("famous") or []) + extra)[:14]
        if n % 10 == 0:
            print("      %d/%d (%s: %d)" % (n, len(thin), iso,
                                            len(countries[iso]["famous"])))
            save(countries)
    return countries


# --------------------------------------------------------------------------

def save(countries):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(countries, f, ensure_ascii=False, indent=1)


# --------------------------------------------------------------------------
# 6. Climate, in words and in one of seven zones
# --------------------------------------------------------------------------
# The zone used to come from latitude bands, which produced neighbouring
# labels a player cannot choose between: Brazil sat at "Tropical" while
# "Equatorial tropical" was on offer as a wrong answer. These seven are
# mutually exclusive, and the country's own Factbook climate paragraph
# decides which one it gets.

ZONES = [
    ("Polar or subpolar", ("arctic", "polar", "subarctic", "tundra", "ice cap")),
    ("Desert or arid", ("desert", "arid", "semiarid", "semi-arid", "hot and dry")),
    ("Mediterranean", ("mediterranean",)),
    ("Highland or alpine", ("alpine", "highland", "montane", "varies with altitude",
                            "varies with elevation")),
    ("Tropical", ("tropical", "equatorial", "monsoon", "rainforest", "savanna",
                  "wet and dry")),
    ("Continental", ("continental", "steppe", "harsh winters", "cold winters")),
    ("Temperate", ("temperate", "maritime", "oceanic", "mild", "moderate")),
]


def climate_zone(text, lat):
    low = (text or "").lower()
    # The Factbook writes the dominant climate first and the exceptions after
    # -- China is "tropical in south to subarctic in north" -- so the zone
    # mentioned earliest is the one the country mostly has. Picking by list
    # order instead had China down as polar.
    hits = [(low.find(word), zone) for zone, words in ZONES
            for word in words if word in low]
    if hits:
        return min(hits)[1]
    if lat is None:
        return None
    a = abs(lat)
    if a < 23.5:
        return "Tropical"
    if a < 35:
        return "Mediterranean"
    if a < 55:
        return "Temperate"
    if a < 66.5:
        return "Continental"
    return "Polar or subpolar"


def stage_climate(countries):
    print("[climate] climate prose and a zone that is answerable")
    got = 0
    for iso, c in sorted(countries.items()):
        d = factbook_for(iso, c)
        text = _clean(field_text((d or {}).get("Geography") or {}, "Climate"))
        if text:
            c["climate_text"] = text
            got += 1
        c["climate_zone"] = climate_zone(text, c.get("lat"))
    print("      %d countries have a climate paragraph" % got)
    return countries


# --------------------------------------------------------------------------
# 7. One government type per country
# --------------------------------------------------------------------------
# Wikidata's P122 lists every form that applies, which for China is communist
# state, socialist state, unitary state and one-party state -- so the quiz
# offered four correct answers and marked three wrong. Both Wikipedia and the
# Factbook state a single government type per country; the Factbook's is the
# one already on disk.

def stage_government(countries):
    print("[government] one government type per country")
    got = 0
    for iso, c in sorted(countries.items()):
        d = factbook_for(iso, c)
        text = _clean(field_text((d or {}).get("Government") or {},
                                 "Government type"))
        if not text:
            continue
        text = re.sub(r"\((?:\d{4}|note)[^)]*\)", "", text).split(";")[0]
        text = text.strip(" .,")
        if text and len(text) < 70:
            c["government_type"] = text[0].upper() + text[1:]
            got += 1
    print("      %d countries have a government type" % got)
    return countries


STAGES = {"languages": stage_languages, "economy": stage_economy,
          "climate": stage_climate, "government": stage_government,
          "people": stage_people, "leaders": stage_leaders,
          "famous": stage_famous}


def main():
    with open(OUT, encoding="utf-8") as f:
        countries = json.load(f)
    wanted = sys.argv[1:] or list(STAGES)
    for name in wanted:
        if name not in STAGES:
            raise SystemExit("unknown stage %r; pick from %s"
                             % (name, ", ".join(STAGES)))
        countries = STAGES[name](countries) or countries
        save(countries)
    print("\nwrote %s" % OUT)
    for field in ("languages", "economy", "famous"):
        have = sum(1 for c in countries.values() if c.get(field))
        print("  %-10s %3d/%d" % (field, have, len(countries)))


if __name__ == "__main__":
    sys.exit(main())

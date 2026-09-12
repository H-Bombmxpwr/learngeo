"""Loads the prebuilt dataset and exposes the lookups the quiz needs.

Everything is read once at import time and kept in memory -- the dataset is a
few megabytes and never changes while the server runs.

The second job of this module is the topic index. Most facts about a country
are shared with other countries: a language, a war, a currency, a form of
government. Those are stored as entities (name + Wikidata id + Wikipedia URL),
and inverting them gives a page per entity listing every country attached to
it. That is what turns the app from a set of country pages into a web you can
wander around.
"""
import json
import os

from . import provenance, supplement
from .data_util import fold, slug, wiki_url

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")


def _thumb(url, width=400):
    """Commons file URLs accept a width param, which saves pulling 8MB photos."""
    if not url:
        return None
    sep = "&" if "?" in url else "?"
    return "%s%swidth=%d" % (url, sep, width)


def ent_name(x):
    """Entities are dicts, but older datasets stored plain strings."""
    return x.get("name") if isinstance(x, dict) else x


# field on a country  ->  (url kind, human label, singular noun)
#
# Anything listed here becomes a page of its own listing every country
# attached to it, and every mention of it anywhere on the site becomes a link
# to that page. The rule is that if a fact is shared between countries it is a
# thread worth pulling -- which is as true of "crude petroleum" and "tropical"
# as it is of "Spanish".
TOPIC_FIELDS = {
    "languages":    ("language", "Languages", "language"),
    "currencies":   ("currency", "Currencies", "currency"),
    "government":   ("government", "Forms of government", "form of government"),
    "religions":    ("religion", "Religions", "religion"),
    "continents":   ("continent", "Continents", "continent"),
    "member_of":    ("organization", "Organizations", "organization"),
    "wars":         ("war", "Wars and conflicts", "war"),
    "highest_point": ("peak", "Highest points", "peak"),
    "exports_t":    ("export", "Exports", "export"),
    "imports_t":    ("import", "Imports", "import"),
    "resources_t":  ("resource", "Natural resources", "natural resource"),
    "industries_t": ("industry", "Industries", "industry"),
    "partners_t":   ("partner", "Trading partners", "trading partner"),
    "climate_t":    ("climate", "Climates", "climate"),
    "landmarks":    ("landmark", "Landmarks and landscapes", "landmark"),
    "govtype_t":    ("govtype", "Government types", "government type"),
}

# Which of those are derived at load time from a plain list of strings rather
# than stored as entities by the fetch scripts.
DERIVED_TOPICS = (
    ("exports_t", "exports"),
    ("imports_t", "imports"),
    ("resources_t", "resources"),
    ("industries_t", "industries"),
)


class World(object):
    def __init__(self):
        path = os.path.join(DATA_DIR, "countries.json")
        if not os.path.exists(path):
            # Under gunicorn this is the first thing that touches the dataset,
            # so it is the only place a deploy missing its data can say so.
            raise SystemExit(
                "%s is missing. It is committed to the repository; if this is "
                "a deploy, check it was not excluded by .gitignore. To rebuild "
                "it: python scripts/fetch_data.py && python scripts/enrich_data.py"
                % path)
        with open(path, encoding="utf-8") as f:
            self.countries = json.load(f)
        with open(os.path.join(DATA_DIR, "countries.geo.json"), encoding="utf-8") as f:
            geo = json.load(f)

        # ISO3 -> geometry, for the outline silhouettes and the clickable map.
        self.shapes = {}
        for feat in geo["features"]:
            if feat.get("id"):
                self.shapes[feat["id"]] = feat["geometry"]
        self.geojson = geo

        # Curated wars, historical figures and landmarks, layered on top of
        # the fetched data. See supplement.py for why they cannot come from a
        # query.
        supplement.apply(self.countries)
        # Then every sourced correction, last, so neither a dataset rebuild
        # nor the supplement can put a wrong value back. See provenance.py.
        provenance.apply(self.countries)
        self._derive_topics()

        self.by_iso3 = {}
        for c in self.countries.values():
            if c.get("iso3"):
                self.by_iso3[c["iso3"]] = c
            for person in self.people_of(c):
                person["image"] = _thumb(person.get("image"))
                # Nobody on a fact card was clickable, because the person
                # queries kept a name and a photo but no link. The enrichment
                # pass fills most of these in; the rest fall back to the
                # article named after the person, which is how Wikipedia
                # titles a biography unless the name is ambiguous.
                if not person.get("wiki") and person.get("name"):
                    person["wiki"] = wiki_url(person["name"])

        self._people = None          # built on first lookup, see person()
        self._domains = {}           # answer sets for the challenge type-ahead
        self.all_isos = sorted(self.countries)
        self.by_continent = {}
        for iso in self.all_isos:
            self.by_continent.setdefault(self.continent_of(iso), []).append(iso)

        self._build_topics()
        self._build_search()

    def _derive_topics(self):
        """Turn the plain string lists into linkable entities.

        The economy fields arrive from the Factbook as bare strings -- "crude
        petroleum", "coffee" -- and the climate zone as one word. Wrapping
        each in the same {name, key} shape the fetched entities use means the
        existing topic index picks them up with no special cases, so every
        export on a country page is a door to every other country that sells
        the same thing.
        """
        for c in self.countries.values():
            econ = c.get("economy") or {}
            for field, source in DERIVED_TOPICS:
                c[field] = [{"name": x} for x in (econ.get(source) or [])]
            # Both directions of trade collapse into one "partner" thread:
            # what you want from it is who a country trades with at all.
            partners = {}
            for key, direction in (("export_partners", "sells to"),
                                   ("import_partners", "buys from")):
                for p in econ.get(key) or []:
                    node = partners.setdefault(p["name"], {"name": p["name"],
                                                           "ways": []})
                    node["ways"].append(direction)
                    if p.get("share") and not node.get("share"):
                        node["share"] = p["share"]
            for node in partners.values():
                node["detail"] = " and ".join(node.pop("ways"))
            c["partners_t"] = list(partners.values())
            c["climate_t"] = ([{"name": c["climate_zone"]}]
                              if c.get("climate_zone") else [])
            c["govtype_t"] = ([{"name": c["government_type"]}]
                              if c.get("government_type") else [])

    @staticmethod
    def people_of(c):
        return ((c.get("famous") or []) + (c.get("leaders") or [])
                + (c.get("past_leaders") or []) + (c.get("key_figures") or []))

    def person(self, name):
        """Everything known about one person, by name.

        Built lazily because most sessions never ask for it. A name can appear
        under several fields for the same country -- Indira Gandhi is a past
        leader and a famous face -- so the entries are merged, with the
        richest value for each field winning.
        """
        if self._people is None:
            self._people = {}
            for iso in self.all_isos:
                c = self.countries[iso]
                for field in ("leaders", "past_leaders", "famous", "key_figures"):
                    for p in c.get(field) or []:
                        if not p.get("name"):
                            continue
                        node = self._people.setdefault(
                            p["name"], {"name": p["name"], "iso2": iso,
                                        "fields": set()})
                        node["fields"].add(field)
                        for k, v in p.items():
                            if v and not node.get(k):
                                node[k] = v
        return self._people.get(name)

    # -- topic index -----------------------------------------------------
    def _build_topics(self):
        """Invert the country -> entity links into entity -> countries."""
        self.topics = {}
        for field, (kind, _, _) in TOPIC_FIELDS.items():
            bucket = self.topics.setdefault(kind, {})
            for iso, c in self.countries.items():
                for ent in c.get(field) or []:
                    if not isinstance(ent, dict):
                        ent = {"name": ent}
                    name = ent.get("name")
                    if not name:
                        continue
                    key = ent.get("qid") or slug(name)
                    node = bucket.setdefault(key, {
                        "key": key, "kind": kind, "name": name,
                        "wiki": ent.get("wiki"), "countries": [],
                    })
                    if not node["wiki"] and ent.get("wiki"):
                        node["wiki"] = ent["wiki"]
                    node["countries"].append({"iso2": iso, "detail": ent})

        # Sort each topic's country list by whatever is most informative:
        # speakers for a language, start year for a form of government.
        for kind, bucket in self.topics.items():
            for node in bucket.values():
                if kind == "language":
                    # Share of the population first -- it is on almost every
                    # country now -- and speaker counts where it is not.
                    node["countries"].sort(
                        key=lambda r: (-(r["detail"].get("share") or 0),
                                       -(r["detail"].get("speakers") or 0)))
                elif kind == "government":
                    node["countries"].sort(
                        key=lambda r: (r["detail"].get("start") or "9999"))
                else:
                    node["countries"].sort(key=lambda r: self.name(r["iso2"]))

    # -- search ----------------------------------------------------------
    def _build_search(self):
        """One flat list of everything the site has a page for.

        Country names, every topic node, and every person the dataset knows
        about. It is a few thousand rows, so matching is a scan -- fast enough
        that the box can answer as you type, without a search engine.
        """
        rows = []
        for iso in self.all_isos:
            c = self.countries[iso]
            rows.append({"label": c["name"], "sub": self.continent_of(iso),
                         "kind": "country", "url": "/country/" + iso,
                         "flag": c["flag_thumb"], "alt": [iso, c.get("iso3") or ""],
                         "rank": 0})
        for kind, bucket in self.topics.items():
            noun = next((sing for _, (k, _, sing) in TOPIC_FIELDS.items()
                         if k == kind), kind)
            for node in bucket.values():
                n = len(node["countries"])
                rows.append({
                    "label": node["name"],
                    "sub": "%s - %d countr%s" % (
                        noun.capitalize(), n, "y" if n == 1 else "ies"),
                    "kind": kind, "url": "/topic/%s/%s" % (kind, node["key"]),
                    "flag": None, "alt": [], "rank": 1,
                })
        seen = set()
        for iso in self.all_isos:
            c = self.countries[iso]
            for p in self.people_of(c):
                key = (p.get("name"), iso)
                if not p.get("name") or key in seen or not p.get("wiki"):
                    continue
                seen.add(key)
                rows.append({"label": p["name"], "sub": c["name"],
                             "kind": "person", "url": "/country/" + iso,
                             "flag": c["flag_thumb"], "alt": [], "rank": 2})
        for r in rows:
            r["_f"] = fold(r["label"])
            r["_alt"] = [fold(a) for a in r["alt"] if a]
        self.search_rows = rows

    def search(self, query, limit=10):
        q = fold(query).strip()
        if not q:
            return []
        hits = []
        for r in self.search_rows:
            if r["_f"].startswith(q):
                score = 0
            elif any(a == q for a in r["_alt"]):
                score = 1
            elif (" " + q) in (" " + r["_f"]):     # start of any word
                score = 2
            elif q in r["_f"]:
                score = 3
            else:
                continue
            hits.append((score, r["rank"], len(r["label"]), r))
        hits.sort(key=lambda h: h[:3])
        return [{k: v for k, v in r.items() if not k.startswith("_")}
                for _, _, _, r in hits[:limit]]

    # -- answer domains, for the challenge-mode type-ahead ----------------
    # Typing a country name unaided is a spelling test, not a geography one,
    # so the box offers the names it will accept. Each domain is the full set
    # of possible answers for one kind of question, built once.
    DOMAIN_FIELD = {
        "capital": "capitals", "currency": "currencies",
        "language": "languages", "continent": "continents",
        "government": "government",
    }

    def domain(self, kind):
        if kind in self._domains:
            return self._domains[kind]
        names = set()
        if kind == "country":
            names = {self.countries[i]["name"] for i in self.all_isos}
        elif kind == "city":
            for iso in self.all_isos:
                names.update(c["name"] for c in self.countries[iso].get("cities") or []
                             if c.get("name"))
        elif kind == "person":
            names = {r["label"] for r in self.search_rows if r["kind"] == "person"}
        elif kind == "climate":
            names = {c["climate_zone"] for c in self.countries.values()
                     if c.get("climate_zone")}
        elif kind == "govtype":
            names = {c["government_type"] for c in self.countries.values()
                     if c.get("government_type")}
        elif kind in self.DOMAIN_FIELD:
            field = self.DOMAIN_FIELD[kind]
            for c in self.countries.values():
                for ent in c.get(field) or []:
                    nm = ent_name(ent)
                    if nm:
                        names.add(nm)
        rows = sorted(names)
        self._domains[kind] = [{"name": n, "_f": fold(n)} for n in rows]
        return self._domains[kind]

    def suggest(self, kind, query, limit=8):
        q = fold(query).strip()
        if not q:
            return []
        starts, inside = [], []
        for row in self.domain(kind):
            if row["_f"].startswith(q):
                starts.append(row["name"])
            elif q in row["_f"]:
                inside.append(row["name"])
            if len(starts) >= limit:
                break
        return (starts + inside)[:limit]

    def topic(self, kind, key):
        return (self.topics.get(kind) or {}).get(key)

    def topic_list(self, kind):
        nodes = list((self.topics.get(kind) or {}).values())
        nodes.sort(key=lambda n: (-len(n["countries"]), n["name"]))
        return nodes

    def topics_for(self, iso2, field):
        """The entities on one country, each with the key its page lives at."""
        out = []
        kind = (TOPIC_FIELDS.get(field) or (None,))[0]
        for ent in (self.get(iso2) or {}).get(field) or []:
            if not isinstance(ent, dict):
                ent = {"name": ent}
            if not ent.get("name"):
                continue
            out.append(dict(ent, kind=kind,
                            key=ent.get("qid") or slug(ent["name"]),
                            mark=supplement.mark_for(kind, ent["name"])))
        return out

    # -- lookups ---------------------------------------------------------
    def get(self, iso2):
        return self.countries.get(iso2)

    def name(self, iso2):
        c = self.countries.get(iso2)
        return c["name"] if c else iso2

    def flag(self, iso2):
        c = self.countries.get(iso2)
        return c["flag_thumb"] if c else None

    def shape(self, iso2):
        c = self.countries.get(iso2)
        return self.shapes.get(c.get("iso3")) if c else None

    def continent_of(self, iso2):
        """The one continent this country is filed under.

        Not simply the first entry in the imported list: that list is
        unordered and counts overseas territory, which is how France came to
        be in Africa and Norway in Antarctica. provenance.py picks one by a
        written-down rule and records that it did.
        """
        c = self.countries.get(iso2) or {}
        if c.get("continent_primary"):
            return c["continent_primary"]
        conts = c.get("continents") or []
        return ent_name(conts[0]) if conts else "Unknown"

    def continents_of(self, iso2):
        """Every continent it genuinely spans, primary first."""
        c = self.countries.get(iso2) or {}
        primary = self.continent_of(iso2)
        return [primary] + [x for x in (c.get("continent_also") or [])
                            if x != primary]

    def member_of_verified(self, iso2, org):
        """Membership of the handful of organisations with a checked list."""
        c = self.countries.get(iso2) or {}
        return (c.get("verified_memberships") or {}).get(org)

    def provenance(self, iso2):
        return provenance.records(self.countries.get(iso2))

    def having(self, *fields):
        """ISO codes of countries that have every one of these fields."""
        return [iso for iso, c in self.countries.items()
                if all(c.get(f) for f in fields)]

    def neighbours(self, iso2, limit=None):
        c = self.countries.get(iso2) or {}
        n = [b for b in c.get("borders", []) if b in self.countries]
        return n[:limit] if limit else n

    def summary_line(self, iso2):
        """A one-sentence teaser used on fact cards."""
        text = (self.countries.get(iso2) or {}).get("summary") or ""
        for end in (". ", "; "):
            if end in text[:400]:
                return text.split(end)[0] + "."
        return text[:220]


WORLD = None


def world():
    global WORLD
    if WORLD is None:
        WORLD = World()
    return WORLD

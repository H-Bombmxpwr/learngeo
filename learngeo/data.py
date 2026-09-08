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
import re

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


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "unknown"


# field on a country  ->  (url kind, human label, singular noun)
TOPIC_FIELDS = {
    "languages":    ("language", "Languages", "language"),
    "currencies":   ("currency", "Currencies", "currency"),
    "government":   ("government", "Forms of government", "form of government"),
    "religions":    ("religion", "Religions", "religion"),
    "continents":   ("continent", "Continents", "continent"),
    "member_of":    ("organization", "Organizations", "organization"),
    "wars":         ("war", "Wars and conflicts", "war"),
    "highest_point": ("peak", "Highest points", "peak"),
}


class World(object):
    def __init__(self):
        with open(os.path.join(DATA_DIR, "countries.json"), encoding="utf-8") as f:
            self.countries = json.load(f)
        with open(os.path.join(DATA_DIR, "countries.geo.json"), encoding="utf-8") as f:
            geo = json.load(f)

        # ISO3 -> geometry, for the outline silhouettes and the clickable map.
        self.shapes = {}
        for feat in geo["features"]:
            if feat.get("id"):
                self.shapes[feat["id"]] = feat["geometry"]
        self.geojson = geo

        self.by_iso3 = {}
        for c in self.countries.values():
            if c.get("iso3"):
                self.by_iso3[c["iso3"]] = c
            for person in (c.get("famous", []) + c.get("leaders", [])
                           + c.get("past_leaders", [])):
                person["image"] = _thumb(person.get("image"))

        self.all_isos = sorted(self.countries)
        self.by_continent = {}
        for iso in self.all_isos:
            self.by_continent.setdefault(self.continent_of(iso), []).append(iso)

        self._build_topics()

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
                    node["countries"].sort(
                        key=lambda r: -(r["detail"].get("speakers") or 0))
                elif kind == "government":
                    node["countries"].sort(
                        key=lambda r: (r["detail"].get("start") or "9999"))
                else:
                    node["countries"].sort(key=lambda r: self.name(r["iso2"]))

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
                            key=ent.get("qid") or slug(ent["name"])))
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
        c = self.countries.get(iso2) or {}
        conts = c.get("continents") or []
        return ent_name(conts[0]) if conts else "Unknown"

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

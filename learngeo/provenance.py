"""Per-fact provenance: where a value came from, when, and what it means.

The imported dataset says "current" without any guarantee of freshness, and
several of its values are wrong in ways no structural check can see -- France
filed under Africa, the Netherlands under South America, Mexico with no
president at all. A bulk refetch would quietly reinstate every one of them.

So corrections live here rather than inline, as records instead of bare
values. Each one carries:

    value        what the dataset should say
    source       a URL a reader can check
    as_of        the date the fact itself is true of
    verified     the date a human last looked at the source
    definition   what is being measured, where that is not obvious
    confidence   high / medium -- medium means "believed right, worth a check"
    note         why the imported value was wrong, so it is not re-applied

`apply()` merges them over the loaded dataset after the fetch scripts and the
supplement, so a rebuild cannot silently undo them, and records what it did on
each country under `provenance`, which is what the country pages and the audit
read.

Where a value is a convention rather than a measurement -- which continent a
transcontinental country "is in" -- the convention is written down in
`CONVENTIONS` and applied uniformly, because the alternative is a quiz that
marks Istanbul wrong for being in the wrong half of Turkey.
"""

TODAY = "2026-09-11"

# --------------------------------------------------------------------------
# Conventions: the definitions the quiz commits to
# --------------------------------------------------------------------------
# These are the answers to "says who?" for every question whose answer depends
# on a choice of definition rather than on a fact. They are shown to the
# player on the question itself, so a disagreement is with a stated rule
# rather than with a silent one.
CONVENTIONS = {
    "continent": (
        "Seven-continent model. A country spanning two continents is filed "
        "under the one containing its capital; the other is accepted too."),
    "city_population": (
        "City proper, not metropolitan area, as recorded by GeoNames. Census "
        "years differ between countries, so only gaps wider than 15 per cent "
        "are asked about."),
    "language_share": (
        "Most widely spoken language by share of the resident population, "
        "first and second language speakers together."),
    "trade_partner": (
        "Share of goods exports by value, CIA World Factbook, most recent "
        "year reported for that country."),
    "war_participation": (
        "Principal belligerents only, named by the modern state that "
        "succeeded the power that fought. Absence from the list is not "
        "evidence that a country took no part."),
    "government_type": (
        "The single form of government named by the CIA World Factbook."),
    "membership": (
        "Full member states only, as the organisation itself lists them."),
    "highest_point": (
        "Highest natural elevation inside the country's internationally "
        "recognised land territory."),
}

# Which convention governs which question mode. The player sees this under the
# question, so "largest city" is never a bare assertion.
MODE_CONVENTION = {
    "continent_of": "continent",
    "biggest_city": "city_population",
    "city_rank": "city_population",
    "language_of": "language_share",
    "trade_partner": "trade_partner",
    "government_of": "government_type",
    "highest_point_of": "highest_point",
    "eu_member": "membership",
    "nato_member": "membership",
    "war_when": "war_participation",
    "war_order": "war_participation",
    "war_between": "war_participation",
}


def _f(value, source, as_of, definition=None, confidence="high", note=None,
       verified=TODAY):
    return {"value": value, "source": source, "as_of": as_of,
            "verified": verified, "definition": definition,
            "confidence": confidence, "note": note}


# --------------------------------------------------------------------------
# Primary continent
# --------------------------------------------------------------------------
# Wikidata's continent list is unordered and includes overseas territory, so
# the first entry -- which is what the dataset used -- put France in Africa,
# Spain in Africa, the Netherlands in South America and Norway in Antarctica.
# It also uses names that are not continents: "Americas", "Eurasia",
# "Insular Oceania", "Australian continent", "Central America".
#
# Every country below is filed under the continent containing its capital, per
# CONVENTIONS["continent"]. Countries not listed keep what the dataset gave
# them, which for the other 166 is already canonical.
CONTINENT_SOURCE = "https://unstats.un.org/unsd/methodology/m49/"

PRIMARY_CONTINENT = {
    "AU": "Oceania", "AZ": "Asia", "CL": "South America", "CY": "Asia",
    "EG": "Africa", "ES": "Europe", "FJ": "Oceania", "FM": "Oceania",
    "FR": "Europe", "GE": "Asia", "ID": "Asia", "IT": "Europe",
    "KI": "Oceania", "KZ": "Asia", "MH": "Oceania", "NL": "Europe",
    "NO": "Europe", "NR": "Oceania", "NZ": "Oceania", "PA": "North America",
    "PG": "Oceania", "PW": "Oceania", "RU": "Europe", "SB": "Oceania",
    "TO": "Oceania", "TR": "Asia", "TV": "Oceania", "US": "North America",
    "VU": "Oceania", "WS": "Oceania", "YE": "Asia",
}

# The second continent a transcontinental state really does sit in. Accepted
# as a typed answer, and never offered as a wrong option.
ALSO_CONTINENT = {
    "AZ": ["Europe"], "EG": ["Asia"], "GE": ["Europe"], "ID": ["Oceania"],
    "KZ": ["Europe"], "RU": ["Asia"], "TR": ["Europe"], "CY": ["Europe"],
    "PA": ["South America"], "US": ["Oceania"], "ES": ["Africa"],
    "FR": ["South America", "Africa"], "NL": ["North America"],
    "PG": ["Asia"], "YE": ["Africa"],
}

CANONICAL_CONTINENTS = ("Africa", "Asia", "Europe", "North America",
                        "South America", "Oceania", "Antarctica")

# Names the import uses that are not continents in the seven-continent model.
CONTINENT_ALIAS = {
    "Insular Oceania": "Oceania",
    "Australian continent": "Oceania",
    "Central America": "North America",
}


# --------------------------------------------------------------------------
# Corrected and added facts
# --------------------------------------------------------------------------
# iso2 -> field -> record. `apply` writes the value and files the record.
FACTS = {
    "NE": {
        # Not a spelling correction: Niger has no official language at all
        # since the Charter of Refoundation, and the import flattened
        # national / official / working into one boolean.
        "languages": _f(
            None,
            "https://cjca-conf.org/wp-content/uploads/2025/07/News-letter-June-2025-Ang.pdf",
            "2025-03-26",
            definition="Article 12 of the Charter of Refoundation: Hausa is "
                       "the national language, French and English are working "
                       "languages, and there is no official language.",
            note="The import marked French official. Do not collapse "
                 "national / official / working back into one flag."),
    },
    "AG": {
        "capitals": _f(
            [{"name": "St. John's",
              "wiki": "https://en.wikipedia.org/wiki/St._John%27s,_Antigua_and_Barbuda"}],
            "https://www.antigua-barbuda.org/Agjohn01.htm", "2026-09-11",
            note="Absent from the import."),
    },
    "MX": {
        # The audit's only "missing leaders" warning. Wikidata models the
        # office, and the query missed the 2024 handover entirely.
        "leaders": _f(
            [{"name": "Claudia Sheinbaum", "role": "head_of_state",
              "start": "2024", "end": None,
              "wiki": "https://en.wikipedia.org/wiki/Claudia_Sheinbaum"}],
            "https://www.gob.mx/presidencia", "2024-10-01",
            definition="President of Mexico: head of state and head of "
                       "government are the same office.",
            note="The import returned an empty leaders list for Mexico."),
    },
}

# Landmarks added where the audit found none. Kept separate because they are
# appended rather than replacing what is there.
ADDED_LANDMARKS = [
    ("AD", "Casa de la Vall", "https://www.govern.ad/ca/l/4669534"),
    ("BB", "Harrison's Cave",
     "https://www.visitbarbados.org/harrison%E2%80%99s-cave-eco-adventure-park"),
]

# --------------------------------------------------------------------------
# Membership, where the import is demonstrably stale
# --------------------------------------------------------------------------
# The imported `member_of` still has the United Kingdom in the European Union
# and leaves the Netherlands out of both the EU and NATO, so it cannot be
# asked about as it stands. These two lists are the full membership as the
# organisations themselves publish it, and they are the only two the quiz
# asks about.
MEMBERSHIPS = {
    "European Union": {
        "source": "https://european-union.europa.eu/principles-countries-history/eu-countries_en",
        "as_of": "2026-09-11",
        "members": ("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT "
                    "NL PL PT RO SK SI ES SE").split(),
    },
    "NATO": {
        "source": "https://www.nato.int/cps/en/natohq/topics_52044.htm",
        "as_of": "2026-09-11",
        "members": ("AL BE BG CA HR CZ DK EE FI FR DE GR HU IS IT LV LT LU ME "
                    "NL MK NO PL PT RO SK SI ES SE TR GB US").split(),
    },
}


# --------------------------------------------------------------------------
# Landmarks that belong to more than one country
# --------------------------------------------------------------------------
# "In which country is the Amazon rainforest?" has eight right answers, and
# the ownership filter cannot see that: it only knows which countries the
# dataset happened to record a landmark against. Naming them is the only fix
# that does not need a polygon per landmark.
SHARED_LANDMARKS = {
    "amazon rainforest", "amazon river", "andes", "alps", "sahara",
    "himalayas", "kalahari desert", "gobi desert", "sahel", "pyrenees",
    "carpathian mountains", "caucasus mountains", "ural mountains",
    "black sea", "caspian sea", "dead sea", "red sea", "mediterranean sea",
    "lake victoria", "lake tanganyika", "lake chad", "lake malawi",
    "lake titicaca", "victoria falls", "iguazu falls", "niagara falls",
    "danube", "rhine", "nile", "mekong", "congo river", "zambezi",
    "great rift valley", "mount everest", "mont blanc", "matterhorn",
    "atacama desert", "patagonia", "balkan mountains", "aral sea",
    "scandinavian mountains", "bering strait", "strait of gibraltar",
    "lake geneva", "lake constance", "tierra del fuego", "arabian desert",
    "silk road", "sundarbans", "gulf of guinea", "sea of galilee",
}


def is_shared_landmark(name):
    return (name or "").strip().lower() in SHARED_LANDMARKS


# --------------------------------------------------------------------------
# Applying it
# --------------------------------------------------------------------------

def _file(country, field, record):
    """Record what was changed, without storing the value a second time."""
    book = country.setdefault("provenance", {})
    book[field] = {k: v for k, v in record.items() if k != "value"}


def apply(countries):
    """Merge every correction over the loaded dataset, in place."""
    _apply_continents(countries)
    _apply_niger(countries.get("NE"))

    for iso, fields in FACTS.items():
        c = countries.get(iso)
        if not c:
            continue
        for field, record in fields.items():
            if record["value"] is not None:
                c[field] = record["value"]
            _file(c, field, record)

    for iso, name, source in ADDED_LANDMARKS:
        c = countries.get(iso)
        if not c:
            continue
        marks = c.setdefault("landmarks", [])
        if not any((m.get("name") or "") == name for m in marks):
            marks.append({"name": name, "source": source, "verified": TODAY})

    for org, spec in MEMBERSHIPS.items():
        members = set(spec["members"])
        for iso, c in countries.items():
            c.setdefault("verified_memberships", {})[org] = iso in members
        for iso in members:
            if iso in countries:
                _file(countries[iso], "member:" + org, _f(
                    True, spec["source"], spec["as_of"],
                    definition=CONVENTIONS["membership"],
                    note="The imported member_of list is out of date for this "
                         "organisation and is not asked about."))
    return countries


def _apply_continents(countries):
    """One canonical continent per country, plus the ones it also spans."""
    for iso, c in countries.items():
        listed = []
        for ent in c.get("continents") or []:
            name = ent.get("name") if isinstance(ent, dict) else ent
            name = CONTINENT_ALIAS.get(name, name)
            if name in CANONICAL_CONTINENTS and name not in listed:
                listed.append(name)
        primary = PRIMARY_CONTINENT.get(iso) or (listed[0] if listed else None)
        also = [x for x in ALSO_CONTINENT.get(iso, []) if x != primary]
        c["continent_primary"] = primary
        c["continent_also"] = also
        # The topic index and every page read `continents`; rewriting it here
        # is what stops "France - Africa" appearing anywhere at all.
        if primary:
            by_name = {}
            for ent in c.get("continents") or []:
                nm = ent.get("name") if isinstance(ent, dict) else ent
                by_name[CONTINENT_ALIAS.get(nm, nm)] = ent
            rebuilt = []
            for n in [primary] + also:
                ent = by_name.get(n)
                ent = dict(ent) if isinstance(ent, dict) else {}
                ent["name"] = n
                rebuilt.append(ent)
            c["continents"] = rebuilt
        if iso in PRIMARY_CONTINENT:
            _file(c, "continents", _f(
                primary, CONTINENT_SOURCE, TODAY,
                definition=CONVENTIONS["continent"],
                note="The imported list was unordered and included overseas "
                     "territory, so its first entry was not the continent the "
                     "country is in."))


def _apply_niger(niger):
    """Hausa national, French and English working, nothing official."""
    if not niger:
        return
    niger["official_languages"] = []
    niger["national_languages"] = ["Hausa"]
    niger["working_languages"] = ["French", "English"]
    for lang in niger.get("languages", []):
        lang["official"] = False
        if lang["name"] == "Hausa":
            lang["status"] = "national"
        elif lang["name"] == "French":
            lang["status"] = "working"
    if not any(l["name"] == "English" for l in niger["languages"]):
        niger["languages"].append({
            "name": "English", "qid": "Q1860",
            "wiki": "https://en.wikipedia.org/wiki/English_language",
            "official": False, "status": "working"})


def records(country):
    """Every provenance note on one country, for its page and the audit."""
    return (country or {}).get("provenance") or {}


def convention_for(mode):
    key = MODE_CONVENTION.get(mode)
    return CONVENTIONS.get(key) if key else None

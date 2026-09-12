"""Question generators.

Every generator takes (world, subject_iso2, rng) and returns a question dict,
or None when that country lacks the data the question needs (plenty of small
states have no photographed leader, for instance). The caller retries with
another mode or another country.

A question dict looks like:

    {"mode", "subject", "prompt", "hint", "media", "choices", "answer"}

`answer` is stripped out before the question is sent to the browser and kept
server-side, so the answer never rides along with the question.
"""
import random

from . import provenance, supplement
from .data import ent_name
from .data_util import fold

# Distractors are drawn from the same continent where possible: guessing
# between four random countries is trivia, guessing between four neighbours is
# actually learning something.
def distractors(world, subject, n, pool=None, exclude=()):
    exclude = set(exclude) | {subject}
    if pool is None:
        pool = world.all_isos
    same = [i for i in pool
            if i not in exclude and world.continent_of(i) == world.continent_of(subject)]
    rest = [i for i in pool if i not in exclude and i not in same]
    random.shuffle(same)
    random.shuffle(rest)
    picked = (same + rest)[:n]
    return picked


def choice_row(world, isos, with_flag=False):
    out = []
    for i in isos:
        c = world.get(i)
        out.append({
            "key": i,
            "label": c["name"],
            "image": c["flag_thumb"] if with_flag else None,
        })
    random.shuffle(out)
    return out


MODE_ANSWER_KIND = {
    # The answer key is an ISO2 code, so challenge mode can accept either the
    # country's name typed in or a click on the map.
    "flag_to_country": "country", "country_to_flag": "country",
    "outline": "country", "capital_to_country": "country",
    "which_borders_both": "country", "border_odd_one_out": "country",
    "leader_photo": "country", "past_leader": "country",
    "famous_person": "country", "higher_lower": "country",
    "city_to_country": "country",
    "map_click": "map",                 # already answered by clicking
    "border_count": "number",
    # Everything else is a plain string the player can type.
    "capital_of": "text", "currency_of": "text", "language_of": "text",
    "government_of": "text", "continent_of": "text", "climate_of": "text",
    "leader_name": "text", "city_in_country": "text", "biggest_city": "text",
    "city_rank": "text",
    "main_export": "text", "main_industry": "text", "main_resource": "text",
    "trade_partner": "text", "landmark_of": "text", "highest_point_of": "text",
    "religion_of": "text", "eu_member": "text", "nato_member": "text",
    "war_when": "number", "war_order": "text", "war_between": "country",
    "figure_known_for": "text", "population_size": "text",
    "landmark_to_country": "country",
}


# Country names that read as nonsense without "the". "Is United States a
# member of NATO" is the kind of sentence that makes a quiz feel machine-made.
THE = {"US", "GB", "NL", "PH", "BS", "GM", "MV", "KM", "MH", "SB", "AE",
       "CZ", "DO", "CF", "CD", "CG", "SD", "SS", "VA", "KN", "VC"}


def the(world, iso):
    name = world.name(iso)
    return ("the " + name) if iso in THE else name


def _q(mode, subject, prompt, choices, answer, media=None, hint=None,
       highlight=None):
    """`highlight` names the thing the question was actually about.

    The fact card is a page of detail, and after a wrong answer the one line
    that would have won it is somewhere in the middle of it. Naming it here
    lets the card mark it and scroll to it -- miss a person and their photo is
    ringed, miss a city and its row lights up. It is a (kind, value) pair, the
    kind matching a section of the card.
    """
    return {
        "mode": mode, "subject": subject, "prompt": prompt, "hint": hint,
        "media": media or {}, "choices": choices, "answer": answer,
        "highlight": highlight,
        "answer_kind": MODE_ANSWER_KIND.get(mode, "text"),
        # What the answer is measured against, where that is a choice rather
        # than a fact -- "largest city" means nothing until you say whether
        # you mean the city or the conurbation. Shown under the question.
        "definition": provenance.convention_for(mode),
    }


# --------------------------------------------------------------------------
# Flags
# --------------------------------------------------------------------------

def flag_to_country(world, iso, rng):
    opts = [iso] + distractors(world, iso, 3)
    if len(opts) < 4:
        return None
    return _q("flag_to_country", iso, "Which country flies this flag?",
              choice_row(world, opts), iso,
              media={"type": "image", "url": world.get(iso)["flag_url"], "frame": "flag"})


def country_to_flag(world, iso, rng):
    opts = [iso] + distractors(world, iso, 3)
    if len(opts) < 4:
        return None
    # `caption` is the answer to "so whose flag was that one, then?" -- the
    # browser keeps it hidden while the question is live and prints it under
    # every flag once you have answered. Labelling only the right one teaches
    # you a quarter of what the question had on screen.
    choices = [{"key": i, "label": None, "image": world.get(i)["flag_url"],
                "caption": world.name(i)} for i in opts]
    rng.shuffle(choices)
    return _q("country_to_flag", iso, "Which of these is the flag of %s?" % world.name(iso),
              choices, iso)


# --------------------------------------------------------------------------
# Shape and position
# --------------------------------------------------------------------------

def outline(world, iso, rng):
    geom = world.shape(iso)
    if not geom:
        return None
    opts = [iso] + [i for i in distractors(world, iso, 6) if world.shape(i)][:3]
    if len(opts) < 4:
        return None
    return _q("outline", iso, "Which country is this?",
              choice_row(world, opts), iso,
              media={"type": "outline", "geometry": geom},
              hint="No labels, no scale -- just the shape.")


def map_click(world, iso, rng):
    if not world.shape(iso):
        return None
    return _q("map_click", iso, "Find %s on the map." % world.name(iso),
              [], world.get(iso)["iso3"], media={"type": "map"},
              hint="Click the country. Zoom in if it is a small one.")


# --------------------------------------------------------------------------
# Borders
# --------------------------------------------------------------------------

def border_odd_one_out(world, iso, rng):
    nb = world.neighbours(iso)
    if len(nb) < 3:
        return None
    non = [i for i in world.all_isos if i != iso and i not in nb]
    same_cont = [i for i in non if world.continent_of(i) == world.continent_of(iso)]
    if not same_cont:
        return None
    wrong = rng.choice(same_cont)
    picked = rng.sample(nb, 3) + [wrong]
    return _q("border_odd_one_out", iso,
              "Which of these does NOT share a land border with %s?" % world.name(iso),
              choice_row(world, picked, with_flag=True), wrong,
              highlight=("fact", "Land borders"))


def border_count(world, iso, rng):
    nb = world.neighbours(iso)
    if not nb:
        return None
    n = len(nb)
    opts = {n}
    while len(opts) < 4:
        delta = rng.choice([-3, -2, -1, 1, 2, 3, 4])
        cand = n + delta
        if cand >= 0:
            opts.add(cand)
    choices = [{"key": str(o), "label": str(o), "image": None} for o in sorted(opts)]
    rng.shuffle(choices)
    return _q("border_count", iso,
              "How many countries share a land border with %s?" % world.name(iso),
              choices, str(n), highlight=("fact", "Land borders"))


def which_borders_both(world, iso, rng):
    """Given two neighbours, name the country between them."""
    nb = world.neighbours(iso)
    if len(nb) < 2:
        return None
    a, b = rng.sample(nb, 2)
    # A distractor that also touches both would make two answers right --
    # Switzerland and Austria both border Germany and Italy.
    both = {i for i in world.all_isos
            if a in world.neighbours(i) and b in world.neighbours(i)}
    opts = [iso] + distractors(world, iso, 3, exclude=set(both) | {a, b})
    if len(opts) < 4:
        return None
    return _q("which_borders_both", iso,
              "Which country borders BOTH %s and %s?" % (world.name(a), world.name(b)),
              choice_row(world, opts, with_flag=True), iso,
              highlight=("fact", "Land borders"))


# --------------------------------------------------------------------------
# Capitals, and the plain-attribute questions
# --------------------------------------------------------------------------

def capital_of(world, iso, rng):
    c = world.get(iso)
    if not c.get("capitals"):
        return None
    answer = ent_name(c["capitals"][0])
    pool = [ent_name(world.get(i)["capitals"][0]) for i in distractors(world, iso, 8)
            if world.get(i).get("capitals")]
    capitals = {ent_name(x) for x in c["capitals"]}
    pool = [p for p in dict.fromkeys(pool) if p not in capitals][:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool]
    rng.shuffle(choices)
    q = _q("capital_of", iso, "Name a capital of %s." % c["name"], choices,
              answer, highlight=("fact", "Capital"))
    q["also"] = [ent_name(x) for x in c["capitals"][1:]]
    return q


def capital_to_country(world, iso, rng):
    c = world.get(iso)
    if not c.get("capitals"):
        return None
    opts = [iso] + distractors(world, iso, 3)
    if len(opts) < 4:
        return None
    return _q("capital_to_country", iso,
              "%s is the capital of which country?" % ent_name(c["capitals"][0]),
              choice_row(world, opts, with_flag=True), iso,
              highlight=("fact", "Capital"))


def _attribute(mode, field, prompt_tmpl):
    """Builds a generator for any list-valued country attribute."""
    def gen(world, iso, rng):
        c = world.get(iso)
        vals = c.get(field)
        if not vals:
            return None
        answer = ent_name(vals[0])
        mine = {ent_name(x) for x in vals}
        pool = []
        for i in distractors(world, iso, len(world.all_isos)):
            for x in world.get(i).get(field) or []:
                nm = ent_name(x)
                if nm and nm not in mine:
                    pool.append(nm)
        pool = list(dict.fromkeys(pool))[:3]
        if len(pool) < 3:
            return None
        choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool]
        rng.shuffle(choices)
        q = _q(mode, iso, prompt_tmpl % c["name"], choices, answer)
        q["also"] = list(mine - {answer})
        return q
    return gen


def language_of(world, iso, rng):
    """Asks for the most spoken language, not the official one. Plenty of
    countries have no official language, and several have an official language
    almost nobody speaks at home."""
    c = world.get(iso)

    def name_of(lang):
        return lang["name"] if isinstance(lang, dict) else lang

    langs = c.get("languages") or []
    if not langs:
        return None
    answer = name_of(langs[0])
    mine = {name_of(x) for x in langs}
    pool = []
    for i in distractors(world, iso, 20):
        for other in world.get(i).get("languages") or []:
            nm = name_of(other)
            if nm not in mine:
                pool.append(nm)
    pool = list(dict.fromkeys(pool))[:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool]
    rng.shuffle(choices)
    hint = None
    first = langs[0]
    if isinstance(first, dict) and first.get("share"):
        hint = "One language is spoken by %g%% of the country." % first["share"]
    return _q("language_of", iso,
              "What is the most widely spoken language in %s?" % the(world, iso),
              choices, answer, hint=hint, highlight=("fact", "Languages"))


def government_of(world, iso, rng):
    """Uses the Factbook's single government type, not Wikidata's list.

    China is a communist state, a socialist state, a unitary state and a
    one-party state, and Wikidata lists all four -- so the question offered
    four correct answers and marked three of them wrong. The Factbook states
    one type per country, which is the thing a quiz can ask about.
    """
    c = world.get(iso)
    answer = c.get("government_type")
    if not answer:
        return None
    mine = {answer.lower()}
    for x in c.get("government") or []:
        mine.add((ent_name(x) or "").lower())
    pool = []
    for i in distractors(world, iso, 40):
        other = world.get(i).get("government_type")
        if other and other.lower() not in mine:
            pool.append(other)
    pool = list(dict.fromkeys(pool))[:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool]
    rng.shuffle(choices)
    return _q("government_of", iso,
              "How is %s governed?" % c["name"], choices, answer,
              highlight=("fact", "Government"))


currency_of = _attribute("currency_of", "currencies", "What is the currency of %s?")


def continent_of(world, iso, rng):
    """Which continent, under one stated rule.

    Not `_attribute`: the imported continent list is unordered and counts
    overseas territory, so its first entry had France in Africa and the
    Netherlands in South America. provenance.py files each country under the
    continent containing its capital; a country that genuinely spans two has
    the second accepted as a typed answer and kept out of the wrong options.
    """
    spans = world.continents_of(iso)
    answer = spans[0] if spans else None
    if not answer or answer == "Unknown":
        return None
    mine = set(spans)
    pool = [x for x in ("Africa", "Asia", "Europe", "North America",
                        "South America", "Oceania") if x not in mine]
    rng.shuffle(pool)
    pool = pool[:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool]
    rng.shuffle(choices)
    q = _q("continent_of", iso, "Which continent is %s in?" % the(world, iso),
           choices, answer, highlight=("fact", "Continent"),
           hint=("It spans more than one; either is accepted."
                 if len(spans) > 1 else None))
    q["also"] = spans[1:]
    return q


# --------------------------------------------------------------------------
# People: current leaders, past leaders, famous faces
# --------------------------------------------------------------------------

def _leaders_with_photo(world, iso, key="leaders"):
    return [p for p in (world.get(iso).get(key) or []) if p.get("image") and p.get("name")]


def leader_photo(world, iso, rng):
    people = _leaders_with_photo(world, iso)
    if not people:
        return None
    p = rng.choice(people)
    opts = [iso] + distractors(world, iso, 3)
    if len(opts) < 4:
        return None
    return _q("leader_photo", iso, "Which country does this person currently lead?",
              choice_row(world, opts, with_flag=True), iso,
              media={"type": "image", "url": p["image"], "frame": "portrait"},
              hint=p["role"].replace("_", " ").title(),
              highlight=("person", p["name"]))


def leader_name(world, iso, rng):
    people = _leaders_with_photo(world, iso)
    if not people:
        return None
    p = rng.choice(people)
    role = "head of state" if p["role"] == "head_of_state" else "head of government"
    pool = []
    for i in distractors(world, iso, 12):
        for q in _leaders_with_photo(world, i):
            if q["name"] != p["name"]:
                pool.append(q["name"])
    pool = list(dict.fromkeys(pool))[:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [p["name"]] + pool]
    rng.shuffle(choices)
    return _q("leader_name", iso,
              "Who is the current %s of %s?" % (role, world.name(iso)),
              choices, p["name"], highlight=("person", p["name"]))


def past_leader(world, iso, rng):
    people = _leaders_with_photo(world, iso, "past_leaders")
    people = [p for p in people if p.get("fame", 0) > 40]
    if not people:
        return None
    p = rng.choice(people)
    opts = [iso] + distractors(world, iso, 3)
    if len(opts) < 4:
        return None
    span = " ".join(x for x in (p.get("start"), "-", p.get("end")) if x)
    return _q("past_leader", iso, "Which country did %s lead?" % p["name"],
              choice_row(world, opts, with_flag=True), iso,
              media={"type": "image", "url": p["image"], "frame": "portrait"},
              hint=("In power %s" % span) if p.get("start") else None,
              highlight=("person", p["name"]))


def famous_person(world, iso, rng):
    people = [p for p in (world.get(iso).get("famous") or []) if p.get("image")]
    if not people:
        return None
    p = rng.choice(people[:10])
    opts = [iso] + distractors(world, iso, 3)
    if len(opts) < 4:
        return None
    occ = ", ".join(p.get("occupations", [])[:2]) or "notable figure"
    life = p.get("born")
    hint = "%s%s" % (occ.capitalize(), (", born %s" % life) if life else "")
    return _q("famous_person", iso, "%s is from which country?" % p["name"],
              choice_row(world, opts, with_flag=True), iso,
              media={"type": "image", "url": p["image"], "frame": "portrait"},
              hint=hint, highlight=("person", p["name"]))


# --------------------------------------------------------------------------
# Cities
# --------------------------------------------------------------------------
# The dataset holds the five largest cities of each country, ranked, and
# nothing was asking about them. A city name is the piece of a country most
# people actually meet first.

ORDINALS = ["largest", "second largest", "third largest",
            "fourth largest", "fifth largest"]


def _cities(world, iso):
    return [c for c in (world.get(iso).get("cities") or []) if c.get("name")]


def city_in_country(world, iso, rng):
    """One real city of this country against three from elsewhere."""
    mine = _cities(world, iso)
    if not mine:
        return None
    answer = rng.choice(mine)["name"]
    # Distractors come from the same continent first, so the question is
    # "which of these is Nigerian" rather than "which of these is African".
    ours = {c["name"] for c in mine}
    pool = []
    for other in distractors(world, iso, 25):
        for city in _cities(world, other):
            if city["name"] not in ours:
                pool.append(city["name"])
    pool = list(dict.fromkeys(pool))
    if len(pool) < 3:
        return None
    rng.shuffle(pool)
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool[:3]]
    rng.shuffle(choices)
    return _q("city_in_country", iso,
              "Which of these is a city in %s?" % world.name(iso), choices, answer,
              highlight=("city", answer))


def city_to_country(world, iso, rng):
    """The other direction: name the country a city belongs to."""
    mine = _cities(world, iso)
    if not mine:
        return None
    city = rng.choice(mine)
    # A city name another country also has would make two answers right --
    # and compared as raw strings, "Cordoba" and "Cordoba" with an accent
    # slipped past, so the comparison is on folded names.
    want = fold(city["name"])
    clashes = {i for i in world.all_isos
               if i != iso and any(fold(c["name"]) == want
                                   for c in _cities(world, i))}
    opts = [iso] + distractors(world, iso, 3, exclude=clashes)
    if len(opts) < 4:
        return None
    return _q("city_to_country", iso, "%s is a city in which country?" % city["name"],
              choice_row(world, opts, with_flag=True), iso,
              hint=("Population about {:,}".format(city["population"])
                    if city.get("population") else None),
              highlight=("city", city["name"]))


def city_rank(world, iso, rng):
    """Where a city sits in its own country's league table.

    Only asked where the gap to the neighbouring city is wide enough that the
    ranking is a fact rather than a coin toss between two places of much the
    same size.
    """
    cities = _cities(world, iso)
    if len(cities) < 4:
        return None
    usable = []
    for i, city in enumerate(cities):
        if not city.get("population"):
            continue
        near = [cities[j] for j in (i - 1, i + 1)
                if 0 <= j < len(cities) and cities[j].get("population")]
        # A 15% gap either side: closer than that and the census year decides
        # the answer, not the geography.
        if all(abs(n["population"] - city["population"]) / float(city["population"]) > 0.15
               for n in near):
            usable.append(i)
    if not usable:
        return None
    i = rng.choice(usable)
    answer = ORDINALS[i]
    choices = [{"key": o, "label": o.capitalize(), "image": None}
               for o in ORDINALS[:len(cities)]]
    rng.shuffle(choices)
    return _q("city_rank", iso,
              "Where does %s rank among the cities of %s?"
              % (cities[i]["name"], world.name(iso)),
              choices, answer, hint="By population, largest first.",
              highlight=("city", cities[i]["name"]))


def biggest_city(world, iso, rng):
    """Which of this country's own cities is the biggest."""
    cities = _cities(world, iso)
    if len(cities) < 4:
        return None
    top = cities[0]
    if not top.get("population") or not cities[1].get("population"):
        return None
    if (top["population"] - cities[1]["population"]) / float(top["population"]) < 0.15:
        return None            # too close to call from this data
    picks = [top] + rng.sample(cities[1:], 3)
    choices = [{"key": c["name"], "label": c["name"], "image": None} for c in picks]
    rng.shuffle(choices)
    return _q("biggest_city", iso,
              "Which is the largest city in %s?" % world.name(iso),
              choices, top["name"], highlight=("city", top["name"]))


# --------------------------------------------------------------------------
# Trade, resources, landmarks and history
# --------------------------------------------------------------------------
# Everything the country pages link to should be askable. These build a
# question from any list-valued field, taking care that no distractor is
# something the country also has -- with exports and industries that happens
# constantly, since half the world sells refined petroleum.

def _list_question(mode, field, prompt_tmpl, hint=None, econ=False):
    def gen(world, iso, rng):
        c = world.get(iso)
        vals = (c.get("economy") or {}).get(field) if econ else c.get(field)
        vals = [v if isinstance(v, str) else (v or {}).get("name")
                for v in (vals or [])]
        vals = [v for v in vals if v]
        if not vals:
            return None
        answer = rng.choice(vals[:3])
        mine = {v.lower() for v in vals}
        pool = []
        for other in distractors(world, iso, 40):
            o = world.get(other)
            theirs = (o.get("economy") or {}).get(field) if econ else o.get(field)
            for v in theirs or []:
                nm = v if isinstance(v, str) else (v or {}).get("name")
                if nm and nm.lower() not in mine:
                    pool.append(nm)
        pool = list(dict.fromkeys(pool))
        if len(pool) < 3:
            return None
        rng.shuffle(pool)
        choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool[:3]]
        rng.shuffle(choices)
        return _q(mode, iso, prompt_tmpl % c["name"], choices, answer, hint=hint)
    return gen


main_export = _list_question(
    "main_export", "exports", "Which of these does %s export?", econ=True,
    hint="One of its top five, by value.")
main_industry = _list_question(
    "main_industry", "industries", "Which of these is a major industry in %s?",
    econ=True)
main_resource = _list_question(
    "main_resource", "resources", "Which natural resource does %s have?",
    econ=True)
religion_of = _list_question(
    "religion_of", "religions", "Which religion is practised in %s?")


def landmark_of(world, iso, rng):
    """Name the landmark that belongs to this country.

    Ranges, rivers, deserts and seas are excluded as answers: the Andes are in
    seven countries and the dataset only knows about the ones it happened to
    record, so "which of these is in Chile" had more than one right answer and
    no way to tell.
    """
    mine = [m["name"] for m in (world.get(iso).get("landmarks") or [])
            if m.get("name")]
    askable = [m for m in mine if not provenance.is_shared_landmark(m)]
    if not askable:
        return None
    answer = rng.choice(askable)
    ours = {m.lower() for m in mine}
    pool = []
    for other in distractors(world, iso, 60):
        for m in world.get(other).get("landmarks") or []:
            nm = m.get("name")
            # A shared landmark is no safer as a wrong option than as an
            # answer: the Alps are not "in Austria and nowhere else" either.
            if nm and nm.lower() not in ours and not provenance.is_shared_landmark(nm):
                pool.append(nm)
    pool = list(dict.fromkeys(pool))
    if len(pool) < 3:
        return None
    rng.shuffle(pool)
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool[:3]]
    rng.shuffle(choices)
    return _q("landmark_of", iso, "Which of these is in %s?" % world.name(iso),
              choices, answer, highlight=("landmark", answer))


def highest_point_of(world, iso, rng):
    peaks = [p.get("name") for p in (world.get(iso).get("highest_point") or [])
             if isinstance(p, dict) and p.get("name")]
    if not peaks:
        return None
    answer = peaks[0]
    pool = []
    for other in distractors(world, iso, 40):
        for p in world.get(other).get("highest_point") or []:
            nm = p.get("name") if isinstance(p, dict) else p
            if nm and nm != answer:
                pool.append(nm)
    pool = list(dict.fromkeys(pool))
    if len(pool) < 3:
        return None
    rng.shuffle(pool)
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool[:3]]
    rng.shuffle(choices)
    return _q("highest_point_of", iso,
              "What is the highest point in %s?" % world.name(iso), choices, answer)


# The Factbook's shorthand for the handful of partners that dominate the
# table, against the names a person would type.
PARTNER_ALIASES = {
    "USA": ["United States", "United States of America", "America"],
    "UK": ["United Kingdom", "Britain", "Great Britain"],
    "South Korea": ["Korea, South", "Republic of Korea"],
    "North Korea": ["Korea, North"],
    "UAE": ["United Arab Emirates", "Emirates"],
    "Netherlands": ["Holland"],
    "Czechia": ["Czech Republic"],
    "Turkey (Turkiye)": ["Turkey", "Turkiye"],
    "Burma": ["Myanmar"],
    "Cote d'Ivoire": ["Ivory Coast"],
}


def _possessive(world, iso):
    name = the(world, iso)
    return name + ("'" if name.endswith("s") else "'s")


def trade_partner(world, iso, rng):
    """Who a country's exports actually go to."""
    partners = [p["name"] for p in
                ((world.get(iso).get("economy") or {}).get("export_partners") or [])
                if p.get("name")]
    if len(partners) < 2:
        return None
    answer = partners[0]
    mine = {p.lower() for p in partners}
    pool = []
    for other in distractors(world, iso, 40):
        for p in ((world.get(other).get("economy") or {}).get("export_partners")
                  or []):
            if p.get("name") and p["name"].lower() not in mine:
                pool.append(p["name"])
    pool = list(dict.fromkeys(pool))
    if len(pool) < 3:
        return None
    rng.shuffle(pool)
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool[:3]]
    rng.shuffle(choices)
    q = _q("trade_partner", iso,
           "Who is the biggest buyer of %s exports?" % _possessive(world, iso),
           choices, answer,
           hint="By share of goods exports, most recent year reported.")
    # The Factbook writes "USA", "UK", "South Korea"; a typed answer should
    # not have to guess which shorthand the table used.
    q["also"] = PARTNER_ALIASES.get(answer, [])
    return q


# --------------------------------------------------------------------------
# Numbers and climate
# --------------------------------------------------------------------------

def higher_lower(world, iso, rng):
    field, word = rng.choice([("population", "a larger population"),
                              ("area", "a larger land area")])
    c = world.get(iso)
    if not c.get(field):
        return None
    pool = [i for i in distractors(world, iso, 25) if world.get(i).get(field)]
    # Pick an opponent that is close enough to be a real question but far
    # enough that the data's rounding does not decide it.
    ratios = [(abs(world.get(i)[field] / c[field] - 1), i) for i in pool]
    ratios = [(r, i) for r, i in ratios if 0.15 < r < 4]
    if not ratios:
        return None
    ratios.sort()
    other = rng.choice(ratios[:8])[1]
    winner = iso if c[field] >= world.get(other)[field] else other
    choices = choice_row(world, [iso, other], with_flag=True)
    return _q("higher_lower", iso, "Which has %s?" % word, choices, winner,
              highlight=("fact", "Population" if field == "population" else "Area"))


def climate_of(world, iso, rng):
    """The zones are deliberately few and far apart.

    Brazil used to be "Tropical" with "Equatorial tropical" among the wrong
    answers, which is not a question anyone can answer. The zones now come
    from the country's own climate description and no two of them overlap.
    """
    c = world.get(iso)
    zone = c.get("climate_zone")
    if not zone:
        return None
    pool = []
    for i in distractors(world, iso, 60):
        z = world.get(i).get("climate_zone")
        if z and z != zone:
            pool.append(z)
    pool = list(dict.fromkeys(pool))[:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [zone] + pool]
    rng.shuffle(choices)
    return _q("climate_of", iso,
              "Which climate does %s mostly have?" % c["name"], choices, zone,
              highlight=("fact", "Climate"))


def driving_side(world, iso, rng):
    side = world.get(iso).get("drives_on")
    if side not in ("left", "right"):
        return None
    return _q("driving_side", iso, "On which side of the road do people drive in %s?" % world.name(iso),
              [{"key": x, "label": x.capitalize(), "image": None} for x in ("left", "right")],
              side, highlight=("fact", "Driving side"))


def calling_code(world, iso, rng):
    answer = world.get(iso).get("calling_code")
    if not answer:
        return None
    pool = sorted({world.get(i).get("calling_code") for i in world.all_isos
                   if world.get(i).get("calling_code") and world.get(i).get("calling_code") != answer})
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + rng.sample(pool, 3)]
    rng.shuffle(choices)
    q = _q("calling_code", iso, "What international calling code is used for %s?" % world.name(iso),
           choices, answer, highlight=("fact", "Calling code"))
    q["also"] = [answer.lstrip("+")]
    return q


# Landmarks whose last word is a common noun take "the": the Eiffel Tower,
# the Great Wall, the Blue Mosque -- but Machu Picchu, Mount Fuji and Petra do
# not. Getting this wrong is small and constant, and it is what makes a
# generated prompt read as generated.
_THE_NOUNS = {
    "tower", "wall", "falls", "palace", "museum", "bridge", "cathedral",
    "mosque", "temple", "statue", "canyon", "desert", "sea", "islands",
    "mountains", "valley", "gardens", "park", "ruins", "basilica", "castle",
    "fort", "fortress", "colosseum", "acropolis", "pyramids", "louvre",
    "kremlin", "abbey", "monastery", "citadel", "reef", "rainforest",
    "delta", "glacier", "caves", "cave", "gorge", "square", "opera",
    "cemetery", "memorial", "observatory", "peninsula", "strait", "canal",
    "army", "gate", "pagoda", "shrine", "monument", "lighthouse", "bay",
    "lagoon", "plateau", "springs", "crater", "dunes", "forest", "coast",
}


def the_landmark(name):
    words = (name or "").split()
    if len(words) > 1 and (words[-1].lower() in _THE_NOUNS
                           or words[0].lower() in _THE_NOUNS):
        return "the " + name
    return name


def landmark_to_country(world, iso, rng):
    landmarks = [m for m in world.get(iso).get("landmarks", [])
                 if m.get("name") and not provenance.is_shared_landmark(m["name"])]
    if not landmarks:
        return None
    name = rng.choice(landmarks)["name"]
    # Recorded ownership is necessary but not sufficient: a range crossing a
    # border may simply not have been recorded against its other countries,
    # which is what the shared-landmark list above is for.
    owners = {i for i in world.all_isos
              if any(m.get("name") == name
                     for m in world.get(i).get("landmarks", []))}
    if len(owners) != 1:
        return None
    opts = [iso] + distractors(world, iso, 3)
    return _q("landmark_to_country", iso,
              "In which country is %s?" % the_landmark(name),
              choice_row(world, opts), iso, highlight=("landmark", name))


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------
# None of these asks whether a country took part in a war. The curated table
# names principal belligerents, and a list of principals cannot settle
# participation in either direction -- which is how the United States came to
# be marked wrong for the Iraq War. What the table does hold, and what is
# asked about here, is dates, the order events happened in, the two principals
# of a war fought between exactly two states, and hand-written notes on who a
# historical figure was.

def war_when(world, iso, rng):
    """The year a conflict this country was in began."""
    wars = supplement.curated_wars_for(iso)
    if not wars:
        return None
    name, start = rng.choice(wars)
    year = int(start)
    opts = {year}
    for delta in rng.sample([-14, -11, -9, -7, -5, -3, 3, 5, 7, 9, 11, 14], 12):
        if len(opts) >= 4:
            break
        # No negative years, and nothing later than the present.
        if 0 < year + delta <= 2026:
            opts.add(year + delta)
    if len(opts) < 4:
        return None
    choices = [{"key": str(o), "label": str(o), "image": None}
               for o in sorted(opts)]
    rng.shuffle(choices)
    return _q("war_when", iso, "In which year did the %s begin?" % name,
              choices, str(year), highlight=("war", name),
              hint="%s was one of the countries involved." % world.name(iso))


def war_order(world, iso, rng):
    """Which of four conflicts came first."""
    mine = supplement.curated_wars_for(iso)
    if not mine:
        return None
    years = supplement.war_years()
    # Every option at least eight years from every other, so the answer does
    # not turn on which month a war is dated from.
    picked = [rng.choice(mine)]
    pool = [(n, y[0]) for n, y in years.items() if y[0]]
    rng.shuffle(pool)
    for name, start in pool:
        if len(picked) >= 4:
            break
        if any(n == name or abs(int(start) - int(s2)) < 8 for n, s2 in picked):
            continue
        picked.append((name, start))
    if len(picked) < 4:
        return None
    answer = min(picked, key=lambda pair: int(pair[1]))[0]
    choices = [{"key": n, "label": n, "image": None} for n, _ in picked]
    rng.shuffle(choices)
    return _q("war_order", iso, "Which of these conflicts began first?",
              choices, answer,
              hint="One of them involved %s." % world.name(iso),
              highlight=("war", answer))


def war_between(world, iso, rng):
    """Only for wars with exactly two principal states, so one answer."""
    pairs = supplement.bilateral_for(iso)
    if not pairs:
        return None
    name, start, other = rng.choice(pairs)
    if not world.get(other):
        return None
    opts = [other] + distractors(world, other, 3, exclude={iso, other})
    if len(opts) < 4:
        return None
    return _q("war_between", iso,
              "The %s was fought between %s and which country?"
              % (name, the(world, iso)),
              choice_row(world, opts, with_flag=True), other,
              hint="It began in %s." % start, highlight=("war", name))


def figure_known_for(world, iso, rng):
    """Who a hand-written historical figure was.

    Only notes of three words or more: "Footballer" against "Composer" is a
    question about the word, not about the person.
    """
    mine = [(n, note) for n, note in supplement.figures_for(iso)
            if len(note.split()) >= 3]
    if not mine:
        return None
    name, answer = rng.choice(mine)
    pool = []
    for other in distractors(world, iso, 40):
        for _, note in supplement.figures_for(other):
            if len(note.split()) >= 3 and note != answer:
                pool.append(note)
    pool = list(dict.fromkeys(pool))
    if len(pool) < 3:
        return None
    rng.shuffle(pool)
    choices = [{"key": x, "label": x, "image": None}
               for x in [answer] + pool[:3]]
    rng.shuffle(choices)
    return _q("figure_known_for", iso, "Who was %s?" % name, choices, answer,
              hint="From %s." % world.name(iso), highlight=("person", name))


# --------------------------------------------------------------------------
# Membership and size
# --------------------------------------------------------------------------

def _membership(mode, org):
    """Yes or no, against a membership list that was checked by hand.

    The imported member_of still has the United Kingdom in the European Union
    and leaves the Netherlands out of it, so only the two organisations with a
    verified list in provenance.py can be asked about at all.
    """
    def gen(world, iso, rng):
        member = world.member_of_verified(iso, org)
        if member is None:
            return None
        answer = "Yes" if member else "No"
        return _q(mode, iso,
                  "Is %s a member of %s?" % (the(world, iso), org),
                  [{"key": x, "label": x, "image": None}
                   for x in ("Yes", "No")],
                  answer, highlight=("fact", "Member of"))
    return gen


eu_member = _membership("eu_member", "European Union")
nato_member = _membership("nato_member", "NATO")

# Order-of-magnitude bands. Population is the one number in the dataset worth
# knowing roughly and hopeless to know exactly, and a band is an honest way to
# ask about a figure whose census year varies from country to country.
POP_BANDS = [
    (0, 100000, "under 100 thousand"),
    (100000, 1000000, "100 thousand to 1 million"),
    (1000000, 10000000, "1 to 10 million"),
    (10000000, 50000000, "10 to 50 million"),
    (50000000, 150000000, "50 to 150 million"),
    (150000000, 500000000, "150 to 500 million"),
    (500000000, 10000000000, "over 500 million"),
]


def population_size(world, iso, rng):
    pop = world.get(iso).get("population")
    if not pop:
        return None
    idx = next((i for i, (lo, hi, _) in enumerate(POP_BANDS)
                if lo <= pop < hi), None)
    if idx is None:
        return None
    lo, hi, answer = POP_BANDS[idx]
    # A figure within a tenth of a band edge is a coin toss between two right
    # answers as soon as the census year moves, so it is not asked about.
    if idx > 0 and pop - lo < 0.1 * (hi - lo):
        return None
    near = [POP_BANDS[i][2] for i in (idx - 2, idx - 1, idx + 1, idx + 2)
            if 0 <= i < len(POP_BANDS) and i != idx]
    rest = [b[2] for i, b in enumerate(POP_BANDS) if i != idx]
    pool = list(dict.fromkeys(near + rest))[:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x.capitalize(), "image": None}
               for x in [answer] + pool]
    rng.shuffle(choices)
    return _q("population_size", iso,
              "Roughly how many people live in %s?" % the(world, iso),
              choices, answer, highlight=("fact", "Population"))


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

MODES = {
    "driving_side": ("Everyday life", "Driving side", driving_side),
    "calling_code": ("Everyday life", "International calling code", calling_code),
    "landmark_to_country": ("Landmarks", "Name the country from a landmark", landmark_to_country),
    "flag_to_country":   ("Flags", "Name the country from its flag", flag_to_country),
    "country_to_flag":   ("Flags", "Pick the right flag", country_to_flag),
    "outline":           ("Shapes", "Name the country from its outline", outline),
    "map_click":         ("Map", "Find it on the world map", map_click),
    "border_odd_one_out": ("Borders", "Spot the country that is not a neighbour", border_odd_one_out),
    "border_count":      ("Borders", "Count the neighbours", border_count),
    "which_borders_both": ("Borders", "Name the country in between", which_borders_both),
    "capital_of":        ("Capitals", "Name the capital", capital_of),
    "capital_to_country": ("Capitals", "Name the country from its capital", capital_to_country),
    "currency_of":       ("Politics", "Name the currency", currency_of),
    "language_of":       ("Politics", "Name the most spoken language", language_of),
    "government_of":     ("Politics", "Name the form of government", government_of),
    "continent_of":      ("Politics", "Name the continent", continent_of),
    "leader_photo":      ("Leaders", "Whose leader is this?", leader_photo),
    "leader_name":       ("Leaders", "Name the current leader", leader_name),
    "past_leader":       ("Leaders", "Name the country a past leader ran", past_leader),
    "famous_person":     ("People", "Place the famous face", famous_person),
    "higher_lower":      ("Numbers", "Bigger or smaller?", higher_lower),
    "climate_of":        ("Climate", "Name the climate zone", climate_of),
    "city_in_country":   ("Cities", "Spot the city that belongs here", city_in_country),
    "city_to_country":   ("Cities", "Name the country from one of its cities", city_to_country),
    "biggest_city":      ("Cities", "Name the largest city", biggest_city),
    "city_rank":         ("Cities", "Rank a city by size", city_rank),
    "main_export":       ("Trade", "Name what it sells", main_export),
    "main_industry":     ("Trade", "Name a major industry", main_industry),
    "main_resource":     ("Trade", "Name what is in the ground", main_resource),
    "trade_partner":     ("Trade", "Name its biggest customer", trade_partner),
    "landmark_of":       ("Landmarks", "Place the landmark", landmark_of),
    "highest_point_of":  ("Landmarks", "Name the highest point", highest_point_of),
    "religion_of":       ("Politics", "Name a religion practised there", religion_of),
    "eu_member":         ("Politics", "In the European Union or not", eu_member),
    "nato_member":       ("Politics", "In NATO or not", nato_member),
    "population_size":   ("Numbers", "How many people live there", population_size),
    "war_when":          ("History", "Date the conflict", war_when),
    "war_order":         ("History", "Put the conflicts in order", war_order),
    "war_between":       ("History", "Name the other side", war_between),
    "figure_known_for":  ("History", "Who were they?", figure_known_for),
}

# What the front page offers. "Grand Tour" mixes everything.
CATEGORIES = [
    ("grand_tour", "Grand Tour", "Everything, shuffled. The full quiz show.", None),
    ("everyday", "Everyday Life", "Practical facts: driving, calling codes and money.", ["driving_side", "calling_code", "currency_of"]),
    ("flags", "Flags", "Flags in both directions.", ["flag_to_country", "country_to_flag"]),
    ("shapes", "Shapes", "Name the country from its silhouette alone.", ["outline"]),
    ("map", "Find It on the Map", "Click the country on a bare world map.", ["map_click"]),
    ("borders", "Borders", "Who touches whom.", ["border_odd_one_out", "border_count", "which_borders_both"]),
    ("capitals", "Capitals", "Capitals, both directions.", ["capital_of", "capital_to_country"]),
    ("leaders", "Leaders", "Current and historical, with photos.", ["leader_photo", "leader_name", "past_leader"]),
    ("people", "Famous People", "Place the face.", ["famous_person"]),
    ("politics", "Politics & Money", "Government, currency, language.", ["government_of", "currency_of", "language_of"]),
    ("cities", "Cities", "Name them, place them, rank them by size.",
     ["city_in_country", "city_to_country", "biggest_city", "city_rank"]),
    ("trade", "Trade & Industry", "What countries sell, dig up and make.",
     ["main_export", "main_industry", "main_resource", "trade_partner"]),
    ("landmarks", "Landmarks", "Wonders, mountains and the highest points.",
     ["landmark_of", "highest_point_of", "landmark_to_country"]),
    ("history", "History", "When it happened, who fought whom, who they were.",
     ["war_when", "war_order", "war_between", "figure_known_for", "past_leader"]),
    ("world", "Climate & Numbers", "Climate, size, population.",
     ["climate_of", "higher_lower", "continent_of", "population_size"]),
    ("institutions", "Alliances", "Who belongs to what.",
     ["eu_member", "nato_member"]),
]

CATEGORY_MODES = {key: modes for key, _, _, modes in CATEGORIES}

# These prompts depend on visible options or admit many valid free answers.
CHOICE_REQUIRED = {"country_to_flag", "border_odd_one_out", "which_borders_both",
                   "higher_lower", "city_in_country", "main_export", "main_industry",
                   "main_resource", "landmark_of", "religion_of",
                   # "Yes" typed blind is a coin toss, "which came first"
                   # needs the four names on screen, and a population band is
                   # a phrase nobody would type unprompted.
                   "eu_member", "nato_member", "war_order", "population_size",
                   "figure_known_for"}

COUNTRY_STUDY_MODES = {"country_to_flag", "capital_of", "currency_of", "language_of",
    "government_of", "continent_of", "border_count", "border_odd_one_out", "leader_name",
    "city_in_country", "biggest_city", "city_rank", "main_export", "main_industry",
    "main_resource", "trade_partner", "landmark_of", "highest_point_of", "climate_of",
    "driving_side", "calling_code", "eu_member", "nato_member", "population_size",
    "war_when", "war_order", "war_between", "figure_known_for"}


# --------------------------------------------------------------------------
# What can actually be asked about one country
# --------------------------------------------------------------------------
# Country practice used to sample from every mode the category allowed and
# hope. For a country with four recorded cities and no photographed leader
# that means a run of retries, a repeated question, or -- for the sparsest
# countries -- a failure to build anything at all. Asking each generator once,
# up front, turns "hope" into a list.

_SUPPORTED = {}

# A generator can fail on one draw and succeed on the next: city_rank needs
# two cities with a wide enough gap between them and picks at random. Three
# seeds is enough to stop calling those modes unavailable.
_SUPPORT_TRIES = 3


def supported_modes(world, iso, modes=None):
    """The modes that can build a question about this country."""
    got = _SUPPORTED.get(iso)
    if got is None:
        ok = set()
        for mode, (_, _, gen) in MODES.items():
            for attempt in range(_SUPPORT_TRIES):
                rng = random.Random("%s/%s/%d" % (iso, mode, attempt))
                try:
                    if gen(world, iso, rng):
                        ok.add(mode)
                        break
                except Exception:
                    break
        got = _SUPPORTED[iso] = frozenset(ok)
    if modes is None:
        return got
    return [m for m in modes if m in got]


def missing_topics(world, iso, modes=None):
    """The question types this country has no data for, by their label.

    Shown on the country's own practice page. "Landmarks: no data recorded"
    is a fact about the dataset worth admitting to, and much better than a
    topic that silently never comes up.
    """
    got = supported_modes(world, iso)
    grouped = {}
    for mode in (modes or MODES):
        if mode in MODES:
            grouped.setdefault(MODES[mode][0], []).append(mode)
    # A topic counts as missing only when none of its modes work. France has
    # no recorded religions, but saying "Politics: unavailable" about a country
    # whose government, currency and language are all askable is just wrong.
    return {label: [MODES[m][1] for m in ms]
            for label, ms in grouped.items()
            if not any(m in got for m in ms)}


def balanced_mode(rng, modes, used):
    """Pick a mode, preferring ones this run has asked about least.

    Uniform sampling over twenty-one modes gives a repeat inside the first few
    questions more often than not, and on a single country a repeat is the
    same question twice. Drawing from the least-used modes spreads a practice
    run over the topics rather than over the dice.
    """
    if not modes:
        return None
    fewest = min(used.get(m, 0) for m in modes)
    return rng.choice([m for m in modes if used.get(m, 0) == fewest])


def domains_for(modes):
    """Mode keys grouped under the topic label the player sees."""
    out = {}
    for mode in modes:
        if mode in MODES:
            out.setdefault(MODES[mode][0], []).append(mode)
    return out


# Every mode, under the heading it is filed against. Progress reports country
# mastery by domain rather than by mode, because "Cities 4/5" is a sentence
# about what you know and "biggest_city 4/5" is a sentence about the code.
DOMAINS = domains_for(MODES)
MODE_DOMAIN = {m: label for label, ms in DOMAINS.items() for m in ms}

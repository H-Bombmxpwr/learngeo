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

from .data import ent_name

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


def _q(mode, subject, prompt, choices, answer, media=None, hint=None):
    return {
        "mode": mode, "subject": subject, "prompt": prompt, "hint": hint,
        "media": media or {}, "choices": choices, "answer": answer,
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
              choice_row(world, picked, with_flag=True), wrong)


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
              choices, str(n))


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
              choice_row(world, opts, with_flag=True), iso)


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
    pool = [p for p in dict.fromkeys(pool) if p != answer][:3]
    if len(pool) < 3:
        return None
    choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool]
    rng.shuffle(choices)
    return _q("capital_of", iso, "What is the capital of %s?" % c["name"], choices, answer)


def capital_to_country(world, iso, rng):
    c = world.get(iso)
    if not c.get("capitals"):
        return None
    opts = [iso] + distractors(world, iso, 3)
    if len(opts) < 4:
        return None
    return _q("capital_to_country", iso,
              "%s is the capital of which country?" % ent_name(c["capitals"][0]),
              choice_row(world, opts, with_flag=True), iso)


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
        for i in distractors(world, iso, 14):
            for x in world.get(i).get(field) or []:
                nm = ent_name(x)
                if nm and nm not in mine:
                    pool.append(nm)
        pool = list(dict.fromkeys(pool))[:3]
        if len(pool) < 3:
            return None
        choices = [{"key": x, "label": x, "image": None} for x in [answer] + pool]
        rng.shuffle(choices)
        return _q(mode, iso, prompt_tmpl % c["name"], choices, answer)
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
              "What is the most spoken language in %s?" % c["name"], choices,
              answer, hint=hint)


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
              "How is %s governed?" % c["name"], choices, answer)


currency_of = _attribute("currency_of", "currencies", "What is the currency of %s?")
continent_of = _attribute("continent_of", "continents", "Which continent is %s in?")


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
              hint=p["role"].replace("_", " ").title())


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
              choices, p["name"])


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
              hint=("In power %s" % span) if p.get("start") else None)


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
              hint=hint)


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
    return _q("higher_lower", iso, "Which has %s?" % word, choices, winner)


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
              "Which climate does %s mostly have?" % c["name"], choices, zone)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

MODES = {
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
}

# What the front page offers. "Grand Tour" mixes everything.
CATEGORIES = [
    ("grand_tour", "Grand Tour", "Everything, shuffled. The full quiz show.", None),
    ("flags", "Flags", "Flags in both directions.", ["flag_to_country", "country_to_flag"]),
    ("shapes", "Shapes", "Name the country from its silhouette alone.", ["outline"]),
    ("map", "Find It on the Map", "Click the country on a bare world map.", ["map_click"]),
    ("borders", "Borders", "Who touches whom.", ["border_odd_one_out", "border_count", "which_borders_both"]),
    ("capitals", "Capitals", "Capitals, both directions.", ["capital_of", "capital_to_country"]),
    ("leaders", "Leaders", "Current and historical, with photos.", ["leader_photo", "leader_name", "past_leader"]),
    ("people", "Famous People", "Place the face.", ["famous_person"]),
    ("politics", "Politics & Money", "Government, currency, language.", ["government_of", "currency_of", "language_of"]),
    ("world", "Climate & Numbers", "Climate, size, population.", ["climate_of", "higher_lower", "continent_of"]),
]

CATEGORY_MODES = {key: modes for key, _, _, modes in CATEGORIES}

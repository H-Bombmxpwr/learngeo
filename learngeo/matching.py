"""Judging a typed answer.

Challenge mode drops the four options, which means the app has to decide
whether what someone typed is the same thing as the answer. Being strict about
it is the fastest way to make a quiz infuriating: nobody should lose a life
for "Cote d'Ivoire" against "Ivory Coast", for "USA", or for a missing accent
on Asuncion.

The rules, in order:

1. Fold accents and case, drop punctuation and the leading "the".
2. Expand the abbreviations that only ever appear one way in a dataset and
   the other way in a person's typing: St., Ste., Mt., Ft., "&".
3. Accept any recorded alias, including the ISO codes.
4. Accept a one-character typo on anything long enough for that to be a typo
   rather than a different word.

It stays deliberately on the generous side. The point is to find out whether
you knew it, and a spelling test is a different game.
"""
import difflib
import re

from .data_util import fold

# Names people actually type, against the dataset's name. Only where the
# alternative is in common use -- not a dumping ground for near misses.
ALIASES = {
    "US": ["usa", "us", "united states", "united states of america", "america"],
    "GB": ["uk", "united kingdom", "britain", "great britain", "england"],
    "NL": ["holland", "the netherlands"],
    "CI": ["ivory coast", "cote divoire", "cote d ivoire"],
    "CV": ["cape verde", "cabo verde"],
    "MM": ["burma", "myanmar"],
    "CZ": ["czech republic", "czechia"],
    "KP": ["north korea", "dprk"],
    "KR": ["south korea"],
    "CD": ["drc", "dr congo", "congo kinshasa", "democratic republic of the congo"],
    "CG": ["congo brazzaville", "republic of the congo"],
    "AE": ["uae", "emirates", "united arab emirates"],
    "VA": ["vatican", "vatican city", "holy see"],
    "TL": ["east timor", "timor leste"],
    "SZ": ["swaziland", "eswatini"],
    "MK": ["macedonia", "north macedonia"],
    "TR": ["turkey", "turkiye"],
    "RU": ["russia", "russian federation"],
    "SY": ["syria"],
    "IR": ["iran", "persia"],
    "LA": ["laos"],
    "TW": ["taiwan", "republic of china"],
    "CN": ["china", "prc"],
    "ST": ["sao tome and principe"],
    "VC": ["saint vincent", "st vincent and the grenadines"],
    "KN": ["saint kitts and nevis", "st kitts"],
    "LC": ["saint lucia", "st lucia"],
    "BA": ["bosnia", "bosnia and herzegovina"],
    "DO": ["dominican republic"],
    "PS": ["palestine"],
    "EG": ["egypt"],
    "SR": ["surinam", "suriname"],
}

_LEADING = re.compile(r"^(the|republic of|kingdom of|state of)\s+")

# Written one way on a map and another by every person who has been there.
# "St." and "Saint" is the one that actually bites: eleven capitals and four
# countries are recorded one way and typed the other, and a quiz that rejects
# "St Johns" for "St. John's" is testing punctuation.
_WORD_FORMS = [
    (re.compile(r"\bste\b"), "sainte"),
    (re.compile(r"\bst\b"), "saint"),
    (re.compile(r"\bmt\b"), "mount"),
    (re.compile(r"\bft\b"), "fort"),
    (re.compile(r"\bcity of\b"), " "),
]


def normalise(text):
    text = fold(text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _LEADING.sub("", text).strip()
    for pattern, full in _WORD_FORMS:
        text = pattern.sub(full, text)
    return re.sub(r"\s+", " ", text).strip()


def close_enough(given, target):
    """One typo's worth of slack, scaled so short words stay exact.

    "Alegria" should pass for "Algeria"; "Chad" must not pass for "Chile".

    The length guard is what keeps Austria from passing for Australia. On
    ratio alone it does -- 0.842 against a 0.84 floor -- and of all the pairs
    in the world to accept for one another, that is the worst one: it is the
    single most common geography mistake there is, and letting it through
    tells someone they knew something they did not.
    """
    if given == target:
        return True
    if len(target) < 5:
        return False
    # A typo adds, drops or swaps one character. It does not change the
    # length of a word by more than one.
    if abs(len(given) - len(target)) > 1:
        return False
    # "Alegria" for "Algeria" is one transposition, which similarity ratios
    # score as two separate errors and reject. It is also the most common way
    # of mistyping a name, so it is checked for directly.
    if _one_edit_apart(given, target):
        return True
    ratio = difflib.SequenceMatcher(None, given, target).ratio()
    return ratio >= (0.88 if len(target) < 9 else 0.84)


def _one_edit_apart(a, b):
    """One insertion, deletion, substitution or adjacent swap -- no more."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(diffs) == 1:
            return True
        if len(diffs) == 2 and diffs[1] == diffs[0] + 1:
            i, j = diffs
            return a[i] == b[j] and a[j] == b[i]
        return False
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(long_)):
        if long_[:i] + long_[i + 1:] == short:
            return True
    return False


def accepted_names(world, iso2):
    """Every spelling that should count as this country."""
    c = world.get(iso2) or {}
    out = [c.get("name") or "", iso2, c.get("iso3") or ""]
    out.extend(ALIASES.get(iso2, []))
    return [normalise(x) for x in out if x]


def matches_country(world, given, iso2):
    given = normalise(given)
    if not given:
        return False
    return any(close_enough(given, name) for name in accepted_names(world, iso2))


def matches_text(given, answer, also=()):
    """A typed answer against a plain string, plus any acceptable variants.

    `also` carries the alternatives the question knows about -- a country's
    other capitals, say, or the same language under a different name.
    """
    given = normalise(given)
    if not given:
        return False
    for target in [answer] + list(also):
        target = normalise(target)
        if not target:
            continue
        if close_enough(given, target):
            return True
    return False


def judge(world, given, pending):
    """True if `given` (free text) answers the pending question."""
    kind = pending.get("answer_kind") or "text"
    answer = pending["answer"]
    if kind in ("country", "map"):
        return matches_country(world, given, answer if len(answer) == 2
                               else _iso_for(world, answer))
    if kind == "number":
        digits = (given or "").strip()
        return bool(digits) and digits == str(answer)
    return matches_text(given, answer, pending.get("also") or ())


def _iso_for(world, iso3):
    """Map questions key their answer by ISO3; everything else uses ISO2."""
    c = world.by_iso3.get(iso3)
    return c["iso2"] if c else iso3

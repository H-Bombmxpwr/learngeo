"""Judging a typed answer.

Challenge mode drops the four options, which means the app has to decide
whether what someone typed is the same thing as the answer. Being strict about
it is the fastest way to make a quiz infuriating: nobody should lose a life
for "Cote d'Ivoire" against "Ivory Coast", for "USA", or for a missing accent
on Asuncion.

The rules, in order:

1. Fold accents and case, drop punctuation and the leading "the".
2. Accept any recorded alias, including the ISO codes.
3. Accept a one-character typo on anything long enough for that to be a typo
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


def normalise(text):
    text = fold(text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _LEADING.sub("", text).strip()


def close_enough(given, target):
    """One typo's worth of slack, scaled so short words stay exact.

    "Alegria" should pass for "Algeria"; "Chad" must not pass for "Chile".
    """
    if given == target:
        return True
    if len(target) < 5:
        return False
    ratio = difflib.SequenceMatcher(None, given, target).ratio()
    return ratio >= (0.88 if len(target) < 9 else 0.84)


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
        # "Mandarin" for "Standard Chinese or Mandarin": accept any
        # significant word of a multi-word answer, so a compound name from the
        # source data does not have to be reproduced exactly.
        parts = [p for p in target.split() if len(p) > 3]
        if len(parts) > 1 and any(close_enough(given, p) for p in parts):
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
        digits = re.sub(r"[^0-9]", "", given or "")
        return bool(digits) and digits == str(answer)
    return matches_text(given, answer, pending.get("also") or ())


def _iso_for(world, iso3):
    """Map questions key their answer by ISO3; everything else uses ISO2."""
    c = world.by_iso3.get(iso3)
    return c["iso2"] if c else iso3

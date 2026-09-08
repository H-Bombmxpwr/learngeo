"""Small helpers shared by the loader and the curated supplement.

They live here rather than in `data.py` so that `supplement.py` can use them
without importing the module that imports it.
"""
import re
import unicodedata


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "unknown"


def wiki_url(title):
    """The English Wikipedia URL for a title.

    Article titles are the page name with spaces as underscores, so this is
    exact for people and places whose article is titled with their name --
    which is the case for everyone in the curated tables, each checked by
    hand. It is a guess for anything else.
    """
    return "https://en.wikipedia.org/wiki/%s" % (title or "").strip().replace(" ", "_")


def fold(text):
    """Lowercase and strip accents, so a search for "sao tome" finds
    Sao Tome and Principe and "cote" finds Cote d'Ivoire."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()

"""Progress tracking and the adaptive question picker.

One SQLite file, no accounts -- this is a single-player learning tool. The
interesting part is `pick`, which decides what to ask next by blending three
things: cards that are due for review, countries you have never seen, and a
difficulty ceiling that rises as you get better.
"""
import math
import os
import random
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "progress.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS mastery (
  iso2      TEXT NOT NULL,
  mode      TEXT NOT NULL,
  seen      INTEGER NOT NULL DEFAULT 0,
  correct   INTEGER NOT NULL DEFAULT 0,
  streak    INTEGER NOT NULL DEFAULT 0,
  ease      REAL    NOT NULL DEFAULT 2.3,
  interval  REAL    NOT NULL DEFAULT 0,
  due_at    REAL    NOT NULL DEFAULT 0,
  last_seen REAL    NOT NULL DEFAULT 0,
  PRIMARY KEY (iso2, mode)
);
CREATE INDEX IF NOT EXISTS mastery_due ON mastery(due_at);

CREATE TABLE IF NOT EXISTS answers (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        REAL NOT NULL,
  iso2      TEXT NOT NULL,
  mode      TEXT NOT NULL,
  correct   INTEGER NOT NULL,
  ms        INTEGER
);

CREATE TABLE IF NOT EXISTS runs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        REAL NOT NULL,
  category  TEXT NOT NULL,
  score     INTEGER NOT NULL,
  asked     INTEGER NOT NULL,
  correct   INTEGER NOT NULL,
  best_streak INTEGER NOT NULL DEFAULT 0
);
"""

MINUTE = 60.0
DAY = 86400.0


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------

def record(iso2, mode, correct, ms=None):
    """Update the card for (country, mode) using a trimmed-down SM-2."""
    now = time.time()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM mastery WHERE iso2=? AND mode=?", (iso2, mode)).fetchone()
        if row is None:
            seen = streak = 0
            ease, interval = 2.3, 0.0
            got = 0
        else:
            seen, got, streak = row["seen"], row["correct"], row["streak"]
            ease, interval = row["ease"], row["interval"]

        if correct:
            streak += 1
            got += 1
            ease = min(3.2, ease * 1.08)
            # First correct answer comes back in 10 minutes, then it stretches.
            interval = 10 * MINUTE if interval <= 0 else interval * ease
            interval = min(interval, 120 * DAY)
        else:
            streak = 0
            ease = max(1.4, ease * 0.75)
            interval = 3 * MINUTE      # missed cards come back inside the session
        seen += 1

        conn.execute(
            """INSERT INTO mastery (iso2, mode, seen, correct, streak, ease, interval,
                                    due_at, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(iso2, mode) DO UPDATE SET
                 seen=excluded.seen, correct=excluded.correct, streak=excluded.streak,
                 ease=excluded.ease, interval=excluded.interval,
                 due_at=excluded.due_at, last_seen=excluded.last_seen""",
            (iso2, mode, seen, got, streak, ease, interval, now + interval, now))
        conn.execute("INSERT INTO answers (ts, iso2, mode, correct, ms) VALUES (?,?,?,?,?)",
                     (now, iso2, mode, 1 if correct else 0, ms))


def record_run(category, score, asked, correct, best_streak):
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (ts, category, score, asked, correct, best_streak)"
            " VALUES (?,?,?,?,?,?)",
            (time.time(), category, score, asked, correct, best_streak))


# --------------------------------------------------------------------------
# The picker
# --------------------------------------------------------------------------

def unlocked_tier(conn):
    """Difficulty ceiling. Starts at the household-name countries and opens up
    as you actually get things right, so you are never shown Eswatini on
    question three."""
    n = conn.execute(
        "SELECT COUNT(DISTINCT iso2) AS n FROM mastery WHERE correct > 0").fetchone()["n"]
    return min(4, 1 + n // 15)


# A game needs this many distinct (country, mode) pairs before it stops
# feeling like a loop. The tier ceiling alone cannot guarantee it: there are
# only 22 tier-1 countries, so a single-mode game like Find It on the Map had
# 22 possible questions in total and repeated inside a single run.
MIN_POOL = 90


def _pool(world, modes, ceiling):
    """Countries inside the ceiling, widened until there is enough to ask."""
    tiers = sorted({(world.get(i).get("tier") or 4) for i in world.all_isos})
    for limit in [t for t in tiers if t >= ceiling] or tiers[-1:]:
        isos = [i for i in world.all_isos if (world.get(i).get("tier") or 4) <= limit]
        if len(isos) * max(1, len(modes)) >= MIN_POOL:
            return isos
    return list(world.all_isos)


def pick(world, modes, rng=None, avoid=()):
    """Choose the next (iso2, mode). `modes` is the list of allowed mode keys."""
    rng = rng or random
    avoid = set(avoid)
    now = time.time()
    modes = list(modes)

    with connect() as conn:
        ceiling = unlocked_tier(conn)
        placeholders = ",".join("?" * len(modes))
        # Overdue by a real margin, not merely past a ten-minute interval in
        # the same sitting -- otherwise everything answered early in a session
        # becomes "due" again before the session ends, and review crowds out
        # everything else.
        due = conn.execute(
            "SELECT iso2, mode FROM mastery WHERE due_at <= ? AND mode IN (%s)"
            " ORDER BY due_at LIMIT 40" % placeholders,
            [now - 5 * MINUTE] + modes).fetchall()
        last = {(r["iso2"], r["mode"]): r["last_seen"] for r in
                conn.execute("SELECT iso2, mode, last_seen FROM mastery").fetchall()}

    due = [(r["iso2"], r["mode"]) for r in due if (r["iso2"], r["mode"]) not in avoid]

    candidates = _pool(world, modes, ceiling)
    unseen = [(i, m) for i in candidates for m in modes
              if (i, m) not in last and (i, m) not in avoid]

    # Review earns its turn, but never at the cost of new material: while
    # anything is still unseen the review share stays low.
    review_odds = 0.5 if not unseen else 0.25
    if due and rng.random() < review_odds:
        return rng.choice(due[:12])
    if unseen:
        return rng.choice(unseen)

    # Everything has been seen at least once. Go round in order of longest
    # untouched rather than uniformly at random, which is what actually
    # stopped the same handful coming back.
    stale = [(i, m) for i in candidates for m in modes if (i, m) not in avoid]
    if not stale:
        stale = [(i, m) for i in candidates for m in modes] or [
            (rng.choice(world.all_isos), rng.choice(modes))]
    stale.sort(key=lambda p: last.get(p, 0.0))
    # A little jitter over the oldest quarter, so the order is not identical
    # every run.
    return rng.choice(stale[:max(8, len(stale) // 4)])


# --------------------------------------------------------------------------
# Stats for the progress page
# --------------------------------------------------------------------------

def overview(world):
    with connect() as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS answered, SUM(correct) AS got FROM answers").fetchone()
        by_country = conn.execute(
            "SELECT iso2, SUM(seen) AS seen, SUM(correct) AS correct,"
            " MAX(due_at) AS due FROM mastery GROUP BY iso2").fetchall()
        by_mode = conn.execute(
            "SELECT mode, SUM(seen) AS seen, SUM(correct) AS correct"
            " FROM mastery GROUP BY mode ORDER BY seen DESC").fetchall()
        runs = conn.execute(
            "SELECT * FROM runs ORDER BY ts DESC LIMIT 10").fetchall()
        weak = conn.execute(
            "SELECT iso2, mode, seen, correct FROM mastery"
            " WHERE seen >= 2 AND correct * 1.0 / seen < 0.6"
            " ORDER BY (correct * 1.0 / seen) ASC, seen DESC LIMIT 15").fetchall()
        ceiling = unlocked_tier(conn)

    mastery = {}
    for r in by_country:
        acc = (r["correct"] / r["seen"]) if r["seen"] else 0
        # "Known" needs both accuracy and repetition -- one lucky guess is not
        # knowledge.
        level = 0
        if r["seen"] >= 2 and acc >= 0.5:
            level = 1
        if r["seen"] >= 4 and acc >= 0.7:
            level = 2
        if r["seen"] >= 6 and acc >= 0.85:
            level = 3
        mastery[r["iso2"]] = {"seen": r["seen"], "correct": r["correct"],
                              "accuracy": acc, "level": level}

    answered = totals["answered"] or 0
    got = totals["got"] or 0
    return {
        "answered": answered,
        "correct": got,
        "accuracy": (got / answered) if answered else 0.0,
        "countries_touched": len(mastery),
        "countries_total": len(world.all_isos),
        "countries_known": sum(1 for m in mastery.values() if m["level"] >= 2),
        "tier": ceiling,
        "mastery": mastery,
        "by_mode": [dict(r) for r in by_mode],
        "runs": [dict(r) for r in runs],
        "weak": [dict(r) for r in weak],
    }

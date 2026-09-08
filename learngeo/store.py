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
    return min(4, 1 + n // 22)


def pick(world, modes, rng=None, avoid=()):
    """Choose the next (iso2, mode). `modes` is the list of allowed mode keys."""
    rng = rng or random
    avoid = set(avoid)
    now = time.time()

    with connect() as conn:
        ceiling = unlocked_tier(conn)
        placeholders = ",".join("?" * len(modes))
        due = conn.execute(
            "SELECT iso2, mode FROM mastery WHERE due_at <= ? AND mode IN (%s)"
            " ORDER BY due_at LIMIT 40" % placeholders,
            [now] + list(modes)).fetchall()
        seen_pairs = {(r["iso2"], r["mode"]) for r in
                      conn.execute("SELECT iso2, mode FROM mastery").fetchall()}

    due = [(r["iso2"], r["mode"]) for r in due if (r["iso2"], r["mode"]) not in avoid]
    # Weighted toward review, but never only review -- you still need new material.
    if due and rng.random() < 0.55:
        return rng.choice(due[:12])

    # Otherwise pick fresh material inside the unlocked tiers, preferring
    # countries and modes you have not met yet.
    candidates = [i for i in world.all_isos if (world.get(i).get("tier") or 4) <= ceiling]
    if not candidates:
        candidates = world.all_isos
    rng.shuffle(candidates)

    unseen = [(i, m) for i in candidates[:80] for m in modes
              if (i, m) not in seen_pairs and (i, m) not in avoid]
    if unseen:
        return rng.choice(unseen)
    return rng.choice(candidates), rng.choice(modes)


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

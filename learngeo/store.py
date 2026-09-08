"""Progress tracking and the adaptive question picker.

One SQLite file and no accounts. Every row is scoped to a `player`, which is
a random id in a year-long cookie -- so two people hitting the same deployed
copy keep separate progress without either of them signing up for anything,
and clearing your cookies is how you reset.

The interesting part is `pick`, which decides what to ask next by blending
four things: cards that are due for review, countries you have never seen, a
difficulty ceiling that rises as you get better, and a bias away from whatever
you have already proved you know.
"""
import math
import os
import random
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where progress is kept. On a host with an ephemeral filesystem this has to
# point at a mounted volume or every deploy wipes your scores, so the path is
# an environment variable: set LEARNGEO_DATA_DIR to the volume's mount point.
# Locally it is just data/, as before.
DATA_DIR = os.environ.get("LEARNGEO_DATA_DIR") or os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "progress.db")

LOCAL = "local"          # the player id used before cookies existed

SCHEMA = """
CREATE TABLE IF NOT EXISTS mastery (
  player    TEXT NOT NULL DEFAULT 'local',
  iso2      TEXT NOT NULL,
  mode      TEXT NOT NULL,
  seen      INTEGER NOT NULL DEFAULT 0,
  correct   INTEGER NOT NULL DEFAULT 0,
  streak    INTEGER NOT NULL DEFAULT 0,
  ease      REAL    NOT NULL DEFAULT 2.3,
  interval  REAL    NOT NULL DEFAULT 0,
  due_at    REAL    NOT NULL DEFAULT 0,
  last_seen REAL    NOT NULL DEFAULT 0,
  PRIMARY KEY (player, iso2, mode)
);
CREATE INDEX IF NOT EXISTS mastery_due ON mastery(player, due_at);

CREATE TABLE IF NOT EXISTS answers (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  player    TEXT NOT NULL DEFAULT 'local',
  ts        REAL NOT NULL,
  iso2      TEXT NOT NULL,
  mode      TEXT NOT NULL,
  correct   INTEGER NOT NULL,
  ms        INTEGER
);

CREATE TABLE IF NOT EXISTS runs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  player    TEXT NOT NULL DEFAULT 'local',
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
    # A freshly mounted volume is an empty directory, and on some hosts it does
    # not exist until first write, so the directory is made before the file.
    if DATA_DIR and not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Add the `player` column to a database written before it existed.

    A table cannot gain a primary-key column in place, so `mastery` is rebuilt
    and its existing rows are handed to the `local` player -- which is the one
    a desktop session without a cookie still uses. `answers` and `runs` only
    need the column appended.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(mastery)")}
    if "player" not in cols:
        conn.executescript("""
            ALTER TABLE mastery RENAME TO mastery_old;
            CREATE TABLE mastery (
              player TEXT NOT NULL DEFAULT 'local',
              iso2 TEXT NOT NULL, mode TEXT NOT NULL,
              seen INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0,
              streak INTEGER NOT NULL DEFAULT 0, ease REAL NOT NULL DEFAULT 2.3,
              interval REAL NOT NULL DEFAULT 0, due_at REAL NOT NULL DEFAULT 0,
              last_seen REAL NOT NULL DEFAULT 0,
              PRIMARY KEY (player, iso2, mode));
            INSERT INTO mastery
              SELECT 'local', iso2, mode, seen, correct, streak, ease,
                     interval, due_at, last_seen FROM mastery_old;
            DROP TABLE mastery_old;
            CREATE INDEX IF NOT EXISTS mastery_due ON mastery(player, due_at);
        """)
    for table in ("answers", "runs"):
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        if "player" not in cols:
            conn.execute("ALTER TABLE %s ADD COLUMN player TEXT NOT NULL "
                         "DEFAULT 'local'" % table)


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------

def record(iso2, mode, correct, ms=None, player=LOCAL):
    """Update the card for (country, mode) using a trimmed-down SM-2."""
    now = time.time()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM mastery WHERE player=? AND iso2=? AND mode=?",
            (player, iso2, mode)).fetchone()
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
            """INSERT INTO mastery (player, iso2, mode, seen, correct, streak,
                                    ease, interval, due_at, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(player, iso2, mode) DO UPDATE SET
                 seen=excluded.seen, correct=excluded.correct, streak=excluded.streak,
                 ease=excluded.ease, interval=excluded.interval,
                 due_at=excluded.due_at, last_seen=excluded.last_seen""",
            (player, iso2, mode, seen, got, streak, ease, interval,
             now + interval, now))
        conn.execute("INSERT INTO answers (player, ts, iso2, mode, correct, ms)"
                     " VALUES (?,?,?,?,?,?)",
                     (player, now, iso2, mode, 1 if correct else 0, ms))


def record_run(category, score, asked, correct, best_streak, player=LOCAL):
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (player, ts, category, score, asked, correct,"
            " best_streak) VALUES (?,?,?,?,?,?,?)",
            (player, time.time(), category, score, asked, correct, best_streak))


def forget(player):
    """Wipe one player's progress. What "start again" means with no account."""
    with connect() as conn:
        for table in ("mastery", "answers", "runs"):
            conn.execute("DELETE FROM %s WHERE player=?" % table, (player,))


# --------------------------------------------------------------------------
# The picker
# --------------------------------------------------------------------------

def unlocked_tier(conn, player=LOCAL):
    """Difficulty ceiling. Starts at the household-name countries and opens up
    as you actually get things right, so you are never shown Eswatini on
    question three."""
    n = conn.execute("SELECT COUNT(DISTINCT iso2) AS n FROM mastery"
                     " WHERE player=? AND correct > 0", (player,)).fetchone()["n"]
    return min(4, 1 + n // 15)


# Two separate floors, because they stop two different kinds of repetition.
#
# MIN_COUNTRIES is the one that matters most, and counting pairs instead of
# countries is what kept it broken: a pool of 22 countries times 23 modes is
# 506 distinct questions, which clears any pair-based floor immediately -- and
# yet you are still being asked about the same 22 places all evening. Variety
# is felt per country, not per question.
MIN_COUNTRIES = 65
MIN_POOL = 90          # and enough distinct questions for a one-mode game


def _pool(world, modes, ceiling):
    """Countries inside the ceiling, widened until there is enough to ask."""
    tiers = sorted({(world.get(i).get("tier") or 4) for i in world.all_isos})
    for limit in [t for t in tiers if t >= ceiling] or tiers[-1:]:
        isos = [i for i in world.all_isos if (world.get(i).get("tier") or 4) <= limit]
        if len(isos) >= MIN_COUNTRIES and len(isos) * max(1, len(modes)) >= MIN_POOL:
            return isos
    return list(world.all_isos)


def pick(world, modes, rng=None, avoid=(), player=LOCAL, adaptive=True):
    """Choose the next (iso2, mode). `modes` is the list of allowed mode keys.

    With `adaptive` off nothing is consulted and nothing is remembered: a
    question is drawn at random from the whole world. That is the setting for
    someone who wants to browse rather than be taught, and it is the honest
    behaviour for "learning off" -- the alternative, tracking silently while
    claiming not to, would be worse than not offering the switch.
    """
    rng = rng or random
    avoid = set(avoid)
    now = time.time()
    modes = list(modes)

    if not adaptive:
        recent = {a[0] for a in avoid}
        pool = [i for i in world.all_isos if i not in recent] or list(world.all_isos)
        return rng.choice(pool), rng.choice(modes)

    with connect() as conn:
        ceiling = unlocked_tier(conn, player)
        placeholders = ",".join("?" * len(modes))
        # Overdue by a real margin, not merely past a ten-minute interval in
        # the same sitting -- otherwise everything answered early in a session
        # becomes "due" again before the session ends, and review crowds out
        # everything else.
        due = conn.execute(
            "SELECT iso2, mode FROM mastery WHERE player=? AND due_at <= ?"
            " AND mode IN (%s) ORDER BY due_at LIMIT 60" % placeholders,
            [player, now - 5 * MINUTE] + modes).fetchall()
        rows = conn.execute(
            "SELECT iso2, mode, last_seen, seen, correct, streak FROM mastery"
            " WHERE player=?", (player,)).fetchall()
    last = {(r["iso2"], r["mode"]): r["last_seen"] for r in rows}
    # Countries you have shown you know: three or more right in a row on
    # something, and better than 80% overall. Asked about far less often --
    # being drilled on Russia when you have never missed a Russia question is
    # the fastest way to stop learning anything.
    by_country = {}
    for r in rows:
        agg = by_country.setdefault(r["iso2"], [0, 0, 0])
        agg[0] += r["seen"]
        agg[1] += r["correct"]
        agg[2] = max(agg[2], r["streak"])
    mastered = {iso for iso, (seen, got, streak) in by_country.items()
                if seen >= 4 and streak >= 3 and got >= 0.8 * seen}

    # A card can outlive the country it was about: the database is not
    # rebuilt when the dataset is, so a row for an ISO code that has since
    # gone would send the generator looking for a country that is not there.
    due = [(r["iso2"], r["mode"]) for r in due
           if (r["iso2"], r["mode"]) not in avoid
           and r["mode"] in modes and world.get(r["iso2"])]

    # Countries asked about recently, whatever the question was. Two questions
    # about Chad in five is what "the same questions" actually feels like,
    # even when the two are a flag and a border count.
    recent_countries = {a[0] for a in avoid}

    candidates = _pool(world, modes, ceiling)
    fresh = [i for i in candidates if i not in recent_countries] or candidates
    # One in six questions still comes from the mastered pile, so knowing
    # something is not the same as never seeing it again.
    if mastered and rng.random() > 0.17:
        thinned = [i for i in fresh if i not in mastered]
        if len(thinned) >= 12:
            fresh = thinned
    unseen = [(i, m) for i in fresh for m in modes
              if (i, m) not in last and (i, m) not in avoid]

    # Review earns its turn, but never at the cost of new material: while
    # anything is still unseen the review share stays low.
    review_odds = 0.5 if not unseen else 0.2
    if due and rng.random() < review_odds:
        # Sample from the whole due list, not its first dozen: ordered by due
        # date, the head of it is the same twelve cards every time.
        soon = [p for p in due if p[0] not in recent_countries] or due
        return rng.choice(soon)
    if unseen:
        return rng.choice(unseen)

    # Everything has been seen at least once. Go round in order of longest
    # untouched rather than uniformly at random, which is what actually
    # stopped the same handful coming back.
    stale = [(i, m) for i in fresh for m in modes if (i, m) not in avoid]
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

def overview(world, player=LOCAL):
    with connect() as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS answered, SUM(correct) AS got FROM answers"
            " WHERE player=?", (player,)).fetchone()
        by_country = conn.execute(
            "SELECT iso2, SUM(seen) AS seen, SUM(correct) AS correct,"
            " MAX(due_at) AS due FROM mastery WHERE player=? GROUP BY iso2",
            (player,)).fetchall()
        by_mode = conn.execute(
            "SELECT mode, SUM(seen) AS seen, SUM(correct) AS correct"
            " FROM mastery WHERE player=? GROUP BY mode ORDER BY seen DESC",
            (player,)).fetchall()
        runs = conn.execute(
            "SELECT * FROM runs WHERE player=? ORDER BY ts DESC LIMIT 10",
            (player,)).fetchall()
        weak = conn.execute(
            "SELECT iso2, mode, seen, correct FROM mastery"
            " WHERE player=? AND seen >= 2 AND correct * 1.0 / seen < 0.6"
            " ORDER BY (correct * 1.0 / seen) ASC, seen DESC LIMIT 15",
            (player,)).fetchall()
        ceiling = unlocked_tier(conn, player)

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

/* Scores, kept in this browser.

   There is no account, so this is personal practice data and nothing more:
   the player can edit it, clearing site data erases it, and it never proves
   anything to anybody else. Server-side mastery is a separate thing and is
   what the adaptive picker reads; these are the numbers on the dashboards.

   Three things the first version got wrong, fixed here:

   - One "best score" across every category, style and length, so a 12-question
     Flags run and an endless Grand Tour competed for the same number. Bests
     are per mode now, and compared only against their own kind.
   - Endless sessions accumulated for ever. Recent sessions are kept in full
     and older ones folded into a running total, so the store has a ceiling.
   - No way to see it, move it or delete it separately from server progress.
     There is an export, an import and a clear, and the page says which data
     each one touches. */
(function () {
  "use strict";

  var KEY = "learngeo.scores.v2";
  var OLD_KEY = "learngeo.scores.v1";
  var KEEP_SESSIONS = 40;         // in full; older ones become totals
  var available = true;

  function blank() {
    return {
      version: 2,
      sessions: {},
      // Per category|style|length, so nothing is ranked against a different
      // game. `runs` counts completed ones; `best` is the highest score.
      records: {},
      // Everything that has aged out of `sessions`, so the headline totals
      // stay true without keeping every run for ever.
      retired: { points: 0, asked: 0, correct: 0, sessions: 0 },
      // Which countries this browser has actually been asked about. Points
      // measure how fast you were; this measures how much of the world you
      // have met, which is the thing the app is for.
      countries: {}
    };
  }

  function read() {
    var raw;
    try {
      raw = localStorage.getItem(KEY);
    } catch (_) {
      available = false;
      return blank();
    }
    if (raw) {
      try {
        var data = JSON.parse(raw);
        if (data && data.version === 2) return fill(data);
      } catch (_) { /* corrupt: fall through and start again */ }
    }
    return migrate();
  }

  function fill(data) {
    var base = blank();
    Object.keys(base).forEach(function (k) {
      if (data[k] === undefined || data[k] === null) data[k] = base[k];
    });
    return data;
  }

  /* Scores saved before per-mode records existed. They are kept -- throwing
     away somebody's history to change a storage format is not a trade they
     agreed to -- but a v1 session recorded no country list, so the countries
     met before this ships are genuinely unknown and are not guessed at. */
  function migrate() {
    var data = blank();
    var raw;
    try {
      raw = localStorage.getItem(OLD_KEY);
    } catch (_) {
      available = false;
      return data;
    }
    if (!raw) return data;
    try {
      var old = JSON.parse(raw) || {};
      Object.keys(old.sessions || {}).forEach(function (id) {
        data.sessions[id] = old.sessions[id];
      });
      data.migrated_from_v1 = true;
    } catch (_) { /* nothing worth keeping */ }
    save(data);
    return data;
  }

  function save(data) {
    try {
      localStorage.setItem(KEY, JSON.stringify(data));
      return true;
    } catch (_) {
      available = false;
      return false;
    }
  }

  // ---- shaping ----------------------------------------------------------

  function recordKey(run) {
    return [run.category || "grand_tour",
            run.challenge ? "challenge" : "choice",
            run.endless ? "endless" : "twelve"].join("|");
  }

  function recordLabel(key) {
    var bits = key.split("|");
    return bits[0].replace(/_/g, " ") + " · " +
      (bits[1] === "challenge" ? "Challenge" : "Multiple choice") + " · " +
      (bits[2] === "endless" ? "Endless" : "12 questions");
  }

  /* Keep the newest sessions in full and fold the rest into one row of
     totals. An endless session that is never finished would otherwise sit in
     the store for ever, and a few hundred of them is a localStorage quota
     failure that looks, from the outside, like the scores being lost. */
  function compact(data) {
    var ids = Object.keys(data.sessions);
    if (ids.length <= KEEP_SESSIONS) return;
    ids.sort(function (a, b) {
      return (data.sessions[b].updated || 0) - (data.sessions[a].updated || 0);
    });
    ids.slice(KEEP_SESSIONS).forEach(function (id) {
      var run = data.sessions[id];
      data.retired.points += run.score || 0;
      data.retired.asked += run.asked || 0;
      data.retired.correct += run.correct || 0;
      data.retired.sessions += 1;
      delete data.sessions[id];
    });
  }

  function totals(data) {
    var out = {
      points: data.retired.points,
      asked: data.retired.asked,
      right: data.retired.correct,
      sessions: data.retired.sessions,
      streak: 0,
      countries: Object.keys(data.countries || {}).length
    };
    Object.keys(data.sessions).forEach(function (id) {
      var run = data.sessions[id];
      out.points += run.score || 0;
      out.asked += run.asked || 0;
      out.right += run.correct || 0;
      out.sessions += 1;
      out.streak = Math.max(out.streak, run.best_streak || 0);
    });
    Object.keys(data.records).forEach(function (key) {
      out.streak = Math.max(out.streak, data.records[key].best_streak || 0);
    });
    return out;
  }

  /* The best completed run of the same kind. "Best" across every category and
     both answer styles at once was not a personal best, it was whichever game
     happened to be scored most generously. */
  function bestOf(data, key) {
    var rec = data.records[key];
    return rec ? rec.best : 0;
  }

  function headline(data) {
    var t = totals(data);
    var best = 0;
    Object.keys(data.records).forEach(function (key) {
      if (key.indexOf("|twelve") !== -1) best = Math.max(best, data.records[key].best);
    });
    return {
      points: t.points,
      best: best,
      accuracy: t.asked ? Math.round(t.right / t.asked * 100) + "%" : "0%",
      streak: t.streak,
      countries: t.countries
    };
  }

  // ---- painting ---------------------------------------------------------

  function paint() {
    var data = read();
    var head = headline(data);
    document.querySelectorAll("[data-score]").forEach(function (el) {
      var v = head[el.dataset.score];
      el.textContent = (typeof v === "number") ? v.toLocaleString() : (v || "0");
    });

    var history = document.getElementById("scoreHistory");
    if (history) {
      var runs = Object.keys(data.sessions).map(function (id) {
        return data.sessions[id];
      });
      if (runs.length) {
        history.textContent = "";
        runs.sort(function (a, b) { return (b.updated || 0) - (a.updated || 0); });
        runs.slice(0, 8).forEach(function (r) {
          var row = document.createElement("p");
          row.textContent = recordLabel(recordKey(r)) + " · " +
            (r.score || 0).toLocaleString() + " points · " +
            (r.correct || 0) + "/" + (r.asked || 0) + " correct";
          history.appendChild(row);
        });
      }
    }

    var records = document.getElementById("scoreRecords");
    if (records) {
      var keys = Object.keys(data.records);
      if (!keys.length) {
        records.textContent = "Finish a run and your best for that game lands here.";
      } else {
        records.textContent = "";
        keys.sort(function (a, b) { return data.records[b].best - data.records[a].best; });
        keys.forEach(function (key) {
          var rec = data.records[key];
          var row = document.createElement("p");
          row.textContent = recordLabel(key) + " — best " +
            rec.best.toLocaleString() + " points, " + rec.runs +
            (rec.runs === 1 ? " run" : " runs");
          records.appendChild(row);
        });
      }
    }

    var note = document.getElementById("scoreSaveNote");
    if (!available && note) {
      note.textContent = "Browser storage is unavailable, so scores cannot be " +
        "saved on this device. Everything else still works.";
    }
  }

  // ---- the API the game calls ------------------------------------------

  window.GeoScores = {
    record: function (response) {
      var data = read();
      var run = response && response.run;
      if (!run || !run.id) return;
      // Replacing a cumulative snapshot makes refresh and replayed responses
      // idempotent: the same answer arriving twice cannot score twice.
      var existing = data.sessions[run.id];
      if (existing && existing.asked > run.asked) return;
      data.sessions[run.id] = {
        id: run.id, category: run.category, challenge: !!run.challenge,
        endless: !!run.endless, score: run.score || 0, asked: run.asked || 0,
        correct: run.correct || 0, best_streak: run.best_streak || 0,
        over: !!run.over, updated: Date.now()
      };
      (run.countries_seen || []).forEach(function (iso) {
        data.countries[iso] = (data.countries[iso] || 0) + 0 + 1;
      });
      if (run.over) {
        var key = recordKey(run);
        var rec = data.records[key] ||
          (data.records[key] = { best: 0, runs: 0, best_streak: 0 });
        // A finished run counts once, however many times its final response
        // is replayed by a refresh.
        if (!existing || !existing.over) rec.runs += 1;
        rec.best = Math.max(rec.best, run.score || 0);
        rec.best_streak = Math.max(rec.best_streak, run.best_streak || 0);
      }
      compact(data);
      save(data);
      paint();
    },

    /* The three things somebody might want to do with their own data, said
       plainly. Export is a file; import merges; clear is only these scores
       and says so, because server progress is cleared elsewhere. */
    export: function () {
      return JSON.stringify(read(), null, 2);
    },

    import: function (text) {
      var incoming;
      try {
        incoming = JSON.parse(text);
      } catch (_) {
        return { error: "That file is not JSON." };
      }
      if (!incoming || !incoming.sessions) {
        return { error: "That file is not a LearnGeo score export." };
      }
      var data = read(), added = 0;
      Object.keys(incoming.sessions).forEach(function (id) {
        var mine = data.sessions[id], theirs = incoming.sessions[id];
        if (!mine || (theirs.asked || 0) > (mine.asked || 0)) {
          data.sessions[id] = theirs;
          added += 1;
        }
      });
      Object.keys(incoming.records || {}).forEach(function (key) {
        var rec = data.records[key] ||
          (data.records[key] = { best: 0, runs: 0, best_streak: 0 });
        rec.best = Math.max(rec.best, incoming.records[key].best || 0);
        rec.runs = Math.max(rec.runs, incoming.records[key].runs || 0);
        rec.best_streak = Math.max(rec.best_streak,
                                   incoming.records[key].best_streak || 0);
      });
      Object.keys(incoming.countries || {}).forEach(function (iso) {
        data.countries[iso] = (data.countries[iso] || 0) +
          incoming.countries[iso];
      });
      compact(data);
      if (!save(data)) return { error: "Could not write to browser storage." };
      paint();
      return { imported: added };
    },

    clear: function () {
      try {
        localStorage.removeItem(KEY);
        localStorage.removeItem(OLD_KEY);
      } catch (_) {
        available = false;
      }
      paint();
    },

    bestFor: bestOf,
    read: read
  };

  paint();
  // Another tab finishing a run should update this one's dashboard.
  window.addEventListener("storage", paint);
})();

/* The quiz stage: fetch a question, render whatever medium it needs,
   take the answer, then raise the paper fact card. */

(function () {
  "use strict";

  var cfg = window.LEARNGEO || {};
  var el = {
    lives: document.getElementById("lives"),
    railCount: document.getElementById("railCount"),
    railStreak: document.getElementById("railStreak"),
    score: document.getElementById("score"),
    media: document.getElementById("media"),
    prompt: document.getElementById("prompt"),
    hint: document.getElementById("hint"),
    choices: document.getElementById("choices"),
    lifelines: document.getElementById("lifelines"),
    answerSlot: document.getElementById("answerSlot"),
    sheetHost: document.getElementById("sheetHost")
  };

  var current = null;      // the question on screen
  var askedAt = 0;
  var locked = false;
  var map = null, mapLayer = null, geoCache = null;
  var scoreBefore = 0;
  var lastAnswer = null;   // kept so the bar can open the card on request

  // ---- helpers ----------------------------------------------------------
  function h(tag, attrs, kids) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (attrs[k] !== null && attrs[k] !== undefined) node.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  }

  // ---- run rail ---------------------------------------------------------
  function paintRun(run) {
    el.lives.innerHTML = "";
    for (var i = 0; i < 3; i++) {
      el.lives.appendChild(h("span", { class: "life" + (i < run.lives ? "" : " spent") }));
    }
    el.score.textContent = run.score.toLocaleString();
    el.railStreak.textContent = run.streak >= 2 ? (run.streak + " in a row") : "";
    Array.prototype.forEach.call(el.lifelines.children, function (b) {
      b.disabled = locked || !run.lifelines[b.dataset.kind];
    });
  }

  // ---- media renderers --------------------------------------------------

  /* Draw a country's GeoJSON as a bare silhouette. Equirectangular, scaled to
     the shape's own bounding box, so size gives nothing away -- only shape. */
  function outlineSVG(geometry) {
    var polys = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    var minX = 180, maxX = -180, minY = 90, maxY = -90;
    polys.forEach(function (poly) {
      poly.forEach(function (ring) {
        ring.forEach(function (pt) {
          if (pt[0] < minX) minX = pt[0];
          if (pt[0] > maxX) maxX = pt[0];
          if (pt[1] < minY) minY = pt[1];
          if (pt[1] > maxY) maxY = pt[1];
        });
      });
    });
    // Latitude is compressed by cos(lat) on an equirectangular map; correcting
    // for it keeps Norway looking like Norway rather than a smear.
    var midLat = (minY + maxY) / 2 * Math.PI / 180;
    var kx = Math.cos(midLat) || 1;
    var w = (maxX - minX) * kx, hgt = (maxY - minY);
    var pad = Math.max(w, hgt) * 0.06;
    var d = "";
    polys.forEach(function (poly) {
      poly.forEach(function (ring) {
        ring.forEach(function (pt, i) {
          var x = (pt[0] - minX) * kx;
          var y = maxY - pt[1];
          d += (i ? "L" : "M") + x.toFixed(3) + " " + y.toFixed(3);
        });
        d += "Z";
      });
    });
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "outline");
    svg.setAttribute("viewBox",
      (-pad) + " " + (-pad) + " " + (w + pad * 2) + " " + (hgt + pad * 2));
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Outline of a country");
    var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    svg.appendChild(path);
    return svg;
  }

  function loadGeo() {
    if (geoCache) return Promise.resolve(geoCache);
    return fetch("/api/geo").then(function (r) { return r.json(); })
      .then(function (g) { geoCache = g; return g; });
  }

  function renderMap() {
    var host = h("div", { id: "map" });
    el.media.appendChild(host);
    return loadGeo().then(function (geo) {
      map = L.map(host, {
        worldCopyJump: false, attributionControl: false,
        minZoom: 1, maxZoom: 7, zoomControl: true
      }).setView([20, 10], 2);
      mapLayer = L.geoJSON(geo, {
        style: function () {
          return { color: "#23566c", weight: 0.8, fillColor: "#12303f", fillOpacity: 1 };
        },
        onEachFeature: function (feature, layer) {
          layer.on("mouseover", function () {
            if (!locked) layer.setStyle({ fillColor: "#1c4356", color: "#3e8c9e" });
          });
          layer.on("mouseout", function () {
            if (!locked) mapLayer.resetStyle(layer);
          });
          layer.on("click", function () {
            if (!locked) answer(feature.id);
          });
        }
      }).addTo(map);
      // Nudge Leaflet: the container was sized after the map was created.
      setTimeout(function () { map.invalidateSize(); }, 60);
    });
  }

  function renderMedia(q) {
    // Leaflet keeps listeners and tiles alive on a container that is merely
    // emptied, and the old layer's green and red kept its colours -- so the
    // next map question opened already showing the previous answer.
    if (map) {
      map.remove();
      map = null;
      mapLayer = null;
    }
    el.media.innerHTML = "";
    var m = q.media || {};
    if (m.type === "image") {
      el.media.appendChild(h("img", {
        src: m.url, class: m.frame === "portrait" ? "portrait" : "flag", alt: ""
      }));
    } else if (m.type === "outline") {
      el.media.appendChild(outlineSVG(m.geometry));
    } else if (m.type === "map") {
      renderMap();
    }
  }

  /* Challenge mode: no options, a box you type into.

     The box suggests the names it will accept, scoped to what the question is
     asking for -- capitals for a capitals question, not all 197 countries.
     Without that it is a spelling test. The judging is still done on the
     server and is generous about accents, aliases and one-character typos, so
     you can also just type and press Enter without touching the list. */
  function renderTypeIn(q) {
    var wrap = h("div", { class: "typein" });
    var input = h("input", {
      type: "text", id: "answerBox", autocomplete: "off",
      spellcheck: "false", placeholder: placeholderFor(q),
      "aria-label": "Type your answer"
    });
    var box = h("div", { class: "ac ac-answer", hidden: "hidden" });
    var send = h("button", { class: "btn", text: "Answer" });

    var rows = [], active = -1, timer = null;

    function close() { box.hidden = true; box.innerHTML = ""; rows = []; active = -1; }

    function open(list) {
      box.innerHTML = "";
      rows = list;
      active = -1;
      if (!list.length) { close(); return; }
      list.forEach(function (name, i) {
        var row = h("div", { class: "ac-row", role: "option" },
                    [h("b", { text: name })]);
        row.addEventListener("mousedown", function (e) {
          e.preventDefault();          // do not blur the box before we read it
          input.value = name;
          close();
          submit();
        });
        row.addEventListener("mouseenter", function () { mark(i); });
        box.appendChild(row);
      });
      box.hidden = false;
    }

    function mark(i) {
      Array.prototype.forEach.call(box.children, function (n, j) {
        n.classList.toggle("on", j === i);
      });
      active = i;
    }

    function look() {
      var v = input.value.trim();
      if (v.length < 1) { close(); return; }
      fetch("/api/suggest?mode=" + encodeURIComponent(q.mode) +
            "&q=" + encodeURIComponent(v))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (input.value.trim() !== v || locked) return;
          open(d.results || []);
        }).catch(close);
    }

    function submit() {
      if (locked) return;
      var v = input.value.trim();
      if (!v) return;
      close();
      answer(null, false, v);
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(look, 90);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (box.hidden || !rows.length) return;
        e.preventDefault();
        var n = active + (e.key === "ArrowDown" ? 1 : -1);
        if (n < 0) n = rows.length - 1;
        if (n >= rows.length) n = 0;
        mark(n);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (active >= 0 && rows[active]) input.value = rows[active];
        submit();
      } else if (e.key === "Escape") {
        close();
      }
    });
    send.addEventListener("click", submit);

    wrap.appendChild(input);
    wrap.appendChild(send);
    wrap.appendChild(box);
    el.choices.className = "choices";
    el.choices.appendChild(wrap);
    if (q.input === "text+map") {
      el.choices.appendChild(h("p", { class: "orclick",
        text: "… or just click it on the map." }));
    }
    setTimeout(function () { input.focus(); }, 40);
  }

  function placeholderFor(q) {
    return { country: "Type the country", capital: "Type the capital",
             city: "Type the city" }[q.answer_kind] || "Type your answer";
  }

  // ---- choices ----------------------------------------------------------
  function renderChoices(q) {
    el.choices.innerHTML = "";
    if (q.challenge) { renderTypeIn(q); return; }
    if (!q.choices.length) {                 // map questions answer by clicking
      el.choices.className = "choices";
      return;
    }
    var flagsOnly = q.choices.every(function (c) { return c.image && !c.label; });
    var isPair = q.choices.length === 2;
    el.choices.className = "choices " + (flagsOnly ? "flags" : isPair ? "pair" : "text");

    q.choices.forEach(function (c, i) {
      var kids = [];
      if (c.image) kids.push(h("img", { src: c.image, class: flagsOnly ? "" : "mini", alt: "" }));
      if (c.label) kids.push(h("span", { text: c.label }));
      var btn = h("button", {
        class: "choice", "data-key": c.key,
        "aria-label": c.label || c.caption || ("Option " + (i + 1))
      }, kids);
      if (c.caption) btn.dataset.caption = c.caption;
      btn.addEventListener("click", function () { answer(c.key); });
      el.choices.appendChild(btn);
    });
  }

  // ---- question flow ----------------------------------------------------
  function nextQuestion() {
    locked = false;
    el.sheetHost.innerHTML = "";
    el.answerSlot.innerHTML = "";
    fetch("/api/next").then(function (r) { return r.json(); }).then(function (q) {
      if (q.error) { el.prompt.textContent = q.error; return; }
      if (q.done) { return; }
      current = q;
      askedAt = Date.now();
      el.prompt.textContent = q.prompt;
      el.hint.textContent = q.hint || "";
      el.railCount.textContent = q.run_length
        ? ("Question " + q.question_no + " of " + q.run_length)
        : ("Question " + q.question_no);
      document.getElementById("railTitle").textContent = q.category_label;
      renderMedia(q);
      renderChoices(q);
      paintRun(q.run);
    });
  }

  function answer(key, skipped, typed) {
    if (locked || !current) return;
    locked = true;
    scoreBefore = current.run.score;
    var ms = Date.now() - askedAt;
    post("/api/answer", { qid: current.qid, choice: key, text: typed,
                          ms: ms, skipped: !!skipped })
      .then(function (res) {
        if (res.error) { el.prompt.textContent = res.error; return; }
        markChoices(res, key);
        paintRun(res.run);
        lastAnswer = res;
        // A wrong map click is the one case where the card is the wrong
        // response: what you needed was to see where the country actually
        // was. The map stays up with the answer flown to and lit, and the
        // card waits behind a button.
        if (!res.finished && !res.correct && map) {
          showBar(res);
          return;
        }
        if (res.finished) {
          showGameOver(res);
        } else if (!res.correct && res.focus) {
          // The question was about a person or a city, so that is what comes
          // up. The country is a button away.
          showFocus(res);
        } else if (res.correct) {
          // Getting it right does not need a full page of teaching thrown at
          // you. The card is one click away for anyone who wants it.
          showBar(res);
        } else {
          showSheet(res);
        }
      });
  }

  function markChoices(res, given) {
    Array.prototype.forEach.call(el.choices.children, function (btn) {
      btn.disabled = true;
      var k = btn.dataset.key;
      if (String(k) === String(res.answer)) btn.classList.add("right");
      else if (String(k) === String(given) && !res.correct) btn.classList.add("wrong");
      // Name every flag, not just the right one: four unlabelled flags on
      // screen is four things you could have learned.
      if (btn.dataset.caption && !btn.querySelector(".caption")) {
        btn.appendChild(h("span", { class: "caption", text: btn.dataset.caption }));
      }
    });
    if (map && mapLayer) {
      mapLayer.eachLayer(function (layer) {
        if (layer.feature.id === res.answer) {
          layer.setStyle({ fillColor: "#6e8b4a", color: "#9dbd6e" });
          map.fitBounds(layer.getBounds().pad(1.2));
        } else if (String(layer.feature.id) === String(given)) {
          layer.setStyle({ fillColor: "#b84a32", color: "#d4735c" });
        }
      });
    }
  }

  // ---- what shows after a correct answer -------------------------------
  function showBar(res) {
    // Getting it right is not proof you knew it, so the bar still says what
    // the thing was -- one line, in case the fourth option was a guess.
    var f = res.focus;
    var note = f ? (f.blurb || factLine(f)) : (res.card.blurb || "");
    var bar = h("div", { class: "answerbar" }, [
      h("span", { class: "said " + (res.correct ? "right" : "wrong"),
                  text: res.correct ? "Correct" : "Not quite" }),
      h("span", { class: "was",
                  text: res.answer_text || (f && f.title) || res.card.name }),
      h("span", { class: "gained",
                  text: res.correct ? ("+" + pointsGained(res))
                                    : "shown in green on the map" })
    ]);
    if (note) bar.appendChild(h("p", { class: "note", text: trim(note, 200) }));
    bar.appendChild(button("Next question", "btn big", nextQuestion));
    bar.appendChild(button("See the card", "btn ghost", function () {
      showSheet(res);
    }));
    el.sheetHost.innerHTML = "";
    el.answerSlot.innerHTML = "";
    el.answerSlot.appendChild(bar);
    bar.querySelector(".btn.big").focus();
  }

  // ---- the end of a run -------------------------------------------------
  function showGameOver(res) {
    var run = res.run;
    var out = run.lives <= 0 ? "Out of lives" : "Run complete";
    var pct = run.asked ? Math.round(100 * run.correct / run.asked) : 0;
    var sheet = h("div", { class: "sheet gameover", role: "dialog",
                           "aria-label": "Run over" }, [
      h("h2", { text: out }),
      h("p", { style: "color:#6b6255;margin:0",
               text: "The answer was " + res.card.name + "." }),
      h("div", { class: "final", text: run.score.toLocaleString() }),
      h("div", { style: "color:#857a68;font-size:.85rem", text: "points" }),
      h("div", { class: "tally" }, [
        h("div", {}, [h("b", { text: run.correct + " / " + run.asked }),
                      h("small", { text: "right" })]),
        h("div", {}, [h("b", { text: pct + "%" }), h("small", { text: "accuracy" })]),
        h("div", {}, [h("b", { text: String(run.best_streak) }),
                      h("small", { text: "best streak" })])
      ])
    ]);
    var actions = h("div", { class: "sheet-actions" });
    actions.appendChild(button("Play again", "btn big", function () {
      post("/api/restart", { category: cfg.category, endless: cfg.endless })
        .then(nextQuestion);
    }));
    actions.appendChild(h("a", { class: "btn ghost", href: "/country/" + res.card.iso2,
                                 text: "Read the card" }));
    actions.appendChild(h("a", { class: "btn ghost", href: "/games",
                                 text: "Other games" }));
    sheet.appendChild(actions);
    var back = h("div", { class: "sheet-back", style: "align-items:center" }, [sheet]);
    el.sheetHost.innerHTML = "";
    el.sheetHost.appendChild(back);
    sheet.querySelector(".btn").focus();
  }

  // ---- the focus card: a person, or a city -----------------------------
  function showFocus(res) {
    var f = res.focus;
    var body = [];

    body.push(h("div", { class: "verdict wrong" }, [
      h("span", { text: res.skipped ? "Skipped" : "Not quite" }),
      h("span", { class: "pts",
                  text: "It was " + (res.answer_text || res.card.name) })
    ]));

    var head = [
      h("h2", { text: f.title }),
      f.subtitle ? h("div", { class: "from" }, [
        f.flag ? h("img", { src: f.flag, alt: "" }) : null,
        h("span", { text: f.subtitle })
      ]) : null,
      f.blurb ? h("p", { text: f.blurb }) : null
    ];
    body.push(h("div", { class: "card-head focus-head" }, [
      f.image ? h("img", { src: f.image, class: "focus-portrait", alt: f.title })
              : h("div", { class: "focus-blank", text: f.kind === "city" ? "◉" : "○" }),
      h("div", {}, head)
    ]));

    if (f.facts && f.facts.length) {
      var facts = h("dl", { class: "facts" });
      f.facts.forEach(function (row) {
        facts.appendChild(h("div", { class: "fact" }, [
          h("dt", { text: row[0] }), h("dd", { text: row[1] })
        ]));
      });
      body.push(facts);
    }

    var actions = h("div", { class: "sheet-actions" });
    actions.appendChild(button("Next question", "btn big", nextQuestion));
    actions.appendChild(button("About " + res.card.name, "btn ghost", function () {
      showSheet(res);
    }));
    if (f.wiki_url) {
      actions.appendChild(h("a", {
        class: "btn ghost", href: f.wiki_url, target: "_blank", rel: "noopener",
        text: "Wikipedia"
      }));
    }
    body.push(actions);

    var sheet = h("div", { class: "sheet focus", role: "dialog",
                           "aria-label": f.title }, body);
    var back = h("div", { class: "sheet-back" }, [sheet]);
    back.addEventListener("click", function (e) {
      if (e.target === back) nextQuestion();
    });
    el.sheetHost.innerHTML = "";
    el.sheetHost.appendChild(back);
    sheet.scrollTop = 0;
    sheet.setAttribute("tabindex", "-1");
    sheet.focus({ preventScroll: true });
  }

  /* Mark the line on the country card that the question turned on, and bring
     it into view. Without this a wrong answer opens a page of facts with no
     sign of which one you needed. */
  function markHighlight(sheet, res) {
    var hl = res.highlight;
    if (!hl || res.correct) return;
    var kind = hl[0], value = String(hl[1]);
    var found = null;
    if (kind === "fact") {
      Array.prototype.forEach.call(sheet.querySelectorAll(".fact"), function (n) {
        var dt = n.querySelector("dt");
        if (!found && dt && dt.textContent === value) found = n;
      });
    } else {
      Array.prototype.forEach.call(sheet.querySelectorAll("[data-name]"), function (n) {
        if (!found && n.dataset.name === value) found = n;
      });
    }
    if (!found) return;
    found.classList.add("lit");
    // The card is its own scroll box, so scroll within it rather than moving
    // the page behind the overlay.
    var top = found.offsetTop - sheet.clientHeight / 3;
    sheet.scrollTop = Math.max(0, top);
  }

  // ---- the paper fact card ---------------------------------------------
  function showSheet(res) {
    var card = res.card;
    var verdict = res.skipped ? "Skipped" : (res.correct ? "Correct" : "Not quite");
    var body = [];

    body.push(h("div", { class: "verdict " + (res.correct ? "right" : "wrong") }, [
      h("span", { text: verdict }),
      h("span", { class: "pts",
                  text: res.correct ? ("+" + pointsGained(res))
                                    : ("It was " + (res.answer_text || card.name)) })
    ]));

    body.push(h("div", { class: "card-head" }, [
      h("img", { src: card.flag, class: "flag", alt: "Flag of " + card.name }),
      h("div", {}, [
        h("h2", { text: card.name }),
        h("div", { class: "code", text: card.iso2 + " / " + card.iso3 }),
        card.blurb ? h("p", { text: card.blurb }) : null
      ])
    ]));

    var facts = h("dl", { class: "facts" });
    card.bullets.forEach(function (b) {
      facts.appendChild(h("div", { class: "fact" }, [
        h("dt", { text: b[0] }), h("dd", { text: b[1] })
      ]));
    });
    body.push(facts);

    // Every fact on the card is a door: entities link to their own page,
    // which lists every other country attached to them.
    if (card.links && card.links.length) {
      body.push(chipStrip("Follow a thread", card.links.map(function (e) {
        return chip("/topic/" + e.kind + "/" + e.key, e.name,
                    e.speakers ? fmt(e.speakers) : null);
      })));
    }
    if (card.wars && card.wars.length) {
      body.push(chipStrip("Wars and conflicts", card.wars.map(function (wr) {
        return chip("/topic/war/" + wr.key, wr.name, wr.start || null);
      })));
    }
    if (card.cities && card.cities.length) {
      body.push(chipStrip("Largest cities", card.cities.map(function (city) {
        return chip(city.wiki, city.name, fmt(city.population), true);
      })));
    }
    if (card.leaders && card.leaders.length) {
      body.push(strip("In charge right now", card.leaders.map(function (p) {
        return person(p.image, p.name, p.party ? (p.role + ", " + p.party) : p.role,
                      p.wiki);
      })));
    }
    // Where the row of famous faces used to be. Nobody needed four more
    // portraits after the two above; what a country sells and to whom is the
    // thing you cannot guess from the map.
    if (card.economy && card.economy.length) {
      var econ = h("div", { class: "facts", style: "margin-top:4px" });
      card.economy.forEach(function (row) {
        econ.appendChild(h("div", { class: "fact" }, [
          h("dt", { text: row[0] }), h("dd", { text: row[1] })
        ]));
      });
      body.push(h("div", { class: "strip" }, [h("h3", { text: "Trade" }), econ]));
    }
    if (card.figures && card.figures.length) {
      body.push(chipStrip("Figures from its history", card.figures.map(function (p) {
        return chip(p.wiki, p.name, null, true);
      })));
    }
    if (card.neighbours && card.neighbours.length) {
      var row = h("div", { class: "neighbours" });
      card.neighbours.forEach(function (n) {
        row.appendChild(h("a", { class: "neighbour", href: "/country/" + n.iso2 }, [
          h("img", { src: n.flag, alt: "" }), h("span", { text: n.name })
        ]));
      });
      body.push(h("div", { class: "strip" }, [h("h3", { text: "Land borders" }), row]));
    }

    var actions = h("div", { class: "sheet-actions" });
    actions.appendChild(button("Next question", "btn big", nextQuestion));
    actions.appendChild(h("a", {
      class: "btn ghost", href: "/country/" + card.iso2, text: "Read the full page"
    }));
    if (card.news_url) {
      actions.appendChild(h("a", {
        class: "btn ghost", href: card.news_url, target: "_blank", rel: "noopener",
        text: "Recent news"
      }));
    }
    if (card.wiki_url) {
      actions.appendChild(h("a", {
        class: "btn ghost", href: card.wiki_url, target: "_blank", rel: "noopener",
        text: "Wikipedia"
      }));
    }
    body.push(actions);

    var sheet = h("div", { class: "sheet", role: "dialog", "aria-label": "Answer" }, body);
    var back = h("div", { class: "sheet-back" }, [sheet]);
    // Dismissing the card goes on with the run, unless it was opened from the
    // bar after a correct answer -- then it goes back to the bar.
    back.addEventListener("click", function (e) {
      if (e.target !== back) return;
      if (res.correct || map) showBar(res); else nextQuestion();
    });
    el.sheetHost.innerHTML = "";
    el.sheetHost.appendChild(back);
    // Focusing the first button dragged the card to its own bottom, so a
    // wrong answer opened on the row of buttons rather than on the country.
    // The card itself takes focus, at the top, where the reading starts.
    sheet.scrollTop = 0;
    sheet.setAttribute("tabindex", "-1");
    sheet.focus({ preventScroll: true });
    markHighlight(sheet, res);
  }

  function pointsGained(res) {
    return (res.run.score - scoreBefore).toLocaleString();
  }

  function fmt(n) {
    return typeof n === "number" ? n.toLocaleString() : n;
  }

  function trim(text, n) {
    return text.length > n ? text.slice(0, n).replace(/\s+\S*$/, "") + "..." : text;
  }

  /* A person or city with no fetched biography still has facts; the first
     two make a serviceable one-line description. */
  function factLine(f) {
    return (f.facts || []).slice(0, 2)
      .map(function (r) { return r[0] + ": " + r[1]; }).join(" · ");
  }

  function chip(href, label, sub, external) {
    var attrs = { class: "neighbour", href: href, "data-name": label };
    if (external) { attrs.target = "_blank"; attrs.rel = "noopener"; }
    return h("a", attrs, [
      h("span", { text: label }),
      sub ? h("small", { style: "color:#857a68", text: sub }) : null
    ]);
  }

  function chipStrip(title, nodes) {
    var row = h("div", { class: "neighbours" });
    nodes.forEach(function (n) { row.appendChild(n); });
    return h("div", { class: "strip" }, [h("h3", { text: title }), row]);
  }

  function strip(title, nodes) {
    var row = h("div", { class: "people" });
    nodes.forEach(function (n) { row.appendChild(n); });
    return h("div", { class: "strip" }, [h("h3", { text: title }), row]);
  }

  function person(img, name, sub, wiki) {
    var kids = [
      img ? h("img", { src: img, alt: name, loading: "lazy" }) : h("div", { class: "person-blank" }),
      h("b", { text: name }),
      sub ? h("small", { text: sub }) : null
    ];
    // Everybody on a card is a link now: a face with no way through to who
    // they were is a dead end on a page that is otherwise all doors.
    if (wiki) {
      return h("a", { class: "person", href: wiki, target: "_blank",
                      rel: "noopener", "data-name": name }, kids);
    }
    return h("div", { class: "person", "data-name": name }, kids);
  }

  function button(label, cls, fn) {
    var b = h("button", { class: cls, text: label });
    b.addEventListener("click", fn);
    return b;
  }

  // ---- lifelines --------------------------------------------------------
  el.lifelines.addEventListener("click", function (e) {
    var btn = e.target.closest(".lifeline");
    if (!btn || locked || !current) return;
    var kind = btn.dataset.kind;
    if (kind === "skip") { answer(null, true); return; }
    if (kind === "fifty" && !current.choices.length) return;   // nothing to cut
    var keys = current.choices.map(function (c) { return c.key; });
    post("/api/lifeline", { qid: current.qid, kind: kind, keys: keys }).then(function (res) {
      if (res.error) return;
      if (res.remove) {
        res.remove.forEach(function (k) {
          var b = el.choices.querySelector('[data-key="' + CSS.escape(String(k)) + '"]');
          if (b) b.classList.add("gone");
        });
      }
      if (res.peek) el.hint.textContent = res.peek;
      paintRun(res.run);
    });
  });

  // ---- keyboard: 1-4 to answer, Enter/Space to advance -------------------
  document.addEventListener("keydown", function (e) {
    var sheetBtn = el.sheetHost.querySelector(".btn.big") ||
                   el.answerSlot.querySelector(".btn.big");
    if (sheetBtn && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault(); sheetBtn.click(); return;
    }
    if (locked) return;
    if (/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) return;
    var n = parseInt(e.key, 10);
    if (n >= 1 && n <= el.choices.children.length) {
      var btn = el.choices.children[n - 1];
      if (btn && !btn.classList.contains("gone")) btn.click();
    }
  });

  nextQuestion();
})();

/* The search box in the header, on every page.

   It answers as you type from /api/search, which scans a flat index of every
   country, topic and person the dataset knows about. Arrow keys move, Enter
   opens the highlighted row, or searches for the raw text if none is. */

(function () {
  "use strict";

  var input = document.getElementById("q");
  var box = document.getElementById("acbox");
  if (!input || !box) return;

  var rows = [];
  var active = -1;
  var timer = null;
  var lastQuery = "";

  function close() {
    box.hidden = true;
    box.innerHTML = "";
    rows = [];
    active = -1;
    input.setAttribute("aria-expanded", "false");
  }

  function open(results) {
    box.innerHTML = "";
    rows = results;
    active = -1;
    if (!results.length) { close(); return; }
    results.forEach(function (r, i) {
      var a = document.createElement("a");
      a.className = "ac-row";
      a.href = r.url;
      a.setAttribute("role", "option");
      a.dataset.index = String(i);
      if (r.flag) {
        var img = document.createElement("img");
        img.src = r.flag;
        img.alt = "";
        a.appendChild(img);
      } else {
        var dot = document.createElement("span");
        dot.className = "ac-dot";
        a.appendChild(dot);
      }
      var text = document.createElement("span");
      var b = document.createElement("b");
      b.textContent = r.label;
      text.appendChild(b);
      if (r.sub) {
        var s = document.createElement("small");
        s.textContent = r.sub;
        text.appendChild(s);
      }
      a.appendChild(text);
      a.addEventListener("mouseenter", function () { highlight(i); });
      box.appendChild(a);
    });
    box.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function highlight(i) {
    var kids = box.children;
    for (var n = 0; n < kids.length; n++) {
      kids[n].classList.toggle("on", n === i);
    }
    active = i;
    if (kids[i]) kids[i].scrollIntoView({ block: "nearest" });
  }

  function look() {
    var q = input.value.trim();
    if (q === lastQuery) return;
    lastQuery = q;
    if (q.length < 1) { close(); return; }
    fetch("/api/search?q=" + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (input.value.trim() !== q) return;   // a later keystroke won
        open(d.results || []);
      })
      .catch(close);
  }

  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(look, 90);
  });
  input.addEventListener("focus", look);

  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (box.hidden || !rows.length) return;
      e.preventDefault();
      var next = active + (e.key === "ArrowDown" ? 1 : -1);
      if (next < 0) next = rows.length - 1;
      if (next >= rows.length) next = 0;
      highlight(next);
    } else if (e.key === "Enter") {
      if (active >= 0 && rows[active]) {
        e.preventDefault();
        window.location.href = rows[active].url;
      }
    } else if (e.key === "Escape") {
      close();
      input.blur();
    }
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".sitesearch")) close();
  });

  // "/" focuses the box, the way it does in every other reference site.
  document.addEventListener("keydown", function (e) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing) {
      e.preventDefault();
      input.focus();
      input.select();
    }
  });
})();

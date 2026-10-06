"use strict";
(() => {
  const C = window.TriviaCore;
  const KEY = "commonplace.v1", SESSION = "commonplace.session.v1";
  const $ = s => document.querySelector(s);
  const view = $("#view");
  const levels = {1: "Foundation", 2: "Connections", 3: "Deep cuts"};
  let state = C.empty(), bank = [], byId = new Map(), topics = [], manifest = {}, entities = null;
  let searchIndex = new Map();
  let session = null, libraryPage = 0, explorePath = [], routeToken = 0;
  let activeEntity = null, entityLimit = 48;
  let libraryFilter = {q: "", topic: "", level: "", kind: "", status: ""};
  const e = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const fmt = n => Number(n).toLocaleString();
  const date = n => new Date(n).toLocaleDateString(undefined, {month: "short", day: "numeric"});
  const topicName = id => topics.find(t => t.id === id)?.name || "My notebook";
  const activeCards = () => [...bank, ...state.custom].filter(c => !state.hidden.includes(c.id));
  const allCards = () => [...bank, ...state.custom];
  function notify(text) { $("#message").textContent = text; $("#message").hidden = false; }
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch { $("#storage-warning").hidden = false; }
  }
  function saveSession() {
    try { session ? sessionStorage.setItem(SESSION, JSON.stringify(session)) : sessionStorage.removeItem(SESSION); }
    catch { $("#storage-warning").hidden = false; }
  }
  function refreshIndex() {
    byId = new Map(allCards().map(c => [c.id, c]));
    searchIndex = new Map(allCards().map(c => [c.id, C.normalise(c.prompt + " " + c.answer + " " + c.explanation)]));
  }
  function stats() {
    const records = activeCards().map(c => state.progress[c.id]).filter(Boolean);
    const seen = records.reduce((n, p) => n + p.seen, 0), right = records.reduce((n, p) => n + p.correct, 0);
    return {seen: records.length, reviews: seen, right, due: records.filter(p => p.due <= Date.now()).length,
      fluent: records.filter(p => p.streak >= 3 && p.interval >= 7).length,
      today: records.filter(p => new Date(p.last).toDateString() === new Date().toDateString()).length,
      accuracy: seen ? Math.round(100 * right / seen) + "%" : "—"};
  }
  function statsHTML() {
    const s = stats();
    return `<div class="stats"><div class="stat"><strong>${fmt(s.due)}</strong><span>due for review</span></div><div class="stat"><strong>${fmt(s.seen)}</strong><span>facts encountered</span></div><div class="stat"><strong>${s.accuracy}</strong><span>unaided recall</span></div><div class="stat"><strong>${fmt(s.fluent)}</strong><span>well remembered</span></div></div>`;
  }
  function topicOptions(selected = "") {
    return topics.map(t => `<option value="${e(t.id)}" ${t.id === selected ? "selected" : ""}>${e(t.name)}</option>`).join("");
  }
  function tags(c) { return `<div class="tags"><span class="tag">${e(topicName(c.topic))}</span><span class="tag warm">${levels[c.level]}</span>${c.generated ? '<span class="tag">Wikidata</span>' : c.personal ? '<span class="tag">Your card</span>' : '<span class="tag">Curated</span>'}</div>`; }
  function source(c) { const url = C.safeURL(c.source); return url ? `<a class="reference" href="${e(url)}" target="_blank" rel="noopener noreferrer">${e(c.source_label || "Read more")} ↗</a>` : ""; }
  function go(route) { if (location.hash === "#" + route) renderRoute(); else location.hash = route; }
  function home() {
    const count = activeCards().length, s = stats();
    view.innerHTML = `<div class="hero"><div><p class="eyebrow">A LITTLE PRACTICE. A MUCH BIGGER WORLD.</p><h1>Become a person<br>who <em>knows things.</em></h1><p class="lede">Follow your curiosity. Connect the dots. Build the kind of knowledge that stays with you long after the quiz.</p></div><div class="orbit-art" aria-hidden="true"><div class="orbit"></div><div class="orbit two"></div><div class="orbit three"></div><span class="orbit-center">Aa</span><span class="orbit-label one">CURIOSITY</span><span class="orbit-label two">CONNECTIONS</span><span class="orbit-dot"></span></div></div>
    ${statsHTML()}
    ${session && !session.finished ? `<div class="notice">You have an unfinished ${session.mode === "challenge" ? "challenge (the clock continues)" : "study session"}. <button class="text-button" data-action="resume">Resume →</button></div>` : ""}
    <div class="practice-row"><article class="daily-card"><span class="tiny-label">YOUR DAILY PRACTICE</span><h2>A little wiser, every day.</h2><p>12 prompts. A mix of fresh discoveries and facts ready for another look. Type first, then connect the answer to its story.</p><button class="btn" data-start="study">Start studying <span aria-hidden="true">→</span></button> <button class="text-button light" data-start="review">Review due (${s.due})</button></article><article class="challenge-card"><span class="tiny-label">PUT IT TO THE TEST</span><h2>The mixed bag.</h2><p>20 questions. Four minutes. No hints. Practise retrieving names and facts when the clock is running.</p><button class="btn ghost" data-start="challenge">Take a challenge ↗</button></article></div>
    <div class="explore-banner"><div><span class="tiny-label">TAKE THE SCENIC ROUTE</span><h2>One answer opens another door.</h2><p>A painting → its artist → another work. Explore connected knowledge, then practise what you found.</p></div><button class="btn" data-go="explore">Find a rabbit hole →</button></div>
    <div class="section-heading"><h2>Where will curiosity take you?</h2><span>${fmt(count)} cards · ${topics.length} subjects</span></div>
    <div class="toolbar compact"><label>Difficulty <select id="home-level"><option value="">All levels</option><option value="1">Foundation</option><option value="2">Connections</option><option value="3">Deep cuts</option></select></label><label>Question bank <select id="home-kind"><option value="">All material</option><option value="curated">Curated teaching cards</option><option value="generated">Wikidata collection</option></select></label></div>
    <div class="topics">${topics.map(t => {
      const cards = activeCards().filter(c => c.topic === t.id), learned = cards.filter(c => (state.progress[c.id]?.streak || 0) >= 3).length;
      return `<button class="topic-card" data-topic="${e(t.id)}"><div class="topic-top"><span class="topic-icon">${t.symbol}</span><span>${fmt(cards.length)} cards ↗</span></div><h3>${e(t.name)}</h3><p>${e(t.description)}</p><div class="meter"><span style="width:${cards.length ? learned / cards.length * 100 : 0}%"></span></div><div class="topic-bottom"><span>${learned ? fmt(learned) + " familiar" : "A new place to begin"}</span><span>→</span></div></button>`;
    }).join("")}</div>`;
  }
  function start(mode, options = {}) {
    let pool = activeCards();
    const kind = $("#home-kind")?.value || "";
    if (kind) pool = pool.filter(c => kind === "generated" ? c.generated : !c.generated && !c.personal);
    const config = {mode, level: $("#home-level")?.value || "", ...options};
    const queue = C.queue(pool, state.progress, config);
    if (!queue.length) { notify(mode === "review" ? "Nothing is due yet. Start a study session to learn something new." : "No cards match these settings. Try another difficulty or collection."); return; }
    session = {mode, queue, index: 0, original: queue.length, results: [], pending: null,
      repeats: [], deadline: mode === "challenge" ? Date.now() + 240000 : null, finished: false};
    saveSession(); go("session");
  }
  function currentCard() { return session && byId.get(session.queue[session.index]); }
  function renderSession() {
    if (!session) return go("home");
    if (session.finished) return summary();
    if (session.deadline && Date.now() >= session.deadline) return finish(true);
    const c = currentCard();
    if (!c) return finish();
    const challenge = session.mode === "challenge";
    view.innerHTML = `<div class="session-head"><button class="btn ghost" data-go="home">← Study desk</button><span class="tag">${challenge ? "Four-minute challenge" : session.mode === "review" ? "Due reviews" : "Recall & connect"}</span><span class="${challenge ? "timer" : "small muted"}" id="session-clock">${challenge ? "" : `${session.index + 1} / ${session.queue.length}`}</span></div><div class="session-meter"><span style="width:${session.index / session.queue.length * 100}%"></span></div>
    <div class="question-shell"><article class="question-card">${tags(c)}<h1 id="question-prompt">${e(c.prompt)}</h1>
    <form class="answer-form" id="answer-form"><input id="answer" type="text" aria-labelledby="question-prompt" placeholder="Pull it from memory…" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="400"><button class="btn primary" type="submit">Check answer →</button></form>
    <div class="question-actions"><button class="text-button" data-action="reveal">${challenge ? "Pass this question" : "I don't know — teach me"}</button>${!challenge ? '<button class="text-button" data-action="hint">A small hint</button>' : ""}</div><div id="hint" class="hint" hidden></div><div id="feedback" class="feedback" aria-live="polite" hidden></div></article>
    <p class="session-note">${challenge ? "The clock keeps running while you read feedback or leave this page." : "Enter to check. A missed answer is the beginning of learning."} <button class="text-button" data-action="finish">Finish session</button></p></div>`;
    if (session.pending) renderFeedback(); else $("#answer").focus({preventScroll: true});
    updateClock();
  }
  function submitAnswer(reveal = false) {
    if (!session || session.pending || session.finished) return;
    if (session.deadline && Date.now() >= session.deadline) return finish(true);
    const c = currentCard(), text = $("#answer").value.trim();
    if (!text && !reveal) { $("#answer").focus(); return; }
    const correct = !reveal && C.judge(text, c);
    session.pending = {text, correct, recalled: correct && !session.hinted, hinted: !!session.hinted, reveal};
    saveSession(); renderFeedback();
  }
  function learningContent(c) {
    return `<h2>${e(c.answer)}</h2><p>${e(c.explanation || "Add an explanation to this card in your notebook.")}</p>${c.hook ? `<div class="memory"><span class="tiny-label">MAKE THE CONNECTION</span>${e(c.hook)}</div>` : ""}${source(c)}${c.generated ? '<p class="small muted">Community-maintained structured fact; inspect the source if the attribution seems incomplete. Any listed answer is accepted.</p>' : ""}`;
  }
  function relatedButtons(c) {
    const ids = c.entities || [];
    return `<div class="connection-actions">${ids.slice(0, 5).map(id => `<button class="btn ghost" data-entity="${e(id)}">Explore ${e(entities?.[id]?.name || (id === ids[0] ? "the subject" : "this connection"))} ↗</button>`).join("")}${!ids.length ? `<button class="btn ghost" data-related="${e(c.id)}">Follow this subject ↗</button>` : ""}<button class="text-button" data-save="${e(c.id)}">${state.saved.includes(c.id) ? "Saved to notebook ✓" : "Save to notebook +"}</button></div>`;
  }
  function renderFeedback() {
    const c = currentCard(), p = session.pending;
    if (!p) return;
    $("#answer-form").hidden = true;
    $(".question-actions").hidden = true;
    const f = $("#feedback"); f.hidden = false;
    f.innerHTML = `<span class="verdict ${p.recalled ? "" : "wrong"}">${p.recalled ? "You found it." : p.correct ? "Correct with a hint — keep practising." : p.reveal ? "A new connection to make." : "Not quite. Here's the connection."}</span>${p.text ? `<p class="small muted">You answered: ${e(p.text)}</p>` : ""}${learningContent(c)}
    ${session.mode === "challenge" ? '<div class="rating-row"><button class="btn primary" data-rate="good">Next question →</button></div>' : p.recalled ? '<p class="small muted">How easily did it come back?</p><div class="rating-row"><button class="btn" data-rate="hard">With effort</button><button class="btn primary" data-rate="good">Got it</button><button class="btn" data-rate="easy">Immediately</button></div>' : '<div class="rating-row"><button class="btn primary" data-rate="again">Keep learning →</button></div>'}
    ${relatedButtons(c)}<button class="text-button delete" data-hide="${e(c.id)}">Hide a questionable card</button>`;
    f.querySelector("[data-rate]")?.focus({preventScroll: true});
  }
  function grade(rating) {
    if (!session?.pending || session.finished) return;
    const c = currentCard(), p = session.pending;
    // Re-read current progress to avoid clobbering work completed in another tab.
    try { const latest = JSON.parse(localStorage.getItem(KEY)); if (latest?.version === 1) state.progress = C.validateBackup(latest).progress; } catch { /* keep working copy */ }
    state.progress[c.id] = C.review(state.progress[c.id], p.recalled, p.recalled ? rating : "again");
    session.results.push({id: c.id, recalled: p.recalled, text: p.text, hinted: p.hinted});
    if (!p.recalled && session.mode !== "challenge" && !session.repeats.includes(c.id) && !state.hidden.includes(c.id)) {
      session.queue.splice(Math.min(session.index + 4, session.queue.length), 0, c.id);
      session.repeats.push(c.id);
    }
    session.index++; session.pending = null; session.hinted = false;
    persist(); saveSession();
    if (session.index >= session.queue.length) finish(); else renderSession();
  }
  function finish(timedOut = false) {
    if (!session || session.finished) return;
    // Credit an answer that was checked before the deadline, even if Next wasn't pressed.
    if (session.pending) {
      const c = currentCard(), p = session.pending;
      state.progress[c.id] = C.review(state.progress[c.id], p.recalled, p.recalled ? "good" : "again");
      session.results.push({id: c.id, recalled: p.recalled, text: p.text, hinted: p.hinted});
      session.pending = null; persist();
    }
    session.finished = true; session.timedOut = timedOut; saveSession(); summary();
  }
  function summary() {
    const first = [...new Map([...session.results].reverse().map(r => [r.id, r])).values()];
    const right = first.filter(r => r.recalled).length;
    const denominator = session.mode === "challenge" ? session.original : first.length;
    const missed = first.filter(r => !r.recalled);
    view.innerHTML = `<div class="summary"><p class="eyebrow">${session.timedOut ? "TIME'S UP" : "A LITTLE MORE CONNECTED"}</p><h1>${session.mode === "challenge" ? "Your mixed bag, unpacked." : "That knowledge is taking root."}</h1><div class="big-score">${right}<small> / ${denominator}</small></div><p class="muted">Unaided first-attempt recall. ${session.results.length > first.length ? `${session.results.length - first.length} additional review attempts completed.` : ""} ${session.mode === "challenge" && first.length < denominator ? `${denominator - first.length} unanswered.` : ""}</p><p class="small muted">Missed or hinted answers return sooner. Unanswered challenge questions do not change your review schedule.</p><div class="summary-actions"><button class="btn primary" data-go="home">Back to the desk →</button>${missed.length ? '<button class="btn" data-action="retry-missed">Revisit the misses</button>' : ""}<button class="btn" data-go="explore">Follow a rabbit hole</button></div><div class="results">${first.map(r => {
      const c = byId.get(r.id); return `<div class="result-row"><span class="verdict ${r.recalled ? "" : "wrong"}">${r.recalled ? "Recalled" : "Revisit"}</span><p>${e(c.prompt)}</p><strong>${e(c.answer)}</strong> <button class="text-button" data-card="${e(c.id)}">Open the connection →</button></div>`;
    }).join("")}</div></div>`;
  }
  function updateClock() {
    if (!session || session.finished || !session.deadline || !$("#session-clock")) return;
    const seconds = Math.max(0, Math.ceil((session.deadline - Date.now()) / 1000));
    $("#session-clock").textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    if (!seconds) finish(true);
  }
  function library() {
    view.innerHTML = `<p class="eyebrow">BUILD YOUR MENTAL BOOKSHELF</p><h1>The knowledge library.</h1><p class="lede">Search a clue, answer or explanation. Filter down to a subject, then practise that collection.</p><div class="toolbar"><input id="library-search" type="search" aria-label="Search knowledge" placeholder="Try Mozart, moons, ancient history…" value="${e(libraryFilter.q)}"><select id="library-topic" aria-label="Subject"><option value="">Every subject</option>${topicOptions(libraryFilter.topic)}</select><select id="library-level" aria-label="Difficulty"><option value="">Every level</option>${Object.entries(levels).map(([id, name]) => `<option value="${id}" ${libraryFilter.level === id ? "selected" : ""}>${name}</option>`).join("")}</select><select id="library-kind" aria-label="Collection"><option value="">All material</option><option value="curated">Curated</option><option value="generated">Wikidata</option><option value="personal">My cards</option></select><select id="library-status" aria-label="Review status"><option value="">All cards</option><option value="due">Due now</option><option value="new">Unseen</option><option value="saved">Saved</option><option value="hidden">Hidden</option></select></div><div class="section-heading"><span id="library-count"></span><button class="btn primary" data-action="practice-filter">Practise this collection →</button></div><div id="library-results" class="library-grid"></div><div id="library-paging" class="toolbar"></div>`;
    $("#library-kind").value = libraryFilter.kind; $("#library-status").value = libraryFilter.status;
    renderLibraryResults();
  }
  function filteredLibrary() {
    const f = libraryFilter, terms = C.normalise(f.q).split(" ").filter(Boolean);
    return allCards().filter(c => {
      const p = state.progress[c.id], hidden = state.hidden.includes(c.id);
      return (f.status === "hidden" ? hidden : !hidden) && (!f.topic || c.topic === f.topic)
        && (!f.level || c.level === Number(f.level))
        && (!f.kind || (f.kind === "generated" ? c.generated : f.kind === "personal" ? c.personal : !c.generated && !c.personal))
        && (!f.status || f.status === "hidden" || (f.status === "due" ? p && p.due <= Date.now() : f.status === "new" ? !p : state.saved.includes(c.id)))
        && terms.every(t => searchIndex.get(c.id).includes(t));
    });
  }
  function renderLibraryResults() {
    const filtered = filteredLibrary(), pageSize = 30;
    $("#library-count").textContent = `${fmt(filtered.length)} cards · answers stay hidden until you open them`;
    $("#library-results").innerHTML = filtered.slice(libraryPage * pageSize, (libraryPage + 1) * pageSize).map(c => `<article class="library-card">${tags(c)}<h3>${e(c.prompt)}</h3><button class="btn ghost" data-card="${e(c.id)}">Open study card →</button>${state.hidden.includes(c.id) ? `<button class="text-button" data-unhide="${e(c.id)}">Restore card</button>` : ""}</article>`).join("") || '<p class="empty">No matching cards. Try a broader search or another filter.</p>';
    $("#library-paging").innerHTML = `<button class="btn" data-page="-1" ${libraryPage === 0 ? "disabled" : ""}>← Previous</button><span class="small muted">Page ${libraryPage + 1} of ${Math.max(1, Math.ceil(filtered.length / pageSize))}</span><button class="btn" data-page="1" ${(libraryPage + 1) * pageSize >= filtered.length ? "disabled" : ""}>Next →</button>`;
  }
  function showCard(id) {
    const c = byId.get(id); if (!c) return;
    $("#dialog-content").innerHTML = `${tags(c)}<h2 id="dialog-title">${e(c.prompt)}</h2>${learningContent(c)}${relatedButtons(c)}<div class="rating-row"><button class="btn primary" data-practice-card="${e(c.id)}">Practise this card</button></div><p class="small muted">Reading a card does not count as successful recall.</p>`;
    $("#card-dialog").showModal();
  }
  function progress() {
    view.innerHTML = `<p class="eyebrow">UNDERSTAND WHAT STICKS</p><h1>Your knowledge, growing.</h1>${statsHTML()}<p class="small muted">“Well remembered” means at least three consecutive recalls and a review interval of seven days or more. It is a study signal, not a guarantee of mastery.</p><div class="panel"><h2>A map of your practice</h2>${topics.map(t => {
      const cards = activeCards().filter(c => c.topic === t.id), records = cards.map(c => state.progress[c.id]).filter(Boolean);
      const seen = records.reduce((n,p) => n + p.seen, 0), right = records.reduce((n,p) => n + p.correct, 0);
      return `<div class="progress-row"><span>${e(t.name)}</span><div class="meter"><span style="width:${seen ? 100 * right / seen : 0}%"></span></div><span>${seen ? Math.round(100 * right / seen) + "% recall" : "Unexplored"}</span></div>`;
    }).join("")}</div><div class="two-col"><section class="panel"><h2>Keep your knowledge.</h2><p class="small muted">Progress, saved cards, personal notes and JetPunk scores live in this browser on this site address. A different browser or port has separate storage. Export before clearing browser data.</p><button class="btn primary" data-action="export">Download backup ↓</button><p class="small muted">Restore replaces this browser's saved study data. Export first if you want to keep both.</p><label>Restore a Commonplace backup<input class="file-input" id="backup-file" type="file" accept="application/json,.json"></label></section><section class="panel"><h2>Where the facts come from</h2><p class="small">120 original teaching cards, plus ${fmt(manifest.cards || 0)} generated cards connecting ${fmt(manifest.entities || 0)} Wikidata entities.</p><p class="small muted">Wikidata's structured data is CC0. Imported facts are community maintained and have not all been reviewed by a human. Difficulty uses approximate popularity, not quiz success rates. Use Hide on a questionable card; hidden cards can be restored in the library.</p><p class="small muted">${manifest.built_at ? "Dataset built " + e(date(Date.parse(manifest.built_at))) + "." : "No expanded dataset has been built yet."} ${manifest.failed_slices?.length ? "Unavailable slices: " + e(manifest.failed_slices.join(", ")) : ""}</p><a class="reference" href="https://www.wikidata.org/wiki/Wikidata:Licensing" target="_blank" rel="noopener noreferrer">Wikidata licensing ↗</a></section></div>`;
  }
  function notebook() {
    view.innerHTML = `<p class="eyebrow">TURN A MISS INTO A MEMORY</p><h1>Your personal commonplace.</h1><p class="lede">Keep a useful discovery. Write a clue in your own words, connect it to something you know, and let it return in your reviews.</p><div class="two-col"><section class="panel"><h2>Add a study card</h2><form id="card-form" class="form-grid"><label>Question<input name="prompt" required maxlength="700" placeholder="A specific clue with a clear answer"></label><label>Answer<input name="answer" required maxlength="300"></label><label>Also accept <small>(separate with semicolons)</small><input name="aliases" maxlength="1000" placeholder="Surname; alternative spelling"></label><div class="two-col"><label>Subject<select name="topic">${topicOptions()}</select></label><label>Difficulty<select name="level"><option value="1">Foundation</option><option value="2" selected>Connections</option><option value="3">Deep cuts</option></select></label></div><label>Why it matters / explanation<textarea name="explanation" maxlength="3000" required></textarea></label><label>Memory connection<input name="hook" maxlength="700" placeholder="Connect the name to a place, event or work"></label><label>Reference URL <small>(optional)</small><input name="source" type="url" maxlength="1000" placeholder="https://…"></label><button class="btn primary" type="submit">Add to my practice +</button></form></section><section class="panel"><h2>A better way to miss a question</h2><ol class="help-list"><li>Play a JetPunk quiz without looking up answers.</li><li>Pick a few misses you want to understand. Check the facts against a reliable reference.</li><li>Write your own clue and an explanation. Include accepted alternative names.</li><li>Explore the answer's connections. A name attached to a story is easier to retrieve.</li><li>Return tomorrow and try to recall it again.</li></ol><h2>${state.custom.length} personal cards</h2>${state.custom.slice(-20).reverse().map(c => `<div class="result-row"><strong>${e(c.prompt)}</strong><div><button class="text-button" data-card="${e(c.id)}">Read</button> · <button class="text-button delete" data-delete="${e(c.id)}">Delete</button></div></div>`).join("") || '<p class="small muted">Your discoveries will appear here.</p>'}<h2 class="space-top">${state.saved.length} saved discoveries</h2><button class="btn" data-action="saved-library">Browse saved cards →</button></section></div>`;
  }
  function benchmarks() {
    view.innerHTML = `<p class="eyebrow">TAKE YOUR KNOWLEDGE OUTSIDE</p><h1>The real quiz is the benchmark.</h1><p class="lede">JoeRainford's Extremely Hard General Knowledge series inspired this studio's breadth. Practise here, then test yourself there.</p><a class="btn" href="https://www.jetpunk.com/series/228770/extremely-hard-general-knowledge" target="_blank" rel="noopener noreferrer">Open the full JetPunk series ↗</a><div class="two-col"><section class="panel"><h2>Log a result</h2><p class="small muted">Record your score after playing on JetPunk. These are your own entries, not automatically verified scores.</p><form id="benchmark-form" class="form-grid"><div class="two-col"><label>Quiz number<input name="quiz" type="number" min="1" max="92" step="1" required></label><label>Score out of 20<input name="score" type="number" min="0" max="20" step="1" required></label></div><button class="btn primary">Save result</button></form></section><section class="panel"><h2>Your recent attempts</h2>${state.benchmarks.slice(-8).reverse().map(b => `<div class="attempt"><span>Quiz #${b.quiz} · ${date(b.at)}</span><strong>${b.score}/20</strong></div>`).join("") || '<p class="small muted">Try a quiz now to establish your starting point. Use an unseen quiz later to test whether your knowledge transfers.</p>'}</section></div><div class="section-heading space-top"><h2>Pick a quiz</h2><span>92 listed when reviewed · opens on JetPunk</span></div><div class="quiz-links">${Array.from({length:92},(_,i)=>i+1).map(n => {
      const attempts = state.benchmarks.filter(b=>b.quiz===n), best = attempts.length ? Math.max(...attempts.map(b=>b.score)) : null;
      return `<a class="quiz-link ${best !== null ? "done" : ""}" href="https://www.jetpunk.com/user-quizzes/228770/extremely-hard-general-knowledge-${n}" target="_blank" rel="noopener noreferrer">#${n}<small>${best === null ? "Play ↗" : "Best " + best + "/20"}</small></a>`;
    }).join("")}</div><p class="small muted space-top">Independent companion, not affiliated with JetPunk. The practice bank contains original prompts and open structured facts, not a reproduction of the series.</p>`;
  }
  async function ensureGraph() {
    if (entities) return;
    const response = await fetch(document.body.dataset.bankUrl.replace(/bank$/, "graph")).catch(() => null);
    if (!response?.ok) throw new Error("Couldn't open the connection library. Please try again.");
    entities = (await response.json()).entities;
    explorePath = explorePath.filter(id => entities[id]);
  }
  async function explore(id, token) {
    view.innerHTML = '<div class="loading">Following the connections…</div>';
    try { await ensureGraph(); } catch (err) { if(token === routeToken) view.innerHTML = `<p class="empty">${e(err.message)}</p>`; return; }
    if (token !== routeToken) return;
    if (id && entities[id]) return entityPage(id);
    const popular = Object.values(entities).filter(n => n.links.length >= 3).sort((a,b)=>b.links.length-a.links.length);
    const starters = [];
    for (const topic of topics) {
      const found = popular.find(n => n.topics.includes(topic.id) && !starters.includes(n));
      if (found) starters.push(found);
    }
    view.innerHTML = `<p class="eyebrow">CURIOSITY DOESN'T TRAVEL IN STRAIGHT LINES</p><h1>Find your next<br><em>rabbit hole.</em></h1><p class="lede">Start with a name you recognise. Follow a work to its creator, a creator to another work, or a place to its neighbours in knowledge.</p><div class="toolbar"><input type="search" id="entity-search" aria-label="Search connected entities" placeholder="Search a person, book, painting, film, place…"></div><div id="entity-search-results"></div><div class="section-heading"><h2>A few doors to open</h2><span>${fmt(Object.keys(entities).length)} connected entities</span></div><div class="library-grid">${starters.map(entityTile).join("") || '<p class="empty">The connected dataset is not installed yet. The knowledge library is still available.</p>'}</div><section class="panel"><h2>Keep a thread, then test it.</h2><p class="small muted">Every connection is a readable link. Your trail appears above the current page. Use “Practise this trail” to turn browsing into recall, or save individual discoveries to revisit later.</p><a class="btn" href="/geography">Explore countries, cultures & places →</a></section>`;
  }
  function entityTile(n) {
    return `<button class="entity-tile" data-entity="${e(n.id)}"><span class="tag">${e(topicName(n.topics[0]))}</span><h3>${e(n.name)}</h3><p>${e(n.description || "Explore the works and subjects connected to this name.")}</p><span class="small">${n.links.length} connections →</span></button>`;
  }
  function entityPage(id) {
    const n = entities[id];
    if (activeEntity !== id) { activeEntity = id; entityLimit = 48; }
    if (explorePath[explorePath.length - 1] !== id) {
      const old = explorePath.indexOf(id);
      explorePath = old >= 0 ? explorePath.slice(0, old + 1) : [...explorePath, id].slice(-12);
    }
    try { sessionStorage.setItem("commonplace.trail.v1", JSON.stringify(explorePath)); } catch { /* optional navigation history */ }
    const links = new Map();
    n.links.forEach(l => l.targets.forEach(target => { if (entities[target]) links.set(l.relation + target, {relation:l.relation, node:entities[target], source:l.source}); }));
    const relatedCards = [...new Set(n.links.map(l=>l.card))].map(id=>byId.get(id)).filter(Boolean);
    const trailHasCards = explorePath.some(q => entities[q].links.some(l => byId.has(l.card)));
    view.innerHTML = `<div class="breadcrumbs"><button class="text-button" data-go="explore">Rabbit holes</button>${explorePath.map(q => `<span aria-hidden="true">/</span><button class="text-button" data-entity="${e(q)}" ${q===id?'aria-current="page"':""}>${e(entities[q].name)}</button>`).join("")}</div><div class="entity-heading"><p class="eyebrow">${e(n.topics.map(topicName).join(" · "))}</p><h1>${e(n.name)}</h1><p class="lede">${e(n.description || "A thread in your knowledge library.")}</p><a class="reference" href="https://www.wikidata.org/wiki/${e(id)}" target="_blank" rel="noopener noreferrer">Inspect Wikidata source ↗</a> ${C.safeURL(n.article) ? `<a class="reference" href="${e(n.article)}" target="_blank" rel="noopener noreferrer">Read the encyclopedia article ↗</a>` : ""}<div class="toolbar"><button class="btn primary" data-practice-entity="${e(id)}" ${relatedCards.length ? "" : "disabled"}>Practise these connections →</button><button class="btn" data-action="practice-trail" ${trailHasCards ? "" : "disabled"}>Practise this trail (${explorePath.length} stops)</button></div></div><div class="section-heading"><h2>Follow a connection</h2><span>${links.size} paths from here</span></div><div class="library-grid">${[...links.values()].slice(0, entityLimit).map(l=>`<article class="connection-tile"><span class="tiny-label">${e(l.relation.toUpperCase())}</span>${entityTile(l.node)}${C.safeURL(l.source) ? `<a class="reference edge-source" href="${e(l.source)}" target="_blank" rel="noopener noreferrer">Source for this connection ↗</a>` : ""}</article>`).join("")}</div>${links.size>entityLimit?'<button class="btn space-top" data-action="more-connections">Show more connections ↓</button>':""}<div class="section-heading space-top"><h2>Turn the connection into recall</h2><span>${relatedCards.length} practice cards</span></div>${!relatedCards.length ? '<p class="small muted">This is an exploration connection, not a scored question. Follow another path to find practice material.</p>' : ""}<div class="library-grid">${relatedCards.slice(0, 8).map(c=>`<article class="library-card"><h3>${e(c.prompt)}</h3><button class="btn ghost" data-card="${e(c.id)}">Open study card →</button></article>`).join("")}</div>`;
  }
  async function followRelated(id) {
    const card = byId.get(id); if (!card) return;
    await ensureGraph();
    const match = Object.values(entities).find(n => [card.answer, ...card.aliases].some(a => C.normalise(a) === C.normalise(n.name)));
    $("#card-dialog").close();
    if (match) go("explore/" + match.id);
    else { libraryFilter = {q: card.answer, topic: "", level: "", kind: "", status: ""}; libraryPage = 0; go("library"); }
  }
  function exportBackup() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], {type:"application/json"}));
    const a = document.createElement("a"); a.href = url; a.download = "commonplace-backup-" + new Date().toISOString().slice(0,10) + ".json"; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function renderRoute() {
    const token = ++routeToken, [route, id] = location.hash.slice(1).split("/");
    $("#message").hidden = true;
    document.querySelectorAll("[data-view]").forEach(b => { b.classList.toggle("active", b.dataset.view === (route || "home")); b.setAttribute("aria-current", b.dataset.view === (route || "home") ? "page" : "false"); });
    if (route === "library") library();
    else if (route === "progress") progress();
    else if (route === "notebook") notebook();
    else if (route === "benchmarks") benchmarks();
    else if (route === "session") renderSession();
    else if (route === "explore") await explore(id, token);
    else home();
    window.scrollTo(0,0);
  }
  document.addEventListener("click", async ev => {
    const b = ev.target.closest("button, a"); if (!b) return;
    try {
      if (b.dataset.view) go(b.dataset.view);
      if (b.dataset.go) go(b.dataset.go);
      if (b.dataset.start) start(b.dataset.start);
      if (b.dataset.topic) start("study", {topic: b.dataset.topic});
      if (b.dataset.rate) grade(b.dataset.rate);
      if (b.dataset.card) showCard(b.dataset.card);
      if (b.dataset.entity) { $("#card-dialog").close(); go("explore/" + b.dataset.entity); }
      if (b.dataset.related) await followRelated(b.dataset.related);
      if (b.dataset.practiceEntity) start("study", {ids: entities[b.dataset.practiceEntity].links.map(l=>l.card)});
      if (b.dataset.practiceCard) { $("#card-dialog").close(); start("study", {ids:[b.dataset.practiceCard]}); }
      if (b.dataset.save) { const id=b.dataset.save; state.saved = state.saved.includes(id)?state.saved.filter(x=>x!==id):[...state.saved,id]; persist(); b.textContent=state.saved.includes(id)?"Saved to notebook ✓":"Save to notebook +"; }
      if (b.dataset.hide) { state.hidden=[...new Set([...state.hidden,b.dataset.hide])]; persist(); b.textContent="Hidden from future practice"; b.disabled=true; }
      if (b.dataset.unhide) { state.hidden=state.hidden.filter(id=>id!==b.dataset.unhide); persist(); renderLibraryResults(); }
      if (b.dataset.delete && confirm("Delete this personal card and its review history?")) { const id=b.dataset.delete; state.custom=state.custom.filter(c=>c.id!==id); delete state.progress[id]; state.saved=state.saved.filter(x=>x!==id); state.hidden=state.hidden.filter(x=>x!==id); persist(); refreshIndex(); notebook(); }
      if (b.dataset.page) { libraryPage += Number(b.dataset.page); renderLibraryResults(); }
      const action = b.dataset.action;
      if (action === "resume") go("session");
      if (action === "reveal") submitAnswer(true);
      if (action === "hint" && !session.pending) {
        session.hinted = true; saveSession(); const answer = currentCard().aliases[0] || currentCard().answer;
        $("#hint").textContent = `Starts with “${answer[0]}”. ${answer.length} characters in one accepted answer. Hinted recall returns sooner.`; $("#hint").hidden=false;
      }
      if (action === "finish") finish();
      if (action === "retry-missed") start("study", {ids:[...new Set(session.results.filter(r=>!r.recalled).map(r=>r.id))]});
      if (action === "practice-filter") start("study", {ids:filteredLibrary().map(c=>c.id)});
      if (action === "practice-trail") start("study", {ids:[...new Set(explorePath.flatMap(id=>entities[id].links.map(l=>l.card)))]});
      if (action === "more-connections" && activeEntity) { entityLimit += 48; entityPage(activeEntity); }
      if (action === "saved-library") { libraryFilter={q:"",topic:"",level:"",kind:"",status:"saved"}; libraryPage=0; go("library"); }
      if (action === "export") exportBackup();
      if (b.classList.contains("dialog-close")) $("#card-dialog").close();
    } catch (err) { notify(err.message || "Something went wrong. Please try again."); }
  });
  document.addEventListener("submit", ev => {
    if (ev.target.id === "answer-form") { ev.preventDefault(); submitAnswer(); }
    if (ev.target.id === "card-form") {
      ev.preventDefault(); const data=Object.fromEntries(new FormData(ev.target));
      try { const card=C.validateCard({...data,id:"custom-"+crypto.randomUUID(),level:Number(data.level),aliases:data.aliases.split(";").map(s=>s.trim()).filter(Boolean)}); state.custom.push(card); persist(); refreshIndex(); notebook(); notify("Added to your notebook and study queue."); } catch(err) { notify(err.message); }
    }
    if (ev.target.id === "benchmark-form") {
      ev.preventDefault(); const f=new FormData(ev.target), record={quiz:Number(f.get("quiz")),score:Number(f.get("score")),at:Date.now()};
      try { C.validateBackup({...C.empty(), benchmarks:[record]}); state.benchmarks.push(record); persist(); benchmarks(); notify("JetPunk score saved."); } catch(err) { notify(err.message); }
    }
  });
  document.addEventListener("input", ev => {
    if (ev.target.id.startsWith("library-")) { libraryFilter={q:$("#library-search").value,topic:$("#library-topic").value,level:$("#library-level").value,kind:$("#library-kind").value,status:$("#library-status").value}; libraryPage=0; renderLibraryResults(); }
    if (ev.target.id === "entity-search") {
      const q=C.normalise(ev.target.value), matches=q?Object.values(entities).filter(n=>C.normalise(n.name+" "+n.description).includes(q)).slice(0,24):[];
      $("#entity-search-results").innerHTML=q?`<div class="library-grid">${matches.map(entityTile).join("") || '<p class="empty">No matching entity in this dataset. Try another name.</p>'}</div>`:"";
    }
  });
  document.addEventListener("change", async ev => {
    if (ev.target.id !== "backup-file" || !ev.target.files[0]) return;
    try {
      if(ev.target.files[0].size>20*1024*1024) throw new Error("Backup exceeds 20 MB.");
      const restored=C.validateBackup(JSON.parse(await ev.target.files[0].text()));
      if (!confirm(`Replace local study data with ${Object.keys(restored.progress).length} progress records and ${restored.custom.length} personal cards?`)) return;
      state=restored; session=null; persist(); saveSession(); refreshIndex(); progress(); notify("Backup restored.");
    } catch(err) { notify("Backup wasn't restored: "+err.message); }
  });
  window.addEventListener("hashchange", renderRoute);
  async function init() {
    $("#today").textContent=new Date().toLocaleDateString(undefined,{weekday:"short",month:"long",day:"numeric"});
    try { const raw=localStorage.getItem(KEY); if(raw) state=C.validateBackup(JSON.parse(raw)); }
    catch { $("#storage-warning").hidden=false; notify("Saved data could not be loaded. Restore a backup in Your progress if needed."); }
    try {
      const response=await fetch(document.body.dataset.bankUrl); if(!response.ok) throw new Error("The question library could not be loaded.");
      const data=await response.json(); bank=data.cards; topics=data.topics; manifest=data.manifest || {}; refreshIndex();
      try { const trail=JSON.parse(sessionStorage.getItem("commonplace.trail.v1") || "[]"); if(Array.isArray(trail) && trail.length<=12 && trail.every(q=>/^Q\d+$/.test(q))) explorePath=trail; } catch { /* start a fresh trail */ }
      try { const raw=sessionStorage.getItem(SESSION), saved=raw?JSON.parse(raw):null; if(saved && Array.isArray(saved.queue) && saved.queue.length<=100 && saved.queue.every(id=>byId.has(id)) && Array.isArray(saved.results) && Number.isInteger(saved.index) && saved.index>=0 && saved.index<=saved.queue.length) session=saved; } catch { /* discard invalid tab state */ }
      await renderRoute(); setInterval(updateClock,500);
    } catch(err) { view.innerHTML=`<div class="empty"><h1>Let's try that again.</h1><p>${e(err.message)}</p><button class="btn" onclick="location.reload()">Reload library</button></div>`; }
  }
  init();
})();

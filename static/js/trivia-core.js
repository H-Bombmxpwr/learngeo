/* Pure learning/validation functions, shared by the interface and browser tests. */
"use strict";
window.TriviaCore = (() => {
  const DAY = 86400000;
  const empty = () => ({version: 1, progress: {}, custom: [], benchmarks: [], saved: [], hidden: []});
  function normalise(s) {
    return String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
      .replace(/&/g, " and ").replace(/[’']/g, "").replace(/−/g, "-").replace(/[^a-z0-9.\s-]/g, " ")
      .replace(/([a-z])-(?=[a-z])/g, "$1 ").trim().replace(/^the\s+/, "").replace(/\s+/g, " ").trim();
  }
  function judge(text, card) {
    const answer = normalise(text);
    return !!answer && [card.answer, ...card.aliases].some(a => normalise(a) === answer);
  }
  function review(previous, recalled, rating, now = Date.now()) {
    const p = previous || {seen: 0, correct: 0, streak: 0, interval: 0};
    const interval = !recalled || rating === "again" ? 10 / 1440
      : rating === "hard" ? Math.max(1, p.interval * 1.2)
      : rating === "easy" ? Math.max(4, p.interval * 3)
      : Math.max(1, p.interval * 2);
    return {seen: p.seen + 1, correct: p.correct + Number(recalled),
      streak: recalled && rating !== "again" ? p.streak + 1 : 0,
      interval: Math.min(interval, 365), due: now + Math.min(interval, 365) * DAY, last: now};
  }
  function shuffle(items) {
    const copy = [...items];
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
  }
  function queue(cards, progress, options = {}, now = Date.now()) {
    let pool = cards.filter(c => (!options.topic || c.topic === options.topic)
      && (!options.level || c.level === Number(options.level))
      && (!options.ids || options.ids.includes(c.id)));
    // Interleave subjects so a thousand films cannot drown out ten language cards.
    function balanced(items) {
      const buckets = new Map();
      for (const item of shuffle(items)) {
        if (!buckets.has(item.topic)) buckets.set(item.topic, []);
        buckets.get(item.topic).push(item);
      }
      const ordered = [];
      while (buckets.size) {
        for (const topic of shuffle([...buckets.keys()])) {
          ordered.push(buckets.get(topic).pop());
          if (!buckets.get(topic).length) buckets.delete(topic);
        }
      }
      return ordered;
    }
    if (options.mode === "challenge") return balanced(pool).slice(0, 20).map(c => c.id);
    const due = shuffle(pool.filter(c => progress[c.id] && progress[c.id].due <= now))
      .sort((a, b) => progress[a.id].due - progress[b.id].due);
    if (options.mode === "review") return due.slice(0, 12).map(c => c.id);
    const fresh = balanced(pool.filter(c => !progress[c.id]));
    const future = balanced(pool.filter(c => progress[c.id] && progress[c.id].due > now));
    // Reviews get the first eight slots; leave room for discovery on a busy day.
    return [...due.slice(0, 8), ...fresh, ...due.slice(8), ...future].slice(0, 12).map(c => c.id);
  }
  function safeURL(value) {
    try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) && !u.username && !u.password ? u.href : ""; }
    catch { return ""; }
  }
  function validateCard(c) {
    if (!c || typeof c !== "object") throw new Error("Each card must be an object.");
    const required = {id: 100, prompt: 700, answer: 300, topic: 40, explanation: 3000, hook: 700};
    const out = {};
    for (const [key, limit] of Object.entries(required)) {
      if (typeof c[key] !== "string" || c[key].length > limit || (!c[key].trim() && ["id", "prompt", "answer", "topic"].includes(key)))
        throw new Error(`Invalid card ${key}.`);
      out[key] = c[key].trim();
    }
    if (!/^custom-[a-zA-Z0-9-]+$/.test(out.id)) throw new Error("Personal card IDs must start with custom-.");
    if (!Array.isArray(c.aliases) || c.aliases.length > 30 || c.aliases.some(a => typeof a !== "string" || a.length > 300))
      throw new Error("Aliases must be a list of short answers.");
    out.aliases = c.aliases;
    if (![1, 2, 3].includes(c.level)) throw new Error("Difficulty must be 1, 2 or 3.");
    out.level = c.level;
    out.source = safeURL(c.source || ""); out.source_label = "Your reference";
    out.personal = true;
    return out;
  }
  function validateBackup(data) {
    if (!data || data.version !== 1 || !data.progress || typeof data.progress !== "object" || Array.isArray(data.progress)
      || !Array.isArray(data.custom) || !Array.isArray(data.benchmarks)) throw new Error("This isn't a Commonplace v1 backup.");
    if (Object.keys(data.progress).length > 50000 || data.custom.length > 5000 || data.benchmarks.length > 10000)
      throw new Error("Backup is too large.");
    const result = empty();
    for (const [key, p] of Object.entries(data.progress)) {
      if (!/^[a-zA-Z0-9-]{1,100}$/.test(key) || !p || typeof p !== "object") throw new Error("Invalid progress record.");
      const clean = {};
      for (const field of ["seen", "correct", "streak", "interval", "due", "last"]) {
        if (typeof p[field] !== "number" || !Number.isFinite(p[field]) || p[field] < 0 || p[field] > 1e15)
          throw new Error("Invalid progress number.");
        clean[field] = p[field];
      }
      if (![p.seen, p.correct, p.streak].every(Number.isInteger) || p.correct > p.seen || p.streak > p.seen)
        throw new Error("Inconsistent progress counts.");
      Object.defineProperty(result.progress, key, {value: clean, enumerable: true, writable: true, configurable: true});
    }
    result.custom = data.custom.map(validateCard);
    if (new Set(result.custom.map(c => c.id)).size !== result.custom.length) throw new Error("Duplicate personal card IDs.");
    result.benchmarks = data.benchmarks.map(b => {
      if (!b || !Number.isInteger(b.quiz) || b.quiz < 1 || b.quiz > 92 || !Number.isInteger(b.score)
        || b.score < 0 || b.score > 20 || typeof b.at !== "number" || !Number.isFinite(b.at) || b.at < 0)
        throw new Error("Invalid JetPunk attempt.");
      return {quiz: b.quiz, score: b.score, at: b.at};
    });
    for (const field of ["saved", "hidden"]) {
      const values = data[field] || [];
      if (!Array.isArray(values) || values.length > 50000 || values.some(id => typeof id !== "string" || !/^[a-zA-Z0-9-]{1,100}$/.test(id)))
        throw new Error("Invalid saved or hidden cards.");
      result[field] = [...new Set(values)];
    }
    return result;
  }
  return {DAY, empty, normalise, judge, review, queue, shuffle, safeURL, validateCard, validateBackup};
})();

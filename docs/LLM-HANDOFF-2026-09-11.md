# LearnGeo fixes and continuation handoff

> **Status, 2026-09-11 (second pass).** Everything under "Prioritized remaining
> work" has now been implemented except accounts, which were deliberately left
> out. What was done to each item, and what is genuinely still open, is written
> under each numbered heading below. Nothing here was deployed or committed.

## Product goal and user requests

Help someone learn a useful amount about **any country** through games and trivia. The user reported incorrect Niger language data; inconsistent Challenge/endless experiences; nonsensical questions; losing the run on refresh; forced country cards after mistakes; mobile map problems; and the screenshot incorrectly rejecting United States for Iraq War participation and claiming Japan was highlighted. They requested better games/dashboard UI, browser-based scores, broader and more accurate data, advice about accounts, and this written handoff. Continue fixing rather than only planning. No deployment or commit was performed.

## Implemented (first pass)

### Games, answers and feedback

- `app.py`: matching now normalizes country/map answers across ISO2 and ISO3. Responses include `answer_iso3` for map highlighting and the actual answer text and awarded points.
- `static/js/play.js`: highlight the right ISO3 geometry, cap answer zoom, and do not claim a map highlight exists for a text question. End-of-run feedback names the answer rather than blindly naming the subject country.
- Wrong/correct/skipped answers show inline feedback. Country/person/city cards are offered by buttons. Dismissing a card returns to feedback. The final score summary still opens at run end.
- Challenge preserves flag images, portraits and outlines. Previously it replaced those clues with a blank map. Restart retains Challenge, endless and country settings.
- `questions.CHOICE_REQUIRED` excludes prompts that require visible alternatives or accept an open-ended range of answers from typed Challenge. Both timed-length and endless Challenge use the same eligibility rules.
- War participation questions are **disabled in the API picker**. (Second pass: removed entirely; see item 3.)
- Typed matching no longer accepts any significant single word of a long answer (e.g. `democratic` for `democratic republic`). Negative numeric answers no longer pass by stripping their minus sign.
- Capital questions accept other recorded capitals; distractors exclude all recorded capitals. Generic attribute questions accept other recorded values. Attribute distractor searches now examine the full country pool; this materially increases continent/currency question coverage.
- Skip consumes its allowance and resets streak. Cut-two is disabled where there are no choices. Used lifelines and their displayed effects survive refresh. Mobile typed questions do not automatically summon the keyboard.

### Persistence and scores

- SQLite `active_runs(player, state)` stores the current question, pending answer, run state, and last feedback. The browser has an anonymous persistent cookie. `/play/...` resumes when category/style/length/country match. (Second pass: re-keyed per run; see item 4.)
- Answer keys and large payloads no longer live in the signed Flask cookie. API/page responses use `Cache-Control: no-store`.
- The player ID is stable throughout the first request.
- Fixed a SQLite resource leak: `ClosingConnection` closes after commit/rollback on context exit.
- `static/js/scores.js`: cumulative snapshots keyed by run UUID, preventing duplicate points on feedback replay. (Second pass: rewritten; see item 9.)
- Railway: set `LEARNGEO_DATA_DIR` to the **existing mounted volume's actual mount path**. This stores `progress.db`, including active runs. Keep a stable `LEARNGEO_SECRET`.

### UI and broader learning

- Game cards have separate labeled selectors for answer style and run length, plus one Play button. Fifteen topic categories now exist.
- A score dashboard appears on home, Games and Progress. Responsive form controls, focus indicators, compact map height, wrapped rail/lifelines, and a full-width mobile search improve usability.
- Question and hint precede the map so the task is visible first. Antarctica is omitted from quiz GeoJSON.
- Country pages offer **Practice [country]**, an endless Grand Tour scoped to that country.
- Added driving-side and calling-code generators, landmark-to-country questions, an Everyday Life category.

### Data corrections

Niger's national/working languages, Antigua and Barbuda's capital, and landmarks for Andorra and Barbados. (Second pass: moved into `learngeo/provenance.py` as sourced records; see item 1.)

---

# Second pass: the prioritized work, item by item

## 1. Data provenance and factual correctness — **done, and it found real errors**

New module **`learngeo/provenance.py`**. Corrections are records, not bare
values: each carries a `source` URL, an `as_of` date (when the fact is true
of), a `verified` date (when a human read the source), a `definition`, a
confidence, and a `note` saying why the imported value was wrong so it is not
reapplied. `apply()` runs **after** the fetch scripts and after
`supplement.py`, so neither a dataset rebuild nor the supplement can put a bad
value back, and it files what it changed under each country's `provenance`
key. Country pages show this as **Checked facts**, with the source link and
both dates.

Errors found and fixed:

- **Continents were wrong for 31 countries, including the obvious ones.**
  Wikidata's continent list is unordered and counts overseas territory, and
  the dataset used its first entry. France was filed under **Africa**, the
  Netherlands under **South America**, Spain under **Africa**, Norway under
  **Antarctica**, Russia under "Eurasia", and fourteen countries under
  "Insular Oceania", which is not a continent. This fed `continent_of`
  questions, the same-continent distractor logic, the atlas, the map panel and
  every country page. Each country is now filed under the continent containing
  its capital — a rule written down in `CONVENTIONS` and shown to the
  player — with genuinely transcontinental states accepting either answer and
  never being offered the other as a wrong option.
- **Mexico had no leaders at all** (the audit's one "missing leaders"
  warning). Added Claudia Sheinbaum, sourced to gob.mx.
- **EU and NATO membership are stale in the import**: the United Kingdom is
  still in the EU and the Netherlands is in neither. Verified lists for those
  two organisations live in `MEMBERSHIPS`; they are the only two the quiz asks
  about, and the imported `member_of` is not asked about at all.
- Niger, Antigua, Andorra and Barbados moved here from inline code.

`scripts/audit_data.py` now reports provenance coverage. Today: **62 of 197
countries carry at least one sourced fact, and 12 of 40 question types state
the convention their answer depends on.** Those two numbers going up is the
remaining work, and it is data-gathering, not code.

**Still open:** the bulk of the dataset is unsourced. Heads of state and
government have not been checked country by country against official sources.

## 2. Ambiguity audit — **done**

- `scripts/audit_data.py` grew an **ambiguity pass**: landmarks recorded in
  more than one country, landmarks known to be shared, city names two
  countries share, adjacent cities too close in size to rank, transcontinental
  countries, and countries with no city population data at all. It reports 53
  handled and 1 open.
- **Shared landmarks** (`provenance.SHARED_LANDMARKS`) are excluded both as
  answers and as distractors. "In which country is the Amazon rainforest?" has
  eight right answers and the ownership filter could not see it, because it
  only knew which countries happened to have recorded it.
- **Definitions are shown to the player** under the question, for every mode
  whose answer depends on one: what "largest city" measures, what "most
  spoken" means, what a trade share is a share of.
- **St./Saint** and friends are normalised in `matching.py`, along with `&`
  and "city of". `matches_text("Saint Johns", "St. John's")` now passes.
- Transcontinental countries and multi-capital countries accept every correct
  answer via `also`.
- **Found and fixed while testing:** the fuzzy matcher accepted **"Austria"
  for "Australia"** (ratio 0.842 against a 0.84 floor) — of all the pairs in
  the world to conflate, the single most common geography mistake there is. A
  typo does not change a word's length by two, so a length guard now rejects
  it; a transposition check was added at the same time so "Alegria" passes for
  "Algeria", which the docstring had always claimed and the code never did.

**Still open:** language shares carry no survey and no date. The convention is
stated; the figure is not sourced. The audit reports this as its one unhandled
ambiguity.

## 3. History redesign — **done**

`war_participant` is **gone**, not merely disabled. The reasoning is now
written into `supplement.py` and onto the Sources page: a list of principal
belligerents cannot settle participation in either direction. It omits
support, basing, occupation and reconstruction, so absence proves nothing —
which is exactly how the United States came to be marked wrong for the Iraq
War.

Every war association now states **what kind of claim it is**:

- `principal belligerent` — hand-written, by the modern state that succeeded
  the power that fought.
- `recorded participant` — from the bulk import, which does not distinguish
  combat from funding, basing or reconstruction.

**Japan is still attached to the Iraq War** in the imported data, and it is
kept: the association is real, and deleting inconvenient data is not
verification. It is labelled as the weaker claim it is, shown as such on the
country page and the fact card, and is the basis of no question. A test
asserts both that the US *is* recorded for the Iraq War and that Japan's row
carries the weaker role.

Four sourced history questions replace it, all built on things the curated
table can actually answer: `war_when` (the year a conflict began),
`war_order` (which of four came first, every option eight years apart),
`war_between` (only for the 13 wars fought between exactly two principals, so
there is one answer), and `figure_known_for` (who a hand-written historical
figure was, notes of three words or more only).

## 4. Concurrency and tabs — **done**

- **A run per tab, not per browser.** `active_runs` is keyed
  `(player, run_id)`. The run id lives in the URL: `/play/flags` redirects to
  `/play/flags?run=<id>`, and every API call names the run it means. Two tabs
  are two games; changing the settings in one no longer destroys the other.
- **Compare-and-set on every write.** Each row carries a `version`; a save
  states the version it read and is refused if the row has moved on. The API
  returns 409 with `conflict: true` and the page says so rather than silently
  flattening the other tab's game.
- **Answering is one transaction.** `store.commit_answer` writes the mastery
  card, the answer log, the finished-run row and the run state together or not
  at all.
- **Idempotency keys.** `answer_events(player, run_id, qid)` means a
  resubmitted answer — a double tap, a retry, two tabs racing — returns the
  first response instead of scoring twice.
- WAL journaling and a busy timeout, so readers do not queue behind writers.
- **Found and fixed while testing:** `/play/<category>` could **redirect
  forever** when a browser did not return its cookie (blocked cookies, or the
  page embedded cross-site). Each hop minted a new run and bounced again. The
  redirect is now capped at one hop.

## 5. State lifecycle — **done**

- `schema_meta` holds a schema version; `_migrate` carries version-1 rows
  (one active run per browser) forward into the new per-run table.
- `store.cleanup_stale()` sweeps runs untouched for a fortnight, called at
  most hourly from the play route.
- **Reset is now named, not one button that did three-quarters of a job.**
  `FORGET_SCOPES` separates server mastery and answers, finished-run history,
  and games in progress; browser scores are a fourth, cleared in the browser.
  The Progress page offers each separately, says in words what each one takes,
  and has one "Erase everything" that genuinely does.
- **Export and import both ways.** `/api/progress/export` and
  `/api/progress/import` for server progress; `GeoScores.export/import` for
  browser scores. One file picker handles both formats, because the two files
  look nothing alike. Mastery merges rather than overwriting.

## 6. Question variety and coverage — **done**

- **`questions.supported_modes(world, iso)`** asks every generator, three
  seeds each, and caches the answer. Country practice draws only from modes
  that can actually build a question, instead of retrying forty times hoping
  Tuvalu grows a land border.
- **`questions.balanced_mode`** draws from the least-used modes in the run, so
  practice spreads over the topics rather than over the dice. Eight questions
  on Tuvalu now produce eight different topics.
- **`questions.missing_topics`** names what a country has no data for, and
  the play page and country page say so out loud. A topic counts as missing
  only when none of its modes work.
- **Country mastery by domain**: `questions.DOMAINS` / `MODE_DOMAIN` group
  modes under the label a player sees.
- New questions, all from data already present: `population_size` (magnitude
  bands, with a guard against figures near a band edge), `eu_member` and
  `nato_member` (against the verified lists), and the four history modes.
- A category with no typed-answer modes — Alliances is all yes/no — falls back
  to multiple choice and says why, instead of failing to start.

**Still open:** food, culture, regions and national institutions need data the
dataset does not have. Adding them means gathering sourced facts, not writing
generators.

## 7. Mobile maps — **done, except real devices**

- **26 countries were not on the quiz map at all.** Singapore, Malta, Bahrain
  and every Pacific and Caribbean microstate have no polygon in this GeoJSON,
  so "find Tuvalu" had no right answer anywhere on screen. `/api/geo` now
  returns a `points` list and the map draws a labelled, clickable marker for
  each.
- **Antimeridian handling.** Rings that straddle 180° are unwrapped before the
  bounding box is taken; Fiji and Kiribati used to render as two specks at
  opposite edges of an empty rectangle.
- Reset-view button, a loading state, and an error state that falls back to a
  typed box so a map question stays answerable when the map does not load.
- **A keyboard-accessible alternative for every map question**: the typed box
  now appears alongside the map in ordinary mode too, judged identically.
  Clicking and typing are two ways into one question.
- Verified at 390px through a same-origin iframe harness (a raw small window
  is misleading on Windows — Edge keeps a wider minimum layout viewport).

**Still open:** no real iOS or Android device testing; no orientation-change
testing. Microstates are points, not shapes, which needs higher-resolution
licensed geometry to fix properly.

## 8. UI and accessibility — **done**

- **Cards are proper dialogs.** `presentSheet` adds an explicit Close button,
  closes on Escape, traps Tab inside the card, and returns focus to whatever
  opened it. Previously Tab walked off into the invisible page behind.
- **One live region.** The whole stage was `aria-live="polite"`, so every
  repaint read the prompt, the hint, all four options and the score out again.
  A single `#liveStatus` now announces the new question, or the verdict.
- **Typeahead no longer answers for you.** Selecting a row fills the box;
  answering is a separate keystroke. Picking the wrong row and losing a life
  in one action is a thing people do once and then stop using the list.
- **In-game Restart and Exit** in the rail, both confirmed.
- **Study one country** is on the Games page, not only on a country's page.
- Screenshots taken at desktop and 390px across games, play, map, challenge,
  progress, country and sources pages.

**Still open:** no screen-reader pass with an actual screen reader.

## 9. Scoring — **done**

- **Per-mode records.** Best is kept per category × answer style × run length.
  One "best score" across every game was not a personal best, it was whichever
  game happened to be scored most generously.
- **Two-option questions are worth half** a four-option one, and a bare map
  click — 197 countries, no options — is worth more (`CHOICE_WEIGHT`).
- **The speed bonus cannot be refreshed into existence.** The server stamps
  each question when it is handed out and takes whichever elapsed time is
  *longer*, so restarting the browser's clock can only cost you.
- **Retention.** 40 sessions are kept in full and older ones folded into
  running totals, so an endless-mode habit cannot grow localStorage until it
  hits the quota — which from the outside looks like the scores being lost.
- **Knowledge, not just speed.** Runs report the countries they covered and
  the dashboard shows **Countries met** alongside points.
- v1 scores migrate to the v2 store rather than being discarded.

## Accounts — deliberately not implemented

Left out at the user's request. The recommendation from the first pass stands:
keep anonymous browser-first play as the default and add optional accounts
only when cross-device sync, backup or social competition is a real need. The
export/import added under item 5 covers moving progress between devices by
hand, which is most of the value without any of the sign-up.

Note that server-side event scoring would still be needed before any trusted
public leaderboard: browser scores are personal practice data the player can
edit, and nothing here changes that.

## Verification

- `python -m unittest discover -s tests -v`: **33 tests pass**, covering all
  16 categories × two answer styles × two lengths, per-tab runs, CAS conflict,
  duplicate-submission idempotency, transactional answers, expired runs,
  schema version, stale sweeping, scoped forget, export/import round-trip,
  continent correctness, war roles, sourced history questions, shared
  landmarks, verified memberships, the mode inventory, balanced practice,
  choice-count scoring, the server clock, and map points.
- `python scripts/audit_data.py --output docs/data-audit.json`: 197 countries,
  **0 errors**, 65 review warnings, 53 ambiguities handled and 1 open.
- JavaScript parsed with esprima; pages rendered and screenshotted in headless
  Edge at desktop width and at 390px through a same-origin iframe.
- Not done: deployment, commit, real mobile devices, a screen-reader pass, and
  a fact-by-fact source audit of the bulk import.

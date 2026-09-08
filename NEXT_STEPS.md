# Next steps

State of LearnGeo as of 7 Sep 2026.

---

## What works now

197 countries, 19 question types, ten games each playable two ways: a scored
run of twelve with three lives, or casual practice with neither. Everything is
linked, and there is now a search box on every page that answers as you type
across countries, languages, wars, currencies, forms of government and the
~1,900 people in the dataset.

| Field | Coverage |
| --- | --- |
| Capitals, cities, flags, outlines | 196-197 / 197 |
| Language breakdown with percentages | 195 / 197 |
| Climate paragraph and zone | 196 / 197 |
| Government type | 191 / 197 |
| Exports, imports, partners, resources | 196 / 197 |
| Land borders | 156 / 197 (the rest are islands) |
| Wars | 197 / 197 |
| Historical figures | 197 / 197 |
| Wikipedia blurbs | 166 / 197 |

---

## Fixed in this pass

- **Borders were the maritime ones again.** `countries.json` had been
  overwritten by a `fetch_data.py` run that lost the polygon check, so Germany
  bordered ten countries including Sweden and Britain. Rebuilt from the
  checkpoint, which still had the filtered set. Germany is nine. Denmark and
  Vatican City had been dropped from the file entirely and are back.
- **Every war was a small one.** Wikidata records a war's participants as the
  state that fought, which before about 1950 no longer exists — so World War II
  had two participants, the War of 1812 had only the United States, and the
  Iraq War was the most widely shared conflict on earth. The belligerents of
  fifty major wars are now written out by hand in `learngeo/supplement.py`
  against their modern successors. World War II has 56, World War I has 41.
- **One language per country.** Wikidata's speaker counts barely exist, and its
  official-language lists are a different question — Sweden did not list
  Swedish, Guatemala had only Spanish. The Factbook's breakdown gives
  percentages and official status for 195 countries, and the topic pages now
  rank by share.
- **Official status was over-claimed.** Wikidata's P37 for the United States
  includes Spanish, Hawaiian, Chamorro and Carolinian — official in a state or
  a territory, not federally. It is now only consulted when the Factbook marks
  nothing official at all.
- **Government questions had four right answers.** Wikidata lists every form
  that applies at once, so China was a communist state, a socialist state, a
  unitary state and a one-party state, and three of them were marked wrong. The
  Factbook states one type per country.
- **Climate questions were unanswerable.** The zone came from latitude bands,
  so Brazil was "Tropical" with "Equatorial tropical" offered as a wrong
  answer. Seven mutually exclusive zones now, chosen from the country's own
  climate paragraph, taking whichever is named first — the Factbook writes the
  dominant climate before the exceptions.
- **Nobody was clickable.** The person queries kept a name and a photo but no
  identifier. Every person on the site is now a Wikipedia link.
- **Missing leaders.** A leader is modelled as the holder of an office, and the
  office often belongs to a state that has dissolved, so Gaddafi appeared
  nowhere on Libya's page and Modi nowhere on India's. Offices are queried both
  ways round, sitting leaders carry their party, and a curated table of two to
  four historical figures covers all 197 countries regardless.
- **Every filter on the site did nothing visible.** Rows were hidden with the
  `hidden` attribute while being flex or grid items, whose `display` beats it.
  One CSS rule fixed the atlas, the topic list and the new search page at once.
- **The map painted through the fact card.** Leaflet's panes carry z-index 400
  and its controls 800, with no stacking context to contain them. The map is
  now its own context and the card sits at 900.
- **Duplicate leaders on cards.** Presidential systems put one person in both
  chairs and the card printed them twice. The two roles are merged into one
  entry.
- **"Which borders both X and Y" had two right answers** whenever a distractor
  also touched both. Those are excluded now.

## Added

- **A search box in the header**, on every page, with keyboard navigation and
  `/` to focus.
- **`/games`**, listing all ten games with both run types, linked from the nav.
- **`/sources`**, explaining what each source is used for and what each gets
  wrong.
- **Economy on every country page and fact card** — exports, imports, trading
  partners with percentages, natural resources, industries, GDP per head. This
  took the place of the second row of portraits on the card.
- **A recent-news link** on every country page and card.
- **A run-over card** with the score, accuracy and best streak, instead of a
  sentence of grey text at the end of a row of buttons.
- **A logo**, used on the home page and as the favicon.
- **Shapes and Find It on the Map are separate games.**
- **Atlas sorting** by name, population, area, mastery or continent.

---

## Known gaps

**Famous faces still cover about 140 of 197.** The Wikidata query needs a
sitelink count that small countries rarely clear. `enrich_data.py famous` drops
the floor per country until something lands, but the endpoint rate-limits hard
over 197 sequential queries, so it wants running in a few sessions. The curated
historical figures cover the gap in the meantime.

**30 countries have no map shape.** `countries.geo.json` has 180 outlines, so
Singapore, Malta and most small island states never appear in outline or
find-it questions. They are excluded automatically. A higher-resolution GeoJSON
would close this.

**Citizenship is noisy.** Wikidata gives Oscar Wilde French citizenship, so he
can appear as a French face.

**City Wikipedia links are guessed** from the city name. Correct for large
cities, occasionally wrong for ambiguous ones.

**The curated tables are English-centric and incomplete by construction.** Two
to four figures per country is a sketch, not a canon, and the choice of who
counts is a judgement. They are all linked to their article so a reader can go
and disagree.

---

## Worth building next

- **Question types for the new data.** Cities, wars and exports are all in the
  dataset and nothing asks about them. "Which country fought in the Chaco War",
  "which of these is Chile's largest export" are both a dozen lines.
- **Review deck.** The picker favours due cards, but there is no dedicated
  "drill the 15 I keep missing" mode. The data is in `store.overview()`.
- **Daily challenge.** Seed the RNG from the date for one fixed set of 12 a
  day. Roughly 20 lines, and it is what makes Worldle sticky.
- **Type-the-answer mode.** Four-option multiple choice is generous; free text
  with fuzzy matching would retain far better.
- **People as pages.** Everyone has a QID and a Wikipedia link but no page
  here, so you cannot yet click a person to see their country and era.

## Smaller cleanups

- No tests. The question generators are pure functions of `(world, iso, rng)`
  and would be easy to cover, particularly that each returns `None` rather than
  raising when data is missing, and that no generator can produce a question
  with two correct answers.
- Score and the pending answer live in the Flask session cookie. Fine for one
  player locally; it would need moving server-side before going anywhere else.
- `data/_checkpoint.json` is 1.8MB of duplicated dataset in the repo. It earns
  its place while the fetch is unreliable, but it should be gitignored.

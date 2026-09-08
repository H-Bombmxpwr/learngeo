# Next steps

State of LearnGeo as of 7 Sep 2026.

---

## What works now

The dataset is fully built: **197 countries** (193 UN members plus Taiwan,
Kosovo, Palestine and Vatican City), and all 19 question types generate.

Everything is linked. A country page is a hub: click a language and you get
every country that speaks it with speaker counts; click a war and you get
everyone who fought in it; click a form of government and you get every country
that has used it, with the years. Topic pages live at `/topics`.

| Field | Coverage |
| --- | --- |
| Capitals, cities, Wikipedia links | 196-197 / 197 |
| Languages (ranked by speakers) | 196 / 197 |
| Current leaders | 196 / 197 |
| Past leaders | 167 / 197 |
| Land borders | 156 / 197 (the rest are islands) |
| Currencies | 175 / 197 |
| Government | 159 / 197 |
| Wars | 127 / 197 |
| Wikipedia blurbs | 163 / 197 |
| Famous people | 117 / 197 |
| Climate prose | 28 / 197 |

I sampled every question type and checked the answers: borders, capitals,
currencies, languages, leaders, past leaders, famous faces, area comparisons
and continents all came back correct.

---

## Bugs fixed in this pass

- **Maritime borders counted as land borders.** The US came back bordering
  Japan, Tonga and the Marshall Islands. Wikidata's P47 includes sea
  boundaries, so every candidate pair is now checked against the real polygons
  (~2km tolerance). Verified against 14 known pairs; US-Russia across the
  Bering Strait is correctly rejected. US is now Canada and Mexico.
- **Languages were official, not spoken.** The US listed Hawaiian, Samoan and
  Chamorro with no English, because it has no federal official language.
  Now uses P2936 "language used" with speaker-count qualifiers: English 215.4M.
- **Denmark and Vatican City were missing entirely** — neither is typed as a
  "sovereign state" in Wikidata. Both are now added by hand.
- **France had no president.** "Current leader" cannot be expressed as
  "statement with no end date"; Wikidata records scheduled end dates. Now
  compares end dates to today.
- **Famous-people queries timed out** on large countries. A Blazegraph
  optimizer hint takes France from a 71-second timeout to 7 seconds.
- **New York's boroughs ranked as US cities.** GeoNames files Brooklyn and
  Queens as PPLA2, the same code as Los Angeles, so they are excluded by name.

---

## Known gaps

**Famous people cover only 117 of 197 countries.** The query needs a Wikidata
sitelink count above 90, which small countries rarely clear. Lowering the floor
per country — or falling back to a lower threshold when the first pass returns
nothing — would fill most of the gap. This is the biggest remaining hole.

**Climate prose exists for only 28 countries**, because it comes from a
"Climate of X" Wikipedia article that mostly does not exist. The structured
`climate_zone` is on all 197, but it is derived from latitude bands plus an
override table, not Köppen data.

**30 countries have no map shape.** `countries.geo.json` has 180 outlines, so
Singapore, Malta and most small island states never appear in outline or
find-it-on-the-map questions. They are excluded automatically rather than
producing broken questions. A higher-resolution GeoJSON would close this.

**Citizenship is noisy.** Wikidata gives Oscar Wilde French citizenship, so he
can appear as a French face.

**City Wikipedia links are guessed** from the city name
(`/wiki/Buenos_Aires`). Correct for large cities, occasionally wrong for
ambiguous names. Cities have no QID, so they are not topic pages.

**`government_of` questions can feel arbitrary** when a country lists several
forms ("republic", "federal republic", "presidential system"). Distractors
never include another form that country holds, so the answer is unambiguous
against the data, but the question is not very illuminating.

---

## Worth building next

- **Question types for the new data.** Cities and wars are in the dataset but
  nothing asks about them yet: "which is the largest city of X", "which of
  these countries fought in the Korean War".
- **Endless mode has no button.** `/play/grand_tour?endless=1` already works.
- **Review deck.** The picker favours due cards, but there is no dedicated
  "drill the 15 I keep missing" mode. The data is in `store.overview()`.
- **Daily challenge.** Seed the RNG from the date for one fixed set of 12
  questions a day. Roughly 20 lines, and it is what makes Worldle sticky.
- **Type-the-answer mode.** Four-option multiple choice is generous; free text
  with fuzzy matching would retain far better.
- **People as topic pages.** Leaders and famous faces have QIDs already but no
  pages, so you cannot yet click a person to see their country and era.

## Smaller cleanups

- No tests. The question generators are pure functions of `(world, iso, rng)`
  and would be easy to cover, particularly that each returns `None` rather
  than raising when data is missing.
- Score and the pending answer live in the Flask session cookie. Fine for one
  player locally; it would need moving server-side before going anywhere else.

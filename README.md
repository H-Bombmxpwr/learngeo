# LearnGeo

A world-knowledge quiz show and a linked encyclopaedia in one. Flags, outlines,
land borders, capitals, largest cities, leaders past and present, famous faces,
wars, languages, climate and politics for 197 countries — and a fact card with
photos after **every** answer, right or wrong.

The idea: quiz games test you, encyclopaedias teach you. This does both. You
play on a dark stage; the answer arrives on atlas paper.

**Everything is linked.** Click a language and see all 64 countries that speak
it, with speaker counts. Click a war and see everyone who fought in it. Click a
form of government and see who has used it, and when. Start at a country and
wander — the way a Wikipedia evening actually goes.

## Run it

```bash
uv sync
uv run python app.py
```

Then open <http://127.0.0.1:5000>.

The dataset is already built, so it starts immediately.

## Rebuild the dataset

```bash
uv run python scripts/fetch_data.py
```

Pulls from Wikidata and Wikipedia into `data/countries.json`. It resumes from a
checkpoint, so it is safe to interrupt and rerun. Nothing hits the network at
request time — once built, the app works offline apart from the images.

## How it works

| File | What it does |
| --- | --- |
| `app.py` | Routes, run state, scoring, fact cards |
| `learngeo/data.py` | Loads the dataset, shapes, and the topic index |
| `learngeo/questions.py` | 19 question generators |
| `learngeo/store.py` | SQLite progress and the spaced-repetition picker |
| `scripts/fetch_data.py` | Builds the dataset from Wikidata |
| `data/countries.geo.json` | Country outlines, for silhouettes and the map |

**Adaptive.** Every (country, question type) pair is a flashcard. Get one right
and it comes back later; get it wrong and it returns within minutes. Difficulty
opens up as you improve — you start on France and Japan, not Eswatini.

**Progress is visible.** The flag wall on the home page is dim at first and
lights up country by country. The Atlas shades what you know using the
elevation tints of a physical map: sea, lowland green, ochre, sienna.

## Where the data comes from

- **Wikidata** (SPARQL) — everything structured, plus photos of people
- **Wikipedia REST API** — the prose blurbs on fact cards
- **flagcdn.com** — flags
- **[johan/world.geo.json](https://github.com/johan/world.geo.json)** — outlines
- **[GeoNames](https://www.geonames.org/)** — largest cities by population

All free, no API keys.

## Pages

| Route | What it is |
| --- | --- |
| `/` | Flag wall, question categories, your stats |
| `/play/<category>` | The quiz show |
| `/atlas` | All 197 countries, shaded by what you know |
| `/country/<ISO2>` | The full dossier, everything clickable |
| `/topics` | Follow a language, war, currency or form of government |
| `/progress` | Accuracy, weak spots, recent runs |

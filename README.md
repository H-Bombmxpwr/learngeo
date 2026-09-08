# LearnGeo

A world-knowledge quiz show and a linked encyclopaedia in one. Flags, outlines,
land borders, capitals, largest cities, leaders past and present, historical
figures, wars, languages with the share of the country that speaks each, what a
country sells and to whom, climate and politics for 197 countries — and a fact
card after every answer you get wrong.

The idea: quiz games test you, encyclopaedias teach you. This does both. You
play on a dark stage; the answer arrives on atlas paper.

**Everything is linked.** Sixteen kinds of thing have a page of their own:
languages, wars, currencies, religions, organisations, forms of government,
climates, landmarks, and every commodity a country buys, sells, mines or
makes. Click "crude petroleum" on Nigeria's page and you get everyone else
who sells it; click Ha Long Bay and you get Vietnam. Search from any page and
the box answers as you type. Start anywhere and wander.

## Run it

```bash
uv sync
uv run python app.py
```

Then open <http://127.0.0.1:5000>.

The dataset is already built, so it starts immediately.

## Rebuild the dataset

```bash
uv sync --extra build                   # shapely, for the border check
uv run python scripts/fetch_data.py     # Wikidata + Wikipedia, ~10 minutes
uv run python scripts/enrich_data.py    # the Factbook pass and the repairs
```

`fetch_data.py` resumes from a checkpoint, so it is safe to interrupt.
`enrich_data.py` takes stage names (`languages`, `economy`, `climate`,
`government`, `figures`, `leaders`, `people`, `famous`) if you only want one. Nothing hits
the network at request time — once built, the app works offline apart from the
photographs.

## How it works

| File | What it does |
| --- | --- |
| `app.py` | Routes, run state, scoring, fact cards, search |
| `learngeo/data.py` | Loads the dataset, shapes, the topic index, the search index |
| `learngeo/supplement.py` | Hand-written wars and historical figures, merged at load |
| `learngeo/questions.py` | 19 question generators |
| `learngeo/store.py` | SQLite progress and the spaced-repetition picker |
| `scripts/fetch_data.py` | Builds the dataset from Wikidata |
| `scripts/enrich_data.py` | Layers the World Factbook on top and repairs the rest |
| `data/countries.geo.json` | Country outlines, for silhouettes and the map |

**Two ways to play.** A scored run is twelve questions and three lives, with a
streak multiplier and points for answering fast. Casual is the same questions
with no lives and no end. Every game offers both, at `/games`.

**Adaptive.** Every (country, question type) pair is a flashcard. Get one right
and it comes back later; get it wrong and it returns within minutes. Difficulty
opens up as you improve — you start on France and Japan, not Eswatini.

**Right and wrong are treated differently.** A correct answer gets a line under
the choices and a Next button; the full card is one click away if you want it.
A wrong answer raises the card, because that is the moment you will actually
read it.

**Progress is visible.** The flag wall on the home page is dim at first and
lights up country by country. The Atlas shades what you know using the
elevation tints of a physical map: sea, lowland green, ochre, sienna.

## Where the data comes from

Wikidata, Wikipedia, the CIA World Factbook, GeoNames, world.geo.json,
flagcdn.com and Wikimedia Commons — all free, no API keys. `/sources` explains
what each is used for, and which of them is wrong about what.

## Pages

| Route | What it is |
| --- | --- |
| `/` | Flag wall, question categories, your stats |
| `/games` | Every game, scored or casual |
| `/play/<category>` | The quiz show |
| `/atlas` | All 197 countries, searchable and sortable |
| `/country/<ISO2>` | The full dossier, everything clickable |
| `/topics` | Follow a language, war, currency or form of government |
| `/search` | Countries, topics and people |
| `/map` | The world, clickable, shaded by what you know |
| `/sources` | Where every field comes from |
| `/progress` | Accuracy, weak spots, recent runs |

## Deploying it

The built dataset is committed, so a host only has to install and start:

```
gunicorn app:app --bind 0.0.0.0:$PORT
```

which is what both `Procfile` and `railway.json` say. Set `LEARNGEO_SECRET`
to anything private — it signs the session cookie holding your score and the
answer to the question on screen. Progress lives in `data/progress.db`, which
is a local SQLite file, so on a host with an ephemeral filesystem it resets
with every deploy; it would need a mounted volume or a real database to
survive.

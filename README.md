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

## Building the dataset

Three commands, in this order. Only the first is slow, and none of them run
while the app is serving — the whole dataset is on disk before you load a page.

```bash
uv sync --extra build                   # shapely, needed for the border check
uv run python scripts/fetch_data.py     # Wikidata + Wikipedia, ~10 minutes
uv run python scripts/enrich_data.py    # the World Factbook pass and the repairs
```

### `scripts/fetch_data.py` — the structured pull

Ten stages over Wikidata's SPARQL endpoint and Wikipedia's REST API. Writes
`data/countries.json`, checkpointing to `data/_checkpoint.json` after every
stage, so an interrupted run resumes rather than starting over. Delete the
checkpoint to force a full rebuild.

| Stage | What it writes |
| --- | --- |
| `core` | Name, ISO codes, QID, population, area, coordinates, flag emoji, calling code, founding date |
| `capitals` | `capitals` |
| `politics` | `official_languages`, `currencies`, `government`, `continents`, `religions`, `member_of`, `highest_point` |
| `borders` | `borders` — **and the polygon check**: Wikidata's "shares border with" counts sea boundaries, so every candidate pair is measured against the real outlines and only coastlines within ~2 km count |
| `languages` | `languages`, ranked by speaker count where Wikidata has one |
| `cities` | `cities` — the five largest per country, from the GeoNames dump |
| `wars` | `wars`, as Wikidata records them |
| `leaders` | `leaders`, `past_leaders` |
| `famous` | `famous` |
| `wikipedia` | `summary`, `wiki_url` |

It then derives `climate_zone`, `hemisphere`, `landlocked`, `has_shape`,
`flag_url`, `flag_thumb` and `tier` (the difficulty ladder).

### `scripts/enrich_data.py` — the repairs

Layers the CIA World Factbook over the top and fixes what the first pass gets
wrong. Takes stage names, so you can run one at a time:

```bash
uv run python scripts/enrich_data.py languages economy   # offline, instant
uv run python scripts/enrich_data.py figures             # Wikipedia, ~5 minutes
uv run python scripts/enrich_data.py leaders             # Wikidata, slow
```

| Stage | Source | What it fixes or adds |
| --- | --- | --- |
| `languages` | Factbook | Rewrites `languages` with the **share of the population** speaking each and whether it is official. Wikidata gave Guatemala one language and did not list Swedish for Sweden |
| `economy` | Factbook | Adds `economy`: exports, imports, trading partners with percentages, natural resources, industries, agriculture, GDP |
| `climate` | Factbook | `climate_text`, and rewrites `climate_zone` as one of seven mutually exclusive zones read from that text |
| `government` | Factbook | `government_type`, one per country. Wikidata listed four for China |
| `figures` | Wikipedia | Writes **`data/figures.json`**: the opening sentence and a portrait for every hand-written figure |
| `people` | Wikidata | Fills in `wiki` and `qid` on people the first pass left unlinkable |
| `leaders` | Wikidata | Re-reads `leaders` and `past_leaders` via the *office*, not the country item, and adds each sitting leader's `party` |
| `famous` | Wikidata | Tops up `famous` for countries below the fame threshold |

Both scripts only ever merge into `data/countries.json`; a failed query leaves
the existing value alone rather than blanking it.

### Written by hand — `learngeo/supplement.py`

Three tables that no query can produce, merged into the dataset **at load
time** rather than written to disk, so re-running either script cannot wipe
them:

- **`WARS`** — the belligerents of fifty major wars, by the modern country
  that succeeded them. Wikidata records participants as the state that
  actually fought, which before about 1950 no longer exists: World War II
  listed Nazi Germany and the Soviet Union, neither of which has an ISO code,
  so the pull came back with WWII at two participants and the Iraq War as the
  most widely shared conflict on earth.
- **`FIGURES`** — two to four historical figures for each of the 197
  countries, each with a short note. A leader is modelled in Wikidata as the
  holder of an office, and the office usually belongs to the historical state,
  so Gaddafi appeared nowhere on Libya's page. The `figures` stage above
  fetches each one's Wikipedia sentence and portrait.
- **`LANDMARKS`** — what each country is known for looking like. Wikidata has
  no property for this; the closest is the highest point, which gives you
  Everest but not the Great Wall or Stonehenge.
- **`RELIGION_MARKS`, `CURRENCY_MARKS`, `ORG_MARKS`** — the glyph shown beside
  each chip.

### What ends up where

| File | Committed | Written by |
| --- | --- | --- |
| `data/countries.json` | yes — a deploy cannot run a ten-minute fetch | both scripts |
| `data/figures.json` | yes | `enrich_data.py figures` |
| `data/countries.geo.json` | yes | vendored from world.geo.json |
| `data/_checkpoint.json` | no | `fetch_data.py`, between stages |
| `data/cities15000.zip`, `data/factbook.zip` | no | downloaded on demand |
| `data/progress.db` | no | the app, as you play |

## How it works

| File | What it does |
| --- | --- |
| `app.py` | Routes, run state, scoring, fact cards, search |
| `learngeo/data.py` | Loads the dataset, shapes, the topic index, the search index |
| `learngeo/supplement.py` | Hand-written wars and historical figures, merged at load |
| `learngeo/questions.py` | 31 question generators |
| `learngeo/matching.py` | Judging a typed answer in challenge mode |
| `learngeo/store.py` | SQLite progress and the spaced-repetition picker |
| `scripts/fetch_data.py` | Builds the dataset from Wikidata |
| `scripts/enrich_data.py` | Layers the World Factbook on top and repairs the rest |
| `data/countries.geo.json` | Country outlines, for silhouettes and the map |

**Fourteen games, each four ways.** A **scored run** is twelve questions and
three lives, with a streak multiplier and points for answering fast. **Casual**
is the same questions with no lives and no end. **Challenge** takes the four
options away: you type the answer — with a type-ahead scoped to what the
question wants, and judging that forgives accents, aliases and one-character
typos — or click the country on the map. Correct challenge answers are worth
half as much again. All of it at `/games`.

There are 5,139 buildable (country, question type) pairs, and generators pick
which city, war, export or leader they ask about, so the real question space is
several times that.

**Adaptive, and you can switch it off.** Every (country, question type) pair is
a flashcard. Get one right and it comes back later; get it wrong and it returns
within minutes. Countries you have proved you know are asked about far less
often, difficulty opens up as you improve, and the picker avoids whatever it
has just asked. Turn adapting off on `/progress` and questions come at random
from the whole world with nothing recorded.

**No account, ever.** Progress is keyed to a random id in a year-long cookie,
so two people on the same deployed copy keep separate scores and nothing about
a person is stored. Clearing cookies — or the button on `/progress` — is how
you start over.

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

The built dataset is committed, so a host only has to install and start. Both
steps go through **uv** — there is no `requirements.txt`, and `uv.lock` is the
single source of truth for what gets installed:

```bash
uv sync --frozen --no-dev                          # exactly what uv.lock pins
uv run --frozen --no-dev gunicorn app:app --bind 0.0.0.0:$PORT
```

`--frozen` fails loudly if the lock has drifted from `pyproject.toml` rather
than quietly resolving something else, and `--no-dev` keeps shapely out: it
lives in the optional `build` extra because only the dataset scripts need it,
and compiling GEOS to serve an already-built JSON file is risk with no upside.

`uv run` rather than a bare `gunicorn` matters — uv installs into a `.venv` it
does not activate, so the console script is not on `PATH` and the deploy dies
with `gunicorn: command not found`.

### The three config files

They say the same thing to different readers, and which one is used depends on
the host:

| File | Read by | Why it is here |
| --- | --- | --- |
| `nixpacks.toml` | Railway's builder (Nixpacks) | The **install** step. Nixpacks defaults to pip and a `requirements.txt`; without this it never runs `uv sync`, so nothing is installed at all. Also pins Python and puts `uv` itself on the image |
| `railway.json` | Railway | The start command, and the restart policy. Takes precedence over the Procfile on Railway |
| `Procfile` | Heroku, Render, Dokku, and Railway as a fallback | The same start command, for hosts that have never heard of `railway.json` |

Only `nixpacks.toml` is load-bearing on Railway today. The other two make the
project start correctly somewhere else without any changes, which is cheap
insurance for four lines of config.

### Environment

Set `LEARNGEO_SECRET` to anything private — it signs the session cookie that
holds your score and the answer to the question on screen. `PORT` is supplied
by the host.

Progress lives in `data/progress.db`, a local SQLite file, so on a host with an
ephemeral filesystem it resets with every deploy. It would need a mounted
volume, or a real database, to survive.

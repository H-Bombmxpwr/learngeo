# Country exploration

The country dossier now has accessible, script-independent reveal cards, a
civilization trail, a short historical timeline, a religion section, and links
to further reading. The home page links to the civilization topic index.

## Content coverage and conventions

`learngeo/explore.py` owns the editorial content. It is layered over the bulk
dataset at load time, so running the fetch scripts does not overwrite it.

- Every country gets study prompts from its available atlas facts. These are
  explicitly labeled as imported; a country reference is not presented as
  verification of each individual imported claim.
- Twelve civilization/state entries connect selected present-day countries.
  The list is intentionally not a complete territorial gazetteer. Dates are
  the life of the culture or polity, not dates of rule over each modern country.
- Ancient emblems, military standards, modern reconstructions and documented
  historical flags are labeled separately. Unknown flags are not invented.
  The Maya are not treated as one empire or as an extinct people.
- Six countries have editorial turning-point timelines and additional trivia:
  France, Germany, Canada, India, Japan and South Africa.
- Twelve countries have religion profiles. Official status is separate from
  affiliation; census/estimate dates and denominators are preserved. Selected
  categories need not sum to 100%. Unaffiliated people are not counted as a
  religion. Unknown values remain unknown, including a ranking for Japan.
- Trivia prompts are not advertised as empirically ranked common quiz questions.

Sources are linked next to the relevant content. For new entries, read the
source, describe the geographic scope, and distinguish the age of a flag from
the age of the polity. Do not reuse a late imperial flag for an earlier dynasty.

## Illustrations

Two simple historical flags are local SVG drawings of public-domain designs.
The Sasanian banner is a **modern artist's reconstruction**, by Oneasy; the
Qing flag is a vector by Sodacan. Their Commons file pages, public-domain
status, and attribution are stored in `explore.ART` and shown in the dossier.
`scripts/fetch_history_assets.py` refreshes those two local files. Rendering
country pages does not require a live image API.

## Game settings

`questions.game_options` is the shared capability definition used by both
the game forms and server normalization. Map mode only offers map clicks;
Alliances only offers yes/no. Mixed categories explain that typed mode omits
questions requiring visible alternatives.

Quiz sessions offer 5, 12 or 25 questions and three lives; either limit ends
the run. Practice has unlimited questions and no life loss. The question
limit is hidden and disabled in practice. URLs, run matching, server completion,
question payloads and both restart controls retain the chosen limit.
Older saved runs default to 12 questions.

## Demonyms and playable learning sections

`data/demonyms.json` contains English demonyms for all 197 atlas countries,
derived from mledoze/countries, with attribution, ODbL-1.0 license, retrieval
date and upstream checksum. It is separately downloadable at
`/data/demonyms.json`. Refresh with `scripts/fetch_demonyms.py`. The loader
adds recorded forms and conservative noun/plural aliases, including Britons,
Dutch people, Batswana and Filipina. Demonym matching is exact after case,
accent and punctuation normalization: Nigerien must not accept Nigerian.
Country search also recognizes demonyms.

`learngeo/lessons.py` converts the same dossier records into playable content.
Eleven new question types cover demonyms; historical flags; civilization
geography, dates and symbols; historical turning points; official religion,
affiliation and interpretation; curated trivia; and the country notebook.
The notebook includes recorded capitals, currencies, languages, borders,
driving, calling codes, founding dates, hemisphere, government, climate,
landlocked status, cities, peaks, landmarks and economic product lists.
Imported facts retain their snapshot caveat. This does not re-enable the
previously disabled, unreliable war-participation questions.

Six new game categories expose those questions. They are also registered in
Grand Tour and single-country study, with direct practice links on each
available section. Missing source content is never fabricated to fill a quiz.
Names support typed answers; full lists, nuanced explanations and dates/ranges
use choices. Scoped games normalize style against that country's coverage.

The picker filters new modes against their actual lesson pool, so a game
with only four distinct historical flags never depends on random retries
through 197 countries. Stable lesson IDs prevent repetition until the
available deck for that mode is exhausted, including flags shared by more
than one modern country. Session history survives refresh.

Explanations, reference links and links back to the exact country section
appear after answering (including wrong answers, skips and the final result)
and survive feedback replay. No answer/explanation metadata is sent with the
unanswered question beyond the visible answer choices.

## Validation

Run `.venv/Scripts/python -m unittest discover -s tests -q`.
`tests/browser_explore.py` additionally checks the mobile layout, local images,
reveal cards, capability controls, practice selector, refresh and restart with
Playwright and Microsoft Edge. It uses an isolated temporary progress database.

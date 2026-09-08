# Rebuilding the data

## Right now — run this when the leaders script finishes

The language parser was fixed after your current run started. It was dropping
every language after the first for any country whose Factbook entry has no
percentages, which is most of Africa: Nigeria showed only English, Kenya only
English and Kiswahili. It also let an HTML entity through, so Tanzania had a
language called `Swahili/Kiswahili &lt`.

```bash
uv run python scripts/enrich_data.py languages economy climate government
```

Offline, no network, takes about two seconds. **Wait until the leaders script
has exited** — both write `data/countries.json`, and two processes writing it
at once will corrupt it.

Then check it worked:

```bash
uv run python -c "import json; d=json.load(open('data/countries.json',encoding='utf-8')); print([l['name'] for l in d['NG']['languages']])"
```

Nigeria should list English, Hausa, Yoruba, Igbo, Fulani — not just English.

Then commit the dataset, since it is what the deploy serves:

```bash
git add data/countries.json && git commit -m "Rebuild languages" && git push
```

---

## The commands, and when each one is needed

| Command | Needs network | Time | Run it when |
| --- | --- | --- | --- |
| `uv run python scripts/enrich_data.py languages economy climate government` | no | seconds | The Factbook parsers changed, or you want the four offline fields refreshed |
| `uv run python scripts/enrich_data.py figures` | Wikipedia | ~5 min | You added names to `FIGURES` in `learngeo/supplement.py` |
| `uv run python scripts/enrich_data.py leaders` | Wikidata | 15–90 min | Leaders are out of date, or you want party affiliations |
| `uv run python scripts/enrich_data.py people` | Wikidata | ~5 min | People are missing Wikipedia links |
| `uv run python scripts/enrich_data.py famous` | Wikidata | slow | You want more famous faces for small countries |
| `uv run python scripts/fetch_data.py` | Wikidata | ~10 min | Full rebuild from scratch. Needs `uv sync --extra build` first, for shapely |

Everything at once:

```bash
uv sync --extra build
uv run python scripts/fetch_data.py
uv run python scripts/enrich_data.py
```

## Rules

- **One at a time.** Every stage rewrites `data/countries.json`. Two processes
  running together will corrupt it. Check with:
  ```bash
  ps -W | grep enrich_data     # Git Bash
  ```
- **Ctrl-C is safe.** Stages save as they go and only ever merge — a failed
  query leaves the existing value alone rather than blanking it. Re-run to
  continue.
- **Wikidata will rate-limit you.** 504 on anything heavy, 429 after a few
  hundred queries. `leaders` and `famous` are the ones this bites; both can be
  re-run later to fill what they missed.
- **Commit `data/countries.json` afterwards.** It is what the deploy serves —
  Railway cannot run a ten-minute fetch on boot.
- **Never commit `data/progress.db`.** It is gitignored; it is your scores.

## What is not rebuilt by any script

`learngeo/supplement.py` is written by hand and merged at load time, so no
rebuild can wipe it:

- `WARS` — who fought in fifty major wars, by modern successor state
- `FIGURES` — two to four historical figures per country
- `LANDMARKS` — what each country is known for
- the chip glyphs for religions, currencies and organisations

Edit that file and the change is live on the next page load. The one exception
is `FIGURES`: adding a name there means running `enrich_data.py figures` to
fetch its Wikipedia sentence and portrait into `data/figures.json`.

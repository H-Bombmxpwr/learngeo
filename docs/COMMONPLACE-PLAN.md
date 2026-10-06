# Commonplace: a general-knowledge learning app

## Goal and scope

Replace the geography-first landing experience with a general-knowledge study
desk. Keep the existing atlas, map, country dossiers, games and progress as a
geography wing. The root workspace launcher is `../study_trivia.py`.

The user's reference is JoeRainford's Extremely Hard General Knowledge series
on JetPunk: specific names, works, historical connections, scientific terms,
sport and British culture. The series index and quizzes 1 and 30 were accessible;
several other sampled pages could not be fetched. This is inspiration for topic
breadth and clue specificity, not an imported copy of that question collection.

## Learning loop

1. A small daily queue combines due reviews, weak material and new facts.
2. Type an answer before seeing it. Explicit aliases and accent folding avoid
   unnecessary spelling penalties; numbers and distinct names stay strict.
3. Reveal an explanation, a memory cue and sources. Hinted/revealed answers
   never count as unaided recall.
4. Missed cards reappear after intervening material and are scheduled sooner.
5. Follow connected entities or a guided trail. Save useful cards to a notebook
   and practise the exact material encountered along the way.
6. Test transfer using a four-minute, 20-question mixed challenge and the actual
   JetPunk quizzes. Record external scores separately from internal recall.

## Content architecture

- **Curated layer:** 120 original cards across 12 subjects, with teaching notes.
- **Scale layer:** thousands of offline cards generated from CC0 Wikidata
  relationships, using English labels, descriptions, aliases and source IDs.
- **Graph:** entities and named relationships power rabbit holes. Shared authors,
  composers, directors, movements and places provide actual connections, rather
  than unrelated random recommendations.
- **Difficulty:** a transparent editorial level for curated cards; approximate
  popularity-based tiers for generated material. Obscurity is not proof of a
  well-written question, so users can filter, flag or hide weak material.
- **Personal layer:** users can add missed facts in their own words and export
  them with progress. Never require an API key to study.

## Data quality and licensing

Use Wikidata's CC0 structured data, not copied Wikipedia prose or scraped quiz
banks. Download at build time, cache by source slice, retry politely, keep the
last successful build, and emit a provenance/coverage manifest. Require readable
English labels. Group multiple objects for a relationship and accept all listed
answers with a prompt explicitly asking for one. Exclude missing labels and
obvious answer leakage. Sources are inspectable; generated facts are not claimed
to be human-verified. Avoid unqualified current officeholders, rankings and
changing records. Retain IDs so rebuilding does not reset a user's learning.

## Interface and accessibility

An editorial study desk with visible search, topic filters, difficulty, an
exploration entry point and clear review counts. Rabbit holes must be reachable
from the main navigation and answer feedback, with breadcrumbs/back, labelled
relationships, source links and a practice button. No graph-only navigation:
the graph must also work as ordinary readable lists and buttons on mobile.
Keyboard controls, visible focus, live feedback, readable contrast and reduced
motion. Progress is local to the browser and origin; provide backup/restore and
explicit storage-failure messages. Existing geography progress remains separate.

## Delivery and verification

Deliver the new home and navigation, sourced dataset and repeatable importer,
study/review/challenge flows, exploration trails, personal notebook, external
benchmark log and backup/restore. Verify dataset identities/aliases/links and
ambiguity handling; review scheduling and failed/revealed recall; browser
reload/resume; keyboard and mobile layouts; personal-card import validation;
and existing LearnGeo regression tests. Document actual imported coverage and
limitations instead of claiming the whole world of trivia is complete.

## Later extensions (not prerequisites for this version)

Account-based device sync, evidence-backed question edits, more relation families,
visual identification with licensed media, and deeper hand-written teaching
essays. A successful local build does not publish or deploy the site.

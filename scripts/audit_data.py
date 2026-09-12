"""Reproducible structural audit; not a substitute for fact/source verification.

Run: python scripts/audit_data.py --output docs/data-audit.json

Three passes, and it is worth being clear about what each one can and cannot
tell you:

**Structure** asks whether the data is the shape the code expects, and whether
every generator can build a well-formed question from it. It cannot tell you
whether any of it is true.

**Ambiguity** asks whether a question with one recorded answer really has one
answer. A landmark in two countries, a city name two countries share, two
cities the same size to within a census revision, a country in two continents:
each is a question a knowledgeable player can get "wrong". This pass finds the
ones that are visible in the data. It cannot find the ones that are not --
Lake Titicaca is only detectably shared if both Peru and Bolivia recorded it.

**Provenance** asks how much of the dataset has a source behind it. The honest
answer is: a little. That number going up is the work.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learngeo.data import world
from learngeo import provenance, questions, supplement
from learngeo.data_util import fold

# Two cities the same size to within this fraction cannot be ranked from data
# whose census years differ by country.
CLOSE_ENOUGH = 0.15


def structure(w):
    errors, warnings, coverage = [], [], Counter()
    codes = Counter(c.get('iso3') for c in w.countries.values())
    for iso in w.all_isos:
        c = w.get(iso)
        if c.get('iso2') != iso or codes[c.get('iso3')] != 1:
            errors.append(f'{iso}: inconsistent or duplicate ISO code')
        for field in ('population', 'area'):
            if c.get(field) is not None and c[field] <= 0:
                errors.append(f'{iso}: non-positive {field}')
        for field in ('capitals', 'languages', 'cities', 'landmarks', 'leaders'):
            if not c.get(field):
                warnings.append(f'{iso}: missing {field}')
        if not w.shape(iso):
            # No longer excluded from map questions: the quiz map now carries
            # a point for each of these. Still worth listing, because a point
            # is a compromise and a shape would be better.
            warnings.append(f'{iso}: no polygon (shown as a point on the map)')
        for nb in w.neighbours(iso):
            if iso not in w.neighbours(nb):
                warnings.append(f'{iso}/{nb}: asymmetric border; verify territorial conventions')
        shares = [l.get('share') for l in c.get('languages', []) if isinstance(l, dict)]
        if any(x is not None and not 0 <= x <= 100 for x in shares):
            errors.append(f'{iso}: language share outside 0..100')
        for mode, (_, _, generator) in questions.MODES.items():
            try:
                random.seed(f'{iso}/{mode}')
                q = generator(w, iso, random)
                if not q:
                    continue
                coverage[mode] += 1
                keys = [str(x['key']) for x in q['choices']]
                if len(set(keys)) != len(keys):
                    errors.append(f'{iso}/{mode}: duplicate choices')
                if keys and str(q['answer']) not in keys:
                    errors.append(f'{iso}/{mode}: answer absent from choices')
                if not q['prompt'] or not q['answer']:
                    errors.append(f'{iso}/{mode}: empty question/answer')
            except Exception as exc:
                errors.append(f'{iso}/{mode}: {type(exc).__name__}: {exc}')
    return errors, warnings, coverage


def ambiguity(w):
    """Questions whose one recorded answer is not the only right answer."""
    found = []

    # A landmark recorded against more than one country, or one the curated
    # list names as shared. Either way it cannot be asked "which country is
    # this in", and the generators skip both.
    owners = {}
    for iso in w.all_isos:
        for m in w.get(iso).get('landmarks') or []:
            if m.get('name'):
                owners.setdefault(m['name'], set()).add(iso)
    for name, isos in sorted(owners.items()):
        if len(isos) > 1:
            found.append({'kind': 'landmark_multi_country', 'subject': name,
                          'detail': 'recorded in ' + ', '.join(sorted(isos)),
                          'handled': True})
    shared = sorted(n for n in owners if provenance.is_shared_landmark(n))
    for name in shared:
        found.append({'kind': 'landmark_known_shared', 'subject': name,
                      'detail': 'named in provenance.SHARED_LANDMARKS; '
                                'excluded from landmark questions',
                      'handled': True})

    # City names two countries share. `city_to_country` excludes the clashing
    # countries from its options, so it is handled -- but the list is worth
    # printing, because it is also the list of names a typed answer could
    # reasonably mean either way.
    cities = {}
    for iso in w.all_isos:
        for city in w.get(iso).get('cities') or []:
            if city.get('name'):
                cities.setdefault(fold(city['name']), set()).add(iso)
    for name, isos in sorted(cities.items()):
        if len(isos) > 1:
            found.append({'kind': 'city_name_shared', 'subject': name,
                          'detail': 'in ' + ', '.join(sorted(isos)),
                          'handled': True})

    # Cities too close in size to rank. Handled by the 15% rule in the
    # generators; counted here so the size of the problem is visible.
    close = 0
    for iso in w.all_isos:
        ranked = [c for c in w.get(iso).get('cities') or [] if c.get('population')]
        for a, b in zip(ranked, ranked[1:]):
            if abs(a['population'] - b['population']) / float(a['population']) <= CLOSE_ENOUGH:
                close += 1
    if close:
        found.append({'kind': 'city_rank_too_close', 'subject': f'{close} pairs',
                      'detail': 'adjacent cities within 15%; not asked about',
                      'handled': True})

    # Transcontinental countries. Handled by a stated convention plus an
    # accepted second answer, which is the only honest way to ask.
    for iso in w.all_isos:
        spans = w.continents_of(iso)
        if len(spans) > 1:
            found.append({'kind': 'transcontinental', 'subject': iso,
                          'detail': ' / '.join(spans) + '; capital rule applied, '
                                                        'both accepted',
                          'handled': True})

    # Cities with no population figure at all, which is what stops them being
    # rankable in the first place.
    missing = [i for i in w.all_isos
               if not any(c.get('population')
                          for c in w.get(i).get('cities') or [])]
    if missing:
        found.append({'kind': 'city_population_missing',
                      'subject': ', '.join(sorted(missing)),
                      'detail': 'no city population recorded; size questions '
                                'unavailable', 'handled': True})

    # The one class this pass cannot close: a language ranking with no
    # measurement behind it. A share is a number from somewhere; without a
    # definition and a date it is not checkable.
    undated = sum(1 for i in w.all_isos
                  for l in w.get(i).get('languages') or []
                  if isinstance(l, dict) and l.get('share') is not None)
    found.append({'kind': 'language_share_undated',
                  'subject': f'{undated} language rows',
                  'detail': 'share recorded with no survey or date; the '
                            'convention is stated but the figure is not sourced',
                  'handled': False})
    return found


def provenance_report(w):
    """How much of this has a source, and which conventions are declared."""
    sourced, by_field = 0, Counter()
    for iso in w.all_isos:
        recs = w.provenance(iso)
        if recs:
            sourced += 1
        for field in recs:
            by_field[field] += 1
    verified_modes = sorted(provenance.MODE_CONVENTION)
    unsourced_modes = sorted(m for m in questions.MODES
                             if m not in provenance.MODE_CONVENTION)
    return {
        'countries_with_any_source': sourced,
        'countries_total': len(w.all_isos),
        'fields_corrected': dict(sorted(by_field.items())),
        'conventions': provenance.CONVENTIONS,
        'modes_with_a_stated_convention': verified_modes,
        'modes_relying_on_the_bulk_import': unsourced_modes,
        'curated_war_rows': len(supplement.WARS),
        'bilateral_wars': len(supplement.BILATERAL),
    }


def audit():
    w = world()
    errors, warnings, coverage = structure(w)
    amb = ambiguity(w)
    return {
        'countries': len(w.all_isos),
        'errors': errors,
        'warnings': warnings,
        'mode_country_coverage': dict(sorted(coverage.items())),
        'ambiguity': {
            'unhandled': [a for a in amb if not a['handled']],
            'handled': [a for a in amb if a['handled']],
        },
        'provenance': provenance_report(w),
        'limitations': [
            'Structural validity does not establish factual accuracy.',
            'Current leaders, governments, population and trade figures still '
            'need dated source verification; only the entries listed under '
            'provenance.fields_corrected have one.',
            'War participation is not asked about. The curated table names '
            'principal belligerents only, which settles neither participation '
            'nor non-participation.',
            'City population years and city/metro definitions are not recorded '
            'per city; the stated convention covers the definition but not the '
            'year.',
            'Language shares carry no survey or date.',
            'Border and historical-country mappings need explicit territorial '
            'conventions.',
            'The ambiguity pass can only see ambiguity the data records. A '
            'landmark in two countries that only one of them lists reads as '
            'unambiguous here.',
        ]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    args = parser.parse_args()
    report = audit()
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    amb = report['ambiguity']
    print(f"{report['countries']} countries; {len(report['errors'])} errors; "
          f"{len(report['warnings'])} review warnings; "
          f"{len(amb['handled'])} ambiguities handled, "
          f"{len(amb['unhandled'])} open")
    prov = report['provenance']
    print(f"{prov['countries_with_any_source']}/{prov['countries_total']} "
          f"countries carry at least one sourced fact; "
          f"{len(prov['modes_with_a_stated_convention'])} of "
          f"{len(questions.MODES)} question types state their convention")
    for error in report['errors']:
        print(error)
    sys.exit(bool(report['errors']))

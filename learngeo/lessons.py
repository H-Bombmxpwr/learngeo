"""Turn the country dossier's structured learning content into quiz records.

The displayed fact remains the answer/explanation. Only distractors and short
retrieval cues are editorial additions. Sources travel with the answer, never
with the unanswered prompt. Sparse topics expose their actual eligible pool.
"""
import hashlib

from . import demonyms, explore
from .data_util import fold

MODES = {
    'demonym_of': ('Demonyms', 'What people are called'),
    'historical_flag': ('Historical flags', 'Recognize a historical flag or reconstructed standard'),
    'civilization_place': ('Civilizations', 'Locate a civilization in its historical region'),
    'civilization_dates': ('Civilizations', 'Recognize a civilization or state\'s period'),
    'civilization_symbol': ('Civilizations', 'Understand flags, emblems and standards'),
    'history_timeline': ('Turning points', 'Date a turning point'),
    'religion_status': ('Religion', 'Distinguish state religion from population affiliation'),
    'religion_affiliation': ('Religion', 'Recall a sourced religious affiliation snapshot'),
    'religion_context': ('Religion', 'Interpret religion data'),
    'country_trivia': ('Trivia', 'Country trivia essentials'),
    'country_notebook': ('Country notebook', 'Recall recorded country facts'),
}
TYPED = {'demonym_of', 'historical_flag'}

REGIONS = {
    'Sumer': 'Southern Mesopotamia (present-day Iraq)',
    'Maya civilization': 'Southern Mexico and parts of Central America',
    'Aztec Triple Alliance': 'Central Mexico, centered on Tenochtitlan, Texcoco and Tlacopan',
    'Inca Empire': 'The Andes, centered at Cusco',
    'Ancient Egypt': 'The Nile valley and delta',
    'Indus Valley civilization': 'Present-day Pakistan and northwestern India',
    'Achaemenid Empire': 'An empire centered in Iran, extending into Egypt and parts of South Asia',
    'Roman Empire': 'An empire centered on Rome and the Mediterranean',
    'Sasanian Empire': 'Iran and Mesopotamia',
    'Bourbon Restoration in France': 'France under its restored monarchy',
    'German Empire': 'A German state with borders different from modern Germany',
    'Qing dynasty': 'A Manchu-led empire including present-day China and Mongolia',
}
# Alternatives to the displayed trivia answers, indexed in the same order.
TRIVIA_WRONG = {
    'FR': [
        ['The Russian Revolution.', 'The American Revolution.', 'The Meiji Restoration.'],
        ['Yes, the same tricolour was used throughout the monarchy.', 'No. A green flag replaced it permanently in 1830.', 'No. It was introduced only in 1958.']],
    'DE': [['1989; opening the Berlin Wall immediately unified the two states.', '1949; both German states were reunited on their founding.', '1871; this was the reunification of East and West Germany.']],
    'CA': [['1 July 1867, at Confederation.', '17 April 1982, at patriation of the Constitution.', '11 November 1918, at the end of the First World War.']],
    'IN': [
        ['A spinning wheel with eight spokes.', 'A lotus with twelve petals.', 'A sun with fifty rays.'],
        ['Yes. Both happened in 1947.', 'Yes. Both happened in 1950.', 'No. The republic began in 1947, before independence in 1950.']],
    'JP': [['The imperial chrysanthemum seal.', 'The postwar Constitution.', 'The first Tokugawa shogun.']],
    'ZA': [['The formation of the Union in 1910.', 'The National Party taking power in 1948.', 'The establishment of the republic in 1961.']],
}


def _unique(values):
    seen, out = set(), []
    for value in values:
        key = fold(str(value)).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(str(value))
    return out


def bank(world):
    if hasattr(world, '_lesson_bank'):
        return world._lesson_bank
    records = {iso: {m: [] for m in MODES} for iso in world.all_isos}
    pools = {}

    def add(iso, mode, key, prompt, answer, wrong=None, pool=None, explanation=None,
            source=None, anchor='trivia', definition=None, media=None, also=()):
        if answer is None or answer == '':
            return
        identity = hashlib.sha256((mode + '/' + key).encode()).hexdigest()[:20]
        row = dict(id=identity, prompt=prompt, answer=str(answer), wrong=wrong, pool=pool,
                   explanation=explanation or str(answer), source=source,
                   learn_url='/country/' + iso + '#' + anchor, definition=definition,
                   media=media or {}, also=list(also))
        records[iso][mode].append(row)
        if pool:
            pools.setdefault(pool, []).append(str(answer))

    for iso in world.all_isos:
        c, d = world.get(iso), explore.dossier(world, iso)
        name = c['name']
        imported = 'From the recorded atlas snapshot; imported figures may not describe the present day.'
        if c.get('demonyms'):
            add(iso, 'demonym_of', iso, 'What is an English demonym for people from %s?' % name,
                c['demonyms'][0], pool='demonym', also=c['demonym_answers'],
                explanation='People from %s are described as %s. A demonym is a place-based name, not an ethnicity.' % (name, ' / '.join(c['demonyms'])),
                source=demonyms.SOURCE, anchor='people-name', definition='Give an English demonym; recorded noun and plural forms are accepted.')
        for era in d['eras']:
            title = era['name']
            common = dict(source=era['source'], anchor='civilizations')
            # Avoid overlapping regional descriptions as distractors. These
            # deliberately distant regions are outside every relevant scope.
            wrong_regions = ['The Japanese archipelago', 'Mainland Australia', 'The islands of the Caribbean']
            add(iso, 'civilization_place', title, 'Which geographic description fits %s?' % title,
                REGIONS[title], wrong=wrong_regions, explanation=era['scope'], **common)
            add(iso, 'civilization_dates', title, 'Which period is recorded for %s?' % title,
                era['dates'], pool='era-dates', explanation=era['dates'] + '. ' + era['scope'],
                definition='Dates describe the civilization or polity as a whole, not continuous rule over every modern country.', **common)
            # Other cultures' "no known flag" descriptions may also be true
            # here. Never use those as wrong alternatives to one another.
            symbol_wrong = (
                ['A surviving ancient cloth banner confirms every detail of this drawing.',
                 'This is the unchanged national flag of modern Iran.',
                 'The design was first introduced for the Qing dynasty in 1889.'] if title == 'Sasanian Empire' else
                ['A surviving seven-stripe national flag proves the rainbow design is ancient.',
                 'The modern flag of Cusco has been unchanged since 1438.',
                 'The empire used the modern national flag of Peru.'] if title == 'Inca Empire' else
                ['Its symbol was the blue dragon national flag adopted in 1889.',
                 'Its symbol was the Canadian maple-leaf flag adopted in 1965.',
                 'Its symbol was the modern Indian tricolour with a 24-spoke wheel.'] if title != 'Qing dynasty' else
                ['This design was used unchanged by every Chinese dynasty since antiquity.',
                 'It is a surviving Roman legionary standard.',
                 'The yellow dragon flag was first adopted after the dynasty ended in 1912.'])
            add(iso, 'civilization_symbol', title, 'Which statement correctly describes the flag or symbols associated with %s?' % title,
                era['symbol'], wrong=symbol_wrong, explanation=era['symbol'], **common)
            if era.get('image'):
                label = 'modern reconstruction of a royal banner' if title == 'Sasanian Empire' else 'historical flag'
                add(iso, 'historical_flag', title, 'Which historical state is associated with this %s?' % label,
                    title, pool='flag-state', media=dict(type='image', url='/static/images/' + era['image'], frame='flag'),
                    explanation=era['dates'] + '. ' + era['symbol'],
                    definition='Identify the historical state, not a present-day country. ' + ('This is an artist\'s reconstruction, not surviving ancient cloth.' if title == 'Sasanian Empire' else ''),
                    also={'Sasanian Empire': ['Sasanian', 'Sassanian', 'Sassanid Empire'], 'Qing dynasty': ['Qing', 'Qing Empire'],
                          'German Empire': ['Imperial Germany'], 'Bourbon Restoration in France': ['Bourbon Restoration', 'Bourbon France']}[title], **common)
        for index, (date, event) in enumerate(d['timeline']):
            add(iso, 'history_timeline', iso + '/' + str(index), '%s: when does this turning point belong? %s' % (name, event),
                date, pool='timeline-date', explanation=date + ': ' + event, source=d['history_source'], anchor='history')
        religion = d['religion']
        if religion:
            status = ('Islam' if iso in {'PK', 'EG', 'SA'} else
                      "Twelver Ja'fari Shia Islam" if iso == 'IR' else 'No national state religion')
            wrong = (['Christianity', 'Buddhism', 'Hinduism'] if 'Islam' in status else ['Islam', 'Christianity', 'Buddhism'])
            add(iso, 'religion_status', iso, 'What is the national official-religion status recorded for %s?' % name,
                status, wrong=wrong, explanation=religion['official'], source=religion['official_source'], anchor='belief',
                definition='Official status describes the state, not what most residents believe.')
            if religion['largest']:
                answer = religion['largest']
                wrong = [r for r in ['Christianity', 'Islam', 'Hinduism', 'Buddhism', 'Judaism'] if r not in answer][:3]
                add(iso, 'religion_affiliation', iso + '/largest', 'In the cited profile of %s, which religious group is largest?' % name,
                    answer, wrong=wrong, explanation=religion['note'], source=religion['source'], anchor='belief', definition=religion['year'])
            for group, share in religion['groups']:
                # Same unit and plausible magnitudes, never an alternate rounding of the right figure.
                wrong = [('%g%%' % v) for v in [share + 10, share - 10, share + 20, share - 20, share + 30] if 0 <= v <= 100][:3]
                add(iso, 'religion_affiliation', iso + '/' + group, 'In %s, what share was recorded for %s?' % (name, group),
                    '%g%%' % share, wrong=wrong, explanation='%s: %g%%. %s' % (group, share, religion['note']),
                    source=religion['source'], anchor='belief', definition=religion['year'] + '. Selected self-reported or estimated affiliation categories, not practice.')
            add(iso, 'religion_context', iso, 'Which reading note applies to the religion profile for %s?' % name,
                religion['note'], wrong=['Affiliation measures exactly how often every person attends religious services.',
                'The largest religion must be the legally established state religion.',
                'A historical census percentage is automatically the percentage today.'],
                source=religion['source'], anchor='belief', definition=religion['year'])
        curated = len(explore.TRIVIA.get(iso, []))
        for index, item in enumerate(d['trivia']):
            if index < curated:
                add(iso, 'country_trivia', iso + '/' + str(index), item['question'], item['answer'],
                    wrong=TRIVIA_WRONG[iso][index], source=item['source'])
            else:
                prompt = item['question']
                # Full-set prompts avoid treating another valid capital/language as wrong.
                if prompt.startswith(('What capital', 'Which currencies', 'Which languages', 'Which countries share')):
                    prompt = 'For %s, which complete recorded list answers: %s' % (name, prompt)
                else:
                    prompt = name + ': ' + prompt
                field = ('capitals' if 'capital' in item['question'] else 'currencies' if 'currencies' in item['question'] else
                         'languages' if 'languages' in item['question'] else 'borders' if 'border' in item['question'] else
                         'drives_on' if 'road' in item['question'] else 'calling_code')
                add(iso, 'country_notebook', iso + '/' + field, prompt, item['answer'], pool=field,
                    source=item['source'], definition=imported)
        # Other compact facts displayed on the country page.
        for field, label in [('founded', 'founding date'), ('hemisphere', 'hemisphere'), ('climate_zone', 'climate zone'),
                             ('government_type', 'form of government')]:
            if c.get(field):
                add(iso, 'country_notebook', iso + '/' + field, 'Which %s is recorded for %s?' % (label, name),
                    c[field], pool=field, source=c.get('wiki_url'), definition=imported)
        add(iso, 'country_notebook', iso + '/landlocked', 'Is %s landlocked?' % name,
            'Yes' if c.get('landlocked') else 'No', wrong=['No' if c.get('landlocked') else 'Yes'],
            source=c.get('wiki_url'), definition='Landlocked means having no coast on the open ocean.')
        for field, label in [('cities', 'cities'), ('highest_point', 'highest points'),
                             ('landmarks', 'landmarks'), ('official_languages', 'official languages')]:
            values = c.get(field) or []
            names = [v.get('name', '') if isinstance(v, dict) else str(v) for v in values]
            names = sorted(set(n for n in names if n))
            if names:
                add(iso, 'country_notebook', iso + '/' + field, 'Which complete list of %s is recorded for %s?' % (label, name),
                    ', '.join(names), pool=field, source=c.get('wiki_url'), definition=imported)
        economy = c.get('economy') or {}
        for field, label in [('exports', 'exports'), ('imports', 'imports'), ('resources', 'natural resources'),
                             ('industries', 'industries'), ('agriculture', 'agricultural products')]:
            values = economy.get(field) or []
            names = sorted(set(str(v) for v in values if isinstance(v, str) and v))
            if names:
                add(iso, 'country_notebook', iso + '/economy/' + field, 'Which complete set of %s is recorded for %s?' % (label, name),
                    ', '.join(names), pool=field, source=c.get('wiki_url'), definition=imported)
    # Deduplicate each shared pool once, rather than redoing it for every
    # country that asks about the same field.
    pools = {key: _unique(values) for key, values in pools.items()}
    for modes in records.values():
        for rows in modes.values():
            for row in rows:
                accepted = {fold(v) for v in [row['answer']] + row['also']}
                alternatives = _unique(row['wrong']) if row['wrong'] is not None else pools.get(row['pool'], [])
                row['wrong'] = [v for v in alternatives if fold(v) not in accepted]
                if not row['wrong']:
                    raise ValueError('No distractors for lesson ' + row['id'])
    world._lesson_bank = records
    return records


def available(world, iso, mode):
    return mode not in MODES or bool(bank(world).get(iso, {}).get(mode))


def question(world, iso, mode, rng, seen=()):
    rows = bank(world).get(iso, {}).get(mode, [])
    if not rows:
        return None
    fresh = [r for r in rows if r['id'] not in seen]
    row = rng.choice(fresh or rows)
    wrong = rng.sample(row['wrong'], min(3, len(row['wrong'])))
    choices = [{'key': v, 'label': v, 'image': None} for v in [row['answer']] + wrong]
    rng.shuffle(choices)
    return dict(mode=mode, subject=iso, prompt=row['prompt'], hint=None, media=row['media'], choices=choices,
                answer=row['answer'], also=row['also'], answer_kind='demonym' if mode == 'demonym_of' else 'text',
                highlight=('fact', 'People are called') if mode == 'demonym_of' else None,
                definition=row['definition'], lesson_id=row['id'],
                explanation=row['explanation'], source=row['source'], learn_url=row['learn_url'],
                source_label='Country reference' if mode == 'country_notebook' else 'Read the source')


def generator(mode):
    def generate(world, iso, rng):
        return question(world, iso, mode, rng)
    return generate

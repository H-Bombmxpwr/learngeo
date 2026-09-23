"""English demonyms, with conservative accepted noun/plural alternatives."""
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / 'data/demonyms.json'
DATA = json.loads(DATA_PATH.read_text(encoding='utf-8'))
SOURCE = 'https://github.com/mledoze/countries'
ALIASES = {
    'GB': ['Briton', 'Britons', 'British people'],
    'NL': ['Netherlander', 'Netherlanders', 'Dutch people'],
    'FR': ['Frenchman', 'Frenchwoman', 'Frenchmen', 'Frenchwomen', 'French people'],
    'ES': ['Spaniard', 'Spaniards', 'Spanish people'],
    'DK': ['Dane', 'Danes', 'Danish people'],
    'FI': ['Finn', 'Finns', 'Finnish people'],
    'SE': ['Swede', 'Swedes', 'Swedish people'],
    'PL': ['Pole', 'Poles', 'Polish people'],
    'IE': ['Irishman', 'Irishwoman', 'Irish people'],
    'TR': ['Turk', 'Turks', 'Turkish people'],
    'HR': ['Croat', 'Croats'], 'RS': ['Serb', 'Serbs'],
    'SK': ['Slovak', 'Slovaks'], 'SI': ['Slovene', 'Slovenes'],
    'CZ': ['Czech', 'Czechs'], 'TH': ['Thai', 'Thais'],
    'BW': ['Batswana', 'Botswanan', 'Botswanans'],
    'LS': ['Basotho', 'Mosotho'], 'PH': ['Filipina', 'Filipinas', 'Filipinos'],
    'SZ': ['Swati', 'Swatis', 'emaSwati', 'Swazis'],
}


def apply(countries):
    for iso, c in countries.items():
        names = list(DATA['countries'].get(iso, []))
        if iso == 'PH':
            names.sort(key=lambda n: n != 'Filipino')
        c['demonyms'] = names
        forms = names + ALIASES.get(iso, [])
        for name in names:
            forms.append(name + ' people')
            if name.endswith(('an', 'ian', 'er')):
                forms.append(name + 's')
        c['demonym_answers'] = list(dict.fromkeys(forms))

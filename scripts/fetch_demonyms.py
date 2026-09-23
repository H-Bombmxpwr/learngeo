"""Extract English demonyms from mledoze/countries (ODbL-1.0).

The derived database remains separately downloadable with attribution. No
country facts or hand-maintained aliases are overwritten by this importer.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://raw.githubusercontent.com/mledoze/countries/master/countries.json'


if __name__ == '__main__':
    response = requests.get(SOURCE, timeout=30)
    response.raise_for_status()
    wanted = json.loads((ROOT / 'data/countries.json').read_text(encoding='utf-8'))
    rows = {}
    for country in response.json():
        iso = country['cca2']
        if iso not in wanted:
            continue
        forms = list(dict.fromkeys(country.get('demonyms', {}).get('eng', {}).values()))
        forms = [v.strip() for v in forms if isinstance(v, str) and v.strip()]
        if forms:
            rows[iso] = forms
    if len(rows) < 190:
        raise ValueError('Unexpected demonym coverage: %s' % len(rows))
    payload = dict(source=SOURCE, attribution='mledoze/countries contributors',
                   license='ODbL-1.0', license_url='https://opendatacommons.org/licenses/odbl/1-0/',
                   retrieved=datetime.now(timezone.utc).date().isoformat(),
                   source_sha256=hashlib.sha256(response.content).hexdigest(),
                   countries=dict(sorted(rows.items())))
    (ROOT / 'data/demonyms.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Imported', len(rows), 'demonyms; missing:', sorted(set(wanted) - set(rows)))

import random

from test_games import Base
from learngeo import explore, lessons, matching, questions, store
from learngeo.data import world


class LessonTests(Base):
    def test_demonyms_cover_atlas_and_are_searchable(self):
        w = world()
        self.assertEqual(len(w.all_isos), 197)
        for iso in w.all_isos:
            self.assertTrue(w.get(iso)['demonyms'], iso)
            self.assertTrue(lessons.bank(w)[iso]['demonym_of'], iso)
        self.assertIn('/country/NL', [r['url'] for r in w.search('Dutch')])
        html = self.client.get('/country/NL').get_data(as_text=True)
        self.assertIn('Dutch', html)
        self.assertIn('Practice demonyms', html)
        response = self.client.get('/data/demonyms.json')
        self.assertEqual(response.json['license'], 'ODbL-1.0')
        self.assertEqual(len(response.json['countries']), 197)
        response.close()

    def test_distinct_demonyms_are_not_fuzzy_matched(self):
        run = self.start('/play/demonyms?country=NE&challenge=1')
        q = self.client.get('/api/next?run=' + run).json
        self.assertTrue(q['challenge'])
        self.assertEqual(q['answer_kind'], 'demonym')
        pending = self.run_data(run)['pending'][q['qid']]
        self.assertTrue(matching.judge(world(), 'Nigerien', pending))
        self.assertFalse(matching.judge(world(), 'Nigerian', pending))
        run = self.start('/play/demonyms?country=GB&challenge=1')
        q = self.client.get('/api/next?run=' + run).json
        response = self.client.post('/api/answer?run=' + run,
                                    json={'qid': q['qid'], 'text': 'Britons'}).json
        self.assertTrue(response['correct'])
        self.assertIn('British', response['answer_text'])

    def test_every_new_learning_section_has_quiz_records(self):
        w, bank = world(), lessons.bank(world())
        for iso in w.all_isos:
            with self.subTest(iso=iso):
                eras = [e for e in explore.CIVILIZATIONS if iso in e['places']]
                for mode in ['civilization_place', 'civilization_dates', 'civilization_symbol']:
                    self.assertEqual(len(bank[iso][mode]), len(eras))
                self.assertEqual(len(bank[iso]['historical_flag']), sum(bool(e['image']) for e in eras))
                self.assertEqual(len(bank[iso]['history_timeline']), len(explore.TIMELINES.get(iso, [])))
                prompts = {r['prompt'] for r in bank[iso]['country_notebook']}
                for question, _, _ in explore.TRIVIA.get(iso, []):
                    self.assertIn(question, prompts)
                self.assertEqual(bool(bank[iso]['religion_status']), iso in explore.RELIGION)
                self.assertTrue(bank[iso]['country_notebook'])
        self.assertEqual(len(bank['IN']['religion_affiliation']), 5)
        self.assertEqual(bank['JP']['religion_affiliation'], [])
        self.assertTrue(bank['JP']['religion_context'])
        for modes in bank.values():
            for rows in modes.values():
                for row in rows:
                    self.assertNotIn(row['answer'], row['wrong'])
                    self.assertTrue(row['wrong'])
                    self.assertTrue(row['source'].startswith('https://'))

    def test_sparse_topic_picker_only_draws_available_records(self):
        w = world()
        for adaptive in [False, True]:
            for mode in ['historical_flag', 'history_timeline', 'religion_status']:
                for _ in range(40):
                    iso, chosen = store.pick(w, [mode], random.Random(_), adaptive=adaptive,
                                            eligible=lambda i, m: lessons.available(w, i, m))
                    self.assertTrue(lessons.bank(w)[iso][chosen])

    def test_new_questions_keep_sources_until_answer_and_restore_feedback(self):
        run = self.start('/play/beliefs?country=IN&endless=1')
        q = self.client.get('/api/next?run=' + run).json
        self.assertNotIn('explanation', q)
        self.assertNotIn('source', q)
        result = self.client.post('/api/answer?run=' + run, json={
            'qid': q['qid'], 'choice': self.answer_for(run, q['qid'])}).json
        self.assertTrue(result['correct'])
        self.assertTrue(result['explanation'])
        self.assertTrue(result['source'].startswith('https://'))
        self.assertEqual(result['learn_url'], '/country/IN#belief')
        restored = self.client.get('/api/next?run=' + run).json['restored_answer']
        self.assertEqual(result['explanation'], restored['explanation'])
        self.assertEqual(result['source'], restored['source'])

    def test_historical_flag_run_visits_every_image_before_repeating(self):
        run = self.start('/play/historical_flags?endless=1')
        seen = set()
        for _ in range(4):
            q = self.client.get('/api/next?run=' + run + '&advance=1').json
            self.assertEqual(q['media']['type'], 'image')
            self.assertNotIn(q['media']['url'], seen)
            seen.add(q['media']['url'])
            self.client.post('/api/answer?run=' + run, json={
                'qid': q['qid'], 'choice': self.answer_for(run, q['qid'])})

    def test_context_only_religion_and_country_scoped_style(self):
        run = self.start('/play/beliefs?country=JP&challenge=1&endless=1')
        self.assertFalse(self.run_data(run)['challenge'])
        for _ in range(4):
            q = self.client.get('/api/next?run=' + run + '&advance=1').json
            if q.get('done'):
                break   # Japan's few religion questions have all been asked
            self.assertNotEqual(q['mode'], 'religion_affiliation')
            self.client.post('/api/answer?run=' + run, json={
                'qid': q['qid'], 'choice': self.answer_for(run, q['qid'])})
        run = self.start('/play/ancient_world?country=EG&challenge=1')
        self.assertFalse(self.run_data(run)['challenge'])
        self.assertEqual(self.client.get('/api/next?run=' + run).status_code, 200)
        self.assertNotIn('Practice these historical flags', self.client.get('/country/EG').get_data(as_text=True))

    def test_country_notebook_rotates_facts(self):
        run = self.start('/play/country_knowledge?country=TV&endless=1')
        seen = set()
        for _ in range(8):
            q = self.client.get('/api/next?run=' + run + '&advance=1').json
            self.assertNotIn(q['prompt'], seen)
            seen.add(q['prompt'])
            self.client.post('/api/answer?run=' + run, json={
                'qid': q['qid'], 'choice': self.answer_for(run, q['qid'])})

    def test_finished_run_keeps_the_last_lesson_explanation(self):
        # The United Kingdom has one demonym question, so a run scoped to it
        # ends after that one rather than asking it five times.
        run = self.start('/play/demonyms?country=GB&challenge=1&length=5')
        q = self.client.get('/api/next?run=' + run + '&advance=1').json
        result = self.client.post('/api/answer?run=' + run, json={
            'qid': q['qid'], 'text': 'British'}).json
        self.assertTrue(result['finished'])
        self.assertEqual(result['learn_url'], '/country/GB#people-name')
        self.assertTrue(result['explanation'])
        self.assertEqual(result['source_label'], 'Read the source')

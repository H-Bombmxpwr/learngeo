"""Regression checks for learning trails and mode-specific run settings."""
from pathlib import Path

from test_games import Base
from learngeo import explore, questions
from learngeo.data import world


class ExplorationTests(Base):
    def test_all_country_pages_render_with_learning_sections(self):
        for iso in world().all_isos:
            with self.subTest(iso=iso):
                response = self.client.get('/country/' + iso)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Trivia essentials', response.data)
                self.assertIn(b'Religion: state', response.data)

    def test_shared_civilizations_and_assets(self):
        w = world()
        for era in explore.CIVILIZATIONS:
            self.assertTrue(era['source'].startswith('https://'))
            if era['image']:
                self.assertTrue((Path(__file__).resolve().parents[1] / 'static' / 'images' / era['image']).is_file())
            for iso in era['places']:
                self.assertIsNotNone(w.get(iso), iso)
                self.assertIn(era['name'], [e['name'] for e in w.get(iso)['civilizations']])
        self.assertEqual(self.client.get('/topic/civilization/roman-empire').status_code, 200)
        self.assertIn(b'reconstructions', self.client.get('/country/IR').data)
        self.assertIn(b'No known flag', self.client.get('/country/PK').data)

    def test_religion_distinguishes_status_affiliation_and_missing_data(self):
        india = explore.dossier(world(), 'IN')['religion']
        self.assertIn('No state religion', india['official'])
        self.assertEqual(india['largest'], 'Hinduism')
        self.assertEqual(india['year'], '2011 census')
        self.assertIsNone(explore.dossier(world(), 'JP')['religion']['largest'])
        self.assertIsNone(explore.dossier(world(), 'TV')['religion'])


class SessionSettingsTests(Base):
    def test_map_and_alliances_cannot_claim_typed_mode(self):
        for category in ('map', 'institutions'):
            run_id = self.start('/play/' + category + '?challenge=1')
            self.assertFalse(self.run_data(run_id)['challenge'])
            q = self.client.get('/api/next?run=' + run_id).json
            self.assertFalse(q['challenge'])
            self.assertFalse(questions.game_options(category)['typed'])

    def test_five_correct_answers_complete_short_run(self):
        run_id = self.start('/play/capitals?length=5')
        for number in range(1, 6):
            q = self.client.get('/api/next?run=' + run_id + '&advance=1').json
            self.assertEqual(q['run_length'], 5)
            result = self.client.post('/api/answer?run=' + run_id, json={
                'qid': q['qid'], 'choice': self.answer_for(run_id, q['qid'])}).json
            self.assertTrue(result['correct'])
            self.assertEqual(result['run']['over'], number == 5)

    def test_length_resume_restart_validation_and_practice(self):
        short = self.start('/play/capitals?length=5')
        self.assertEqual(short, self.start('/play/capitals?length=5'))
        long = self.start('/play/capitals?length=25')
        self.assertNotEqual(short, long)
        restarted = self.client.post('/api/restart', json={
            'category': 'capitals', 'length': 25}).json['run']
        self.assertEqual(restarted['length'], 25)
        invalid = self.start('/play/capitals?length=999')
        self.assertEqual(self.run_data(invalid)['length'], 12)
        practice = self.start('/play/capitals?endless=1&length=5')
        for _ in range(6):
            q = self.client.get('/api/next?run=' + practice + '&advance=1').json
            self.assertIsNone(q['run_length'])
            result = self.client.post('/api/answer?run=' + practice, json={
                'qid': q['qid'], 'choice': self.answer_for(practice, q['qid'])}).json
            self.assertFalse(result['run']['over'])

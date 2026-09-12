import json
import random
import tempfile
import unittest
from unittest.mock import patch

import app as web
from learngeo import matching, provenance, questions, store, supplement
from learngeo.data import world


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(store, "DB_PATH", self.tmp.name + "/test.db")
        self.dir = patch.object(store, "DATA_DIR", self.tmp.name)
        self.db.start()
        self.dir.start()
        web.app.config.update(TESTING=True)
        self.client = web.app.test_client()

    def tearDown(self):
        self.db.stop()
        self.dir.stop()
        self.tmp.cleanup()

    # -- helpers ----------------------------------------------------------
    def player(self):
        return self.client.get_cookie(web.PLAYER_COOKIE).value

    def start(self, path):
        """Open a game page and return the run id it redirects to."""
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302, path)
        return response.headers["Location"].split("run=")[1].split("&")[0]

    def run_data(self, run_id):
        state, _ = store.load_run(self.player(), run_id)
        return state

    def answer_for(self, run_id, qid):
        return self.run_data(run_id)["pending"][qid]["answer"]


class GameTests(Base):
    def test_refresh_preserves_question_feedback_and_score(self):
        run = self.start("/play/flags?challenge=1")
        q = self.client.get("/api/next?run=" + run).json
        self.client.get("/play/flags?challenge=1&run=" + run)
        self.assertEqual(q["qid"], self.client.get("/api/next?run=" + run).json["qid"])
        res = self.client.post("/api/answer?run=" + run, json={
            "qid": q["qid"], "text": self.answer_for(run, q["qid"]),
            "ms": 10000}).json
        self.assertTrue(res["correct"])
        self.assertEqual(res["run"]["asked"], 1)
        restored = self.client.get("/api/next?run=" + run).json
        self.assertEqual(restored["restored_answer"]["run"]["score"],
                         res["run"]["score"])
        self.assertNotEqual(
            self.client.get("/api/next?run=%s&advance=1" % run).json["qid"],
            q["qid"])

    def test_all_categories_both_styles_and_lengths(self):
        for category in questions.CATEGORY_MODES:
            for challenge in (False, True):
                for endless in (False, True):
                    with self.subTest(category=category, challenge=challenge,
                                      endless=endless):
                        run = self.client.post("/api/restart", json=dict(
                            category=category, challenge=challenge,
                            endless=endless)).json["run"]["id"]
                        response = self.client.get("/api/next?run=" + run)
                        self.assertEqual(response.status_code, 200)
                        q = response.json
                        self.assertIn("qid", q)
                        if q["challenge"]:
                            self.assertNotIn(q["mode"], questions.CHOICE_REQUIRED)
                            self.assertNotIn("these", q["prompt"])
                        if q["mode"] in ("flag_to_country", "leader_photo", "outline"):
                            self.assertIn(q["media"]["type"], ("image", "outline"))

    def test_map_accepts_iso3_for_country_question(self):
        run = self.start("/play/flags?challenge=1")
        q = self.client.get("/api/next?run=" + run).json
        iso3 = world().get(self.answer_for(run, q["qid"]))["iso3"]
        res = self.client.post("/api/answer?run=" + run,
                               json={"qid": q["qid"], "choice": iso3}).json
        self.assertTrue(res["correct"])
        self.assertEqual(res["answer_iso3"], iso3)

    def test_browser_isolation_and_pages(self):
        run = self.start("/play/flags")
        q = self.client.get("/api/next?run=" + run).json
        other = web.app.test_client()
        other_run = other.get("/play/flags").headers["Location"].split("run=")[1]
        self.assertNotEqual(q["run"]["id"],
                            other.get("/api/next?run=" + other_run).json["run"]["id"])
        for url in ("/", "/games", "/progress", "/map", "/country/NE",
                    "/country/FR", "/atlas"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_country_practice_and_lifelines_survive_refresh(self):
        run = self.start("/play/grand_tour?endless=1&country=NE")
        q = self.client.get("/api/next?run=" + run).json
        self.assertEqual(self.run_data(run)["pending"][q["qid"]]["subject"], "NE")
        hint = self.client.post("/api/lifeline?run=" + run,
                                json={"qid": q["qid"], "kind": "peek"}).json
        restored = self.client.get("/api/next?run=" + run).json
        self.assertEqual(restored["hint"], hint["peek"])
        self.assertEqual(restored["run"]["lifelines"]["peek"], 0)
        self.client.post("/api/answer?run=" + run,
                         json={"qid": q["qid"], "skipped": True})
        next_q = self.client.get("/api/next?run=%s&advance=1" % run).json
        self.assertEqual(next_q["run"]["lifelines"]["skip"], 0)
        self.assertEqual(self.run_data(run)["pending"][next_q["qid"]]["subject"], "NE")

    def test_finished_run_restores_and_restart_keeps_challenge(self):
        run = self.start("/play/flags?challenge=1")
        for _ in range(3):
            q = self.client.get("/api/next?run=%s&advance=1" % run).json
            res = self.client.post("/api/answer?run=" + run, json={
                "qid": q["qid"], "text": "definitely wrong"}).json
        self.assertTrue(res["finished"])
        self.assertTrue(
            self.client.get("/api/next?run=" + run).json["restored_answer"]["finished"])
        fresh_id = self.client.post("/api/restart?run=" + run, json={
            "category": "flags", "challenge": True}).json["run"]["id"]
        fresh = self.client.get("/api/next?run=" + fresh_id).json
        self.assertTrue(fresh["challenge"])
        self.assertEqual(fresh["run"]["score"], 0)


class TabAndConcurrencyTests(Base):
    """Item 4 of the handoff: a run per tab, and writes that cannot race."""

    def test_two_tabs_keep_separate_runs(self):
        first = self.start("/play/flags")
        second = self.start("/play/capitals?endless=1")
        self.assertNotEqual(first, second)
        # Both are still live, and each resumes its own question.
        q1 = self.client.get("/api/next?run=" + first).json
        q2 = self.client.get("/api/next?run=" + second).json
        self.assertNotEqual(q1["qid"], q2["qid"])
        self.assertEqual(q1["run"]["id"], first)
        self.assertEqual(q2["run"]["id"], second)
        # And a bare visit to the first tab's settings finds the first run,
        # not whichever was touched most recently.
        self.assertIn(first, self.client.get("/play/flags").headers["Location"])

    def test_settings_in_the_url_beat_the_run_named_in_it(self):
        run = self.start("/play/flags")
        other = self.start("/play/flags?challenge=1&run=" + run)
        self.assertNotEqual(run, other)
        self.assertTrue(self.run_data(other)["challenge"])

    def test_duplicate_submission_scores_once(self):
        run = self.start("/play/flags")
        q = self.client.get("/api/next?run=" + run).json
        body = {"qid": q["qid"], "choice": self.answer_for(run, q["qid"]),
                "ms": 4000}
        first = self.client.post("/api/answer?run=" + run, json=body).json
        second = self.client.post("/api/answer?run=" + run, json=body).json
        self.assertEqual(first["points"], second["points"])
        self.assertEqual(first["run"]["score"], second["run"]["score"])
        self.assertEqual(self.run_data(run)["asked"], 1)

    def test_answer_is_one_transaction(self):
        """Mastery, the answer log and the run state move together."""
        run = self.start("/play/flags")
        q = self.client.get("/api/next?run=" + run).json
        self.client.post("/api/answer?run=" + run, json={
            "qid": q["qid"], "choice": self.answer_for(run, q["qid"])})
        blob = store.export_data(self.player())
        self.assertEqual(len(blob["answers"]), 1)
        self.assertEqual(len(blob["mastery"]), 1)
        self.assertEqual(self.run_data(run)["asked"], 1)

    def test_a_stale_version_is_refused_not_applied(self):
        pid = "concurrency"
        store.save_run(pid, "r", {"id": "r", "score": 1})
        self.assertIsNotNone(store.save_run(pid, "r", {"id": "r", "score": 2}, 1))
        # A second writer still holding version 1 is told no, and the value
        # it would have written never lands.
        self.assertIsNone(store.save_run(pid, "r", {"id": "r", "score": 99}, 1))
        self.assertEqual(store.load_run(pid, "r")[0]["score"], 2)

    def test_expired_run_is_reported_not_resurrected(self):
        run = self.start("/play/flags")
        self.client.post("/api/run/abandon?run=" + run)
        response = self.client.get("/api/next?run=" + run)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json["expired"])


class LifecycleTests(Base):
    """Item 5: schema versions, stale runs, scoped reset, export and import."""

    def test_schema_version_is_recorded(self):
        with store.connect() as conn:
            self.assertEqual(store.schema_version(conn), store.SCHEMA_VERSION)

    def test_stale_runs_are_swept(self):
        store.save_run("p", "old", {"id": "old"})
        self.assertEqual(store.cleanup_stale(days=0), 1)
        self.assertIsNone(store.load_run("p", "old")[0])

    def test_forget_scopes_are_separate(self):
        run = self.start("/play/flags")
        q = self.client.get("/api/next?run=" + run).json
        self.client.post("/api/answer?run=" + run, json={
            "qid": q["qid"], "choice": self.answer_for(run, q["qid"])})

        # Clearing mastery leaves the game in progress alone...
        self.client.post("/api/forget", json={"scopes": ["mastery"]})
        self.assertEqual(store.export_data(self.player())["mastery"], [])
        self.assertIsNotNone(self.run_data(run))

        # ...and clearing games in progress is what removes it.
        self.client.post("/api/forget", json={"scopes": ["active"]})
        self.assertIsNone(self.run_data(run))

    def test_export_then_import_round_trips(self):
        run = self.start("/play/flags")
        q = self.client.get("/api/next?run=" + run).json
        self.client.post("/api/answer?run=" + run, json={
            "qid": q["qid"], "choice": self.answer_for(run, q["qid"])})
        blob = self.client.get("/api/progress/export").json
        self.assertEqual(blob["format"], "learngeo-progress")

        other = web.app.test_client()
        other.get("/")
        result = other.post("/api/progress/import", json={"data": blob}).json
        self.assertEqual(result["imported"]["mastery"], len(blob["mastery"]))
        self.assertEqual(result["imported"]["answers"], len(blob["answers"]))

    def test_import_rejects_a_file_that_is_not_ours(self):
        response = self.client.post("/api/progress/import",
                                    json={"data": {"hello": "world"}})
        self.assertEqual(response.status_code, 400)


class DataTests(unittest.TestCase):
    """Items 1 to 3: provenance, ambiguity and the history redesign."""

    def test_niger_languages(self):
        c = world().get("NE")
        self.assertEqual(c["national_languages"], ["Hausa"])
        self.assertEqual(c["official_languages"], [])
        self.assertFalse(next(l for l in c["languages"]
                              if l["name"] == "French")["official"])
        self.assertEqual(
            questions.language_of(world(), "NE", random.Random(3))["answer"],
            "Hausa")
        self.assertIn("languages", world().provenance("NE"))

    def test_matching_stays_generous_without_being_wrong(self):
        self.assertTrue(matching.matches_text("St Johns", "St. John's"))
        self.assertTrue(matching.matches_text("Saint Johns", "St. John's"))
        self.assertTrue(matching.matches_text("Alegria", "Algeria"))
        self.assertFalse(matching.matches_text("democratic", "democratic republic"))
        # The one pair that must never be accepted for one another.
        self.assertFalse(matching.matches_text("Austria", "Australia"))
        self.assertFalse(matching.matches_text("Australia", "Austria"))
        self.assertFalse(matching.judge(world(), "-3", {"answer_kind": "number",
                                                        "answer": "3"}))

    def test_continents_are_the_ones_the_countries_are_in(self):
        w = world()
        for iso, expected in (("FR", "Europe"), ("NL", "Europe"),
                              ("ES", "Europe"), ("NO", "Europe"),
                              ("US", "North America"), ("TR", "Asia"),
                              ("EG", "Africa"), ("AU", "Oceania")):
            self.assertEqual(w.continent_of(iso), expected, iso)
        # Every country lands on one of the seven, and none on "Eurasia".
        for iso in w.all_isos:
            self.assertIn(w.continent_of(iso), provenance.CANONICAL_CONTINENTS)
        # A transcontinental country accepts either side.
        q = questions.continent_of(w, "TR", random.Random(1))
        self.assertEqual(q["answer"], "Asia")
        self.assertIn("Europe", q["also"])
        self.assertTrue(matching.matches_text("Europe", q["answer"], q["also"]))

    def test_mexico_has_a_sourced_leader(self):
        leaders = world().get("MX")["leaders"]
        self.assertTrue(leaders)
        self.assertIn("leaders", world().provenance("MX"))
        self.assertTrue(world().provenance("MX")["leaders"]["source"])

    def test_war_participation_is_not_asked_about(self):
        self.assertNotIn("war_participant", questions.MODES)
        # The underlying association still names the United States for the
        # Iraq War -- the reason the question was retired was that a list of
        # principals cannot settle participation either way, not that the
        # list was wrong.
        iraq = [w for w in world().get("US")["wars"] if w["name"] == "Iraq War"]
        self.assertTrue(iraq, "the US should still be recorded for the Iraq War")
        self.assertEqual(iraq[0]["role"], supplement.PARTICIPATION_ROLE)
        # Japan is attached to the Iraq War by the imported source, which does
        # not separate combat from reconstruction. The association is kept --
        # it is real, and deleting inconvenient data is not verification --
        # but it is labelled as the weaker claim it is, and it is no longer
        # the basis of any question.
        japan = [w for w in world().get("JP")["wars"] if w["name"] == "Iraq War"]
        self.assertTrue(japan)
        self.assertEqual(japan[0]["role"], supplement.IMPORTED_ROLE)
        self.assertNotEqual(japan[0]["role"], supplement.PARTICIPATION_ROLE)
        # Every war row, curated or imported, says which kind of claim it is.
        for iso in ("US", "JP", "FR", "BR"):
            for war in world().get(iso).get("wars") or []:
                self.assertIn(war["role"], (supplement.PARTICIPATION_ROLE,
                                            supplement.IMPORTED_ROLE))

    def test_history_questions_are_sourced_and_answerable(self):
        w = world()
        q = questions.war_when(w, "GB", random.Random(4))
        self.assertTrue(q and str(int(q["answer"])) == q["answer"])
        q = questions.war_between(w, "GB", random.Random(4))
        self.assertTrue(q)
        self.assertEqual(len(q["choices"]), 4)
        q = questions.war_order(w, "FR", random.Random(4))
        years = supplement.war_years()
        picked = [years[c["label"]][0] for c in q["choices"]]
        self.assertEqual(years[q["answer"]][0], min(picked))

    def test_shared_landmarks_are_not_asked_about(self):
        w = world()
        for _ in range(30):
            q = questions.landmark_to_country(w, "BR", random.Random())
            if q:
                self.assertNotIn("Amazon", q["prompt"])
        self.assertTrue(provenance.is_shared_landmark("Andes"))

    def test_membership_questions_use_the_checked_list(self):
        w = world()
        # The imported member_of still has the UK in the EU and leaves the
        # Netherlands out of it; the checked list is what is asked about.
        self.assertTrue(w.member_of_verified("NL", "European Union"))
        self.assertFalse(w.member_of_verified("GB", "European Union"))
        self.assertTrue(w.member_of_verified("NL", "NATO"))
        q = questions.eu_member(w, "GB", random.Random(1))
        self.assertEqual(q["answer"], "No")

    def test_every_mode_states_its_convention_or_needs_none(self):
        w = world()
        q = questions.biggest_city(w, "DE", random.Random(2))
        self.assertIn("City proper", q["definition"])

    def test_mode_inventory_matches_what_can_be_generated(self):
        w = world()
        got = questions.supported_modes(w, "TV")
        self.assertNotIn("border_count", got)      # Tuvalu has no neighbours
        self.assertIn("capital_of", got)
        self.assertIn("Borders", questions.missing_topics(
            w, "TV", sorted(questions.COUNTRY_STUDY_MODES)))

    def test_country_practice_spreads_over_the_topics(self):
        """A run on one country should not ask the same thing twice early."""
        used = {}
        modes = sorted(questions.COUNTRY_STUDY_MODES)
        picked = []
        for i in range(8):
            mode = questions.balanced_mode(random.Random(i), modes, used)
            picked.append(mode)
            used[mode] = used.get(mode, 0) + 1
        self.assertEqual(len(set(picked)), 8)


class ScoringTests(Base):
    """Item 9: what a question is worth, and what the clock counts."""

    def test_two_option_questions_are_worth_less(self):
        run = {"streak": 0}
        wide = web.award(run, {"choice_count": 4}, 12000)
        narrow = web.award(run, {"choice_count": 2}, 12000)
        self.assertLess(narrow, wide)

    def test_the_clock_cannot_be_restarted_by_refreshing(self):
        import time as _time
        pending = {"asked_at": _time.time() - 30}
        # The browser claims one second, because it was refreshed; the server
        # knows the question has been open for thirty.
        self.assertGreater(web.elapsed_ms(pending, 1000), 20000)
        # A browser reporting longer than the server is believed as it is.
        self.assertEqual(web.elapsed_ms({"asked_at": _time.time()}, 5000), 5000)

    def test_a_run_reports_the_countries_it_covered(self):
        run = self.start("/play/flags")
        q = self.client.get("/api/next?run=" + run).json
        res = self.client.post("/api/answer?run=" + run, json={
            "qid": q["qid"], "choice": self.answer_for(run, q["qid"])}).json
        self.assertTrue(res["run"]["countries_seen"])


class MapTests(Base):
    """Item 7: the countries that were not on the map at all."""

    def test_countries_without_a_polygon_get_a_point(self):
        geo = self.client.get("/api/geo").json
        ids = {p["id"] for p in geo["points"]}
        self.assertIn(world().get("TV")["iso3"], ids)
        self.assertIn(world().get("SG")["iso3"], ids)
        # And nothing is both a polygon and a point.
        self.assertFalse(ids & {f.get("id") for f in geo["features"]})

    def test_antarctica_stays_out(self):
        geo = self.client.get("/api/geo").json
        self.assertNotIn("ATA", {f.get("id") for f in geo["features"]})


if __name__ == "__main__":
    unittest.main()

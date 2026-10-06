"""The whole-dataset review: the reported errors stay fixed."""
from test_games import Base
from learngeo import review
from learngeo.data import world


def names(rows):
    return [r["name"] if isinstance(r, dict) else r for r in rows or []]


class ReviewTests(Base):
    def test_main_language_leads_the_list(self):
        w = world()
        for iso, lang in [("BR", "Portuguese"), ("DE", "German"),
                          ("VN", "Vietnamese"), ("EG", "Arabic")]:
            with self.subTest(iso=iso):
                first = w.get(iso)["languages"][0]
                self.assertEqual(first["name"], lang)
                self.assertTrue(first["official"])
        self.assertNotIn("Japanese", names(w.get("BR")["languages"]))
        self.assertEqual(names(w.get("RU")["official_languages"]), ["Russian"])

    def test_no_language_row_is_parse_debris(self):
        for iso in world().all_isos:
            for lang in world().get(iso).get("languages") or []:
                self.assertNotIn("(", lang["name"].replace("(Bokmål)", "").replace("(Nynorsk)", ""), iso)
                self.assertNotIn(lang["name"].lower(), review.LANG_DROP, iso)

    def test_euro_area_has_a_currency(self):
        for iso in ("FR", "DE", "IE", "LT", "CY", "BG"):
            self.assertEqual(names(world().get(iso)["currencies"]), ["Euro"], iso)

    def test_city_lists_have_no_districts(self):
        us = names(world().get("US")["cities"])
        self.assertNotIn("Brooklyn", us)
        self.assertNotIn("Queens", us)
        self.assertEqual(names(world().get("NL")["cities"])[0], "Amsterdam")
        self.assertEqual(names(world().get("PK")["cities"])[0], "Karachi")
        for iso in world().all_isos:
            pops = [c.get("population") or 0 for c in world().get(iso).get("cities") or []]
            self.assertEqual(pops, sorted(pops, reverse=True), iso)

    def test_famous_people_belong_to_one_country(self):
        owners = {}
        for iso in world().all_isos:
            for name in names(world().get(iso).get("famous")):
                owners.setdefault(name, set()).add(iso)
        self.assertEqual({n: o for n, o in owners.items() if len(o) > 1}, {})
        self.assertNotIn("Frank Sinatra", names(world().get("IT")["famous"]))

    def test_neutral_countries_did_not_fight_world_war_two(self):
        for iso in ("IE", "SE", "CH", "ES", "PT"):
            self.assertNotIn("World War II", names(world().get(iso).get("wars")), iso)

    def test_country_page_labels_the_review(self):
        html = self.client.get("/country/BR").get_data(as_text=True)
        self.assertIn("AI-assisted review", html)
        self.assertIn("Portuguese", html)

    def test_small_section_links_to_the_worldwide_game(self):
        # The United States has a handful of religion questions and one
        # demonym: too few for a run of their own.
        html = self.client.get("/country/US").get_data(as_text=True)
        self.assertIn("Practice demonyms around the world", html)
        self.assertNotIn("category=demonyms&amp;country=US", html)

    def test_small_section_run_ends_instead_of_repeating(self):
        run = self.start("/play/beliefs?country=US&endless=1")
        prompts = []
        for _ in range(20):
            q = self.client.get("/api/next?run=" + run + "&advance=1").json
            if q.get("done"):
                break
            prompts.append(q["prompt"])
            result = self.client.post("/api/answer?run=" + run, json={
                "qid": q["qid"], "choice": self.answer_for(run, q["qid"])}).json
            if result["finished"]:
                break
        self.assertTrue(result["finished"])
        self.assertEqual(len(prompts), len(set(prompts)))

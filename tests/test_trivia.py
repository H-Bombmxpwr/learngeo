"""Content and route invariants for the general-knowledge transformation."""
import importlib.util
import gzip
import json
from pathlib import Path
import re
import unittest

from app import app
from learngeo.trivia import graph
from learngeo.trivia_bank import TOPICS, cards
from test_games import Base

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("trivia_builder", ROOT / "scripts/build_trivia.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class TriviaTests(Base):
    def test_curated_bank_has_stable_unique_sourced_cards(self):
        bank = cards()
        self.assertEqual(len(bank), 120)
        self.assertEqual(len({c["id"] for c in bank}), 120)
        self.assertEqual({c["topic"] for c in bank}, {t["id"] for t in TOPICS})
        for c in bank:
            with self.subTest(card=c["id"]):
                self.assertTrue(c["prompt"] and c["answer"] and c["explanation"] and c["hook"])
                self.assertIn(c["level"], (1, 2, 3))
                self.assertTrue(c["source"].startswith("https://en.wikipedia.org/wiki/"))

    def test_root_is_general_knowledge_and_geography_remains_accessible(self):
        client = app.test_client()
        home = client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"Commonplace", home.data)
        self.assertIn(b"Rabbit holes", home.data)
        self.assertEqual(client.get("/geography").status_code, 200)
        self.assertEqual(client.get("/trivia/").status_code, 200)
        self.assertEqual(len(client.get("/trivia/bank").json["topics"]), 12)

    def test_large_payloads_support_browser_compression(self):
        response = app.test_client().get("/trivia/bank", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(response.headers["Content-Encoding"], "gzip")
        self.assertGreater(len(json.loads(gzip.decompress(response.data))["cards"]), 5000)

    def test_large_graph_has_no_dangling_connections(self):
        data = graph()
        self.assertGreater(len(data["cards"]), 5000)
        self.assertEqual(data["manifest"]["license"], "CC0-1.0")
        bank = {c["id"]: c for c in data["cards"]}
        self.assertEqual(len(bank), len(data["cards"]))
        allowed = {t["id"] for t in TOPICS}
        for card in bank.values():
            self.assertIn(card["topic"], allowed)
            self.assertTrue(card["aliases"])
            self.assertTrue(card["source"].startswith("https://www.wikidata.org/wiki/"))
            self.assertTrue(all(q in data["entities"] for q in card["entities"]))
            self.assertTrue(card["generated"])
        for node in data["entities"].values():
            self.assertFalse(re.fullmatch(r"Q\d+", node["name"]))
            for link in node["links"]:
                if link["card"] is not None:
                    self.assertIn(link["card"], bank)
                self.assertTrue(all(q in data["entities"] for q in link["targets"]))

    def test_progress_is_kept_on_the_server_per_player(self):
        self.assertEqual(self.client.get("/trivia/state").json, None)
        state = {"version": 1, "progress": {"h01": {"seen": 1, "correct": 1, "streak": 1,
                 "interval": 1, "due": 1, "last": 1}}, "custom": [], "benchmarks": [],
                 "saved": [], "hidden": []}
        self.assertEqual(self.client.put("/trivia/state", json=state).status_code, 200)
        self.assertEqual(self.client.get("/trivia/state").json, state)
        # Another browser has its own cookie and so its own progress.
        self.assertIsNone(app.test_client().get("/trivia/state").json)
        self.assertEqual(self.client.put("/trivia/state", json={"version": 2}).status_code, 400)

    def test_countries_bridge_the_studio_and_the_geography_wing(self):
        bank = self.client.get("/trivia/bank").json
        self.assertEqual(bank["countries"]["Q142"]["iso2"], "FR")
        page = self.client.get("/country/FR")
        self.assertIn(b'id="studio"', page.data)
        self.assertIn(b"#explore/Q142", page.data)
        self.assertIn(b"Mont Blanc", page.data)
        generated = next(c for c in bank["cards"] if c.get("generated"))
        self.assertTrue(generated["reading"][0]["url"].startswith("https://en.wikipedia.org/wiki/"))

    def test_multiple_attributions_are_grouped_and_all_accepted(self):
        spec = builder.SLICES[0]
        def row(target, label):
            values = {"item":"http://www.wikidata.org/entity/Q100", "object":"http://www.wikidata.org/entity/"+target,
                "itemLabel":"Example Work", "objectLabel":label, "links":"75", "objectAlias":label+" Alias"}
            return {k:{"value":v} for k,v in values.items()}
        data = builder.build([(spec,{"retrieved_at":"2026-10-05", "rows":[row("Q101","First Author"),row("Q102","Second Author")]})])
        self.assertEqual(len(data["cards"]),1)
        card = data["cards"][0]
        self.assertIn("First Author",card["aliases"])
        self.assertIn("Second Author",card["aliases"])
        self.assertTrue(card["prompt"].startswith("Name an author"))
        self.assertEqual(len(data["entities"]["Q100"]["links"][0]["targets"]),2)

    def test_answer_leakage_and_excessive_attribution_are_excluded(self):
        spec = builder.SLICES[0]
        values = {"item":"http://www.wikidata.org/entity/Q100", "object":"http://www.wikidata.org/entity/Q101",
                  "itemLabel":"Bob's Book", "objectLabel":"Bob", "links":"80"}
        data = builder.build([(spec,{"retrieved_at":"2026-10-05", "rows":[{k:{"value":v} for k,v in values.items()}]})])
        self.assertEqual(data["cards"],[])
        self.assertIn("Q100", data["entities"])
        self.assertIsNone(data["entities"]["Q100"]["links"][0]["card"])


if __name__ == "__main__":
    unittest.main()

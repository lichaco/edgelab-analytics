"""Pruebas del proveedor gratuito ESPN sin llamadas a internet."""
import unittest
from datetime import datetime, timezone
from scripts.build_public_odds import (
    price, lines, normalize_provider, odds_for_event, safe_ref,
    build_snapshot, enumerate_soccer_ids,
)

NOW = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
NBA = {"id": "401111111", "competitionId": "nba", "sport": "basket",
       "home": "Boston Celtics", "away": "Chicago Bulls",
       "utc": "2026-10-26T23:00:00Z"}
PREMIER = {"id": "openfootball-eng.1-2026-10-26-Arsenal-Liverpool",
           "competitionId": "eng.1", "sport": "football",
           "home": "Arsenal FC", "away": "Liverpool FC",
           "utc": "2026-10-26T20:00:00Z"}


class PublicOddsTests(unittest.TestCase):
    def test_american_to_decimal(self):
        self.assertEqual(price(-110), 1.9091)
        self.assertEqual(price(150), 2.5)
        self.assertEqual(price(-400), 1.25)
        self.assertIsNone(price(None))
        self.assertIsNone(price(0))
        self.assertIsNone(price(-30))
        self.assertIsNone(price(True))

    def test_sport_moneyline_and_totals(self):
        data = {"provider": {"name": "DraftKings"},
                "overUnder": 224.5, "overOdds": -110, "underOdds": -120,
                "spread": -2.5, "homeTeamOdds": {"moneyLine": -150, "spreadOdds": -112},
                "awayTeamOdds": {"moneyLine": 130, "spreadOdds": -109}}
        markets = lines(data, soccer=False)
        self.assertEqual([x["kind"] for x in markets], ["result", "totals", "spread"])
        self.assertEqual(markets[0]["selections"]["home"], 1.6667)
        self.assertEqual(markets[1]["line"], 224.5)
        self.assertEqual(markets[2]["line"], -2.5)

    def test_soccer_1x2_requires_draw(self):
        data = {"provider": {"name": "Caesars"},
                "homeTeamOdds": {"moneyLine": -150},
                "awayTeamOdds": {"moneyLine": 130}}
        self.assertEqual(lines(data, soccer=True), [])
        data["drawOdds"] = {"moneyLine": 280}
        markets = lines(data, soccer=True)
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0]["selections"]["draw"], 3.8)

    def test_no_invented_totals_price(self):
        self.assertEqual(lines({"overUnder": 2.5}, soccer=True), [])
        self.assertIsNone(normalize_provider({"provider": {"name": "DraftKings"}}, False))

    def test_only_allowed_espn_reference_urls(self):
        good = "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401111111/competitions/401111111/odds/41"
        self.assertEqual(safe_ref(good, "401111111", "basketball", "nba"),
                         good.replace("http:", "https:"))
        self.assertIsNone(safe_ref("https://evil.example/odds/41", "401111111", "basketball", "nba"))
        self.assertIsNone(safe_ref("https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/42/competitions/42/odds/41", "401111111", "basketball", "nba"))

    def test_odds_reader_with_provider_refs(self):
        def getter(url):
            if url.endswith("odds?limit=20"):
                return {"items": [{"$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401111111/competitions/401111111/odds/41"}]}
            return {"provider": {"name": "DraftKings"},
                    "homeTeamOdds": {"moneyLine": -130},
                    "awayTeamOdds": {"moneyLine": 120}}
        books, errors = odds_for_event("401111111", "nba", getter)
        self.assertEqual(errors, [])
        self.assertEqual(books["DraftKings"][0]["selections"]["home"], 1.7692)

    def test_calendar_matches_public_odds(self):
        def getter(url):
            self.assertIn("scoreboard?dates=20261026", url)
            return {"events": [{"id": "401222222", "date": "2026-10-26T20:00:00Z",
                                "competitions": [{"competitors": [
                                   {"homeAway": "home", "team": {"displayName": "Arsenal"}},
                                   {"homeAway": "away", "team": {"displayName": "Liverpool"}}
                                ]}]}]}
        mapping, errors = enumerate_soccer_ids([PREMIER], NOW, getter)
        self.assertEqual(errors, [])
        self.assertEqual(mapping[PREMIER["id"]], "401222222")

    def test_pipeline_no_keys_no_false_quotes(self):
        def getter(_url):
            return {"events": []}
        def odds_reader(eid, league):
            self.assertEqual(eid, "401111111")
            self.assertEqual(league, "nba")
            return {"DraftKings": [{"kind": "result", "market": "Ganador",
                    "line": None, "label": "",
                    "selections": {"home": 1.8, "away": 2.1},
                    "updated_at": None}]}, []
        snap = build_snapshot({"fixtures": [NBA]}, NOW, getter, odds_reader)
        self.assertEqual(snap["diagnostics"]["requires_key"], False)
        self.assertEqual(len(snap["events"]), 1)
        self.assertEqual(snap["events"][0]["fixture_id"], NBA["id"])
        self.assertEqual(snap["diagnostics"]["books"]["DraftKings"], 1)
        self.assertNotIn("secret", str(snap))

if __name__ == "__main__":
    unittest.main()

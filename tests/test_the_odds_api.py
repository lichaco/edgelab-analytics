import json
import unittest
from datetime import datetime, timezone, timedelta

from scripts.build_the_odds_api import (
    choose_market, decimal, enrich_snapshot, match_fixture,
    merge_market_data, normalized_props, pick_event, team_key,
)


CLOCK = datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc)
FUTURE = (CLOCK + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
NBA = {"id": "nba777", "competitionId": "nba", "sport": "basket",
       "home": "Los Angeles Lakers", "away": "New York Knicks",
       "utc": FUTURE, "status": "pre"}
NHL = {"id": "nhl888", "competitionId": "nhl", "sport": "nhl",
       "home": "New Jersey Devils", "away": "Los Angeles Kings",
       "utc": FUTURE, "status": "pre"}


def event(fixture, id="provider-event-1"):
    return {"id": id, "home_team": fixture["home"], "away_team": fixture["away"],
            "commence_time": FUTURE}


def board_for(sport, market):
    return {"bookmakers": [
        {"key": "draftkings", "title": "DraftKings", "markets": [{
            "key": market, "last_update": "2026-10-24T13:54:00Z",
            "outcomes": [
                {"name": "Over", "description": "Player A", "point": 24.5, "price": 1.91},
                {"name": "Under", "description": "Player A", "point": 24.5, "price": 1.91},
                {"name": "Over", "description": "Player A", "point": 25.5, "price": 2.12},
                {"name": "Over", "description": "Player B", "point": 24.5, "price": 2.05},
            ]
        }]}
    ]}


class TestTheOddsAPI(unittest.TestCase):
    def test_name_aliases_and_fixture_match(self):
        self.assertEqual(team_key("LA Lakers"), team_key("Los Angeles Lakers"))
        e = event(NBA)
        e["home_team"] = "LA Lakers"
        e["away_team"] = "NY Knicks"
        self.assertEqual(match_fixture(e, [NBA, NHL], "nba", CLOCK)["id"], "nba777")
        self.assertIsNone(match_fixture(e, [NBA], "nhl", CLOCK))
        bad = {**e, "away_team": "Boston Celtics"}
        self.assertIsNone(match_fixture(bad, [NBA], "nba", CLOCK))

    def test_numeric_validation(self):
        self.assertIsNone(decimal(True))
        self.assertIsNone(decimal(0.9))
        self.assertIsNone(decimal(float("nan")))
        self.assertEqual(decimal(1.912345), 1.9123)

    def test_player_and_line_are_never_mixed(self):
        market = choose_market("basketball_nba", CLOCK)
        books = normalized_props(board_for("basketball_nba", market), "basketball_nba", market, CLOCK)
        self.assertEqual(list(books), ["DraftKings"])
        props = books["DraftKings"]
        self.assertEqual(len(props), 3)
        a = next(x for x in props if x["label"].startswith("Player A") and x["line"] == 24.5)
        self.assertEqual(a["selections"], {"over": 1.91, "under": 1.91})
        self.assertEqual(a["source"], "The Odds API")
        self.assertNotEqual(
            next(x for x in props if x["label"].startswith("Player B"))["label"], a["label"]
        )

    def test_merge_preserves_espn_markets(self):
        existing = {
            "fixture_id": NBA["id"], "competition_id": "nba", "sport": "basket",
            "home": NBA["home"], "away": NBA["away"], "utc": FUTURE,
            "books": {"DraftKings": [{
                "kind": "result", "line": None, "label": "",
                "selections": {"home": 1.9, "away": 2.0}
            }]}
        }
        snapshot = {"events": [existing]}
        market = choose_market("basketball_nba", CLOCK)
        books = normalized_props(board_for("basketball_nba", market), "basketball_nba", market, CLOCK)
        self.assertEqual(merge_market_data(snapshot, NBA, "odds-id", books), 3)
        self.assertEqual(merge_market_data(snapshot, NBA, "odds-id", books), 0)
        self.assertEqual(len(existing["books"]["DraftKings"]), 4)
        self.assertEqual(existing["books"]["DraftKings"][0]["kind"], "result")

    def test_skips_without_key_or_quota(self):
        snap = {"schema": 1, "events": [], "diagnostics": {}}
        calendar = {"fixtures": [NBA]}
        self.assertEqual(enrich_snapshot(snap, calendar, "", CLOCK)["diagnostics"]["the_odds_api"]["status"],
                         "not_configured")
        paths = []

        def no_credit(path, params, key):
            paths.append(path)
            if path.endswith("/events"):
                return [event(NBA)], 39, 0
            raise AssertionError("A paid request must not be made")

        output = enrich_snapshot(snap, calendar, "example-secret", CLOCK, getter=no_credit)
        self.assertEqual(output["diagnostics"]["the_odds_api"]["status"], "quota_reserved")
        self.assertTrue(all(p.endswith("/events") for p in paths))

    def test_one_billable_call_and_secret_not_published(self):
        snap = {"schema": 1, "generated_at": "2026-10-24T14:00:00Z",
                "events": [], "provider": "ESPN Core", "diagnostics": {"status": "empty"}}
        calendar = {"fixtures": [NBA]}
        requested = []
        chosen_market = choose_market("basketball_nba", CLOCK)

        def fake_get(path, params, key):
            self.assertEqual(key, "secret-not-publish")
            requested.append((path, params))
            if path == "basketball_nba/events":
                return [event(NBA)], 400, 0
            if path == "icehockey_nhl/events":
                return [], 400, 0
            self.assertEqual(path, "basketball_nba/events/provider-event-1/odds")
            self.assertEqual(params["markets"], chosen_market)
            self.assertEqual(params["regions"], "us")
            return board_for("basketball_nba", chosen_market), 399, 1

        result = enrich_snapshot(snap, calendar, "secret-not-publish", CLOCK, getter=fake_get)
        self.assertEqual(sum(x[0].endswith("/odds") for x in requested), 1)
        self.assertEqual(result["diagnostics"]["the_odds_api"]["props_added"], 3)
        self.assertEqual(result["diagnostics"]["the_odds_api"]["requests_charged"], 1)
        self.assertNotIn("secret-not-publish", json.dumps(result))
        self.assertEqual(result["events"][0]["fixture_id"], NBA["id"])

    def test_misordered_or_stale_game_not_matched(self):
        e = event(NBA)
        e["home_team"], e["away_team"] = e["away_team"], e["home_team"]
        self.assertIsNone(match_fixture(e, [NBA], "nba", CLOCK))
        old = {**event(NBA), "commence_time": "2026-10-23T17:00:00Z"}
        self.assertIsNone(match_fixture(old, [NBA], "nba", CLOCK))


if __name__ == "__main__":
    unittest.main()

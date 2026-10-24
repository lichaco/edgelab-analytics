import unittest
import json
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from scripts.build_dunkapi import (
    empty_cache, odds_candidates, prepare_public, profile_recent,
    estimated_prop, run, fixture_teams, DAY_MAX_CREDITS,
)

CLOCK = datetime(2026, 10, 24, 15, 37, tzinfo=timezone.utc)
STARTS = "2026-10-24T23:30:00Z"
LABEL = "Jalen Brunson (Puntos)"


def odds_snapshot():
    return {
        "events": [{
            "sport": "basket", "competition_id": "nba", "fixture_id": "espn-1",
            "home": "New York Knicks", "away": "Boston Celtics", "utc": STARTS,
            "books": {
                "DraftKings": [
                    {"kind": "prop", "label": LABEL, "line": 25.5,
                     "selections": {"over": 1.91, "under": 1.88},
                     "updated_at": "2026-10-24T15:32:00Z"},
                    {"kind": "prop", "label": "Jalen Brunson (Asistencias)", "line": 6.5,
                     "selections": {"over": 2.02}, "updated_at": "2026-10-24T15:32:00Z"},
                    {"kind": "prop", "label": "Wrong Player (Puntos)", "line": 33.5,
                     "selections": {"over": 1.80}, "updated_at": "2026-10-24T15:32:00Z"},
                ],
                "FanDuel": [{
                    "kind": "prop", "label": LABEL, "line": 26.5,
                    "selections": {"over": 2.09}, "updated_at": "2026-10-24T15:32:00Z"
                }]
            }
        }]
    }


def example_profile():
    return {
        "player": {"name": "Jalen Brunson", "player_id": "abc123", "team": "NYK"},
        "recent_games": [
            {"date": f"2026-10-{23-i:02}", "minutes": 32+i%3, "pts": 26+i%5,
             "reb": 3+i%3, "ast": 7+i%4}
            for i in range(9)
        ],
        "seasons": [{"season": 2027, "season_type": "regular", "games": 9}],
    }


class DunkAPITests(unittest.TestCase):
    def test_candidates_only_valid_overs(self):
        c = odds_candidates(odds_snapshot(), CLOCK)
        self.assertEqual(len(c), 1)
        self.assertEqual(len(c[0]["quotes"]), 3)
        self.assertEqual(c[0]["team_codes"], ["BOS", "NYK"])
        self.assertEqual(fixture_teams({"home": "LA Clippers", "away": "Utah Jazz"}), {"LAC", "UTA"})

    def test_sample_date_and_size(self):
        profile = example_profile()
        self.assertEqual(len(profile_recent(profile, datetime.fromisoformat(STARTS.replace("Z", "+00:00")), CLOCK)), 9)
        estimate = estimated_prop(profile, "Puntos", 25.5,
                                  datetime.fromisoformat(STARTS.replace("Z", "+00:00")), CLOCK)
        self.assertTrue(.02 < estimate["p"] < .98)
        self.assertEqual(estimate["sample_size"], 9)
        old = deepcopy(profile)
        for row in old["recent_games"]:
            row["date"] = "2026-04-17"
        self.assertIsNone(estimated_prop(old, "Puntos", 25.5,
                                         datetime.fromisoformat(STARTS.replace("Z", "+00:00")), CLOCK))
        too_short = deepcopy(profile)
        too_short["recent_games"] = too_short["recent_games"][:4]
        self.assertIsNone(estimated_prop(too_short, "Puntos", 25.5,
                                         datetime.fromisoformat(STARTS.replace("Z", "+00:00")), CLOCK))

    def test_one_daily_batch_and_no_keys_in_public_output(self):
        calls = []
        def fake(tool, payload, key):
            self.assertEqual(key, "secret-placeholder")
            calls.append(tool)
            if tool == "search_players":
                return {"players": [
                    {"name": "Jalen Brunson", "team": "NYK", "player_id": "abc123"},
                    {"name": "Jalen Brunson", "team": "SAC", "player_id": "wrong"}
                ]}, 489
            if tool == "get_player":
                return example_profile(), 484
            if tool == "get_injuries":
                return {"date": "2026-10-24", "injuries": []}, 482
            raise AssertionError("Unexpected endpoint")
        cache, public = run(odds_snapshot(), empty_cache(), "secret-placeholder", CLOCK, fake)
        self.assertEqual(calls, ["search_players", "get_player", "get_injuries"])
        self.assertEqual(public["diagnostics"]["credits_estimated_max"], 8)
        self.assertLessEqual(public["diagnostics"]["credits_estimated_max"], DAY_MAX_CREDITS)
        self.assertEqual(len(public["forecasts"]), 3)
        self.assertEqual(public["status"], "ok")
        self.assertNotIn("secret-placeholder", json.dumps(public))
        self.assertNotIn("recent_games", json.dumps(public))
        self.assertNotIn("player_id", json.dumps(public))
        self.assertFalse(public["forecasts"][0]["calibrated"])
        self.assertEqual(cache["credits_remaining"], 482)
        calls.clear()
        cache, second = run(odds_snapshot(), cache, "secret-placeholder", CLOCK, fake)
        self.assertEqual(calls, [])
        self.assertEqual(second["status"], "cached_today")

    def test_report_of_out_player_blocks_projection(self):
        cache = empty_cache()
        cache["profiles"]["jalen brunson"] = {
            "data": example_profile(), "fetched_at": "2026-10-24T15:34:00Z"
        }
        cache["injuries"] = {"date": "2026-10-24", "injuries": [
            {"player_id": "abc123", "status": "Out"}
        ]}
        forecasts = prepare_public(odds_snapshot(), cache, CLOCK)
        self.assertEqual(forecasts, [])

    def test_stale_quotes_and_stale_injury_report(self):
        cache = empty_cache()
        cache["profiles"]["jalen brunson"] = {
            "data": example_profile(), "fetched_at": "2026-10-24T15:34:00Z"
        }
        cache["injuries"] = {"date": "2026-10-10", "injuries": []}
        result = prepare_public(odds_snapshot(), cache, CLOCK)
        self.assertFalse(result[0]["injuries_fresh"])
        self.assertTrue(any("lesiones" in x for x in result[0]["warnings"]))
        stale = deepcopy(odds_snapshot())
        for market in stale["events"][0]["books"]["DraftKings"]:
            market["updated_at"] = "2026-10-23T01:00:00Z"
        stale["events"][0]["books"]["FanDuel"][0]["updated_at"] = "2026-10-23T01:00:00Z"
        self.assertEqual(prepare_public(stale, cache, CLOCK), [])

    def test_invalid_key_does_not_call_api(self):
        def reject(*_args):
            raise AssertionError("Unexpected call")
        _, snap = run(odds_snapshot(), empty_cache(), "", CLOCK, reject)
        self.assertEqual(snap["status"], "not_configured")
        _, snap = run(odds_snapshot(), empty_cache(), "some-secret", CLOCK + timedelta(hours=3), reject)
        self.assertEqual(snap["status"], "outside_refresh_window")
        empty_odds = {"events": []}
        _, snap = run(empty_odds, empty_cache(), "some-secret", CLOCK, reject)
        self.assertEqual(snap["status"], "no_prop_markets")


if __name__ == "__main__":
    unittest.main()

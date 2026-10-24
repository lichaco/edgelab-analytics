import json
import unittest
from datetime import datetime, timedelta, timezone

from scripts.build_nba_official import (
    empty_cache, schedule_games, parse_boxscore, minutes_value,
    odds_candidates, forecast_metrics, run, parse_date, NBA_CDN,
)

CLOCK = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
START = "2026-10-25T23:30:00Z"
BOOK = "DraftKings"


def odds_board():
    return {"schema": 1, "events": [{
        "fixture_id": "espn-nba-123", "sport": "basket", "competition_id": "nba",
        "home": "New York Knicks", "away": "Boston Celtics", "utc": START,
        "books": {BOOK: [
            {"kind": "prop", "label": "Jalen Brunson (Puntos)", "line": 25.5,
             "selections": {"over": 1.99, "under": 1.82},
             "updated_at": "2026-10-24T16:58:00Z"},
            {"kind": "prop", "label": "Jalen Brunson (Triples)", "line": 2.5,
             "selections": {"over": 2.15},
             "updated_at": "2026-10-24T16:58:00Z"},
            {"kind": "prop", "label": "Other Player (Puntos)", "line": 26.5,
             "selections": {"over": 1.80},
             "updated_at": "2026-10-24T16:58:00Z"},
        ]}
    }]}


def schedule():
    games = []
    for n in range(6):
        day = 20-n
        games.append({
            "gameId": f"00226000{n+1:02}",
            "gameStatus": 3, "gameDateTimeUTC": f"2026-10-{day:02}T02:00:00Z",
            "homeTeam": {"teamTricode": "NYK"}, "awayTeam": {"teamTricode": "BOS"}
        })
    return {"leagueSchedule": {"gameDates": [{"gameDate": "2026-10-20", "games": games}]}}


def boxscore(game):
    return {"game": {"gameId": game["id"], "gameStatus": 3,
                     "homeTeam": {"teamTricode": game["home"], "players": [
                         {"personId": 1628973, "name": "Jalen Brunson",
                          "statistics": {"minutes": "PT34M15.00S", "points": 26,
                                         "reboundsTotal": 4, "assists": 7, "threePointersMade": 3}},
                         {"personId": 999, "name": "DNP player", "statistics": {
                             "minutes": "PT0M0.00S", "points": 0, "reboundsTotal": 0,
                             "assists": 0, "threePointersMade": 0}}
                     ]}, "awayTeam": {"teamTricode": game["away"], "players": []}}}


class NBAOfficialTests(unittest.TestCase):
    def test_minutes_and_malformed(self):
        self.assertAlmostEqual(minutes_value({"minutes": "PT34M15.00S"}), 34.25)
        self.assertAlmostEqual(minutes_value({"minutes": "32:30"}), 32.5)
        self.assertEqual(minutes_value({"minutes": "PT0S"}), 0)
        self.assertIsNone(minutes_value({}))
        self.assertIsNone(minutes_value({"minutes": "PT85M"}))

    def test_schedule_filters_regular_final_and_future(self):
        s = schedule()
        game = s["leagueSchedule"]["gameDates"][0]["games"][0]
        future = dict(game, gameId="0022600099", gameDateTimeUTC="2026-10-27T01:00:00Z")
        preseason = dict(game, gameId="0012600998")
        in_progress = dict(game, gameId="0022600088", gameStatus=2)
        s["leagueSchedule"]["gameDates"][0]["games"].extend([future, preseason, in_progress])
        parsed = schedule_games(s, CLOCK)
        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0]["id"], "0022600001")
        with self.assertRaises(ValueError):
            schedule_games({"leagueSchedule": {"gameDates": "invalid"}}, CLOCK)

    def test_parse_boxscore_requires_final_and_correct_game_id(self):
        game = schedule_games(schedule(), CLOCK)[0]
        p = parse_boxscore(boxscore(game), game)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]["player_id"], "1628973")
        self.assertEqual(p[0]["stats"]["Triples"], 3)
        broken = boxscore(game)
        broken["game"]["gameStatus"] = 2
        with self.assertRaises(ValueError):
            parse_boxscore(broken, game)

    def test_odds_candidates_filter_only_real_market(self):
        candidates = odds_candidates(odds_board(), CLOCK)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(candidates[0]["markets"]), 2)
        self.assertEqual(candidates[0]["team_codes"], {"BOS", "NYK"})

    def test_forecasts_derived_without_raw_boxscores(self):
        seen = []
        def fake_get(path):
            seen.append(path)
            if path.startswith("staticData/"):
                return schedule()
            if path.startswith("liveData/boxscore/"):
                gid = path.removeprefix("liveData/boxscore/boxscore_").removesuffix(".json")
                game = next(x for x in schedule_games(schedule(), CLOCK) if x["id"] == gid)
                return boxscore(game)
            raise AssertionError("Unexpected endpoint")
        cache, snapshot = run(odds_board(), empty_cache(), CLOCK, getter=fake_get)
        self.assertEqual(snapshot["diagnostics"]["status"], "ok")
        self.assertEqual(snapshot["diagnostics"]["boxscores_new"], 6)
        self.assertEqual(len(snapshot["forecasts"]), 2)
        p = snapshot["forecasts"][0]
        self.assertEqual(p["sample_size"], 6)
        self.assertEqual(p["source"], "NBA Official CDN")
        self.assertFalse(p["calibrated"])
        text = json.dumps(snapshot)
        self.assertNotIn("personId", text)
        self.assertNotIn("1628973", text)
        self.assertNotIn("recent_games", text)
        seen.clear()
        _, again = run(odds_board(), cache, CLOCK + timedelta(hours=1), getter=fake_get)
        self.assertEqual(again["diagnostics"]["boxscores_cached"], 6)
        self.assertEqual(seen, [])

    def test_failed_official_source_is_diagnostic_not_fake(self):
        def deny(_path):
            raise PermissionError("403")
        _, snap = run(odds_board(), empty_cache(), CLOCK, getter=deny)
        self.assertEqual(snap["diagnostics"]["status"], "nba_cdn_unavailable")
        self.assertEqual(snap["forecasts"], [])
        self.assertNotIn("403", json.dumps(snap))

    def test_early_season_without_five_games_no_model(self):
        small = schedule()
        small["leagueSchedule"]["gameDates"][0]["games"] = small["leagueSchedule"]["gameDates"][0]["games"][:3]
        def fake_get(path):
            if path.startswith("staticData/"):
                return small
            gid = path.removeprefix("liveData/boxscore/boxscore_").removesuffix(".json")
            game = next(g for g in schedule_games(small, CLOCK) if g["id"] == gid)
            return boxscore(game)
        _, snap = run(odds_board(), empty_cache(), CLOCK, getter=fake_get)
        self.assertEqual(snap["diagnostics"]["status"], "insufficient_sample")
        self.assertEqual(snap["forecasts"], [])

    def test_outside_window_has_no_network(self):
        _, snap = run({"events": []}, empty_cache(), CLOCK, getter=lambda _p: 1/0)
        self.assertEqual(snap["diagnostics"]["status"], "no_prop_markets")


if __name__ == "__main__":
    unittest.main()

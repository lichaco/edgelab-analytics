"""Tests unitarios sin conexión a Odds-API.io ni secretos."""
import unittest
from datetime import datetime, timezone
from scripts.build_odds import (
    normalized_markets, match_event, build_snapshot, norm, price, parse_time,
)

CLOCK = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
FIXTURE = {
    'id': 'match-1', 'competitionId': 'eng.1', 'sport': 'football',
    'home': 'Arsenal FC', 'away': 'Liverpool FC',
    'utc': '2026-10-28T20:00:00Z'
}

class OddsTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(norm('Atlético de Madrid'), 'atletico madrid')
        self.assertEqual(norm('Atletico Madrid'), 'atletico madrid')
        self.assertEqual(price('1.91'), 1.91)
        self.assertIsNone(price('mal dato'))
        self.assertIsNone(price(0.9))
        self.assertIsNone(parse_time('sin hora'))

    def test_event_matching(self):
        e = {'date': '2026-10-28T20:00:00Z', 'home': 'Arsenal', 'away': 'Liverpool'}
        self.assertEqual(match_event(e, [FIXTURE])['id'], 'match-1')
        e['away'] = 'Manchester City'
        self.assertIsNone(match_event(e, [FIXTURE]))
        e['away'] = 'Liverpool'
        e['date'] = '2026-10-29T22:00:00Z'
        self.assertIsNone(match_event(e, [FIXTURE]))

    def test_quotes_no_invention(self):
        m = normalized_markets({
            'name': 'ML', 'odds': [{'home': '1.88', 'draw': '3.6', 'away': '4.1'}]
        }, 'football')
        self.assertEqual(m[0]['kind'], 'result')
        self.assertEqual(m[0]['selections']['draw'], 3.6)
        self.assertEqual(m[0]['line'], None)
        self.assertEqual(normalized_markets({'name': 'Player Props', 'odds': [{'hdp': 25.5, 'label': 'J. Doe (Points)', 'over': '1.9'}]}, 'basket')[0]['kind'], 'prop')
        self.assertEqual(normalized_markets({'name': 'Mystery', 'odds': [{'over': '2.0'}]}, 'football'), [])

    def test_without_key(self):
        snap = build_snapshot({'fixtures': [FIXTURE]}, '', clock=CLOCK)
        self.assertEqual(snap['diagnostics']['status'], 'not_configured')
        self.assertEqual(snap['events'], [])
        self.assertNotIn('apiKey', str(snap))

    def test_full_pipeline_mock(self):
        event = {'id': 333, 'home': 'Arsenal', 'away': 'Liverpool',
                 'date': '2026-10-28T20:00:00Z'}
        calls = []
        def fake_getter(path, params):
            calls.append(path)
            if path == '/events':
                return [event]
            return [{'id': 333, 'bookmakers': {
                'Betano': [{'name': 'ML', 'updatedAt': '2026-10-24T18:00:00Z',
                           'odds': [{'home': '2.2', 'draw': '3.3', 'away': '3.4'}]}],
                'DraftKings': [{'name': 'Totals', 'odds': [
                           {'hdp': 2.5, 'over': '1.95', 'under': '1.89'}]}]
            }}]
        snap = build_snapshot({'fixtures': [FIXTURE]}, 'test-secret', getter=fake_getter, clock=CLOCK)
        self.assertEqual(len(snap['events']), 1)
        self.assertEqual(snap['events'][0]['fixture_id'], 'match-1')
        self.assertEqual(snap['events'][0]['books']['Betano'][0]['selections']['home'], 2.2)
        self.assertEqual(snap['events'][0]['books']['DraftKings'][0]['line'], 2.5)
        self.assertEqual(snap['diagnostics']['requests'], 3)
        self.assertNotIn('test-secret', str(snap))

if __name__ == '__main__':
    unittest.main()

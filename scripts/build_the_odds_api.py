#!/usr/bin/env python3
"""The Odds API v4 -> EdgeLab odds.json (NBA/NHL player props, no secrets published).

Run after build_calendar.py and build_public_odds.py. The free /events endpoints
are used for discovery; a maximum of ONE one-market, one-region event-odds
request is made per run (at most 1 credit). ESPN odds are preserved.
"""
from __future__ import annotations

import difflib
import json
import math
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "assets" / "data" / "calendar.json"
ODDS = ROOT / "assets" / "data" / "odds.json"
HOST = "https://api.the-odds-api.com/v4/sports"
SOURCE = "The Odds API"
SPORTS = {
    "basketball_nba": ("nba", "basket", ("player_points", "player_rebounds", "player_assists", "player_threes")),
    "icehockey_nhl": ("nhl", "nhl", ("player_shots_on_goal", "player_points")),
}
MARKET_NAMES = {
    ("basketball_nba", "player_points"): "Puntos",
    ("basketball_nba", "player_rebounds"): "Rebotes",
    ("basketball_nba", "player_assists"): "Asistencias",
    ("basketball_nba", "player_threes"): "Triples",
    ("icehockey_nhl", "player_shots_on_goal"): "Tiros a portería",
    ("icehockey_nhl", "player_points"): "Puntos NHL",
}
BOOK_PRIORITY = ("draftkings", "fanduel", "betmgm", "caesars", "betrivers", "bet365")
MAX_BOOKS = 5
MAX_MARKETS_PER_BOOK = 140
MIN_CREDITS_RESERVE = 40
MAX_EVENT_HOURS = 20


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None


def api_get(path, params, key, timeout=14):
    """Return (JSON, remaining, last_cost). Do NOT log the URL: it contains the key."""
    url = f"{HOST}/{path.lstrip('/')}?" + urlencode({**params, "apiKey": key})
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "EdgeLabAnalytics/0.8 (https://github.com/lichaco/edgelab-analytics)",
    })
    with urlopen(req, timeout=timeout) as response:
        payload = json.load(response)
        remaining = response.headers.get("x-requests-remaining")
        last = response.headers.get("x-requests-last")
    return payload, (int(remaining) if remaining and remaining.isdecimal() else None), (
        int(last) if last and last.isdecimal() else None
    )


def team_key(name):
    if not isinstance(name, str):
        return ""
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    value = re.sub(r"\b(?:fc|cf|the)\b", "", value)
    value = " ".join(value.split())
    value = value.replace("los angeles", "la").replace("l a ", "la ")
    value = value.replace("new york", "ny").replace("new jersey", "nj")
    return value


def name_score(a, b):
    a, b = team_key(a), team_key(b)
    if not a or not b:
        return 0.0
    return 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()


def match_fixture(event, fixtures, competition, clock):
    event_time = parse_time(event.get("commence_time"))
    if not event_time or not (clock < event_time <= clock + timedelta(hours=MAX_EVENT_HOURS)):
        return None
    home, away = event.get("home_team"), event.get("away_team")
    if not isinstance(home, str) or not isinstance(away, str):
        return None
    matches = []
    for f in fixtures:
        if f.get("competitionId") != competition or f.get("status") != "pre":
            continue
        kickoff = parse_time(f.get("utc"))
        if not kickoff or abs((kickoff - event_time).total_seconds()) > 3 * 3600:
            continue
        h = name_score(home, f.get("home"))
        a = name_score(away, f.get("away"))
        if min(h, a) < .79 or (h + a) / 2 < .88:
            continue
        score = (h + a) / 2 - abs((kickoff - event_time).total_seconds()) / (3 * 3600) * .08
        matches.append((score, f))
    matches.sort(key=lambda row: -row[0])
    if not matches or (len(matches) > 1 and matches[0][0] - matches[1][0] < .07):
        return None
    return matches[0][1]


def pick_event(event_groups, fixtures, clock):
    """Match only known fixtures; rotate preference for NBA/NHL coverage."""
    round_index = int(clock.timestamp() // (3 * 3600))
    preferred = ("basketball_nba", "basketball_nba", "icehockey_nhl")[round_index % 3]
    options = []
    for sport, games in event_groups.items():
        league = SPORTS[sport][0]
        for event in games if isinstance(games, list) else []:
            if not isinstance(event, dict) or not isinstance(event.get("id"), str):
                continue
            fixture = match_fixture(event, fixtures, league, clock)
            if not fixture:
                continue
            remaining = (parse_time(event["commence_time"]) - clock).total_seconds() / 3600
            # Modest preference for the rotating sport without picking distant games.
            priority = remaining + (0 if sport == preferred else 3)
            options.append((priority, sport, event, fixture))
    options.sort(key=lambda row: row[0])
    return options[0][1:] if options else None


def choose_market(sport, clock):
    keys = SPORTS[sport][2]
    return keys[int(clock.timestamp() // (3 * 3600)) % len(keys)]


def decimal(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 4) if math.isfinite(value) and 1.001 < value <= 100 else None


def line_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) and 0 <= v <= 200 else None


def normalized_props(board, sport, key, clock):
    """Normalize same-player, same-market, same-line outcome pairs."""
    if not isinstance(board, dict) or not isinstance(board.get("bookmakers"), list):
        return {}
    selected = []
    for book in board["bookmakers"]:
        if not isinstance(book, dict) or not isinstance(book.get("markets"), list):
            continue
        book_id, title = book.get("key"), book.get("title")
        if not isinstance(book_id, str) or not isinstance(title, str) or not title.strip():
            continue
        groups = {}
        for market in book["markets"]:
            if not isinstance(market, dict) or market.get("key") != key:
                continue
            updated_at = market.get("last_update") or book.get("last_update")
            dt = parse_time(updated_at)
            if dt is not None and dt > clock + timedelta(minutes=5):
                continue
            for outcome in market.get("outcomes", []):
                if not isinstance(outcome, dict) or outcome.get("name") not in ("Over", "Under"):
                    continue
                player = outcome.get("description")
                point = line_number(outcome.get("point"))
                price = decimal(outcome.get("price"))
                if not isinstance(player, str) or not player.strip() or len(player) > 80:
                    continue
                if point is None or price is None:
                    continue
                label = f"{player.strip()} ({MARKET_NAMES[(sport, key)]})"
                group_key = (label, point)
                row = groups.setdefault(group_key, {
                    "kind": "prop", "market": MARKET_NAMES[(sport, key)],
                    "label": label, "line": point, "selections": {},
                    "source": SOURCE, "updated_at": iso(dt) if dt is not None else iso(clock),
                })
                row["selections"][outcome["name"].lower()] = price
        if groups:
            # Prioritize an Over whose decimal price passes the user's >1.80 filter,
            # but keep Under solely as a complementary price for no-vig comparisons.
            props = sorted(groups.values(), key=lambda row: (
                row["selections"].get("over", 0) <= 1.80,
                row["label"], row["line"]
            ))[:MAX_MARKETS_PER_BOOK]
            selected.append((book_id.lower(), title.strip()[:65], props))
    selected.sort(key=lambda b: (BOOK_PRIORITY.index(b[0]) if b[0] in BOOK_PRIORITY else 99, b[1]))
    return {title: markets for _, title, markets in selected[:MAX_BOOKS]}


def merge_market_data(snapshot, fixture, event_id, books):
    """Append distinct markets to the ESPN event; do not overwrite ESPN prices."""
    if not books:
        return 0
    event = next((e for e in snapshot["events"] if
                  e.get("fixture_id") == fixture["id"] and e.get("competition_id") == fixture["competitionId"]), None)
    if event is None:
        event = {
            "fixture_id": fixture["id"], "competition_id": fixture["competitionId"],
            "sport": fixture["sport"], "home": fixture["home"], "away": fixture["away"],
            "utc": fixture["utc"], "books": {}, "source": SOURCE,
        }
        snapshot["events"].append(event)
    event["the_odds_api_event_id"] = event_id
    count = 0
    for book, incoming in books.items():
        existing = event["books"].setdefault(book, [])
        identifiers = {(m.get("kind"), m.get("label"), m.get("line")) for m in existing}
        for market in incoming:
            identifier = (market["kind"], market["label"], market["line"])
            if identifier not in identifiers:
                existing.append(market)
                identifiers.add(identifier)
                count += 1
    snapshot["events"].sort(key=lambda e: e["utc"])
    return count


def enrich_snapshot(snapshot, calendar, key, clock=None, getter=api_get):
    """Public output never contains the API key, request URLs, or raw error messages."""
    clock = clock or now_utc()
    diagnostics = snapshot.setdefault("diagnostics", {})
    ds = {"status": "not_configured", "provider": SOURCE,
          "requests_charged": 0, "props_added": 0, "events_matched": 0,
          "remaining_credits": None, "market": None, "sport": None, "errors": []}
    diagnostics["the_odds_api"] = ds
    if not key:
        return snapshot
    fixtures = calendar.get("fixtures", [])
    if not isinstance(fixtures, list):
        ds["status"] = "invalid_calendar"
        return snapshot
    groups = {}
    remaining_values = []
    for sport in SPORTS:
        try:
            data, remaining, _ = getter(f"{sport}/events", {"dateFormat": "iso"}, key)
        except Exception as exc:
            ds["errors"].append(sport + ": " + type(exc).__name__)
            continue
        groups[sport] = data if isinstance(data, list) else []
        if remaining is not None:
            remaining_values.append(remaining)
    if not groups:
        ds["status"] = "source_unavailable"
        return snapshot
    if remaining_values:
        ds["remaining_credits"] = min(remaining_values)
    # The API must report credits remaining before we permit a chargeable call.
    if ds["remaining_credits"] is None:
        ds["status"] = "quota_unknown"
        return snapshot
    if ds["remaining_credits"] <= MIN_CREDITS_RESERVE + 1:
        ds["status"] = "quota_reserved"
        return snapshot
    selected = pick_event(groups, fixtures, clock)
    if not selected:
        ds["status"] = "no_matched_upcoming_event"
        return snapshot
    sport, event, fixture = selected
    ds["sport"] = sport
    ds["events_matched"] = 1
    market = choose_market(sport, clock)
    ds["market"] = market
    event_id = event["id"]
    # One market, one region, ONE paid call maximum per build.
    try:
        board, remaining, cost = getter(
            f"{sport}/events/{event_id}/odds",
            {"regions": "us", "markets": market, "oddsFormat": "decimal",
             "dateFormat": "iso"}, key
        )
    except Exception as exc:
        ds["status"] = "request_failed"
        ds["errors"].append(type(exc).__name__)
        return snapshot
    if remaining is not None:
        ds["remaining_credits"] = remaining
    if cost is not None:
        ds["requests_charged"] = cost
    books = normalized_props(board, sport, market, clock)
    ds["props_added"] = merge_market_data(snapshot, fixture, event_id, books)
    ds["status"] = "ok" if ds["props_added"] else "market_not_available"
    if ds["props_added"]:
        snapshot["provider"] = "ESPN Core + The Odds API"
        snapshot["note"] = ("Cuotas prepartido indicativas: ESPN Core y The Odds API. "
                            "Player props sujetos a disponibilidad y cambio de precios.")
    return snapshot


def main():
    if not CALENDAR.exists() or not ODDS.exists():
        raise SystemExit("Construye calendar.json y odds.json de ESPN primero.")
    calendar = json.loads(CALENDAR.read_text(encoding="utf-8"))
    snapshot = json.loads(ODDS.read_text(encoding="utf-8"))
    if snapshot.get("schema") != 1 or not isinstance(snapshot.get("events"), list):
        raise SystemExit("Formato odds.json inválido; no se publicarán cuotas.")
    key = os.environ.get("THE_ODDS_API_KEY", "").strip()
    enrich_snapshot(snapshot, calendar, key)
    ODDS.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    d = snapshot["diagnostics"]["the_odds_api"]
    print("THE ODDS API:", d["status"], "| market:", d["market"], "| new props:", d["props_added"],
          "| credits charged:", d["requests_charged"], "| remaining:", d["remaining_credits"],
          "| errors:", len(d["errors"]))


if __name__ == "__main__":
    main()

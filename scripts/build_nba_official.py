#!/usr/bin/env python3
"""NBA-owned CDN schedule + final boxscores -> derived player-prop probabilities.

Uses public NBA-owned endpoints (NOT a licensed or guaranteed public API).
No API keys, no scraping around access controls. If the NBA returns 403 or
times out, emit explicit diagnostics and let the preexisting DunkAPI fallback
run independently. Never invent stats or substitute bookmaker probabilities.

Published output contains projections only. Raw official schedule/boxscores
remain in a private GitHub Actions cache, not on GitHub Pages.
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ODDS_PATH = ROOT / "assets" / "data" / "odds.json"
OUT = ROOT / "assets" / "data" / "nba_official_predictions.json"
CACHE = ROOT / ".edgelab-cache" / "nba-official-private.json"
NBA_CDN = "https://cdn.nba.com/static/json"
SCHEDULE_PATHS = (
    "staticData/scheduleLeagueV2_1.json",
    "staticData/scheduleLeagueV2.json",
)
BOXSCORE_PREFIX = "liveData/boxscore/boxscore_"
SOURCE_URL = "https://www.nba.com/stats"
FIELDS = {
    "Puntos": "points", "Rebotes": "reboundsTotal",
    "Asistencias": "assists", "Triples": "threePointersMade",
}
SD_FLOORS = {"Puntos": 5.5, "Rebotes": 2.2, "Asistencias": 1.8, "Triples": 1.15}
# Deliberately conservative to avoid hammering NBA's undocumented feeds.
MAX_BOX_REQUESTS = 24
MAX_HISTORY_DAYS = 75
MIN_GAMES = 5
MAX_PLAYERS = 12
MAX_CACHE_GAMES = 150
MAX_BOX_AGE_HOURS = 96
SCHEDULE_AGE_HOURS = 8


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def normalized(name):
    if not isinstance(name, str):
        return ""
    # Accents and punctuation removed; do not use fuzzy names for statistical identity.
    raw = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", raw))


def get_json(path, timeout=12):
    if not path.startswith(("staticData/", "liveData/boxscore/")):
        raise ValueError("NBA path not allowed")
    req = Request(f"{NBA_CDN}/{path}", headers={
        "Accept": "application/json",
        "User-Agent": "EdgeLabAnalytics/1.0 (+https://github.com/lichaco/edgelab-analytics)",
    })
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("NBA response not OK")
        return json.load(response)


def empty_cache():
    return {"schema": 1, "schedule": None, "schedule_at": None, "boxscores": {}}


def load_cache(path=CACHE):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if d.get("schema") == 1 and isinstance(d.get("boxscores"), dict) else empty_cache()
    except (OSError, ValueError, TypeError, AttributeError):
        return empty_cache()


def save_cache(cache, path=CACHE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def schedule_games(payload, now):
    """Get played, regular season games with canonical 10-digit NBA IDs."""
    league = payload.get("leagueSchedule") if isinstance(payload, dict) else None
    if not isinstance(league, dict) or not isinstance(league.get("gameDates"), list):
        raise ValueError("NBA schedule invalid")
    games = []
    for block in league["gameDates"]:
        if not isinstance(block, dict) or not isinstance(block.get("games"), list):
            continue
        for g in block["games"]:
            if not isinstance(g, dict) or g.get("gameStatus") != 3:
                continue
            gid = str(g.get("gameId", ""))
            # 002... official NBA regular-season game; exclude summer/preseason/All-Star.
            if not re.fullmatch(r"002\d{7}", gid):
                continue
            team_a = (g.get("homeTeam") or {}).get("teamTricode")
            team_b = (g.get("awayTeam") or {}).get("teamTricode")
            if not all(isinstance(t, str) and re.fullmatch(r"[A-Z]{3}", t) for t in (team_a, team_b)):
                continue
            date_str = g.get("gameDateTimeUTC") or g.get("gameDateUTC") or block.get("gameDate")
            when = parse_date(date_str)
            if when is None or when >= now or (now - when).days > MAX_HISTORY_DAYS:
                continue
            games.append({"id": gid, "date": when.date().isoformat(),
                          "home": team_a, "away": team_b})
    return sorted({g["id"]: g for g in games}.values(), key=lambda x: (x["date"], x["id"]), reverse=True)


def minutes_value(stats):
    """Parse boxscore minutes, often ISO 'PT34M08.00S', sometimes '34:08'."""
    if not isinstance(stats, dict):
        return None
    for key in ("minutes", "minutesCalculated"):
        val = stats.get(key)
        if isinstance(val, (float, int)) and not isinstance(val, bool):
            if 0 <= val <= 65:
                return float(val)
        if not isinstance(val, str):
            continue
        match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", val)
        if match and any(x is not None for x in match.groups()):
            h, m, s = match.groups()
            minutes = 60*float(h or 0)+float(m or 0)+float(s or 0)/60
            if minutes <= 65:
                return minutes
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", val)
        if match:
            minutes = float(match.group(1)) + float(match.group(2))/60
            if minutes <= 65:
                return minutes
    return None


def parse_boxscore(payload, game):
    """Extract final box score only; avoid in-game player samples and DNP rows."""
    entry = payload.get("game") if isinstance(payload, dict) else None
    if not isinstance(entry, dict) or str(entry.get("gameId")) != game["id"] or entry.get("gameStatus") != 3:
        raise ValueError("NBA boxscore is incomplete or unmatched")
    output = []
    for location, tricode in (("homeTeam", game["home"]), ("awayTeam", game["away"])):
        team = entry.get(location) or {}
        if team.get("teamTricode") != tricode or not isinstance(team.get("players"), list):
            raise ValueError("NBA boxscore team mismatch")
        for p in team["players"]:
            if not isinstance(p, dict):
                continue
            stats = p.get("statistics") or {}
            minutes = minutes_value(stats)
            if minutes is None or minutes < 12 or minutes > 65:
                continue
            name = p.get("name")
            if not isinstance(name, str) or not name.strip():
                a, b = p.get("firstName"), p.get("familyName")
                name = f"{a} {b}".strip() if isinstance(a, str) and isinstance(b, str) else None
            if not isinstance(name, str) or not normalized(name):
                continue
            pid = p.get("personId")
            if not isinstance(pid, (int, str)) or not str(pid).isdigit():
                continue
            data = {}
            if any(not isinstance(stats.get(v), (int, float)) or isinstance(stats[v], bool) or stats[v] < 0
                   for v in FIELDS.values()):
                continue
            for key, official in FIELDS.items():
                data[key] = float(stats[official])
            output.append({"player_id": str(pid), "name": name, "team": tricode,
                           "date": game["date"], "minutes": round(minutes, 3),
                           "game_id": game["id"], "stats": data})
    return output


def odds_candidates(odds, clock):
    """Find real >1.80 NBA overs without confusing similarly-named markets."""
    result = {}
    for event in odds.get("events", []):
        if not isinstance(event, dict) or event.get("sport") != "basket" or event.get("competition_id") != "nba":
            continue
        when = parse_date(event.get("utc"))
        if when is None or when <= clock:
            continue
        # Official IDs are resolved by team names using local team-code dictionary.
        try:
            from .build_dunkapi import TEAM_CODES
        except ImportError:
            from build_dunkapi import TEAM_CODES
        home = TEAM_CODES.get(normalized(event.get("home")))
        away = TEAM_CODES.get(normalized(event.get("away")))
        if not home or not away or home == away:
            continue
        for book, markets in (event.get("books") or {}).items():
            if not isinstance(markets, list):
                continue
            for market in markets:
                if not isinstance(market, dict) or market.get("kind") != "prop":
                    continue
                match = re.fullmatch(r"(.+?) \((Puntos|Rebotes|Asistencias|Triples)\)", market.get("label", ""))
                if not match:
                    continue
                point = market.get("line")
                if not isinstance(point, (int, float)) or isinstance(point, bool) or not math.isfinite(point):
                    continue
                if point < 0 or abs(point - math.floor(point) - .5) > 1e-8:
                    continue
                quote = (market.get("selections") or {}).get("over")
                if not isinstance(quote, (int, float)) or isinstance(quote, bool) or not math.isfinite(quote) or quote <= 1.80:
                    continue
                stamp_val = parse_date(market.get("updated_at"))
                if stamp_val is None or not (0 <= (clock-stamp_val).total_seconds() <= 8*3600):
                    continue
                name, metric = match.groups()
                key = (event["fixture_id"], normalized(name))
                item = result.setdefault(key, {"player_name": name, "name_key": normalized(name),
                    "fixture_id": event["fixture_id"], "utc": event["utc"],
                    "team_codes": {home, away}, "markets": []})
                item["markets"].append({
                    "label": market["label"], "kind": metric, "line": float(point),
                    "book": book, "price": float(quote), "updated_at": market.get("updated_at")
                })
    return sorted(result.values(), key=lambda c: (c["utc"], -len(c["markets"]), c["player_name"]))[:MAX_PLAYERS]


def forecast_metrics(history, kind, line, clock):
    """Return experimental normal model, never a bookmaker-derived probability."""
    rows = sorted(history, key=lambda x: x["date"], reverse=True)[:10]
    if len(rows) < MIN_GAMES:
        return None
    samples = [r["stats"][kind] for r in rows]
    minutes = [r["minutes"] for r in rows]
    w = [.88**i for i in range(len(rows))]
    mean = sum(x*weight for x, weight in zip(samples, w))/sum(w)
    sd = max(statistics.stdev(samples), SD_FLOORS[kind])
    baseline = statistics.mean(minutes)
    recent = statistics.mean(minutes[:min(5, len(minutes))])
    if baseline < 12 or recent < 12:
        return None
    expected = max(.85, min(1.15, recent/baseline))
    mean *= expected
    # half-point integer counts -> P(X > line) ~= 1-Phi((line-mean)/sd).
    p = .5*math.erfc((line-mean)/(sd*math.sqrt(2)))
    return {"p": round(max(.025, min(.975, p)), 5),
            "projected_mean": round(mean, 2), "sd": round(sd, 2),
            "minutes_reference": round(recent, 1), "sample_size": len(rows),
            "last_game": rows[0]["date"]}


def assemble_predictions(candidates, games, cache, clock):
    """Require unique player identity (NBA personId) matching one of the two teams."""
    games_by_id = {g["id"]: g for g in games}
    out = []
    for c in candidates:
        start = parse_date(c["utc"])
        if start is None:
            continue
        target = c["name_key"]
        samples = []
        ids = set()
        for gid, value in cache.get("boxscores", {}).items():
            g = games_by_id.get(gid)
            if not g or g["date"] >= start.date().isoformat() or not {g["home"],g["away"]}.intersection(c["team_codes"]):
                continue
            for player in value.get("players", []):
                if player.get("team") in c["team_codes"] and normalized(player.get("name")) == target:
                    ids.add(player.get("player_id"))
                    samples.append(player)
        if len(ids) != 1:
            continue
        samples = [r for r in samples if r["player_id"] in ids]
        # Avoid double-counting duplicate/cached game rows.
        uniq = {r["game_id"]: r for r in samples}
        history = sorted(uniq.values(), key=lambda x: (x["date"], x["game_id"]), reverse=True)[:10]
        if not history:
            continue
        for market in c["markets"]:
            result = forecast_metrics(history, market["kind"], market["line"], clock)
            if result is None:
                continue
            out.append({
                "fixture_id": c["fixture_id"], "player": c["player_name"],
                "market_label": market["label"], "market_line": market["line"],
                "book": market["book"], "quote": market["price"],
                "quote_updated_at": market["updated_at"], "market": market["kind"],
                **result,
                "injury_status": None, "injuries_fresh": False,
                "warnings": [
                    "Estadísticas de box scores NBA; modelo NO calibrado.",
                    "No se dispone de reporte de lesiones NBA validado automáticamente.",
                    "Minutos inferidos de juegos recientes; rotaciones y blowout no cuantificados.",
                ],
                "source": "NBA Official CDN",
                "source_url": "https://cdn.nba.com/static/json/liveData/boxscore/",
                "stats_checked_at": iso(clock), "model": "official-nba-recent10-normal-v1",
                "calibrated": False,
            })
    return out


def fetch_schedule(cache, clock, getter):
    old = cache.get("schedule")
    at = parse_date(cache.get("schedule_at"))
    # If NBA rejects requests, cached schedule older than 8h is diagnostic only:
    # NEVER create a fresh prediction based on stale schedule after a known failure.
    if isinstance(old, dict) and at is not None and 0 <= (clock-at).total_seconds() < SCHEDULE_AGE_HOURS*3600:
        return schedule_games(old, clock), "cached"
    for path in SCHEDULE_PATHS:
        try:
            payload = getter(path)
            games = schedule_games(payload, clock)
            cache["schedule"], cache["schedule_at"] = payload, iso(clock)
            return games, path
        except Exception:
            continue
    return None, None


def run(odds, cache, clock=None, getter=get_json):
    clock = clock or utcnow()
    cache = cache if isinstance(cache, dict) and cache.get("schema") == 1 else empty_cache()
    ds = {"status": "no_prop_markets", "candidate_players": 0, "boxscores_new": 0,
          "boxscores_cached": 0, "games_considered": 0, "schedule_source": None,
          "errors": [], "source": "NBA CDN"}
    output = {"schema": 1, "generated_at": iso(clock), "source": "NBA Official CDN",
              "forecasts": [], "diagnostics": ds,
              "note": "Solo proyecciones derivadas; estadísticas oficiales desde NBA CDN si disponible. "
                      "Modelo exploratorio no calibrado y sin verificación de lesiones."}
    candidates = odds_candidates(odds, clock)
    ds["candidate_players"] = len(candidates)
    if not candidates:
        return cache, output
    games, used = fetch_schedule(cache, clock, getter)
    if games is None:
        ds["status"] = "nba_cdn_unavailable"
        ds["errors"].append("El proveedor NBA rechazó o no respondió; se conserva DunkAPI si está activo.")
        return cache, output
    ds["schedule_source"] = used
    want_teams = set().union(*(c["team_codes"] for c in candidates))
    relevant = [g for g in games if g["home"] in want_teams or g["away"] in want_teams]
    ds["games_considered"] = len(relevant)
    if not relevant:
        ds["status"] = "no_final_games"
        return cache, output
    boxscores = cache.setdefault("boxscores", {})
    # Prefer matches close to upcoming events. Immutable final-game boxes may be cached.
    requests = 0
    for game in relevant:
        gid = game["id"]
        saved = boxscores.get(gid)
        if isinstance(saved, dict) and saved.get("players") is not None:
            ds["boxscores_cached"] += 1
            continue
        if requests >= MAX_BOX_REQUESTS:
            break
        requests += 1
        try:
            box = getter(BOXSCORE_PREFIX + gid + ".json")
            players = parse_boxscore(box, game)
            boxscores[gid] = {"players": players, "cached_at": iso(clock)}
            ds["boxscores_new"] += 1
        except Exception as exc:
            # Respect 403/access denial: don't repeatedly hammer the CDN.
            ds["errors"].append("boxscore:" + type(exc).__name__)
            if type(exc).__name__ in ("HTTPError", "TimeoutError"):
                break
    # Trim old cache. Historical raw data is never copied into _site.
    keep = {g["id"] for g in games[:MAX_CACHE_GAMES]}
    for key in list(boxscores):
        if key not in keep:
            del boxscores[key]
    output["forecasts"] = assemble_predictions(candidates, games, cache, clock)
    ds["status"] = ("ok" if output["forecasts"] else
                    "insufficient_sample" if ds["boxscores_new"] or ds["boxscores_cached"] else
                    "nba_cdn_unavailable")
    if ds["status"] == "insufficient_sample":
        ds["errors"].append("Sin al menos cinco box scores oficiales comparables por jugador.")
    return cache, output


def main():
    if not ODDS_PATH.exists():
        raise SystemExit("Primero generar odds.json.")
    odds = json.loads(ODDS_PATH.read_text(encoding="utf-8"))
    cache, snapshot = run(odds, load_cache())
    save_cache(cache)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    d = snapshot["diagnostics"]
    print("NBA OFFICIAL:", d["status"], "| candidates:", d["candidate_players"],
          "| new boxes:", d["boxscores_new"], "| cached boxes:", d["boxscores_cached"],
          "| forecasts:", len(snapshot["forecasts"]), "| errors:", len(d["errors"]))


if __name__ == "__main__":
    main()

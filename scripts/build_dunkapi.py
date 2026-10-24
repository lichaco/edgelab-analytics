#!/usr/bin/env python3
"""DunkAPI -> derived NBA prop forecasts for EdgeLab.

Never publish raw DunkAPI records, game logs, key or a reusable data feed.
Use existing The Odds API / ESPN fixture and prop lines as the input universe.
Cache provider responses in .edgelab-cache/ (GitHub Actions cache, not Pages).
A free account has 500 monthly credits: at most two new players and one
injury report per day, during a single UTC scheduling window.
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ODDS_PATH = ROOT / "assets" / "data" / "odds.json"
OUT = ROOT / "assets" / "data" / "nba_predictions.json"
CACHE = ROOT / ".edgelab-cache" / "dunkapi-private.json"
ENDPOINT = "https://mcp.dunkapi.com/v1/"
SOURCE_URL = "https://dunkapi.com/docs/get-player"
INJURIES_URL = "https://dunkapi.com/docs/get-injuries"
MARKETS = {"Puntos": "pts", "Rebotes": "reb", "Asistencias": "ast"}
DAY_MAX_PLAYERS = 2
DAY_MAX_CREDITS = 14  # 2*(search 1 + get_player 5) + get_injuries 2
CREDIT_RESERVE = 70
MAX_PROFILE_AGE_HOURS = 48
REFRESH_HOUR_UTC = 15  # cron at 15:37 UTC; other 3-hour runs reuse cached output
TEAM_CODES = {
    "atlanta hawks": "ATL", "boston celtics": "BOS", "brooklyn nets": "BKN",
    "charlotte hornets": "CHA", "chicago bulls": "CHI", "cleveland cavaliers": "CLE",
    "dallas mavericks": "DAL", "denver nuggets": "DEN", "detroit pistons": "DET",
    "golden state warriors": "GSW", "houston rockets": "HOU",
    "indiana pacers": "IND", "la clippers": "LAC", "los angeles clippers": "LAC",
    "los angeles lakers": "LAL", "la lakers": "LAL",
    "memphis grizzlies": "MEM", "miami heat": "MIA", "milwaukee bucks": "MIL",
    "minnesota timberwolves": "MIN", "new orleans pelicans": "NOP",
    "new york knicks": "NYK", "oklahoma city thunder": "OKC",
    "orlando magic": "ORL", "philadelphia 76ers": "PHI", "phoenix suns": "PHX",
    "portland trail blazers": "POR", "sacramento kings": "SAC",
    "san antonio spurs": "SAS", "toronto raptors": "TOR", "utah jazz": "UTA",
    "washington wizards": "WAS",
}


def utc_now():
    return datetime.now(timezone.utc)


def stamp(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None


def normalized(name):
    if not isinstance(name, str):
        return ""
    raw = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", raw)).strip()


def fixture_teams(event):
    return {TEAM_CODES.get(normalized(event.get("home"))), TEAM_CODES.get(normalized(event.get("away")))} - {None}


def fetch_tool(tool, params, key, timeout=18):
    """Return (payload, credits_remaining). Never expose the key or the request body in logs."""
    if tool not in {"search_players", "get_player", "get_injuries"}:
        raise ValueError("unsupported endpoint")
    body = json.dumps(params, separators=(",", ":")).encode("utf-8")
    request = Request(ENDPOINT + tool, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": key,
        "User-Agent": "EdgeLabAnalytics/0.9",
    })
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
        remaining = response.headers.get("X-Credits-Remaining")
    remain = int(remaining) if remaining and remaining.isdecimal() else None
    return payload, remain


def empty_cache():
    return {"schema": 1, "refreshed_on": None, "profiles": {}, "injuries": None,
            "injuries_updated_at": None, "credits_remaining": None}


def load_cache(path=CACHE):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != 1 or not isinstance(data.get("profiles"), dict):
            return empty_cache()
        return data
    except (OSError, ValueError, TypeError, AttributeError):
        return empty_cache()


def save_cache(cache, path=CACHE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def line_ok(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and (
        value >= 0 and abs(value - math.floor(value) - 0.5) < 1e-8)


def odds_candidates(odds, clock):
    """Collect unique players with actual >1.80 Over props and a future NBA fixture."""
    candidates = {}
    for event in odds.get("events", []):
        if event.get("sport") != "basket" or event.get("competition_id") != "nba":
            continue
        starts = parse_time(event.get("utc"))
        if starts is None or starts <= clock:
            continue
        teams = fixture_teams(event)
        if len(teams) != 2:
            continue
        for book, markets in event.get("books", {}).items():
            if not isinstance(markets, list):
                continue
            for m in markets:
                if not isinstance(m, dict) or m.get("kind") != "prop":
                    continue
                match = re.fullmatch(r"(.+?) \((Puntos|Rebotes|Asistencias)\)", m.get("label", ""))
                if not match or not line_ok(m.get("line")):
                    continue
                price = m.get("selections", {}).get("over")
                if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price <= 1.80:
                    continue
                name, kind = match.groups()
                player_key = normalized(name)
                if not player_key:
                    continue
                k = (event["fixture_id"], player_key)
                entry = candidates.setdefault(k, {
                    "fixture_id": event["fixture_id"], "team_codes": sorted(teams),
                    "name": name.strip(), "player_key": player_key, "utc": event["utc"],
                    "quotes": [],
                })
                entry["quotes"].append({
                    "book": book, "label": m["label"], "line": m["line"],
                    "kind": kind, "price": float(price),
                    "updated_at": m.get("updated_at"),
                })
    return sorted(candidates.values(), key=lambda c: (c["utc"], -len(c["quotes"]), c["name"]))


def resolve_player(candidate, key, getter, remaining):
    payload, new_remaining = getter("search_players", {"name": candidate["name"], "limit": 8}, key)
    if new_remaining is None:
        return None, None
    if new_remaining < CREDIT_RESERVE + 5:
        return None, new_remaining
    matching = [p for p in payload.get("players", []) if
                normalized(p.get("name")) == candidate["player_key"]
                and str(p.get("team", "")).upper() in candidate["team_codes"]]
    if len(matching) != 1:
        return None, new_remaining
    return matching[0], new_remaining


def injury_map(snapshot, event_time, clock):
    """Only use reports dated within 48 hours and before the fixture."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("injuries"), list):
        return {}, False
    report_date = snapshot.get("date")
    try:
        day = datetime.strptime(report_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {}, False
    age = (clock.date() - day).days
    if not (0 <= age <= 2) or day > event_time.date():
        return {}, False
    return {
        str(x["player_id"]): x for x in snapshot["injuries"]
        if isinstance(x, dict) and x.get("player_id")
    }, True


def profile_recent(profile, event_time, clock):
    """At least five usable games within 45 days, strictly BEFORE the event."""
    rows = profile.get("recent_games", [])
    if not isinstance(rows, list):
        return []
    usable = []
    for g in rows:
        if not isinstance(g, dict):
            continue
        day = parse_time(str(g.get("date")) + "T12:00:00Z")
        if day is None or day.date() >= event_time.date() or day.date() > clock.date():
            continue
        if (clock.date() - day.date()).days > 45:
            continue
        minutes = g.get("minutes")
        if not isinstance(minutes, (float, int)) or isinstance(minutes, bool) or minutes < 12:
            continue
        if not all(isinstance(g.get(stat), (float, int)) and not isinstance(g.get(stat), bool) and
                   g[stat] >= 0 for stat in ("pts", "reb", "ast")):
            continue
        usable.append(g)
    usable.sort(key=lambda g: g["date"], reverse=True)
    # Do not mix teams after trades without explicit revalidation.
    return usable[:10]


def estimated_prop(profile, kind, line, event_time, clock):
    games = profile_recent(profile, event_time, clock)
    if len(games) < 5:
        return None
    stat = MARKETS[kind]
    sample = [float(g[stat]) for g in games]
    minutes = [float(g["minutes"]) for g in games]
    n = len(sample)
    weights = [0.88 ** i for i in range(n)]
    mean = sum(a * w for a, w in zip(sample, weights)) / sum(weights)
    sd = statistics.stdev(sample)
    # Conservative variance floors prevent overconfident predictions on small samples.
    minimum_sd = {"Puntos": 5.5, "Rebotes": 2.2, "Asistencias": 1.8}[kind]
    sd = max(sd, minimum_sd)
    baseline = statistics.mean(minutes)
    expected = statistics.mean(minutes[: min(5, n)])
    if baseline < 12 or expected < 12:
        return None
    mean *= max(0.85, min(1.15, expected / baseline))
    # Normal approximation with half-point threshold; empirical, NOT calibrated.
    p = math.erfc((float(line) - mean) / (sd * math.sqrt(2))) / 2
    p = max(0.025, min(0.975, p))
    return {"p": round(p, 5), "projected_mean": round(mean, 2),
            "minutes_reference": round(expected, 1), "sample_size": n,
            "sd": round(sd, 2), "last_game": games[0]["date"]}


def prepare_public(odds, cache, clock):
    forecasts = []
    candidates = odds_candidates(odds, clock)
    profile_data = cache.get("profiles", {})
    injuries, injuries_fresh = injury_map(cache.get("injuries"), clock + timedelta(days=1), clock)
    for candidate in candidates:
        profile_record = profile_data.get(candidate["player_key"])
        if not isinstance(profile_record, dict):
            continue
        fetched_at = parse_time(profile_record.get("fetched_at"))
        if fetched_at is None or not (0 <= (clock - fetched_at).total_seconds() <= MAX_PROFILE_AGE_HOURS * 3600):
            continue
        profile = profile_record.get("data")
        player = profile.get("player") if isinstance(profile, dict) else None
        if not isinstance(player, dict) or normalized(player.get("name")) != candidate["player_key"]:
            continue
        if player.get("team") not in candidate["team_codes"]:
            continue
        starts = parse_time(candidate["utc"])
        record = injuries.get(str(player.get("player_id"))) if injuries_fresh else None
        status = str(record.get("status", "")).lower() if record else ""
        excluded = any(term in status for term in ("out", "doubtful", "inactive"))
        warn = []
        if excluded:
            warn.append("Lesión o ausencia: consulta el estado antes del partido.")
        elif "questionable" in status or "day-to-day" in status:
            warn.append("Jugador en duda: minutos no confirmados.")
        if not injuries_fresh:
            warn.append("Reporte de lesiones ausente o de antigüedad superior a 48 horas.")
        warn.append("Minutos por tendencia histórica, NO confirmación de alineación.")
        warn.append("Riesgo de blowout no cuantificado; revisar spread y rotaciones.")
        for quote in candidate["quotes"]:
            quoted_at = parse_time(quote.get("updated_at"))
            if quoted_at is None or not (0 <= (clock - quoted_at).total_seconds() <= 8 * 3600):
                continue
            estimated = estimated_prop(profile, quote["kind"], quote["line"], starts, clock)
            if estimated is None or excluded:
                continue
            # Do not publish ten-game logs or season-wide raw DunkAPI datasets.
            forecasts.append({
                "fixture_id": candidate["fixture_id"], "player": candidate["name"],
                "market_label": quote["label"], "market_line": quote["line"],
                "book": quote["book"], "quote": quote["price"], "quote_updated_at": quote["updated_at"],
                "market": quote["kind"], **estimated,
                "injury_status": status or None,
                "injuries_fresh": injuries_fresh,
                "warnings": warn, "source": "DunkAPI", "source_url": SOURCE_URL,
                "stats_checked_at": profile_record["fetched_at"],
                "model": "recent10-normal-heuristic-v1", "calibrated": False,
            })
    return forecasts


def run(odds, cache, key, clock=None, getter=fetch_tool):
    clock = clock or utc_now()
    cache = cache if isinstance(cache, dict) and cache.get("schema") == 1 else empty_cache()
    diagnostics = {"status": "not_configured", "players_fetched": 0,
                   "credits_estimated_max": 0, "remaining_credits": cache.get("credits_remaining"),
                   "injuries_checked": False, "errors": []}
    if not key:
        return cache, {"schema": 1, "generated_at": stamp(clock), "status": "not_configured",
                       "forecasts": [], "diagnostics": diagnostics}
    candidates = odds_candidates(odds, clock)
    if cache.get("refreshed_on") == clock.date().isoformat():
        diagnostics["status"] = "cached_today"
    elif clock.hour != REFRESH_HOUR_UTC:
        diagnostics["status"] = "outside_refresh_window"
    elif not candidates:
        diagnostics["status"] = "no_prop_markets"
    else:
        # Mark immediately, including failed calls: reruns cannot repeatedly bill.
        cache["refreshed_on"] = clock.date().isoformat()
        diagnostics["status"] = "attempted"
        budget = DAY_MAX_CREDITS
        candidate_new = [c for c in candidates if
                         not (c["player_key"] in cache["profiles"] and
                              (parse_time(cache["profiles"][c["player_key"]].get("fetched_at")) or
                               clock - timedelta(days=10)) >= clock - timedelta(hours=40))]
        for c in candidate_new[:DAY_MAX_PLAYERS]:
            if budget < 6:
                break
            if isinstance(cache.get("credits_remaining"), int) and cache["credits_remaining"] < CREDIT_RESERVE + 6:
                diagnostics["status"] = "quota_reserved"
                break
            # Cost: 1 search + 5 get_player. If remaining header absent, stop.
            try:
                identity, remaining = resolve_player(c, key, getter, cache.get("credits_remaining"))
                budget -= 1
                diagnostics["credits_estimated_max"] += 1
                cache["credits_remaining"] = remaining
                if identity is None:
                    continue
                payload, remaining = getter("get_player", {"player_id": str(identity["player_id"])}, key)
                budget -= 5
                diagnostics["credits_estimated_max"] += 5
                cache["credits_remaining"] = remaining
                player = payload.get("player") if isinstance(payload, dict) else None
                if not isinstance(player, dict) or normalized(player.get("name")) != c["player_key"]:
                    continue
                if str(player.get("team")) not in c["team_codes"]:
                    continue
                cache["profiles"][c["player_key"]] = {"data": payload, "fetched_at": stamp(clock)}
                diagnostics["players_fetched"] += 1
            except Exception as exc:
                diagnostics["errors"].append("perfil:" + type(exc).__name__)
                continue
        if budget >= 2 and diagnostics["players_fetched"] and (
            cache.get("credits_remaining") is None or cache["credits_remaining"] >= CREDIT_RESERVE + 2
        ):
            try:
                report, remaining = getter("get_injuries", {}, key)
                diagnostics["credits_estimated_max"] += 2
                cache["credits_remaining"] = remaining
                cache["injuries"] = report
                cache["injuries_updated_at"] = stamp(clock)
                diagnostics["injuries_checked"] = True
            except Exception as exc:
                diagnostics["errors"].append("lesiones:" + type(exc).__name__)
        if diagnostics["status"] == "attempted":
            diagnostics["status"] = "ok" if diagnostics["players_fetched"] else "no_profiles"
    # Future event features cannot be based on future observations.
    forecast = prepare_public(odds, cache, clock)
    public = {"schema": 1, "generated_at": stamp(clock), "status": diagnostics["status"],
              "source": "DunkAPI", "source_url": SOURCE_URL,
              "forecasts": forecast, "diagnostics": diagnostics,
              "note": "Proyecciones derivadas; sin game logs, sin garantías y sin calibración histórica."}
    return cache, public


def main():
    if not ODDS_PATH.exists():
        raise SystemExit("Primero generar odds.json.")
    odds = json.loads(ODDS_PATH.read_text(encoding="utf-8"))
    cache = load_cache()
    cache, snapshot = run(odds, cache, os.environ.get("DUNKAPI_API_KEY", "").strip())
    save_cache(cache)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ds = snapshot["diagnostics"]
    print("DUNKAPI:", ds["status"], "| perfiles:", ds["players_fetched"],
          "| forecasts:", len(snapshot["forecasts"]), "| cuota restante:", ds["remaining_credits"],
          "| errores:", len(ds["errors"]))


if __name__ == "__main__":
    main()

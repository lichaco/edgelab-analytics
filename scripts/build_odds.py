#!/usr/bin/env python3
"""Snapshot prepartido Odds-API.io -> GitHub Pages; secretos solo en Actions.

No se publican eventos sin emparejamiento fiable con el calendario.
No se generan cuotas ni partidos simulados.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "assets" / "data" / "calendar.json"
OUTPUT = ROOT / "assets" / "data" / "odds.json"
BASE = "https://api.odds-api.io/v3"
BOOKS = ("Betano", "DraftKings")
SPORTS = ("football", "nba", "wnba", "nhl", "american-football")
MAX_EVENTS = 70

def now_utc():
    return datetime.now(timezone.utc)

def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None

def norm(name):
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = name.replace("los angeles", "la").replace("new york", "ny")
    name = re.sub(r"[^a-z0-9]+", " ", name)
    stop = {"fc", "cf", "afc", "sc", "the", "de", "del", "club", "football", "futbol"}
    return " ".join(x for x in name.split() if x not in stop)

def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def match_event(event, fixtures):
    home, away = event.get("home"), event.get("away")
    when = parse_time(event.get("date"))
    if not (home and away and when):
        return None
    candidates = []
    for f in fixtures:
        start = parse_time(f.get("utc"))
        if not start or abs((start - when).total_seconds()) > 14 * 3600:
            continue
        h = similarity(home, f.get("home"))
        a = similarity(away, f.get("away"))
        if min(h, a) < .74 or (h + a) / 2 < .82:
            continue
        # Rechazar emparejamientos dudosos, incluidos equipos con el orden invertido.
        score = (h + a) / 2 - abs((start - when).total_seconds()) / (14 * 3600) * .07
        candidates.append((score, f))
    candidates.sort(key=lambda x: -x[0])
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .09:
        return None
    return candidates[0][1]

def price(value):
    try:
        val = float(value)
        if 1.001 < val < 1001 and val == val:
            return round(val, 4)
    except (ValueError, TypeError, OverflowError):
        pass
    return None

def quote_choices(row, keys):
    found = {}
    for key in keys:
        value = price(row.get(key))
        if value is not None:
            found[key] = value
    return found

def normalized_markets(market, sport):
    name = str(market.get("name", "")).strip()
    low = name.lower()
    updated = market.get("updatedAt")
    rows = market.get("odds", [])
    if not isinstance(rows, list):
        return []
    if low in ("ml", "moneyline", "1x2", "match winner", "3-way result"):
        kind = "result"
    elif low in ("totals", "total goals"):
        kind = "goals" if sport == "football" else "totals"
    elif "corner" in low and ("total" in low or "over" in low):
        kind = "corners"
    elif ("booking" in low or "card" in low) and ("total" in low or "over" in low):
        kind = "cards"
    elif low in ("spread", "handicap", "map handicap", "map spread"):
        kind = "spread"
    elif low == "player props":
        kind = "prop"
    else:
        return []  # Solo mercados comprendidos: nunca inferir qué representa una línea.
    out = []
    for row in rows[:250]:
        if not isinstance(row, dict):
            continue
        choices = quote_choices(row, ("home", "draw", "away") if kind == "result" or kind == "spread" else ("over", "under"))
        if not choices:
            continue
        try:
            line = float(row.get("hdp")) if row.get("hdp") is not None else None
        except (ValueError, TypeError):
            line = None
        if kind in ("goals", "totals", "corners", "cards", "spread", "prop") and line is None:
            continue
        label = str(row.get("label", "")).strip()[:110] if kind == "prop" else ""
        if kind == "prop" and not label:
            continue
        out.append({"kind": kind, "market": name, "line": line,
                    "label": label, "selections": choices, "updated_at": updated})
    return out

def api_get(path, params, key, getter=None):
    params = dict(params, apiKey=key)
    url = BASE + path + "?" + urlencode(params)
    if getter is not None:
        return getter(path, params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "EdgeLab/0.5"})
    # La URL contiene la clave, así que no imprimir url ni traza con querystring.
    with urlopen(request, timeout=22) as response:
        payload = json.load(response)
    if isinstance(payload, dict) and (payload.get("error") or payload.get("success") is False):
        raise ValueError("Proveedor devolvió error de API")
    return payload

def event_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("events", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("Formato de eventos no reconocido")

def board_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "events"):
            if isinstance(payload.get(key), list):
                return payload[key]
        if payload.get("id") is not None:
            return [payload]
    raise ValueError("Formato de cuotas no reconocido")

def build_snapshot(calendar, key, getter=None, clock=None):
    clock = clock or now_utc()
    diagnostics = {"status": "not_configured", "provider": "Odds-API.io",
                   "books_requested": list(BOOKS), "events_seen": 0, "events_matched": 0,
                   "boards": 0, "errors": [], "requests": 0}
    output = {"schema": 1, "generated_at": clock.isoformat().replace("+00:00", "Z"),
              "provider": "Odds-API.io", "events": [], "diagnostics": diagnostics,
              "note": "Cuotas prepartido en instantáneas, no en vivo; no garantiza disponibilidad ni ganancias."}
    if not key:
        return output
    fixtures = [f for f in calendar.get("fixtures", []) if f.get("utc") and
                parse_time(f.get("utc")) and parse_time(f["utc"]) > clock]
    if not fixtures:
        diagnostics["status"] = "no_fixtures"
        return output
    sport_for = {"football": "football", "nba": "basket", "wnba": "basket", "nhl": "nhl",
                 "american-football": "nfl"}
    matched = {}
    diagnostics["status"] = "ok"
    for sport in SPORTS:
        available = [x for x in fixtures if x.get("sport") == sport_for[sport]]
        if sport in ("nba", "wnba"):
            wanted = sport.upper()
            available = [x for x in available if x.get("competitionId") == wanted.lower()]
        if not available:
            continue
        for book in BOOKS:
            try:
                diagnostics["requests"] += 1
                events = event_list(api_get("/events", {"sport": sport, "bookmaker": book, "status": "pending", "limit": "500"}, key, getter))
                diagnostics["events_seen"] += len(events)
                for event in events:
                    if not isinstance(event, dict) or not event.get("id"):
                        continue
                    when = parse_time(event.get("date"))
                    if not when or when <= clock:
                        continue
                    fixture = match_event(event, available)
                    if not fixture:
                        continue
                    record = matched.setdefault(str(event["id"]), {"event": event, "fixture": fixture})
                    # Si la API usa el mismo event id, consolidar Betano y DraftKings.
                    if record["fixture"]["id"] != fixture["id"]:
                        diagnostics["errors"].append("ID de evento ambiguo, omitido")
                        matched.pop(str(event["id"]), None)
                # No se publican cuotas sin match exacto.
            except Exception as exc:
                diagnostics["errors"].append(sport + "/" + book + ": " + type(exc).__name__)
    chosen = sorted(matched.values(), key=lambda x: x["fixture"]["utc"])[:MAX_EVENTS]
    diagnostics["events_matched"] = len(chosen)
    for i in range(0, len(chosen), 10):
        ids = [str(x["event"]["id"]) for x in chosen[i:i + 10]]
        try:
            diagnostics["requests"] += 1
            boards = board_list(api_get("/odds/multi", {
                "eventIds": ",".join(ids), "bookmakers": ",".join(BOOKS),
                "markets": "ML,Totals,Spread,Player Props,Corners Totals,Bookings Totals"
            }, key, getter))
        except Exception as exc:
            diagnostics["errors"].append("odds/multi: " + type(exc).__name__)
            continue
        wanted = {str(x["event"]["id"]): x["fixture"] for x in chosen[i:i + 10]}
        for board in boards:
            if not isinstance(board, dict) or str(board.get("id")) not in wanted:
                continue
            fixture = wanted[str(board["id"])]
            raw_books = board.get("bookmakers", {})
            if not isinstance(raw_books, dict):
                continue
            books = {}
            for name in BOOKS:
                markets = raw_books.get(name, [])
                if not isinstance(markets, list):
                    continue
                out_markets = []
                for m in markets:
                    if isinstance(m, dict):
                        out_markets += normalized_markets(m, fixture["sport"])
                if out_markets:
                    books[name] = out_markets
            if not books:
                continue
            output["events"].append({
                "fixture_id": fixture["id"], "competition_id": fixture["competitionId"],
                "sport": fixture["sport"], "home": fixture["home"], "away": fixture["away"],
                "utc": fixture["utc"], "provider_event_id": str(board["id"]), "books": books
            })
            diagnostics["boards"] += 1
    if not output["events"]:
        diagnostics["status"] = "empty_or_unmatched" if not diagnostics["errors"] else "partial_or_error"
    elif diagnostics["errors"]:
        diagnostics["status"] = "partial"
    return output

def main():
    if not CALENDAR.exists():
        raise SystemExit("Primero construir el calendario")
    calendar = json.loads(CALENDAR.read_text(encoding="utf-8"))
    try:
        snapshot = build_snapshot(calendar, os.environ.get("ODDS_API_IO_KEY", "").strip())
    except Exception as exc:
        # No incluir excepciones con URL/clave en salida pública.
        snapshot = {"schema": 1, "generated_at": now_utc().isoformat(),
                    "provider": "Odds-API.io", "events": [],
                    "diagnostics": {"status": "error", "errors": [type(exc).__name__]}}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    d = snapshot["diagnostics"]
    print("Odds:", d.get("status"), "| eventos:", len(snapshot["events"]),
          "| solicitudes:", d.get("requests", 0), "| errores:", len(d.get("errors", [])))

if __name__ == "__main__":
    main()

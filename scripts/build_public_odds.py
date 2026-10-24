#!/usr/bin/env python3
"""Obtener cuotas gratuitas de referencia publicadas por ESPN Core.

Usa feeds JSON públicos sin claves privadas ni APIs comerciales. Los mercados
se normalizan solo si ESPN entrega precios reales; nunca se inventan líneas.
Ejecutar después de scripts/build_calendar.py en GitHub Actions.
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import json
import math
import re

try:
    from .build_odds import match_event
except ImportError:
    from build_odds import match_event

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "assets" / "data" / "calendar.json"
OUT = ROOT / "assets" / "data" / "odds.json"
BASE = "https://sports.core.api.espn.com/v2/sports/"
PUBLIC_SITE = "https://site.api.espn.com/apis/site/v2/sports/"
CORE = {
    "eng.1": ("soccer", "eng.1"), "esp.1": ("soccer", "esp.1"),
    "ita.1": ("soccer", "ita.1"), "ger.1": ("soccer", "ger.1"),
    "fra.1": ("soccer", "fra.1"), "chi.1": ("soccer", "chi.1"),
    "nba": ("basketball", "nba"), "wnba": ("basketball", "wnba"),
    "nhl": ("hockey", "nhl"), "nfl": ("football", "nfl"),
}
BUDGET = {"football": 30, "basket": 25, "nhl": 22, "nfl": 16}
BOOK_PREFERENCE = {
    "draftkings": 0, "fanduel": 1, "betmgm": 2, "caesars": 3,
    "bet365": 4, "espn bet": 5,
}
MAX_ITEMS = 4
MAX_REF_FETCH = 3
DATE_LIMIT = 9


def utcnow():
    return datetime.now(timezone.utc)


def parse_utc(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def get_json(url, timeout=12):
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "EdgeLabAnalytics/0.6 (+https://github.com/lichaco/edgelab-analytics)",
    })
    with urlopen(req, timeout=timeout) as res:
        if res.status != 200:
            raise ValueError("HTTP no exitoso")
        return json.load(res)


def price(v):
    """American -> decimal. Prevent accidental interpretation of score/probability."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, dict):
        return price(v.get("american") or v.get("moneyLine") or v.get("value"))
    try:
        p = float(v)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(p):
        return None
    if 1.001 < p <= 30 and int(p) != p:
        return round(p, 4)  # Some JSONs expose decimal prices directly.
    if p >= 100:
        return round(1 + p / 100, 4)
    if p <= -100:
        return round(1 + 100 / abs(p), 4)
    return None


def team_price(item, key):
    block = item.get(key)
    if isinstance(block, dict):
        return price(block.get("moneyLine"))
    return price(block)


def lines(item, soccer=False):
    """Safe selection extraction; distinguish a 3-way 1X2 from 2-way winners."""
    out = []
    home, away = team_price(item, "homeTeamOdds"), team_price(item, "awayTeamOdds")
    draw = team_price(item, "drawOdds")
    if not soccer and home and away:
        out.append({"kind": "result", "market": "Ganador", "line": None,
                    "label": "", "selections": {"home": home, "away": away}})
    elif soccer and home and away and draw:
        out.append({"kind": "result", "market": "1X2", "line": None,
                    "label": "", "selections": {"home": home, "draw": draw, "away": away}})
    # Some feeds have no spread/total prices. Never substitute -110.
    line = item.get("overUnder")
    if isinstance(line, (float, int)) and not isinstance(line, bool) and 0.0 < line < 1000:
        choices = {}
        for name, key in (("over", "overOdds"), ("under", "underOdds")):
            q = price(item.get(key))
            if q:
                choices[name] = q
        if choices:
            out.append({"kind": "goals" if soccer else "totals",
                        "market": "Total goles" if soccer else "Total puntos/goles",
                        "line": float(line), "label": "", "selections": choices})
    spread = item.get("spread")
    if not soccer and isinstance(spread, (float, int)) and not isinstance(spread, bool):
        choices = {}
        for name, key in (("home", "homeTeamOdds"), ("away", "awayTeamOdds")):
            block = item.get(key)
            if isinstance(block, dict):
                q = price(block.get("spreadOdds"))
                if q:
                    choices[name] = q
        if choices:
            out.append({"kind": "spread", "market": "Hándicap (línea local)",
                        "line": float(spread), "label": "",
                        "selections": choices})
    stamp = item.get("lastModified") or item.get("lastUpdated")
    for m in out:
        m["updated_at"] = stamp if isinstance(stamp, str) else None
    return out


def normalize_provider(item, soccer=False):
    if not isinstance(item, dict):
        return None
    provider = item.get("provider", {})
    if isinstance(provider, dict):
        name = provider.get("name")
    elif isinstance(provider, str):
        name = provider
    else:
        name = None
    if not isinstance(name, str) or not name.strip():
        return None
    market_list = lines(item, soccer=soccer)
    if not market_list:
        return None
    return name.strip()[:65], market_list


def safe_ref(ref, event_id, path, league):
    if not isinstance(ref, str):
        return None
    parts = urlsplit(ref.replace("http://", "https://", 1))
    prefix = f"/v2/sports/{path}/leagues/{league}/events/{event_id}/competitions/{event_id}/odds/"
    if parts.scheme != "https" or parts.netloc != "sports.core.api.espn.com":
        return None
    if not parts.path.startswith(prefix):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]+", parts.path[len(prefix):]):
        return None
    return "https://" + parts.netloc + parts.path


def odds_for_event(event_id, league, fetch_json=get_json):
    sport, code = CORE[league]
    eid = str(event_id)
    if not eid.isdecimal() or len(eid) > 15:
        return [], ["event_id_inválido"]
    url = f"{BASE}{sport}/leagues/{code}/events/{eid}/competitions/{eid}/odds?limit=20"
    try:
        payload = fetch_json(url)
    except Exception as e:
        return [], [type(e).__name__]
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return [], ["respuesta_inválida"]
    source = payload["items"]
    # Prioritize inlined rows; refs are not dereferenced unless needed.
    inline = [x for x in source if isinstance(x, dict) and x.get("provider")]
    refs = [x for x in source if isinstance(x, dict) and x.get("$ref") and not x.get("provider")]
    errors = []
    if not inline:
        for item in refs[:MAX_REF_FETCH]:
            u = safe_ref(item.get("$ref"), eid, sport, code)
            if not u:
                continue
            try:
                inline.append(fetch_json(u))
            except Exception as exc:
                errors.append(type(exc).__name__)
    selected = []
    for it in inline:
        result = normalize_provider(it, soccer=sport == "soccer")
        if result:
            selected.append(result)
    selected.sort(key=lambda kv: (BOOK_PREFERENCE.get(kv[0].lower(), 99), kv[0]))
    # Explicit sportsbook labels, no duplicates.
    books = {}
    for name, markets in selected:
        if name not in books and len(books) < MAX_ITEMS:
            books[name] = markets
    return books, errors


def enumerate_soccer_ids(fixtures, clock, fetch_json=get_json):
    """Bridge OpenFootball fixture IDs to ESPN event IDs conservatively."""
    pairs = {}
    errors = []
    by_date = defaultdict(list)
    for f in fixtures:
        if f.get("competitionId") not in CORE or f.get("sport") != "football":
            continue
        # OpenFootball fixtures use textual ID; ESPN fixtures already have numeric id.
        if str(f.get("id", "")).isdecimal():
            continue
        kickoff = parse_utc(f.get("utc"))
        if kickoff and kickoff > clock:
            by_date[(f["competitionId"], kickoff.date())].append(f)
    for (league, day), candidates in sorted(by_date.items()):
        if league not in CORE or league == "chi.1":
            continue
        sport, code = CORE[league]
        url = f"{PUBLIC_SITE}{sport}/{code}/scoreboard?dates={day:%Y%m%d}&limit=300"
        try:
            data = fetch_json(url)
            if not isinstance(data.get("events"), list):
                continue
            for event in data["events"]:
                try:
                    competition = event["competitions"][0]
                    rivals = competition["competitors"]
                    h = next(x for x in rivals if x.get("homeAway") == "home")["team"]["displayName"]
                    a = next(x for x in rivals if x.get("homeAway") == "away")["team"]["displayName"]
                    event_id = str(event["id"])
                    when = parse_utc(event["date"])
                    if not when or not event_id.isdecimal() or when <= clock:
                        continue
                    event_like = {"date": event["date"], "home": h, "away": a}
                    matched = match_event(event_like, candidates)
                    if matched:
                        pairs[matched["id"]] = event_id
                except (KeyError, ValueError, IndexError, StopIteration, TypeError):
                    continue
        except Exception as exc:
            errors.append(f"{league}: {type(exc).__name__}")
    return pairs, errors


def build_snapshot(calendar, clock=None, getter=get_json, odds_reader=None):
    clock = clock or utcnow()
    odds_reader = odds_reader or (lambda event_id, lg: odds_for_event(event_id, lg, getter))
    ds = {"status": "ok", "provider": "ESPN Core", "requires_key": False,
          "events_considered": 0, "events_with_odds": 0, "books": {},
          "errors": [], "coverage": {}}
    snap = {"schema": 1, "generated_at": clock.isoformat().replace("+00:00", "Z"),
            "provider": "ESPN Core (referencia pública, no oficial)", "events": [],
            "diagnostics": ds,
            "note": "Cuotas de referencia prepartido de ESPN Core. No en vivo; sin props ni garantía de cobertura."}
    fixtures = []
    until = clock + timedelta(days=DATE_LIMIT)
    for f in calendar.get("fixtures", []):
        kick = parse_utc(f.get("utc"))
        if kick and clock < kick <= until and f.get("sport") in BUDGET and f.get("competitionId") in CORE:
            fixtures.append(f)
    if not fixtures:
        ds["status"] = "no_fixtures"
        return snap
    fixtures.sort(key=lambda f: f["utc"])
    per_sport = defaultdict(int)
    eligible = []
    for f in fixtures:
        sport = f["sport"]
        if per_sport[sport] < BUDGET[sport]:
            per_sport[sport] += 1
            eligible.append(f)
    ds["events_considered"] = len(eligible)
    mapping, errs = enumerate_soccer_ids([f for f in eligible if f.get("sport") == "football"], clock, getter)
    ds["errors"].extend(errs[:8])
    tasks = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        for fixture in eligible:
            lid = fixture["competitionId"]
            event_id = fixture.get("id") if str(fixture.get("id", "")).isdecimal() else mapping.get(fixture["id"])
            if not event_id:
                continue
            tasks[pool.submit(odds_reader, event_id, lid)] = (fixture, str(event_id))
        for fut in as_completed(tasks):
            f, event_id = tasks[fut]
            try:
                books, event_errors = fut.result()
            except Exception as exc:
                ds["errors"].append(f'{f["competitionId"]}: {type(exc).__name__}')
                continue
            if event_errors and len(ds["errors"]) < 20:
                ds["errors"].extend((f["competitionId"] + ": " + e for e in event_errors[:2]))
            if not books:
                continue
            ds["events_with_odds"] += 1
            for name in books:
                ds["books"][name] = ds["books"].get(name, 0) + 1
            snap["events"].append({
                "fixture_id": f["id"], "competition_id": f["competitionId"],
                "sport": f["sport"], "home": f["home"], "away": f["away"],
                "utc": f["utc"], "provider_event_id": event_id, "books": books,
                "source": "ESPN Core",
            })
    snap["events"].sort(key=lambda e: e["utc"])
    for sport in BUDGET:
        ds["coverage"][sport] = sum(x["sport"] == sport for x in snap["events"])
    if not snap["events"]:
        ds["status"] = "empty_or_unavailable"
    elif ds["errors"]:
        ds["status"] = "partial"
    return snap


def main():
    if not CALENDAR.exists():
        raise SystemExit("Falta calendar.json generado por build_calendar.py")
    calendar = json.loads(CALENDAR.read_text(encoding="utf-8"))
    try:
        snapshot = build_snapshot(calendar)
    except Exception as exc:
        snapshot = {"schema": 1, "generated_at": utcnow().isoformat().replace("+00:00", "Z"),
                    "provider": "ESPN Core", "events": [],
                    "diagnostics": {"status": "error", "errors": [type(exc).__name__],
                                    "requires_key": False}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    diagnostics = snapshot["diagnostics"]
    print("FREE ESPN ODDS:", diagnostics.get("status"), 
          "| revisados:", diagnostics.get("events_considered", 0),
          "| partidos con cuotas:", len(snapshot["events"]),
          "| casas:", diagnostics.get("books", {}),
          "| incidencias:", len(diagnostics.get("errors", [])))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a static, keyless sports calendar for GitHub Pages.

OpenFootball (public-domain, fixtures + dated scores) for Europe's top 5.
ESPN unofficial public daily scoreboards for Chile, NBA, WNBA, NHL, NFL.
Never fabricate kick-off times for fixtures with date-only sources.
"""
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'assets' / 'data' / 'calendar.json'
LEAGUES = {
    'eng.1': {'label': 'Premier League', 'path': 'soccer', 'openfootball': 'en.1', 'zone': 'Europe/London'},
    'esp.1': {'label': 'La Liga', 'path': 'soccer', 'openfootball': 'es.1', 'zone': 'Europe/Madrid'},
    'ita.1': {'label': 'Serie A', 'path': 'soccer', 'openfootball': 'it.1', 'zone': 'Europe/Rome'},
    'ger.1': {'label': 'Bundesliga', 'path': 'soccer', 'openfootball': 'de.1', 'zone': 'Europe/Berlin'},
    'fra.1': {'label': 'Ligue 1', 'path': 'soccer', 'openfootball': 'fr.1', 'zone': 'Europe/Paris'},
    'chi.1': {'label': 'Primera División Chile', 'path': 'soccer'},
    'nba': {'label': 'NBA', 'path': 'basketball'},
    'wnba': {'label': 'WNBA', 'path': 'basketball'},
    'nhl': {'label': 'NHL', 'path': 'hockey'},
    'nfl': {'label': 'NFL', 'path': 'football'},
}


def get_json(url, timeout=12):
    req = Request(url, headers={
        'User-Agent': 'EdgeLabCalendar/0.4 (personal project; https://github.com/lichaco/edgelab-analytics)',
        'Accept': 'application/json',
    })
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f'HTTP {response.status}')
        return json.load(response)


def _sport(path, league_id):
    return 'football' if path == 'soccer' else 'basket' if path == 'basketball' else league_id


def normalize_espn(payload, league_id):
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        raise ValueError('ESPN JSON sin events')
    meta = LEAGUES[league_id]
    items = []
    for event in payload['events']:
        try:
            kickoff = datetime.fromisoformat(event['date'].replace('Z', '+00:00')).astimezone(timezone.utc)
            competitors = event['competitions'][0]['competitors']
            home = next(x for x in competitors if x.get('homeAway') == 'home')['team']['displayName']
            away = next(x for x in competitors if x.get('homeAway') == 'away')['team']['displayName']
            status = event.get('status', {}).get('type', {})
            if status.get('state') != 'pre' or status.get('completed') or not home or not away:
                continue
            items.append({
                'id': str(event['id']), 'competitionId': league_id, 'league': meta['label'],
                'sport': _sport(meta['path'], league_id), 'home': home, 'away': away,
                'utc': kickoff.isoformat().replace('+00:00', 'Z'),
                'date': kickoff.date().isoformat(), 'status': 'pre', 'finished': False,
                'source': 'ESPN',
            })
        except (KeyError, StopIteration, IndexError, TypeError, ValueError):
            continue
    return items


def normalize_openfootball(payload, league_id, start, end, now):
    if not isinstance(payload, dict) or not isinstance(payload.get('matches'), list):
        raise ValueError('OpenFootball JSON sin matches')
    meta = LEAGUES[league_id]
    fixtures, history = [], []
    for match in payload['matches']:
        day_text = match.get('date')
        if not isinstance(day_text, str):
            continue
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            continue
        home, away = match.get('team1'), match.get('team2')
        if not isinstance(home, str) or not isinstance(away, str) or not home or not away or home == away:
            continue
        score = match.get('score')
        ft = score.get('ft') if isinstance(score, dict) else None
        completed = (isinstance(ft, list) and len(ft) == 2 and
                     all(type(x) is int and 0 <= x <= 25 for x in ft))
        if completed and day < now.date():
            history.append({'date': day_text, 'home': home, 'away': away, 'hg': ft[0], 'ag': ft[1]})
            continue
        if completed or not(start.date() <= day <= end.date()):
            continue
        kickoff_text = match.get('time')
        kickoff_utc = None
        if isinstance(kickoff_text, str):
            try:
                # The published local time may be provisional, but we never infer one.
                local = datetime.strptime(f'{day_text}T{kickoff_text}', '%Y-%m-%dT%H:%M').replace(tzinfo=ZoneInfo(meta['zone']))
                kickoff_utc = local.astimezone(timezone.utc)
            except (ValueError, TypeError):
                pass
        # Date-only fixtures on the current day might already have started.
        if kickoff_utc is None and day <= now.astimezone(ZoneInfo(meta['zone'])).date():
            continue
        if kickoff_utc and kickoff_utc <= now:
            continue
        fixtures.append({
            'id': f'openfootball-{league_id}-{day_text}-{home}-{away}',
            'competitionId': league_id, 'league': meta['label'], 'sport': 'football',
            'home': home, 'away': away, 'utc': kickoff_utc.isoformat().replace('+00:00', 'Z') if kickoff_utc else None,
            'date': day_text, 'status': 'pre', 'finished': False,
            'timeTBD': kickoff_utc is None, 'source': 'OpenFootball',
        })
    return fixtures, history


def football_seasons(now):
    # Europe cross-year season 2026-27 on Oct 2026.
    start = now.year if now.month >= 7 else now.year - 1
    return (f'{start-1}-{str(start)[-2:]}', f'{start}-{str(start+1)[-2:]}')


def gather_openfootball(league_id, start, end, now):
    meta = LEAGUES[league_id]
    prev, curr = football_seasons(now)
    fixtures, hist, errs = [], [], []
    for season in (prev, curr):
        url = f'https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{meta["openfootball"]}.json'
        try:
            p = get_json(url)
            fi, hi = normalize_openfootball(p, league_id, start, end, now)
            fixtures.extend(fi)
            hist.extend(hi)
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, json.JSONDecodeError) as e:
            errs.append(f'{season}: {str(e)[:100]}')
    return league_id, fixtures, hist, errs


def daily_espn_url(league_id, day):
    meta = LEAGUES[league_id]
    return ('https://site.api.espn.com/apis/site/v2/sports/'
            + meta['path'] + '/' + league_id + '/scoreboard?dates=' + day.strftime('%Y%m%d') + '&limit=300')


def gather_espn(league_id, start, end):
    items, errors, success = [], [], 0
    current = start.date()
    consecutive_errors = 0
    while current <= end.date():
        url = daily_espn_url(league_id, current)
        try:
            p = get_json(url)
            items.extend(normalize_espn(p, league_id))
            success += 1
            consecutive_errors = 0
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, json.JSONDecodeError) as e:
            errors.append(f'{current}: {str(e)[:110]}')
            consecutive_errors += 1
            # Avoid hammering a provider that blocks GitHub Actions runners.
            if consecutive_errors >= 3:
                errors.append('Consultas detenidas tras tres errores consecutivos.')
                break
        current += timedelta(days=1)
    return league_id, items, success, errors


def create_snapshot(now=None, days=31, getter_open=gather_openfootball, getter_espn=gather_espn):
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=1)
    end = now + timedelta(days=days)
    fixtures, history, diagnostics = [], {}, {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {}
        for lid, meta in LEAGUES.items():
            if 'openfootball' in meta:
                futures[pool.submit(getter_open, lid, start, end, now)] = lid
            else:
                futures[pool.submit(getter_espn, lid, start, end)] = lid
        for fut in as_completed(futures):
            lid = futures[fut]
            meta = LEAGUES[lid]
            try:
                result = fut.result()
                if 'openfootball' in meta:
                    _, items, hist, errors = result
                    history[lid] = sorted(hist, key=lambda x: x['date'])[-750:]
                    diagnostics[lid] = {'provider': 'OpenFootball', 'matches': len(items), 'history': len(hist), 'errors': errors}
                else:
                    _, items, success, errors = result
                    diagnostics[lid] = {'provider': 'ESPN', 'matches': len(items), 'days_ok': success, 'errors': errors[:4]}
                fixtures.extend(items)
            except Exception as ex:
                diagnostics[lid] = {'provider': 'OpenFootball' if 'openfootball' in meta else 'ESPN', 'matches': 0, 'errors': [f'Error interno: {type(ex).__name__}']}
    # Unique IDs and actual future kicks only; keep date-only future entries.
    distinct = {}
    for f in fixtures:
        if f.get('utc'):
            try:
                if datetime.fromisoformat(f['utc'].replace('Z', '+00:00')) <= now:
                    continue
            except (ValueError, TypeError):
                continue
        elif f.get('date', '') <= now.astimezone(ZoneInfo('America/Santiago')).date().isoformat():
            continue
        distinct[f['competitionId'] + ':' + f['id']] = f
    fixture_list = sorted(distinct.values(), key=lambda x: (x.get('utc') or x['date']+'T23:59Z', x['competitionId'], x['id']))
    return {
        'schema': 1, 'generated_at': now.isoformat().replace('+00:00', 'Z'),
        'days': days, 'fixtures': fixture_list, 'history': history, 'diagnostics': diagnostics,
        'note': 'Datos abiertos/no oficiales; validar cambios de horarios en la competición original. Sin odds ni encuentros simulados.'
    }


def main():
    snapshot = create_snapshot()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('Calendario guardado:', OUT, '| encuentros:', len(snapshot['fixtures']))
    for lid, diag in snapshot['diagnostics'].items():
        print(f'{lid}: {diag["matches"]} partidos, {len(diag.get("errors", []))} errores')
    if not any(d.get('matches', 0) for d in snapshot['diagnostics'].values()):
        print('ADVERTENCIA: ninguna fuente confirmó encuentros. La web mostrará el error y ofrecerá consulta directa.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
import requests, json, re, sys, unicodedata
from datetime import datetime, timezone, timedelta

# ESPN's JSON API — structured data, no HTML parsing needed
ESPN_API = (
    "https://site.web.api.espn.com/apis/site/v2/sports/golf/leaderboard"
    "?league=pga&tournamentId=401811941"
)
BST = timezone(timedelta(hours=1))

TEAM_PLAYERS = [
    'Rory McIlroy', 'Tommy Fleetwood', 'Russell Henley', 'Gary Woodland',
    'Cameron Young', 'Adam Scott', 'Shane Lowry', 'Justin Thomas',
    'Hideki Matsuyama', 'Patrick Reed', 'Collin Morikawa', 'Patrick Cantlay',
    'Jon Rahm', 'Jacob Bridgeman', 'Jake Knapp', 'Sepp Straka',
    'Ludvig Aberg', 'Jordan Spieth', 'Sung-Jae Im', 'Cameron Smith',
    'Scottie Scheffler', 'Chris Gotterup', 'Akshay Bhatia', 'Daniel Berger',
    'JJ Spaun', 'Justin Rose', 'Nicolai Hojgaard', 'Jason Day',
    'Bryson DeChambeau', 'Brooks Koepka', 'Corey Conners', 'Max Homa',
    'Xander Schauffele', 'Min Woo Lee', 'Si Woo Kim', 'Harris English',
    'Matt Fitzpatrick', 'Robert MacIntyre', 'Tyrrell Hatton', 'Ryan Gerard',
]

def to_ascii(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()

# Normalised lookup: ascii-lowercased full name → canonical name
PLAYER_LOOKUP = {to_ascii(p): p for p in TEAM_PLAYERS}

# Extra aliases for tricky names
ALIASES = {
    'nicolai hojgaard':  'Nicolai Hojgaard',
    'nicolai højgaard':  'Nicolai Hojgaard',
    'sung-jae im':       'Sung-Jae Im',
    'sungjae im':        'Sung-Jae Im',
    'si woo kim':        'Si Woo Kim',
    'j.j. spaun':        'JJ Spaun',
    'jj spaun':          'JJ Spaun',
    'ludvig aberg':      'Ludvig Aberg',
    'ludvig åberg':      'Ludvig Aberg',
}

def match_player(display_name):
    norm = to_ascii(display_name.strip())
    if norm in PLAYER_LOOKUP:
        return PLAYER_LOOKUP[norm]
    if norm in ALIASES:
        return ALIASES[norm]
    for alias, canon in ALIASES.items():
        if to_ascii(alias) == norm:
            return canon
    return None

def fmt_score(val):
    if val is None:
        return '--'
    try:
        v = int(val)
        if v == 0:
            return 'E'
        return f'+{v}' if v > 0 else str(v)
    except:
        return str(val)

def fmt_round(val):
    if val is None:
        return '--'
    try:
        return str(int(val))
    except:
        return str(val)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.espn.com/golf/leaderboard',
}

def parse(data):
    scores = {}
    current_round = 'R1'

    try:
        event = data['events'][0]
        comp  = event['competitions'][0]

        # Detect current round
        cr = comp.get('status', {}).get('period', 1)
        current_round = f'R{cr}'

        for competitor in comp.get('competitors', []):
            athlete = competitor.get('athlete', {})
            display = athlete.get('displayName', '')
            our_name = match_player(display)
            if not our_name:
                continue

            status = competitor.get('status', {})
            pos_val  = status.get('position', {}).get('displayValue', '--')
            thru     = status.get('thru', None)
            is_live  = thru is not None and thru != 18 and str(thru) != '18'

            # to-par score
            score_val = competitor.get('score', {}).get('displayValue', '--')

            # Cut / WD / DQ
            is_cut = pos_val.upper() in ('CUT', 'WD', 'DQ', 'MDF', 'DNF', 'MC')
            pos_num = None
            if not is_cut:
                m = re.match(r'T?(\d+)', str(pos_val))
                if m:
                    pos_num = int(m.group(1))

            # Round scores from linescores
            linescores = competitor.get('linescores', [])
            def rnd(i):
                if i < len(linescores):
                    v = linescores[i].get('value')
                    return fmt_round(v) if v is not None else '--'
                return '--'

            scores[our_name] = {
                'position': pos_num,
                'cut':      is_cut,
                'live':     is_live,
                'toPar':    score_val,
                'r1': rnd(0), 'r2': rnd(1), 'r3': rnd(2), 'r4': rnd(3),
            }
            print(f"  [ok] {our_name:<22} pos={str(pos_val):<6} "
                  f"toPar={score_val:<5} R1={rnd(0)} R2={rnd(1)}")

    except (KeyError, IndexError) as e:
        print(f"  Parse error: {e}")

    missing = [p for p in TEAM_PLAYERS if p not in scores]
    if missing:
        print(f"  Missing: {missing}")

    return scores, current_round


if __name__ == '__main__':
    try:
        now_bst = datetime.now(BST).strftime('%H:%M BST')
        print(f"[{now_bst}] Fetching ESPN JSON API...")

        resp = requests.get(ESPN_API, headers=HEADERS, timeout=25)
        resp.raise_for_status()

        data = resp.json()
        print(f"  HTTP {resp.status_code} | {len(resp.text):,} bytes")

        # Save raw for debugging
        with open('debug_espn.html', 'w') as f:
            json.dump(data, f, indent=2)

        scores, rnd = parse(data)

        if len(scores) == 0:
            print("  No players matched — aborting.")
            sys.exit(1)

        missing = [p for p in TEAM_PLAYERS if p not in scores]
        print(f"  Round: {rnd} | Matched {len(scores)}/{len(TEAM_PLAYERS)}")
        if missing:
            print(f"  Still missing: {missing}")

        result = {
            'currentRound': rnd,
            'lastUpdated':  datetime.now(BST).strftime('%H:%M BST'),
            'source':       'ESPN JSON API',
            'players':      scores,
        }
        with open('scores.json', 'w') as f:
            json.dump(result, f, indent=2)

        print(f"✓ scores.json written — {rnd} — {len(scores)} players")

    except Exception as e:
        print(f"✗ Fatal: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

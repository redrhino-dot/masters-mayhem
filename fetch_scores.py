#!/usr/bin/env python3
import requests, json, re, sys, unicodedata
from datetime import datetime, timezone, timedelta

ESPN_URL = "https://www.espn.com/golf/leaderboard/_/tournamentId/401811941"
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

SLUG_MAP = {
    'rory-mcilroy':       'Rory McIlroy',
    'tommy-fleetwood':    'Tommy Fleetwood',
    'russell-henley':     'Russell Henley',
    'gary-woodland':      'Gary Woodland',
    'cameron-young':      'Cameron Young',
    'adam-scott':         'Adam Scott',
    'shane-lowry':        'Shane Lowry',
    'justin-thomas':      'Justin Thomas',
    'hideki-matsuyama':   'Hideki Matsuyama',
    'patrick-reed':       'Patrick Reed',
    'collin-morikawa':    'Collin Morikawa',
    'patrick-cantlay':    'Patrick Cantlay',
    'jon-rahm':           'Jon Rahm',
    'jacob-bridgeman':    'Jacob Bridgeman',
    'jake-knapp':         'Jake Knapp',
    'sepp-straka':        'Sepp Straka',
    'ludvig-aberg':       'Ludvig Aberg',
    'jordan-spieth':      'Jordan Spieth',
    'sungjae-im':         'Sung-Jae Im',
    'sung-jae-im':        'Sung-Jae Im',
    'cameron-smith':      'Cameron Smith',
    'scottie-scheffler':  'Scottie Scheffler',
    'chris-gotterup':     'Chris Gotterup',
    'akshay-bhatia':      'Akshay Bhatia',
    'daniel-berger':      'Daniel Berger',
    'jj-spaun':           'JJ Spaun',
    'j.j.-spaun':         'JJ Spaun',
    'justin-rose':        'Justin Rose',
    'nicolai-hojgaard':   'Nicolai Hojgaard',
    'jason-day':          'Jason Day',
    'bryson-dechambeau':  'Bryson DeChambeau',
    'brooks-koepka':      'Brooks Koepka',
    'corey-conners':      'Corey Conners',
    'max-homa':           'Max Homa',
    'xander-schauffele':  'Xander Schauffele',
    'min-woo-lee':        'Min Woo Lee',
    'si-woo-kim':         'Si Woo Kim',
    'harris-english':     'Harris English',
    'matt-fitzpatrick':   'Matt Fitzpatrick',
    'robert-macintyre':   'Robert MacIntyre',
    'tyrrell-hatton':     'Tyrrell Hatton',
    'ryan-gerard':        'Ryan Gerard',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Referer': 'https://www.espn.com/golf/',
}

def to_ascii(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s).strip()

def parse_pos(t):
    t = t.strip().upper()
    if t in ('CUT', 'MC', 'WD', 'DQ', 'MDF', 'DNF', 'RTD'):
        return None, True
    m = re.match(r'T?(\d+)', t)
    return (int(m.group(1)), False) if m else (None, False)

def get_row(html, idx):
    tr_start = html.rfind('<tr', 0, idx)
    tr_end   = html.find('</tr>', idx)
    if tr_start == -1:
        return []
    row = html[tr_start: tr_end + 5 if tr_end != -1 else idx + 4000]
    tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
    return [strip_tags(td) for td in tds]

def extract_scores(html, idx):
    anchor_end = html.find('</a>', idx)
    after = html[anchor_end if anchor_end != -1 else idx:]
    row_end = after.find('</tr>')
    seg = after[:row_end] if row_end != -1 else after[:3000]
    atds = [strip_tags(td) for td in re.findall(r'<td[^>]*>(.*?)</td>', seg, re.DOTALL)]
    def cell(i): return atds[i] if i < len(atds) else '--'
    return cell(0), cell(3), cell(4), cell(5), cell(6)

def detect_round(html):
    m = re.search(r'Round (\d)\s*[-–]\s*(?:Play|In Progress|Suspended|Complete|Tee)', html)
    if m:
        return f'R{m.group(1)}'
    m = re.search(r'Round (\d) -', html)
    if m:
        return f'R{m.group(1)}'
    return 'R1'

def parse(html):
    scores = {}

    # ── Pass 1: slug-based search ──────────────────────────────
    for slug, our_name in SLUG_MAP.items():
        if our_name in scores:
            continue
        idx = html.find(f'/{slug}')
        if idx == -1:
            continue
        tds = get_row(html, idx)
        pos_text = next((t for t in tds if t and t != ' '), None)
        pos, cut = parse_pos(pos_text) if pos_text else (None, False)
        to_par, r1, r2, r3, r4 = extract_scores(html, idx)
        scores[our_name] = {
            'position': pos, 'cut': cut, 'live': False,
            'toPar': to_par, 'r1': r1, 'r2': r2, 'r3': r3, 'r4': r4,
        }
        print(f"  [slug] {our_name:<22} pos={str(pos_text):<6} toPar={to_par:<5} R1={r1} R2={r2}")

    # ── Pass 2: name-text fallback ─────────────────────────────
    # Strips inner tags from anchors so <a><span>Name</span></a> works too
    missing = [p for p in TEAM_PLAYERS if p not in scores]
    if missing:
        print(f"  Fallback for: {missing}")
        fallback_map = {to_ascii(p.split()[-1]): p for p in missing}

        for m in re.finditer(r'<a[^>]*>(.*?)</a>', html, re.DOTALL):
            raw_inner = m.group(1)
            text = strip_tags(raw_inner).strip()
            if not text or len(text) > 50:
                continue
            norm = to_ascii(text)
            for word in norm.split():
                if word not in fallback_map:
                    continue
                our_name = fallback_map[word]
                if our_name in scores:
                    continue
                first = to_ascii(our_name.split()[0])
                if first not in norm:
                    continue
                idx = m.start()
                tds = get_row(html, idx)
                pos_text = next((t for t in tds if t and t != ' '), None)
                pos, cut = parse_pos(pos_text) if pos_text else (None, False)
                to_par, r1, r2, r3, r4 = extract_scores(html, idx)
                scores[our_name] = {
                    'position': pos, 'cut': cut, 'live': False,
                    'toPar': to_par, 'r1': r1, 'r2': r2, 'r3': r3, 'r4': r4,
                }
                print(f"  [name] {our_name:<22} pos={str(pos_text):<6} toPar={to_par:<5} R1={r1} R2={r2}")

    # ── Pass 3: mark anything still missing as CUT ─────────────
    for p in TEAM_PLAYERS:
        if p not in scores:
            print(f"  [cut?] {p} not found in HTML — marking as CUT")
            scores[p] = {
                'position': None, 'cut': True, 'live': False,
                'toPar': '--', 'r1': '--', 'r2': '--', 'r3': '--', 'r4': '--',
            }

    return scores, detect_round(html)

if __name__ == '__main__':
    try:
        now_bst = datetime.now(BST).strftime('%H:%M BST')
        print(f"[{now_bst}] Fetching ESPN leaderboard...")
        resp = requests.get(ESPN_URL, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        html = resp.text
        print(f"  {len(html):,} bytes | HTTP {resp.status_code}")

        with open('debug_espn.html', 'w', encoding='utf-8') as f:
            f.write(html)

        scores, rnd = parse(html)
        matched = [p for p in scores if not scores[p].get('cut')]
        missing  = [p for p in TEAM_PLAYERS if p not in scores]
        print(f"  Round detected: {rnd}")
        print(f"  Active: {len(matched)} | Total: {len(scores)}/{len(TEAM_PLAYERS)}")
        if missing:
            print(f"  Still missing: {missing}")

        result = {
            'currentRound': rnd,
            'lastUpdated':  datetime.now(BST).strftime('%H:%M BST'),
            'source':       'ESPN HTML',
            'players':      scores,
        }
        with open('scores.json', 'w') as f:
            json.dump(result, f, indent=2)
        print(f"✓ scores.json updated — {rnd} — {len(scores)} players")

    except Exception as e:
        print(f"✗ Fatal: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

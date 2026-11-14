#!/usr/bin/env python3
"""MNY local server. All user data stays in data/mny.sqlite3."""
import json
import base64
import hashlib
import re
import os
import sqlite3
import threading
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs, quote

ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get('MNY_DATABASE', ROOT / 'data' / 'mny.sqlite3'))
LOCK = threading.Lock()

def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS players (id TEXT PRIMARY KEY, nickname TEXT NOT NULL, full_name TEXT NOT NULL, photo TEXT NOT NULL)')
    connection.commit()
    return connection

def valid_state(value):
    return (isinstance(value, dict) and isinstance(value.get('players'), list)
            and isinstance(value.get('games'), list)
            and all(isinstance(p, dict) and isinstance(p.get('id'), str)
                    and isinstance(p.get('name'), str) and p['name'].strip()
                    and isinstance(p.get('fullName', ''), str)
                    and isinstance(p.get('photo', ''), str) for p in value['players'])
            and len({p['id'] for p in value['players']}) == len(value['players'])
            and (value.get('active') is None or isinstance(value['active'], dict)))

def broadcast_events(game):
    if not game:
        return []
    events = []
    seats = game.get('seats', [])
    frames = game.get('phaseHistory', [])[:game.get('phaseCursor', len(game.get('phaseHistory', [])))+1]
    states = [frame.get('state', {}) for frame in frames] + [game]
    for i, seat in enumerate(seats):
        if seat.get('alive', True) or not re.match(r'^(Заголосован|Поднят при равенстве)', seat.get('reason') or ''):
            continue
        day = game.get('day', 0)
        for state in states:
            previous = state.get('seats', [])
            if i < len(previous) and previous[i].get('alive') is False and re.match(r'^(Заголосован|Поднят при равенстве)', previous[i].get('reason') or ''):
                day = state.get('day', day)
                break
        events.append({'kind': 'vote', 'number': i+1, 'day': day, 'order': day*10})
    # Use the engine's assigned voting days; do not infer them from elimination time.
    seen = {(event['day'], event['number']) for event in events if event['kind'] == 'vote'}
    for removal in game.get('voteDisqualifications', []):
        index = removal.get('seat')
        if type(index) is not int or not 0 <= index < len(seats):
            continue
        seat = seats[index]
        if seat.get('alive', True) or not re.match(r'^(Удалён|4 фола)', seat.get('reason') or ''):
            continue
        for day in removal.get('targets', []):
            if type(day) is not int or day < 0 or day > game.get('day', -1) or (day, index+1) in seen:
                continue
            events.append({'kind': 'vote', 'number': index+1, 'day': day, 'order': day*10})
            seen.add((day, index+1))
    nights = list(game.get('nights', []))
    if game.get('phase') == 'night' or game.get('phase') == 'finished' and game.get('finishedPhase') == 'night':
        draft = dict(game.get('nightDraft') or {}, day=game.get('day', 0))
        nights = [night for night in nights if night.get('day') != draft['day']] + [draft]
    completed_days = {night.get('day', -1) for night in nights if night.get('day', -1) >= 0}
    if (game.get('ballot') or {}).get('stage') == 'result':
        completed_days.add(game.get('day', 0))
    for day in completed_days:
        if not any(event['kind'] == 'vote' and event['day'] == day for event in events):
            events.append({'kind': 'vote', 'number': 0, 'day': day, 'order': day*10})
    for night in nights:
        day = night.get('day', -1)
        if day < 0:
            continue
        for key, kind, offset in [('kill', 'shot', 1), ('don', 'don', 2), ('sheriff', 'sheriff', 3)]:
            target = night.get(key)
            if type(target) is int and 0 <= target < len(seats) and not (key == 'kill' and night.get('missed')):
                events.append({'kind': kind, 'number': target+1, 'day': day, 'order': day*10+offset})
    return sorted(events, key=lambda event: (event['order'], event['number']))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def allowed_host(self):
        return self.headers.get('Host', '').split(':')[0] in ('localhost', '127.0.0.1')

    def reply(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.allowed_host():
            return self.reply(403, {'error': 'Invalid host'})
        path = unquote(urlsplit(self.path).path)
        if path in ('/api/broadcast', '/api/broadcast-photo'):
            with LOCK, connect() as conn:
                row = conn.execute('SELECT revision,payload FROM state WHERE id=1').fetchone()
            state = json.loads(row[1]) if row else {}
            profiles = {p['id']: p for p in state.get('players', [])}
            if path == '/api/broadcast-photo':
                player_id = parse_qs(urlsplit(self.path).query).get('id', [''])[0]
                photo = profiles.get(player_id, {}).get('photo', '')
                match = re.fullmatch(r'data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=\s]+)', photo)
                if not match:
                    return self.reply(404, {'error': 'Photo not found'})
                try:
                    data = base64.b64decode(match[2], validate=True)
                except ValueError:
                    return self.reply(404, {'error': 'Invalid photo'})
                self.send_response(200)
                self.send_header('Content-Type', 'image/' + match[1])
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(data)
                return
            game = state.get('active')
            demo_summary = None
            if parse_qs(urlsplit(self.path).query).get('demo') == ['game']:
                try:
                    demo = json.loads((ROOT / 'work' / 'broadcast-demo.json').read_text())
                    game = demo['game']
                    demo_summary = demo['summary']
                except (OSError, ValueError, KeyError):
                    return self.reply(404, {'error': 'Demo not found'})
            seats = []
            if game:
                for i, seat in enumerate(game.get('seats', [])[:10]):
                    profile = profiles.get(seat.get('id'), {})
                    photo = profile.get('photo', '')
                    photo_url = '/api/broadcast-photo?id=' + quote(str(seat.get('id', '')), safe='') + '&v=' + hashlib.sha256(photo.encode()).hexdigest()[:16] if photo else None
                    seats.append({'number': i+1, 'name': game.get('guests', {}).get(seat.get('id')) or profile.get('name', ''), 'photo': photo_url, 'role': seat.get('role') if seat.get('roleAssigned') is True or (seat.get('roleAssigned') is None and (seat.get('role') != 'civil' or game.get('phase') != 'setup')) else None, 'alive': seat.get('alive', True), 'reason': seat.get('reason')})
            return self.reply(200, {'gameId': game.get('id') if game else None, 'seats': seats, 'events': broadcast_events(game), 'demoSummary': demo_summary})
        if path == '/api/state':
            with LOCK, connect() as conn:
                row = conn.execute('SELECT revision,payload FROM state WHERE id=1').fetchone()
            return self.reply(200, {'revision': row[0] if row else 0, 'state': json.loads(row[1]) if row else None})
        if any(p.startswith('.') or p in ('data', 'tests', 'work', '__pycache__') for p in Path(path).parts) or path.endswith(('.py', '.sqlite3')):
            return self.reply(404, {'error': 'Not found'})
        super().do_GET()

    def do_PUT(self):
        origin = self.headers.get('Origin')
        if not self.allowed_host() or (origin and origin != 'http://' + self.headers.get('Host', '')):
            return self.reply(403, {'error': 'Invalid origin'})
        if urlsplit(self.path).path != '/api/state':
            return self.reply(404, {'error': 'Not found'})
        if not self.headers.get('Content-Type', '').startswith('application/json'):
            return self.reply(415, {'error': 'JSON required'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 100 * 1024 * 1024:
                return self.reply(413, {'error': 'Invalid size'})
            payload = json.loads(self.rfile.read(size))
            state, revision = payload['state'], payload['revision']
            if not valid_state(state) or not isinstance(revision, int):
                raise ValueError('Invalid state')
            with LOCK, connect() as conn:
                row = conn.execute('SELECT revision FROM state WHERE id=1').fetchone()
                current = row[0] if row else 0
                if revision != current:
                    return self.reply(409, {'error': 'State changed in another window', 'revision': current})
                if row:
                    backup_dir = DATABASE.parent / 'backups'
                    backup_dir.mkdir(exist_ok=True)
                    backup_path = backup_dir / ('mny-' + date.today().isoformat() + '.sqlite3')
                    if not backup_path.exists():
                        with sqlite3.connect(backup_path) as backup:
                            conn.backup(backup)
                conn.execute('INSERT OR REPLACE INTO state VALUES (1,?,?)', (current + 1, json.dumps(state, ensure_ascii=False)))
                conn.execute('DELETE FROM players')
                conn.executemany('INSERT INTO players VALUES (?,?,?,?)', [(p['id'], p['name'], p.get('fullName', ''), p.get('photo', '')) for p in state['players']])
            return self.reply(200, {'revision': current + 1})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self.reply(400, {'error': 'Invalid data'})
        except (sqlite3.Error, OSError):
            return self.reply(500, {'error': 'Database write failed'})

if __name__ == '__main__':
    with connect():
        pass
    port = int(os.environ.get('MNY_PORT', '3000'))
    print(f'MNY: http://localhost:{port} | Database: {DATABASE}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()

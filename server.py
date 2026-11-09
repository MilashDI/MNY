#!/usr/bin/env python3
"""MNY local server. All user data stays in data/mny.sqlite3."""
import json
import os
import sqlite3
import threading
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

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

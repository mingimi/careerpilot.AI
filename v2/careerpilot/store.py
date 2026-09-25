"""Single-user SQLite storage. Outbox is an extension point for future delivery."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, path=None):
        path = path or os.environ.get('CAREERPILOT_DB', str(Path(__file__).resolve().parents[1] / 'data' / 'careerpilot.db'))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, status TEXT DEFAULT 'Not scanned', checked TEXT, UNIQUE(name,url));
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, company_id INTEGER, payload TEXT, first_seen TEXT, last_seen TEXT);
        CREATE TABLE IF NOT EXISTS outbox (job_id TEXT PRIMARY KEY, payload TEXT, created TEXT, acknowledged INTEGER DEFAULT 0);
        ''')
    def profile(self):
        row = self.db.execute('SELECT payload FROM profile WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {}
    def save_profile(self, profile):
        with self.db: self.db.execute('INSERT OR REPLACE INTO profile VALUES (1,?)', (json.dumps(profile),))
    def add_company(self, name, url):
        if not name.strip() and not url.strip(): raise ValueError('Enter a company name or careers URL.')
        from urllib.parse import urlparse
        with self.db: self.db.execute('INSERT OR IGNORE INTO companies(name,url) VALUES (?,?)', (name.strip() or urlparse(url).hostname, url.strip()))
    def companies(self): return [dict(r) for r in self.db.execute('SELECT * FROM companies ORDER BY name')]
    def update_company(self, cid, url):
        with self.db: self.db.execute("UPDATE companies SET url=?,status='Not scanned' WHERE id=?", (url,cid))
    def remove_company(self, cid):
        with self.db:
            self.db.execute('DELETE FROM outbox WHERE job_id IN (SELECT id FROM jobs WHERE company_id=?)', (cid,))
            self.db.execute('DELETE FROM jobs WHERE company_id=?', (cid,))
            self.db.execute('DELETE FROM companies WHERE id=?', (cid,))
    def status(self, cid, message):
        with self.db: self.db.execute('UPDATE companies SET status=?,checked=? WHERE id=?',(message,now(),cid))
    def ingest(self, cid, jobs, profile, threshold=75):
        from .core import match
        new = alerts = 0
        with self.db:
            for job in jobs:
                exists = self.db.execute('SELECT 1 FROM jobs WHERE id=?',(job['id'],)).fetchone()
                stamp = now()
                self.db.execute('INSERT INTO jobs VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,last_seen=excluded.last_seen', (job['id'],cid,json.dumps(job),stamp,stamp))
                if not exists:
                    new += 1
                    result = match(job,profile)
                    if result['score'] >= threshold and result['coverage'] >= 70:
                        payload = dict(job=job, match=result, event='new_high_match_job')
                        self.db.execute('INSERT OR IGNORE INTO outbox(job_id,payload,created) VALUES (?,?,?)',(job['id'],json.dumps(payload),stamp))
                        alerts += 1
        return new, alerts
    def jobs(self):
        return [dict(json.loads(r['payload']), first_seen=r['first_seen'],last_seen=r['last_seen']) for r in self.db.execute('SELECT * FROM jobs ORDER BY first_seen DESC')]
    def alerts(self): return [dict(r, payload=json.loads(r['payload'])) for r in self.db.execute('SELECT * FROM outbox ORDER BY created DESC')]
    def acknowledge(self, jid):
        with self.db: self.db.execute('UPDATE outbox SET acknowledged=1 WHERE job_id=?',(jid,))

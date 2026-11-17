"""Persistent conservative budget reservations. Uncertain requests never free money."""
from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

MAX_BUDGET_MICROUSD = 15_000_000
MODEL = 'gpt-6.1-terra'
MAX_OUTPUT = 4096
MAX_BODY_BYTES = 24000
PRICING = {'model': MODEL, 'verified_date': '2026-11-17',
           'source': 'https://developers.openai.com/api/docs/models/gpt-6.1-terra',
           'input_usd_per_million': '1', 'cached_input_usd_per_million': '0.05',
           'output_usd_per_million': '5',
           'reservation_input_usd_per_million': '3.5',
           'scope': 'Usage-derived estimate, not a billing invoice. Reservations conservatively allow input plus longest standard cache-write pricing and never release unused allowance.'}

class BudgetError(ValueError): pass

class Budget:
    def __init__(self, path, limit_usd='15'):
        amount = Decimal(str(limit_usd))
        if not amount.is_finite() or not 0 < amount <= 15:
            raise BudgetError('Budget must be greater than zero and at most $15')
        self.limit = int(amount * 1_000_000)
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, reservation INTEGER NOT NULL, state TEXT NOT NULL, usage_json TEXT, estimate_micro TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), limit_micro INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (self.limit,))
            # A later invocation may lower the cap, never silently raise it.
            db.execute('UPDATE settings SET limit_micro=MIN(limit_micro,?) WHERE id=1', (self.limit,))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            db.execute('BEGIN IMMEDIATE'); yield db; db.commit()
        except BaseException:
            db.rollback(); raise
        finally:
            db.close()

    @staticmethod
    def reservation(body):
        if len(body) > MAX_BODY_BYTES:
            raise BudgetError('Request exceeds the bounded input budget')
        # UTF-8 bytes conservatively bound content tokens; extra allowance covers
        # fixed request/schema formatting. No tools, images, history or auto retries.
        return int((Decimal(len(body) + 4096) * Decimal('3.5') + MAX_OUTPUT * 5)
                   .to_integral_value(rounding=ROUND_CEILING))

    def reserve(self, body):
        reserve = self.reservation(body)
        with self.connection() as db:
            if db.execute("SELECT 1 FROM requests WHERE state IN ('pending','uncertain')").fetchone():
                raise BudgetError('Unresolved request: stop and reconcile before any more spending')
            limit = db.execute('SELECT limit_micro FROM settings WHERE id=1').fetchone()[0]
            used = db.execute('SELECT COALESCE(SUM(reservation),0) FROM requests').fetchone()[0]
            if used + reserve > limit:
                raise BudgetError('Conservative session spending cap reached')
            key = uuid4().hex
            db.execute('INSERT INTO requests VALUES(?,?,?,NULL,NULL)', (key, reserve, 'pending'))
        return key

    def complete(self, key, usage):
        try:
            inp, out = usage['input_tokens'], usage['output_tokens']
            cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
            if any(type(v) is not int or v < 0 for v in [inp, out, cached]) or cached > inp:
                raise ValueError('Invalid usage')
            estimate = Decimal(inp-cached) + Decimal(cached)*Decimal('.05') + Decimal(out)*5
            with self.connection() as db:
                row = db.execute('SELECT reservation,state FROM requests WHERE id=?', (key,)).fetchone()
                if row is None or row[1] != 'pending': raise BudgetError('Unknown or completed request')
                if inp > MAX_BODY_BYTES+4096 or out > MAX_OUTPUT or estimate > row[0]:
                    raise BudgetError('Usage exceeded reserved bounds; reconciliation required')
                db.execute("UPDATE requests SET state='completed',usage_json=?,estimate_micro=? WHERE id=?",
                           (json.dumps(usage), str(estimate), key))
            return str(estimate/1_000_000)
        except (KeyError, TypeError, ValueError):
            self.uncertain(key)
            raise BudgetError('Missing or unexpected usage; no further calls allowed')

    def uncertain(self, key):
        with self.connection() as db:
            db.execute("UPDATE requests SET state='uncertain' WHERE id=? AND state='pending'", (key,))

    def summary(self):
        with self.connection() as db:
            rows = db.execute('SELECT reservation,state,estimate_micro FROM requests').fetchall()
            limit = db.execute('SELECT limit_micro FROM settings WHERE id=1').fetchone()[0]
        return {'cap_usd': str(Decimal(limit)/1_000_000),
                'reserved_upper_bound_usd': str(Decimal(sum(r[0] for r in rows))/1_000_000),
                'usage_estimate_usd': str(sum((Decimal(r[2]) for r in rows if r[2] is not None), Decimal(0))/1_000_000),
                'requests': len(rows), 'unresolved': sum(r[1] != 'completed' for r in rows), 'pricing': PRICING}

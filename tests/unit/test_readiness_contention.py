"""Readiness must tolerate short SQLite locks and reject persistent failures."""
from contextlib import closing
import sqlite3
import threading
from urllib.parse import quote

from healthcare_quality import showcase


def database(tmp_path):
    path = tmp_path / 'readiness.sqlite'
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE required_table(id INTEGER PRIMARY KEY)')
        db.commit()
    return path


def test_readiness_recovers_after_short_exclusive_lock(tmp_path, monkeypatch):
    path = database(tmp_path)
    connect = sqlite3.connect
    acquired = threading.Event()
    probing = threading.Event()
    errors = []

    def hold_lock():
        try:
            with closing(connect(path, isolation_level=None)) as db:
                db.execute('BEGIN EXCLUSIVE')
                acquired.set()
                if not probing.wait(5):
                    raise AssertionError('Readiness probe did not start')
                # Keep the lock longer than the previous 200 ms probe budget.
                threading.Event().wait(.35)
                db.rollback()
        except BaseException as error:
            errors.append(error)
            acquired.set()

    def observe_probe(*args, **kwargs):
        if kwargs.get('uri') and quote(str(path.resolve())) in args[0]:
            probing.set()
        return connect(*args, **kwargs)

    monkeypatch.setattr(showcase.sqlite3, 'connect', observe_probe)
    worker = threading.Thread(target=hold_lock)
    worker.start()
    try:
        assert acquired.wait(5) and not errors
        result = showcase.readiness([('storage', path, 'required_table')])
        assert result['status'] == 'ready'
        assert result['storage'] == {'storage': 'ready'}
    finally:
        probing.set()
        worker.join(timeout=5)
    assert not worker.is_alive() and not errors


def test_readiness_rejects_persistent_lock_and_recovers_after_release(tmp_path):
    path = database(tmp_path)
    with closing(sqlite3.connect(path, isolation_level=None)) as blocker:
        blocker.execute('BEGIN EXCLUSIVE')
        result = showcase.readiness([('storage', path, 'required_table')])
        assert result['status'] == 'unavailable'
        assert result['storage'] == {'storage': 'unavailable'}
        blocker.rollback()
    assert showcase.readiness([('storage', path, 'required_table')])['status'] == 'ready'

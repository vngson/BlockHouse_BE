"""Consistent SQLite backups. Never copy a live .db file with shutil."""
import logging
import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def snapshot(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError('Backup destination must be new and different from the source.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.partial-' + uuid4().hex)
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=30)) as reader:
            with closing(sqlite3.connect(temporary)) as writer:
                reader.backup(writer, pages=256, sleep=0.05)
                if writer.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Database backup verification failed.')
        # Publish the verified file atomically without overwriting an existing target.
        # Windows rename refuses existing destinations; POSIX link has the same guarantee.
        if os.name == 'nt':
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


class Backups:
    def __init__(self, database, folder, keep=30):
        self.database = Path(database).resolve()
        self.folder = Path(folder).resolve()
        self.keep = max(2, int(keep))
        self.lock = threading.Lock()
        self.last_error = False

    def files(self):
        return sorted(self.folder.glob('BlockHouse-*.sqlite3'), key=lambda p: p.name, reverse=True)

    def status(self):
        files = self.files()
        return dict(folder=str(self.folder), count=len(files), latest=files[0].name if files else None,
                    last_error=self.last_error, retention=self.keep)

    def create(self):
        with self.lock:
            try:
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                output = snapshot(self.database, self.folder / f'BlockHouse-{stamp}.sqlite3')
                for old in self.files()[self.keep:]:
                    old.unlink()
                self.last_error = False
                return output.name
            except Exception:
                self.last_error = True
                logging.exception('BlockHouse backup failed')
                raise

    def start(self, interval_hours=6):
        def run():
            while True:
                try:
                    self.create()
                except Exception:
                    pass  # Logged and exposed in maintenance/status; retry next interval.
                threading.Event().wait(interval_hours * 3600)
        threading.Thread(target=run, daemon=True, name='BlockHouse-backup').start()

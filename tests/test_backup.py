import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from backup import Backups, snapshot
from runtime import import_database


class BackupTests(unittest.TestCase):
    def test_live_wal_backup_keeps_committed_rows_and_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'shop.db'
            with closing(sqlite3.connect(source)) as connection:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('CREATE TABLE orders(id INTEGER PRIMARY KEY, total INTEGER)')
                connection.execute('INSERT INTO orders VALUES(1, 123000)')
                connection.commit()
                output = snapshot(source, Path(folder) / 'copy.db')
                with closing(sqlite3.connect(output)) as backup:
                    self.assertEqual(backup.execute('SELECT total FROM orders').fetchone()[0], 123000)
                    self.assertEqual(backup.execute('PRAGMA quick_check').fetchone()[0], 'ok')

    def test_backup_never_overwrites_existing_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'source.db', Path(folder) / 'target.db'
            with closing(sqlite3.connect(source)) as connection:
                connection.execute('CREATE TABLE example(id INTEGER)')
            target.write_bytes(b'keep this database')
            with self.assertRaises(ValueError): snapshot(source, target)
            self.assertEqual(target.read_bytes(), b'keep this database')

    def test_retention_only_removes_own_verified_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'shop.db'
            with closing(sqlite3.connect(source)) as connection:
                connection.execute('CREATE TABLE example(id INTEGER)')
            manager = Backups(source, Path(folder) / 'backups', keep=2)
            first = manager.create()
            unrelated = manager.folder / 'manual.sqlite3'
            unrelated.write_bytes(b'preserve')
            manager.create(); manager.create()
            self.assertEqual(manager.status()['count'], 2)
            self.assertFalse((manager.folder / first).exists())
            self.assertTrue(unrelated.exists())

    def test_import_validates_schema_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'old.db', Path(folder) / 'new.db'
            with closing(sqlite3.connect(source)) as connection:
                for name in ['NhanVien', 'DichVu', 'DonHang', 'DonHang_DichVu']:
                    connection.execute(f'CREATE TABLE {name}(id INTEGER)')
            before = source.read_bytes()
            import_database(source, target)
            self.assertEqual(before, source.read_bytes())
            target_before = target.read_bytes()
            with self.assertRaises(ValueError): import_database(source, target)
            self.assertEqual(target_before, target.read_bytes())
            with self.assertRaises(ValueError): import_database(Path(folder) / 'missing.db', Path(folder) / 'other.db')

if __name__ == '__main__': unittest.main()

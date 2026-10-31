"""Installed runtime paths, a per-data-directory process lock, and explicit import."""
import logging
import logging.handlers
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from backup import snapshot


def prepare_runtime(folder=None):
    if folder is None:
        return None, None, None  # Preserve developer/legacy DB selection unless explicitly installed.
    directory = Path(folder)
    if not directory.is_absolute():
        raise ValueError('Data directory must be absolute.')
    directory.mkdir(parents=True, exist_ok=True)
    directory = directory.resolve()
    logs = directory / 'logs'
    logs.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(logs / 'backend.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    # Keep the handle open for the entire process. Lock is released even after a crash.
    handle = (directory / 'backend.lock').open('a+b')
    handle.seek(0)
    if os.name == 'nt':
        import msvcrt
        if handle.read(1) == b'':
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return directory, directory / 'BlockHouse.db', handle


def import_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError('Source database does not exist.')
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'NhanVien', 'DichVu', 'DonHang', 'DonHang_DichVu'} <= tables:
            raise ValueError('Not a BlockHouse database.')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Source database verification failed.')
    return snapshot(source, destination)


def install_stop_handler(*servers):
    """Local Windows event allows the installer to drain requests before updating."""
    if os.name != 'nt':
        return
    import ctypes
    import threading
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateEventW(None, True, False, os.getenv('BLOCKHOUSE_STOP_EVENT', 'Local\\BlockHouseBackendStop'))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    def shutdown():
        # Mutate the socket map on Waitress's I/O thread, never the event waiter.
        for server in servers:
            server.close()
        for server in servers:
            server.task_dispatcher.shutdown(timeout=25)
        servers[0].asyncore.close_all(map=servers[0]._map)

    def wait():
        try:
            kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
            servers[0].trigger.pull_trigger(shutdown)
        finally:
            kernel.CloseHandle(handle)
    threading.Thread(target=wait, daemon=True, name='BlockHouse-stop').start()

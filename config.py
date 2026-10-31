import os
import sys

RELEASE_DB_PATH = os.path.join('D:', os.sep, 'Release_BlackHouse', 'BlockHouse.db')


def _local_db_path() -> str:
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'BlockHouse.db')


def _resolve_db_path() -> str:
    if os.path.exists(RELEASE_DB_PATH):
        return RELEASE_DB_PATH
    return _local_db_path()


class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.getenv('BLOCKHOUSE_DB_PATH', _resolve_db_path())
    SQLALCHEMY_TRACK_MODIFICATIONS = False


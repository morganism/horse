import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


def _row_factory(cursor, row):
    return dict(zip([c[0] for c in cursor.description], row))


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = _row_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


@contextmanager
def db_conn(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = get_conn(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_schema(db_path: str) -> None:
    schema_file = Path(__file__).parent / "schema.sql"
    sql = schema_file.read_text()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with db_conn(db_path) as conn:
        conn.executescript(sql)
        conn.execute(
            "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(1, datetime('now'))"
        )


def fetchone(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    cur = conn.execute(sql, params)
    return cur.fetchone()


def fetchall(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    cur = conn.execute(sql, params)
    return cur.fetchall()


def execute(conn: sqlite3.Connection, sql: str, params=()) -> sqlite3.Cursor:
    return conn.execute(sql, params)


def executemany(conn: sqlite3.Connection, sql: str, params_seq) -> None:
    conn.executemany(sql, params_seq)

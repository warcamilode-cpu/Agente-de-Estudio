import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "estudio.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migraciones(conn: sqlite3.Connection) -> None:
    """Aplica cambios de schema sobre una DB existente (ALTER TABLE idempotente)."""
    columnas_topics = {r[1] for r in conn.execute("PRAGMA table_info(topics)")}
    if "parent_id" not in columnas_topics:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN parent_id INTEGER REFERENCES topics(id) ON DELETE CASCADE"
        )


def init_db() -> None:
    schema = SCHEMA_PATH.read_text()
    with get_connection() as conn:
        conn.executescript(schema)
        _migraciones(conn)
        conn.commit()
    print(f"Base de datos inicializada en {DB_PATH}")

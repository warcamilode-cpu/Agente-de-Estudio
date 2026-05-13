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
    """Aplica cambios de schema sobre una DB existente (idempotente)."""
    columnas_topics = {r[1] for r in conn.execute("PRAGMA table_info(topics)")}
    if "parent_id" not in columnas_topics:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN parent_id INTEGER REFERENCES topics(id) ON DELETE CASCADE"
        )

    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "sesiones_chat" not in tablas:
        conn.executescript("""
            CREATE TABLE sesiones_chat (
                session_id     TEXT PRIMARY KEY,
                titulo         TEXT DEFAULT 'Nueva sesión',
                topic_id       INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                creado_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                actualizado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE mensajes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sesiones_chat(session_id) ON DELETE CASCADE,
                rol        TEXT NOT NULL,
                contenido  TEXT NOT NULL,
                creado_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX idx_mensajes_session ON mensajes(session_id);
        """)


def init_db() -> None:
    schema = SCHEMA_PATH.read_text()
    with get_connection() as conn:
        conn.executescript(schema)
        _migraciones(conn)
        conn.commit()
    print(f"Base de datos inicializada en {DB_PATH}")

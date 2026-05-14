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
    if "documentos" not in tablas:
        conn.executescript("""
            CREATE TABLE documentos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id        INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                titulo          TEXT NOT NULL,
                tipo            TEXT NOT NULL,
                archivo_nombre  TEXT NOT NULL,
                archivo_path    TEXT NOT NULL,
                contenido_texto TEXT DEFAULT '',
                tags            TEXT DEFAULT '',
                creado_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_documentos_topic ON documentos(topic_id);
        """)

    if "semestres" not in tablas:
        conn.executescript("""
            CREATE TABLE semestres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                orden INTEGER DEFAULT 0,
                creado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE materias (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                semestre_id   INTEGER NOT NULL REFERENCES semestres(id) ON DELETE CASCADE,
                nombre        TEXT NOT NULL,
                emoji         TEXT DEFAULT '📚',
                color         TEXT DEFAULT '#6366f1',
                docente       TEXT DEFAULT '',
                email_docente TEXT DEFAULT '',
                salon         TEXT DEFAULT '',
                creada_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE clases (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
                fecha      DATE NOT NULL,
                titulo     TEXT NOT NULL,
                temas      TEXT DEFAULT '',
                creada_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE apuntes_cornell (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                clase_id          INTEGER NOT NULL UNIQUE REFERENCES clases(id) ON DELETE CASCADE,
                indicios          TEXT DEFAULT '',
                notas_principales TEXT DEFAULT '',
                resumen           TEXT DEFAULT '',
                actualizado_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE acciones_clase (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                clase_id  INTEGER NOT NULL REFERENCES clases(id) ON DELETE CASCADE,
                tipo      TEXT NOT NULL,
                contenido TEXT NOT NULL,
                resuelto  INTEGER DEFAULT 0,
                creada_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE referencias_rapidas (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
                termino    TEXT NOT NULL,
                definicion TEXT NOT NULL,
                creada_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_materias_semestre   ON materias(semestre_id);
            CREATE INDEX idx_clases_materia      ON clases(materia_id);
            CREATE INDEX idx_acciones_clase      ON acciones_clase(clase_id);
            CREATE INDEX idx_referencias_materia ON referencias_rapidas(materia_id);
        """)

    # Migración: tabla programas (pregrado/posgrado) y programa_id en semestres
    if "programas" not in tablas:
        conn.executescript("""
            CREATE TABLE programas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT NOT NULL,
                tipo        TEXT DEFAULT 'pregrado',
                descripcion TEXT DEFAULT '',
                creado_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    columnas_sem = {r[1] for r in conn.execute("PRAGMA table_info(semestres)")}
    if "programa_id" not in columnas_sem:
        conn.execute(
            "ALTER TABLE semestres ADD COLUMN programa_id INTEGER REFERENCES programas(id) ON DELETE SET NULL"
        )

    # Migración: materia_id en tablas que antes usaban topic_id
    columnas_fc   = {r[1] for r in conn.execute("PRAGMA table_info(flashcards)")}
    columnas_docs = {r[1] for r in conn.execute("PRAGMA table_info(documentos)")}
    columnas_sc   = {r[1] for r in conn.execute("PRAGMA table_info(sesiones_chat)")} if "sesiones_chat" in tablas else set()

    if "materia_id" not in columnas_fc:
        conn.execute("ALTER TABLE flashcards ADD COLUMN materia_id INTEGER REFERENCES materias(id) ON DELETE SET NULL")
    if "materia_id" not in columnas_docs:
        conn.execute("ALTER TABLE documentos ADD COLUMN materia_id INTEGER REFERENCES materias(id) ON DELETE SET NULL")
    if "sesiones_chat" in tablas and "materia_id" not in columnas_sc:
        conn.execute("ALTER TABLE sesiones_chat ADD COLUMN materia_id INTEGER REFERENCES materias(id) ON DELETE SET NULL")

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

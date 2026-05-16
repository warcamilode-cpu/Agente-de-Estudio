"""Fixtures compartidos para los tests de integración."""
import sqlite3
import pytest
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


@pytest.fixture
def db_mem():
    """Base de datos SQLite en memoria con el schema base aplicado."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    # Tabla sesiones_estudio con materia_id (migración)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semestre_id INTEGER,
            nombre TEXT NOT NULL,
            emoji TEXT DEFAULT '📚',
            color TEXT DEFAULT '#6366f1',
            docente TEXT DEFAULT '',
            email_docente TEXT DEFAULT '',
            salon TEXT DEFAULT '',
            creada_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    yield conn
    conn.close()

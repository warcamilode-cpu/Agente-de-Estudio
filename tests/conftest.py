"""Fixtures compartidos para los tests de integración."""
import sqlite3
import pytest
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def _crear_db_mem() -> sqlite3.Connection:
    """Crea una DB en memoria con schema base + migraciones mínimas para tests."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    # Migración: materia_id en sesiones_estudio
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sesiones_estudio)")}
    if "materia_id" not in cols:
        conn.execute("ALTER TABLE sesiones_estudio ADD COLUMN materia_id INTEGER")
    # Migración: materia_id en flashcards
    cols_fc = {r[1] for r in conn.execute("PRAGMA table_info(flashcards)")}
    if "materia_id" not in cols_fc:
        conn.execute("ALTER TABLE flashcards ADD COLUMN materia_id INTEGER")
    conn.commit()
    return conn


@pytest.fixture
def db_mem():
    """Base de datos SQLite en memoria con el schema base aplicado."""
    conn = _crear_db_mem()
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def dashboard_app():
    """App de FastAPI mínima con solo el router de dashboard — sin slowapi."""
    from fastapi import FastAPI
    from routers import dashboard_router
    _app = FastAPI()
    _app.include_router(dashboard_router.router)
    return _app


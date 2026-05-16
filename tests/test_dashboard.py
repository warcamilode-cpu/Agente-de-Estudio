"""Tests de los endpoints del dashboard usando DB en memoria (sin importar main)."""
import pytest
from datetime import date
from contextlib import contextmanager
from unittest.mock import patch
from fastapi.testclient import TestClient
from tests.conftest import _crear_db_mem


@pytest.fixture
def client(dashboard_app):
    return TestClient(dashboard_app)


@pytest.fixture(autouse=True)
def mock_db():
    """Reemplaza db() con una conexión en memoria para todos los tests."""
    conn = _crear_db_mem()

    @contextmanager
    def _fake_db():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with patch("routers.dashboard_router.db", _fake_db):
        yield conn

    conn.close()


def test_resumen_vacio(client):
    resp = client.get("/dashboard/resumen")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_notas"] == 0
    assert data["total_flashcards"] == 0
    assert data["tiempo_estudiado_seg"] == 0


def test_racha_sin_sesiones(client):
    resp = client.get("/dashboard/racha")
    assert resp.status_code == 200
    assert resp.json()["racha_dias"] == 0


def test_registrar_sesion(client):
    resp = client.post("/dashboard/sesion", json={
        "tipo": "flashcards",
        "duracion_seg": 300,
        "cards_revisadas": 10,
        "cards_correctas": 7,
    })
    assert resp.status_code == 201
    assert resp.json()["registrado"] is True


def test_racha_con_sesion_hoy(client, mock_db):
    mock_db.execute(
        "INSERT INTO sesiones_estudio (tipo, duracion_seg) VALUES ('chat', 60)"
    )
    mock_db.commit()
    resp = client.get("/dashboard/racha")
    assert resp.status_code == 200
    assert resp.json()["racha_dias"] >= 1

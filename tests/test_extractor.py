"""Tests de extracción y chunking de texto."""
import pytest
import tempfile
from pathlib import Path
from services.extractor import extraer_texto, chunkear_texto


# ── chunkear_texto ───────────────────────────────────────────────

def test_texto_vacio():
    assert chunkear_texto("") == []


def test_texto_corto_no_divide():
    texto = "Hola mundo"
    chunks = chunkear_texto(texto, tam=500)
    assert chunks == [texto]


def test_texto_largo_se_divide():
    texto = "palabra " * 200
    chunks = chunkear_texto(texto, tam=100, solapamiento=20)
    assert len(chunks) > 1


def test_chunks_no_vacios():
    texto = "a " * 300
    chunks = chunkear_texto(texto, tam=80)
    for chunk in chunks:
        assert chunk.strip() != ""


def test_solapamiento_genera_continuidad():
    texto = "A" * 50 + " " + "B" * 50 + " " + "C" * 50
    chunks = chunkear_texto(texto, tam=60, solapamiento=20)
    assert len(chunks) >= 2


def test_chunk_respeta_tamaño_maximo():
    texto = "x" * 1000
    chunks = chunkear_texto(texto, tam=200, solapamiento=0)
    for chunk in chunks:
        assert len(chunk) <= 210  # margen por cortes en separadores


# ── extraer_texto ────────────────────────────────────────────────

def test_extraer_txt():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("Contenido de prueba TXT")
        ruta = f.name
    resultado = extraer_texto(ruta)
    assert "Contenido de prueba TXT" in resultado
    Path(ruta).unlink()


def test_extraer_md():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write("# Título\n\nPárrafo de prueba.")
        ruta = f.name
    resultado = extraer_texto(ruta)
    assert "Párrafo de prueba" in resultado
    Path(ruta).unlink()


def test_extraer_json():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
        f.write('{"clave": "valor"}')
        ruta = f.name
    resultado = extraer_texto(ruta)
    assert "valor" in resultado
    Path(ruta).unlink()


def test_extraer_formato_no_soportado():
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        ruta = f.name
    resultado = extraer_texto(ruta)
    assert resultado == ""
    Path(ruta).unlink()

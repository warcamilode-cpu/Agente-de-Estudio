"""Generación de embeddings usando bge-m3 via Ollama (1024 dims).

Requiere Ollama corriendo en OLLAMA_BASE_URL con el modelo bge-m3 disponible.
Si la llamada falla, retorna None y el sistema cae en BM25-lite automáticamente.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

MODELO = os.getenv("MODELO_EMBEDDINGS_OLLAMA", "bge-m3")
DIMS = 1024
_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def generar_embedding(texto: str) -> list[float] | None:
    """Retorna vector de 1024 floats via bge-m3, o None si Ollama no está disponible."""
    try:
        import httpx
        resp = httpx.post(
            f"{_OLLAMA_URL}/api/embeddings",
            json={"model": MODELO, "prompt": texto},
            timeout=30.0,
        )
        resp.raise_for_status()
        vec = resp.json().get("embedding")
        if not vec:
            log.warning("Embedder: Ollama respondió pero 'embedding' está vacío.")
            return None
        return vec
    except Exception as e:
        log.warning("Embedder bge-m3 no disponible: %s", e)
        return None


def disponible() -> bool:
    """Verifica si bge-m3 está accesible en Ollama."""
    return generar_embedding("verificación") is not None

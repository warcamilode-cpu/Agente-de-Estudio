"""Generación de embeddings usando bge-m3 via Ollama (1024 dims).

Si Ollama no está disponible o el modelo falla, generar_embedding()
retorna None y el sistema cae automáticamente en BM25-lite.
"""
import logging
import os

import httpx

log = logging.getLogger(__name__)

MODELO = os.getenv("MODELO_EMBED", "bge-m3")
DIMS = 1024
_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def generar_embedding(texto: str) -> list[float] | None:
    """Retorna vector denso de 1024 floats via bge-m3 en Ollama, o None si no disponible."""
    try:
        r = httpx.post(
            f"{_OLLAMA_URL}/api/embed",
            json={"model": MODELO, "input": texto},
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json()
        embeddings = data.get("embeddings")
        if not embeddings:
            return None
        vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
        return vec
    except Exception as e:
        log.warning("Embedder Ollama (%s) no disponible: %s", MODELO, e)
        return None


def disponible() -> bool:
    """Retorna True si Ollama + bge-m3 responden correctamente."""
    return generar_embedding("test") is not None

"""Generación de embeddings usando sentence-transformers (all-MiniLM-L6-v2, 384 dims).

Carga el modelo de forma lazy al primer uso. Si sentence-transformers no está
instalado o el modelo falla, todas las funciones retornan None y el sistema
cae automáticamente en BM25-lite.
"""
from __future__ import annotations

import logging

_model = None
_intentado = False

MODELO = "all-MiniLM-L6-v2"
DIMS = 384


def _cargar_modelo():
    global _model, _intentado
    if _intentado:
        return _model
    _intentado = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODELO)
        logging.info("Embedder: modelo %s cargado correctamente.", MODELO)
    except Exception as e:
        logging.warning("Embedder no disponible (sentence-transformers): %s", e)
        _model = None
    return _model


def generar_embedding(texto: str) -> list[float] | None:
    """Retorna vector normalizado de 384 floats, o None si el modelo no está disponible."""
    modelo = _cargar_modelo()
    if modelo is None:
        return None
    try:
        vec = modelo.encode(texto, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        logging.warning("Error al generar embedding: %s", e)
        return None


def disponible() -> bool:
    return _cargar_modelo() is not None

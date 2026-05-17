"""Cliente para whisper-server (whisper.cpp). Transcribe audio/video a texto.

Requiere whisper-server corriendo en WHISPER_URL (por defecto 127.0.0.1:8765).
Si el servicio no está disponible, lanza una excepción descriptiva.
"""
from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8765")


def transcribir(ruta_audio: str, idioma: str = "es") -> str:
    """Envía el archivo de audio a whisper-server y retorna el texto transcripto."""
    nombre = os.path.basename(ruta_audio)
    log.info("Whisper: iniciando transcripción de '%s' (idioma=%s)", nombre, idioma)
    with open(ruta_audio, "rb") as f:
        resp = httpx.post(
            f"{_WHISPER_URL}/inference",
            files={"file": (nombre, f, "audio/mpeg")},
            data={"language": idioma},
            timeout=httpx.Timeout(10.0, read=600.0),
        )
    resp.raise_for_status()
    data = resp.json()
    segments = data.get("segments", [])
    if segments:
        texto = "\n".join(s["text"].strip() for s in segments if s.get("text", "").strip())
    else:
        texto = data.get("text", "").strip()
    log.info("Whisper: transcripción completada — %d segmentos, %d caracteres", len(segments), len(texto))
    return texto


def disponible() -> bool:
    """Verifica si whisper-server está accesible."""
    try:
        resp = httpx.get(f"{_WHISPER_URL}/", timeout=3.0)
        return resp.status_code < 500
    except Exception:
        return False

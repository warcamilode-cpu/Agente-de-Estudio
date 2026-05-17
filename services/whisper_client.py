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

_MIME = {
    ".mp3":  "audio/mpeg",
    ".mp4":  "video/mp4",
    ".wav":  "audio/wav",
    ".m4a":  "audio/mp4",
    ".ogg":  "audio/ogg",
    ".webm": "audio/webm",
    ".mkv":  "video/x-matroska",
    ".flac": "audio/flac",
}


def transcribir(ruta_audio: str, idioma: str = "es") -> str:
    """Envía el archivo de audio a whisper-server y retorna el texto transcripto."""
    nombre = os.path.basename(ruta_audio)
    ext    = os.path.splitext(nombre)[1].lower()
    mime   = _MIME.get(ext, "application/octet-stream")
    log.info("Whisper: iniciando transcripción de '%s' (idioma=%s, mime=%s)", nombre, idioma, mime)
    with open(ruta_audio, "rb") as f:
        resp = httpx.post(
            f"{_WHISPER_URL}/inference",
            files={"file": (nombre, f, mime)},
            data={"language": idioma, "response_format": "json"},
            timeout=httpx.Timeout(10.0, read=600.0),
        )
    if not resp.is_success:
        cuerpo = resp.text[:500]
        log.error("Whisper-server respondió %d: %s", resp.status_code, cuerpo)
        raise RuntimeError(
            f"whisper-server respondió {resp.status_code}. "
            f"Verificá que el archivo sea WAV/MP3 compatible y que FFmpeg esté instalado. "
            f"Detalle del servidor: {cuerpo}"
        )
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

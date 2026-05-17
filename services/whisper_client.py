"""Cliente para whisper-server (whisper.cpp). Transcribe audio/video a texto.

Requiere whisper-server corriendo en WHISPER_URL (por defecto 127.0.0.1:8765).
Cualquier formato soportado por FFmpeg se convierte a WAV 16 kHz mono antes de
enviarlo, porque whisper.cpp puede estar compilado sin libav (solo WAV nativo).
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8765")


def _convertir_a_wav(ruta_audio: str) -> tuple[str, bool]:
    """
    Convierte el archivo a WAV 16 kHz mono usando FFmpeg.
    Retorna (ruta_wav, es_temporal). Si ya es WAV lo retorna tal cual.
    """
    ext = os.path.splitext(ruta_audio)[1].lower()
    if ext == ".wav":
        return ruta_audio, False

    fd, ruta_wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        resultado = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", ruta_audio,
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                ruta_wav,
            ],
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError:
        os.remove(ruta_wav)
        raise RuntimeError("FFmpeg no encontrado. Instalá ffmpeg para transcribir formatos distintos a WAV.")
    except subprocess.TimeoutExpired:
        os.remove(ruta_wav)
        raise RuntimeError("FFmpeg tardó demasiado convirtiendo el archivo.")

    if resultado.returncode != 0:
        os.remove(ruta_wav)
        stderr = resultado.stderr.decode(errors="replace")[:300]
        raise RuntimeError(f"FFmpeg no pudo convertir el archivo: {stderr}")

    log.info("Whisper: convertido a WAV temporal '%s'", ruta_wav)
    return ruta_wav, True


def transcribir(ruta_audio: str, idioma: str = "es") -> str:
    """Convierte el audio a WAV, lo envía a whisper-server y retorna el texto."""
    nombre_orig = os.path.basename(ruta_audio)
    log.info("Whisper: iniciando transcripción de '%s' (idioma=%s)", nombre_orig, idioma)

    ruta_wav, es_temporal = _convertir_a_wav(ruta_audio)
    try:
        with open(ruta_wav, "rb") as f:
            resp = httpx.post(
                f"{_WHISPER_URL}/inference",
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"language": idioma, "response_format": "json"},
                timeout=httpx.Timeout(10.0, read=600.0),
            )
    finally:
        if es_temporal and os.path.exists(ruta_wav):
            os.remove(ruta_wav)

    if not resp.is_success:
        cuerpo = resp.text[:500]
        log.error("Whisper-server respondió %d: %s", resp.status_code, cuerpo)
        raise RuntimeError(
            f"whisper-server respondió {resp.status_code}. Detalle: {cuerpo}"
        )

    data = resp.json()
    segments = data.get("segments", [])
    if segments:
        texto = "\n".join(s["text"].strip() for s in segments if s.get("text", "").strip())
    else:
        texto = data.get("text", "").strip()
    log.info("Whisper: completado — %d segmentos, %d caracteres", len(segments), len(texto))
    return texto


def disponible() -> bool:
    """Verifica si whisper-server está accesible."""
    try:
        resp = httpx.get(f"{_WHISPER_URL}/", timeout=3.0)
        return resp.status_code < 500
    except Exception:
        return False

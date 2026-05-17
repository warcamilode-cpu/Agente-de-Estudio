"""Cliente de transcripción usando faster-whisper (CTranslate2).

GPU detectada automáticamente; cae a CPU+int8 si CUDA no está disponible.
El modelo se descarga de HuggingFace en el primer uso (~1.5 GB para medium).
Variables de entorno opcionales:
  WHISPER_DEVICE        cuda | cpu          (default: cuda)
  WHISPER_COMPUTE_TYPE  float16 | int8      (default: float16)
  WHISPER_MODEL         tiny|base|small|medium|large-v3  (default: medium)
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_DEVICE       = os.getenv("WHISPER_DEVICE", "cuda")
_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
_MODEL_SIZE   = os.getenv("WHISPER_MODEL", "medium")

_modelo = None


def _cargar_modelo():
    global _modelo
    if _modelo is not None:
        return _modelo
    from faster_whisper import WhisperModel
    log.info(
        "Cargando faster-whisper: modelo=%s device=%s compute=%s",
        _MODEL_SIZE, _DEVICE, _COMPUTE_TYPE,
    )
    try:
        _modelo = WhisperModel(_MODEL_SIZE, device=_DEVICE, compute_type=_COMPUTE_TYPE)
        log.info("faster-whisper listo en %s", _DEVICE)
    except Exception as e:
        log.warning("GPU no disponible (%s) — usando CPU int8", e)
        _modelo = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
    return _modelo


def _convertir_a_wav(ruta_audio: str) -> tuple[str, bool]:
    """Convierte a WAV 16 kHz mono con FFmpeg si no es ya WAV."""
    ext = os.path.splitext(ruta_audio)[1].lower()
    if ext == ".wav":
        return ruta_audio, False
    fd, ruta_wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", ruta_audio, "-ar", "16000", "-ac", "1", "-f", "wav", ruta_wav],
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError:
        os.remove(ruta_wav)
        raise RuntimeError("FFmpeg no encontrado.")
    except subprocess.TimeoutExpired:
        os.remove(ruta_wav)
        raise RuntimeError("FFmpeg tardó demasiado.")
    if result.returncode != 0:
        os.remove(ruta_wav)
        raise RuntimeError(f"FFmpeg: {result.stderr.decode(errors='replace')[:300]}")
    return ruta_wav, True


def transcribir(ruta_audio: str, idioma: str = "es") -> str:
    """Transcribe el audio con faster-whisper (GPU si está disponible)."""
    nombre = os.path.basename(ruta_audio)
    log.info("Whisper: iniciando '%s' (idioma=%s, device=%s)", nombre, idioma, _DEVICE)

    ruta_wav, es_temporal = _convertir_a_wav(ruta_audio)
    try:
        modelo = _cargar_modelo()
        segments, info = modelo.transcribe(
            ruta_wav,
            language=idioma,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        log.info("Idioma detectado: %s (%.0f%%)", info.language, info.language_probability * 100)
        texto = "\n".join(seg.text.strip() for seg in segments if seg.text.strip())
    finally:
        if es_temporal and os.path.exists(ruta_wav):
            os.remove(ruta_wav)

    log.info("Whisper: completado — %d caracteres", len(texto))
    return texto


def disponible() -> bool:
    """Verifica si faster-whisper está instalado."""
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        return True
    except ImportError:
        return False

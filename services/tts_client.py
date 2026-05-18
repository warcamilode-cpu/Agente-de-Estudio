"""Cliente TTS con Kokoro-ONNX.

El modelo se descarga de GitHub Releases en el primer uso (~300 MB).
Variables de entorno:
  KOKORO_VOZ        ID de voz (default: ef_dora)
  KOKORO_VELOCIDAD  velocidad de habla 0.5–2.0 (default: 1.0)
"""
from __future__ import annotations

import io
import logging
import os
import re
import urllib.request
import wave

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_CACHE_DIR   = os.path.expanduser("~/.cache/kokoro-onnx")
_MODEL_PATH  = os.path.join(_CACHE_DIR, "kokoro-v1.0.onnx")
_VOICES_PATH = os.path.join(_CACHE_DIR, "voices-v1.0.bin")
_MODEL_URL   = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
_VOICES_URL  = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"


def _descargar_si_falta(ruta: str, url: str) -> None:
    if os.path.exists(ruta):
        return
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    log.info("Descargando %s…", os.path.basename(url))
    urllib.request.urlretrieve(url, ruta + ".tmp")
    os.rename(ruta + ".tmp", ruta)
    log.info("Descargado: %s (%.1f MB)", os.path.basename(ruta), os.path.getsize(ruta) / 1e6)

_VOZ_DEFAULT = os.getenv("KOKORO_VOZ", "ef_dora")
_VELOCIDAD   = float(os.getenv("KOKORO_VELOCIDAD", "1.0"))
_kokoro      = None

VOCES = [
    {"id": "ef_dora",  "nombre": "Dora (español, femenina)"},
    {"id": "ef_santa", "nombre": "Santa (español, femenina)"},
    {"id": "em_alex",  "nombre": "Alex (español, masculino)"},
    {"id": "af_sky",   "nombre": "Sky (inglés, femenina)"},
    {"id": "af_bella", "nombre": "Bella (inglés, femenina)"},
    {"id": "am_adam",  "nombre": "Adam (inglés, masculino)"},
]

MAX_CHARS_TTS = 4000


def _cargar_modelo():
    global _kokoro
    if _kokoro is not None:
        return _kokoro
    from kokoro_onnx import Kokoro

    log.info("Cargando Kokoro TTS…")
    _descargar_si_falta(_MODEL_PATH,  _MODEL_URL)
    _descargar_si_falta(_VOICES_PATH, _VOICES_URL)
    _kokoro = Kokoro(_MODEL_PATH, _VOICES_PATH)
    log.info("Kokoro TTS listo")
    return _kokoro


def _numpy_a_wav(samples, sample_rate: int) -> bytes:
    import numpy as np
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        pcm = (samples * 32767).astype(np.int16)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _trocear(texto: str, max_chars: int = 500) -> list[str]:
    """Divide texto largo en fragmentos respetando puntuación."""
    if len(texto) <= max_chars:
        return [texto] if texto.strip() else []
    fragmentos: list[str] = []
    for parrafo in texto.split("\n"):
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        if len(parrafo) <= max_chars:
            fragmentos.append(parrafo)
        else:
            oraciones = re.split(r"(?<=[.!?;]) +", parrafo)
            actual = ""
            for o in oraciones:
                if len(actual) + len(o) + 1 <= max_chars:
                    actual = (actual + " " + o).strip()
                else:
                    if actual:
                        fragmentos.append(actual)
                    actual = o[:max_chars]
            if actual:
                fragmentos.append(actual)
    return fragmentos or [texto[:max_chars]]


def sintetizar(texto: str, voz: str | None = None, velocidad: float | None = None, idioma: str = "es") -> bytes:
    """Sintetiza texto a WAV. Retorna bytes del archivo WAV."""
    import numpy as np

    voz       = voz or _VOZ_DEFAULT
    velocidad = velocidad if velocidad is not None else _VELOCIDAD

    if len(texto) > MAX_CHARS_TTS:
        texto = texto[:MAX_CHARS_TTS]
        log.warning("Texto truncado a %d caracteres para TTS.", MAX_CHARS_TTS)

    modelo = _cargar_modelo()
    fragmentos = _trocear(texto.strip())

    all_samples = []
    sample_rate = 24000
    for frag in fragmentos:
        if not frag.strip():
            continue
        try:
            samples, sr = modelo.create(frag, voice=voz, speed=velocidad, lang=idioma)
            all_samples.append(samples)
            sample_rate = sr
        except Exception as e:
            log.warning("TTS falló en fragmento ('%s…'): %s", frag[:40], e)

    if not all_samples:
        raise RuntimeError("No se pudo sintetizar ningún fragmento del texto.")

    combined = np.concatenate(all_samples)
    log.info("TTS completado: %d fragmentos, %d muestras (%.1fs)", len(all_samples), len(combined), len(combined) / sample_rate)
    return _numpy_a_wav(combined, sample_rate)


def disponible() -> bool:
    try:
        import kokoro_onnx  # noqa: F401
        return True
    except ImportError:
        return False

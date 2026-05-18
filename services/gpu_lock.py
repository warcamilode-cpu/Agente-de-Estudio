"""Lock global de GPU para evitar ejecuciones simultáneas de Whisper y Ollama/Qwen3."""
from __future__ import annotations

import os
import threading
import time

import httpx

_lock   = threading.Lock()
_en_uso: str | None = None
_inicio: float | None = None

_OLLAMA_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_MODELO_OLLAMA = os.getenv("MODELO_OLLAMA", "qwen3:8b")

NOMBRES = {
    "whisper": "Transcripción de audio (Whisper)",
    "ollama":  "Chat con IA local (Qwen3)",
}


def adquirir(servicio: str) -> tuple[bool, str]:
    """Intenta adquirir el lock de GPU.

    Retorna (True, "") si lo obtuvo, o (False, mensaje_error) si está ocupada.
    """
    with _lock:
        global _en_uso, _inicio
        if _en_uso is not None and _en_uso != servicio:
            ocupante = NOMBRES.get(_en_uso, _en_uso)
            secs = int(time.time() - (_inicio or time.time()))
            mins = secs // 60
            tiempo = f"{mins}m {secs % 60}s" if mins else f"{secs}s"
            return False, (
                f"La GPU está siendo usada por {ocupante} (hace {tiempo}). "
                "Esperá a que termine antes de iniciar otra operación."
            )
        _en_uso = servicio
        _inicio = time.time()
        return True, ""


def liberar(servicio: str) -> None:
    with _lock:
        global _en_uso, _inicio
        if _en_uso == servicio:
            _en_uso = None
            _inicio = None


def estado() -> dict:
    with _lock:
        return {
            "en_uso": _en_uso,
            "servicio_nombre": NOMBRES.get(_en_uso, _en_uso) if _en_uso else None,
            "segundos": int(time.time() - _inicio) if _inicio else None,
        }


def liberar_ollama() -> None:
    """Pide a Ollama que descargue el modelo de VRAM (keep_alive=0)."""
    try:
        httpx.post(
            f"{_OLLAMA_URL}/api/generate",
            json={"model": _MODELO_OLLAMA, "keep_alive": 0},
            timeout=8.0,
        )
    except Exception:
        pass  # Ollama no está corriendo — no es un error

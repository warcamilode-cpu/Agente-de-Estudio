"""
Abstracción de cliente LLM. El resto del proyecto importa solo este módulo.
Proveedor activo: Claude (Anthropic). Ollama pendiente de integración.
"""
import logging
import os
import time
from typing import Generator
from dotenv import load_dotenv
import anthropic

load_dotenv()

log = logging.getLogger(__name__)

_session_id_ctx: str | None = None  # fijado por el router antes del stream


def registrar_sesion_ctx(session_id: str | None) -> None:
    global _session_id_ctx
    _session_id_ctx = session_id


def _guardar_metrica(tokens_in: int, tokens_out: int, duracion: float) -> None:
    try:
        from database.connection import db
        with db() as conn:
            conn.execute(
                "INSERT INTO metricas_tokens (session_id, modelo, tokens_in, tokens_out, duracion_seg) VALUES (?,?,?,?,?)",
                (_session_id_ctx, _MODELO_CLAUDE, tokens_in, tokens_out, round(duracion, 2)),
            )
    except Exception as e:
        log.warning("No se pudo guardar métrica de tokens: %s", e)

_PROVEEDOR = os.getenv("LLM_PROVEEDOR", "claude")
_MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-haiku-4-5-20251001")
_MAX_TOKENS      = 4096
_MAX_TOKENS_PLAN = 8192

_cliente_claude: anthropic.Anthropic | None = None


def _get_claude() -> anthropic.Anthropic:
    global _cliente_claude
    if _cliente_claude is None:
        _cliente_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _cliente_claude


def preguntar(system_prompt: str, mensajes: list[dict], max_tokens: int | None = None) -> str:
    if _PROVEEDOR == "claude":
        t0 = time.monotonic()
        respuesta = _get_claude().messages.create(
            model=_MODELO_CLAUDE,
            max_tokens=max_tokens or _MAX_TOKENS,
            system=system_prompt,
            messages=mensajes,
        )
        dur = time.monotonic() - t0
        uso = respuesta.usage
        log.info(
            "LLM preguntar | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
            _MODELO_CLAUDE, uso.input_tokens, uso.output_tokens, dur,
        )
        _guardar_metrica(uso.input_tokens, uso.output_tokens, dur)
        return respuesta.content[0].text
    raise NotImplementedError(f"Proveedor '{_PROVEEDOR}' no implementado aún")


def preguntar_stream(system_prompt: str, mensajes: list[dict], max_tokens: int | None = None) -> Generator[str, None, None]:
    if _PROVEEDOR == "claude":
        t0 = time.monotonic()
        with _get_claude().messages.stream(
            model=_MODELO_CLAUDE,
            max_tokens=max_tokens or _MAX_TOKENS,
            system=system_prompt,
            messages=mensajes,
        ) as stream:
            for text in stream.text_stream:
                yield text
            uso = stream.get_final_message().usage
            dur = time.monotonic() - t0
            log.info(
                "LLM stream | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
                _MODELO_CLAUDE, uso.input_tokens, uso.output_tokens, dur,
            )
            _guardar_metrica(uso.input_tokens, uso.output_tokens, dur)
        return
    raise NotImplementedError(f"Proveedor '{_PROVEEDOR}' no implementado aún")

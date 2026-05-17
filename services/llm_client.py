"""
Abstracción de cliente LLM. El resto del proyecto importa solo este módulo.
Proveedores: claude (Anthropic API) u ollama (local — Qwen3 8B Q4_K_M).
Cambiar de proveedor: modificar LLM_PROVEEDOR en .env, sin tocar ningún router.
"""
import json
import logging
import os
import re
import time
from typing import Generator

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_session_id_ctx: str | None = None


def registrar_sesion_ctx(session_id: str | None) -> None:
    global _session_id_ctx
    _session_id_ctx = session_id


_PROVEEDOR    = os.getenv("LLM_PROVEEDOR", "claude")
_MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-haiku-4-5-20251001")
_OLLAMA_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_MODELO_OLLAMA = os.getenv("MODELO_OLLAMA", "qwen3:8b")
_MAX_TOKENS      = 4096
_MAX_TOKENS_PLAN = 8192


def _modelo_activo() -> str:
    return _MODELO_OLLAMA if _PROVEEDOR == "ollama" else _MODELO_CLAUDE


def _guardar_metrica(tokens_in: int, tokens_out: int, duracion: float) -> None:
    try:
        from database.connection import db
        with db() as conn:
            conn.execute(
                "INSERT INTO metricas_tokens (session_id, modelo, tokens_in, tokens_out, duracion_seg) VALUES (?,?,?,?,?)",
                (_session_id_ctx, _modelo_activo(), tokens_in, tokens_out, round(duracion, 2)),
            )
    except Exception as e:
        log.warning("No se pudo guardar métrica de tokens: %s", e)


# ── Claude ────────────────────────────────────────────────────────────────────

_cliente_claude = None


def _get_claude():
    global _cliente_claude
    if _cliente_claude is None:
        import anthropic
        _cliente_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _cliente_claude


# ── Ollama ────────────────────────────────────────────────────────────────────

def _aplicar_modo_think(mensajes: list[dict], modo_think: bool) -> list[dict]:
    """Prepende /think o /no_think al último mensaje de usuario (Qwen3)."""
    prefijo = "/think" if modo_think else "/no_think"
    copia = [dict(m) for m in mensajes]
    for i in range(len(copia) - 1, -1, -1):
        if copia[i].get("role") == "user":
            contenido = copia[i]["content"]
            if isinstance(contenido, str) and not contenido.startswith(("/think", "/no_think")):
                copia[i]["content"] = f"{prefijo}\n{contenido}"
            break
    return copia


def _filtrar_think(gen: Generator[str, None, None]) -> Generator[str, None, None]:
    """Filtra bloques <think>...</think> del stream de Qwen3 en tiempo real."""
    buffer = ""
    in_think = False
    for chunk in gen:
        buffer += chunk
        resultado = ""
        while buffer:
            if in_think:
                end = buffer.find("</think>")
                if end != -1:
                    buffer = buffer[end + 8:]
                    in_think = False
                else:
                    buffer = ""
                    break
            else:
                start = buffer.find("<think>")
                if start != -1:
                    resultado += buffer[:start]
                    buffer = buffer[start + 7:]
                    in_think = True
                else:
                    safe_len = max(0, len(buffer) - 7)
                    resultado += buffer[:safe_len]
                    buffer = buffer[safe_len:]
                    break
        if resultado:
            yield resultado
    if buffer and not in_think:
        yield buffer


def _preguntar_ollama(system_prompt: str, mensajes: list[dict], modo_think: bool) -> str:
    import httpx
    msgs = [{"role": "system", "content": system_prompt}] + _aplicar_modo_think(mensajes, modo_think)
    t0 = time.monotonic()
    resp = httpx.post(
        f"{_OLLAMA_URL}/api/chat",
        json={"model": _MODELO_OLLAMA, "messages": msgs, "stream": False},
        timeout=300.0,
    )
    resp.raise_for_status()
    data = resp.json()
    dur = time.monotonic() - t0
    tokens_in = data.get("prompt_eval_count", 0)
    tokens_out = data.get("eval_count", 0)
    log.info(
        "LLM preguntar | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
        _MODELO_OLLAMA, tokens_in, tokens_out, dur,
    )
    _guardar_metrica(tokens_in, tokens_out, dur)
    texto = data["message"]["content"]
    if "<think>" in texto:
        texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()
    return texto


def _preguntar_stream_ollama(
    system_prompt: str, mensajes: list[dict], modo_think: bool
) -> Generator[str, None, None]:
    import httpx
    msgs = [{"role": "system", "content": system_prompt}] + _aplicar_modo_think(mensajes, modo_think)
    t0 = time.monotonic()
    tokens_in = 0
    tokens_out = 0

    def _raw():
        nonlocal tokens_in, tokens_out
        with httpx.stream(
            "POST",
            f"{_OLLAMA_URL}/api/chat",
            json={"model": _MODELO_OLLAMA, "messages": msgs, "stream": True},
            timeout=httpx.Timeout(10.0, read=300.0),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    tokens_in = data.get("prompt_eval_count", 0)
                    tokens_out = data.get("eval_count", 0)

    yield from _filtrar_think(_raw())
    dur = time.monotonic() - t0
    log.info(
        "LLM stream | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
        _MODELO_OLLAMA, tokens_in, tokens_out, dur,
    )
    _guardar_metrica(tokens_in, tokens_out, dur)


# ── Interfaz pública ──────────────────────────────────────────────────────────

def preguntar(
    system_prompt: str,
    mensajes: list[dict],
    max_tokens: int | None = None,
    modo_think: bool = False,
) -> str:
    if _PROVEEDOR == "ollama":
        return _preguntar_ollama(system_prompt, mensajes, modo_think)
    # Claude
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


def preguntar_stream(
    system_prompt: str,
    mensajes: list[dict],
    max_tokens: int | None = None,
    modo_think: bool = False,
) -> Generator[str, None, None]:
    if _PROVEEDOR == "ollama":
        yield from _preguntar_stream_ollama(system_prompt, mensajes, modo_think)
        return
    # Claude
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

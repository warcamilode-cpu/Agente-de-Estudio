"""
Abstracción de cliente LLM.
Controla con LLM_PROVEEDOR=claude|ollama en .env.
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

_PROVEEDOR     = os.getenv("LLM_PROVEEDOR", "claude")
_MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-haiku-4-5-20251001")
_MODELO_OLLAMA = os.getenv("MODELO_OLLAMA", "qwen3.5:9b")
_OLLAMA_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_MAX_TOKENS      = 4096
_MAX_TOKENS_PLAN = 8192

_session_id_ctx: str | None = None


def registrar_sesion_ctx(session_id: str | None) -> None:
    global _session_id_ctx
    _session_id_ctx = session_id


def _guardar_metrica(tokens_in: int, tokens_out: int, duracion: float) -> None:
    try:
        from database.connection import db
        modelo = _MODELO_CLAUDE if _PROVEEDOR == "claude" else _MODELO_OLLAMA
        with db() as conn:
            conn.execute(
                "INSERT INTO metricas_tokens (session_id, modelo, tokens_in, tokens_out, duracion_seg) VALUES (?,?,?,?,?)",
                (_session_id_ctx, modelo, tokens_in, tokens_out, round(duracion, 2)),
            )
    except Exception as e:
        log.warning("No se pudo guardar métrica de tokens: %s", e)


# ── Claude ────────────────────────────────────────────────────────

import anthropic

_cliente_claude: anthropic.Anthropic | None = None


def _get_claude() -> anthropic.Anthropic:
    global _cliente_claude
    if _cliente_claude is None:
        _cliente_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _cliente_claude


# ── Ollama ────────────────────────────────────────────────────────

def _filtrar_think(texto: str) -> str:
    """Elimina bloques <think>…</think> que genera Qwen3 en modo razonamiento."""
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


def _sanitizar_texto(texto: str) -> str:
    """Elimina tokens de control LLM de una cadena de texto."""
    return re.sub(r"<\|[^|>]{1,30}\|>|</?s>|\[/?INST\]", "", texto, flags=re.IGNORECASE)


def _ollama_preguntar(system: str, mensajes: list[dict], max_tokens: int, modo_think: bool = False) -> str:
    import httpx

    # Qwen3: /think activa razonamiento extendido, /no_think lo desactiva
    think_prefix = "/think\n" if modo_think else "/no_think\n"
    mensajes_mod = [
        {**m, "content": _sanitizar_texto(m["content"])} if isinstance(m.get("content"), str) else m
        for m in mensajes
    ]
    if mensajes_mod and mensajes_mod[0]["role"] == "user":
        mensajes_mod[0] = {**mensajes_mod[0], "content": think_prefix + mensajes_mod[0]["content"]}
    msgs = [{"role": "system", "content": _sanitizar_texto(system)}] + mensajes_mod
    t0 = time.monotonic()
    r = httpx.post(
        f"{_OLLAMA_URL}/api/chat",
        json={"model": _MODELO_OLLAMA, "messages": msgs, "stream": False,
              "options": {"num_predict": max_tokens}},
        timeout=300.0,
    )
    r.raise_for_status()
    dur = time.monotonic() - t0
    data = r.json()
    texto = _filtrar_think(data["message"]["content"])
    uso = data.get("prompt_eval_count", 0)
    sal = data.get("eval_count", 0)
    log.info("LLM Ollama | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
             _MODELO_OLLAMA, uso, sal, dur)
    _guardar_metrica(uso, sal, dur)
    return texto


def _ollama_stream(system: str, mensajes: list[dict], max_tokens: int, modo_think: bool = False) -> Generator[str, None, None]:
    import httpx

    think_prefix = "/think\n" if modo_think else "/no_think\n"
    mensajes_mod = [
        {**m, "content": _sanitizar_texto(m["content"])} if isinstance(m.get("content"), str) else m
        for m in mensajes
    ]
    if mensajes_mod and mensajes_mod[0]["role"] == "user":
        mensajes_mod[0] = {**mensajes_mod[0], "content": think_prefix + mensajes_mod[0]["content"]}
    msgs = [{"role": "system", "content": _sanitizar_texto(system)}] + mensajes_mod
    t0 = time.monotonic()
    tokens_in = tokens_out = 0

    # Buffer para filtrar bloque <think> inicial
    think_buf   = ""
    think_done  = False
    think_found = False

    with httpx.stream(
        "POST",
        f"{_OLLAMA_URL}/api/chat",
        json={"model": _MODELO_OLLAMA, "messages": msgs, "stream": True,
              "options": {"num_predict": max_tokens}},
        timeout=300.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue

            chunk = data.get("message", {}).get("content", "") or ""

            if not think_done:
                think_buf += chunk
                # Si el modelo no abre <think>, saltar directo a streaming
                if not think_found and not think_buf.lstrip().startswith("<think>"):
                    think_done = True
                    if think_buf:
                        yield think_buf
                    think_buf = ""
                elif "</think>" in think_buf:
                    think_done = True
                    after = think_buf.split("</think>", 1)[1]
                    if after.strip():
                        yield after.lstrip("\n")
                    think_buf = ""
                elif "<think>" in think_buf:
                    think_found = True
            else:
                if chunk:
                    yield chunk

            if data.get("done"):
                tokens_in  = data.get("prompt_eval_count", 0)
                tokens_out = data.get("eval_count", 0)
                break

    dur = time.monotonic() - t0
    log.info("LLM Ollama stream | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
             _MODELO_OLLAMA, tokens_in, tokens_out, dur)
    _guardar_metrica(tokens_in, tokens_out, dur)


# ── API pública ───────────────────────────────────────────────────

def preguntar(system_prompt: str, mensajes: list[dict], max_tokens: int | None = None, modo_think: bool = False) -> str:
    mt = max_tokens or _MAX_TOKENS
    if _PROVEEDOR == "ollama":
        return _ollama_preguntar(system_prompt, mensajes, mt, modo_think)

    # Claude (modo_think ignorado — usa extended thinking si se necesita)
    t0 = time.monotonic()
    respuesta = _get_claude().messages.create(
        model=_MODELO_CLAUDE,
        max_tokens=mt,
        system=system_prompt,
        messages=mensajes,
    )
    dur = time.monotonic() - t0
    uso = respuesta.usage
    log.info("LLM Claude | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
             _MODELO_CLAUDE, uso.input_tokens, uso.output_tokens, dur)
    _guardar_metrica(uso.input_tokens, uso.output_tokens, dur)
    return respuesta.content[0].text


def preguntar_stream(system_prompt: str, mensajes: list[dict], max_tokens: int | None = None, modo_think: bool = False) -> Generator[str, None, None]:
    mt = max_tokens or _MAX_TOKENS
    if _PROVEEDOR == "ollama":
        yield from _ollama_stream(system_prompt, mensajes, mt, modo_think)
        return

    # Claude
    t0 = time.monotonic()
    with _get_claude().messages.stream(
        model=_MODELO_CLAUDE,
        max_tokens=mt,
        system=system_prompt,
        messages=mensajes,
    ) as stream:
        for text in stream.text_stream:
            yield text
        uso = stream.get_final_message().usage
        dur = time.monotonic() - t0
        log.info("LLM Claude stream | modelo=%s tokens_in=%d tokens_out=%d dur=%.1fs",
                 _MODELO_CLAUDE, uso.input_tokens, uso.output_tokens, dur)
        _guardar_metrica(uso.input_tokens, uso.output_tokens, dur)

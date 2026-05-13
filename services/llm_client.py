"""
Abstracción de cliente LLM. El resto del proyecto importa solo este módulo.
Proveedor activo: Claude (Anthropic). Ollama pendiente de integración.
"""
import os
from typing import Generator
from dotenv import load_dotenv
import anthropic

load_dotenv()

_PROVEEDOR = os.getenv("LLM_PROVEEDOR", "claude")
_MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-haiku-4-5-20251001")
_MAX_TOKENS = 2048

_cliente_claude: anthropic.Anthropic | None = None


def _get_claude() -> anthropic.Anthropic:
    global _cliente_claude
    if _cliente_claude is None:
        _cliente_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _cliente_claude


def preguntar(system_prompt: str, mensajes: list[dict]) -> str:
    if _PROVEEDOR == "claude":
        respuesta = _get_claude().messages.create(
            model=_MODELO_CLAUDE,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=mensajes,
        )
        return respuesta.content[0].text
    raise NotImplementedError(f"Proveedor '{_PROVEEDOR}' no implementado aún")


def preguntar_stream(system_prompt: str, mensajes: list[dict]) -> Generator[str, None, None]:
    if _PROVEEDOR == "claude":
        with _get_claude().messages.stream(
            model=_MODELO_CLAUDE,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=mensajes,
        ) as stream:
            for text in stream.text_stream:
                yield text
        return
    raise NotImplementedError(f"Proveedor '{_PROVEEDOR}' no implementado aún")

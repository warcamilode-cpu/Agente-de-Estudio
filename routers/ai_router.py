import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services import llm_client, context_builder

router = APIRouter(prefix="/ai", tags=["ai"])

# Historial en memoria: {session_id: [{"role": ..., "content": ...}]}
_historiales: dict[str, list[dict]] = {}
MAX_HISTORIAL = 10  # últimos 10 mensajes (5 turnos)


class ChatIn(BaseModel):
    session_id: str
    message: str
    topic_id: int | None = None


@router.post("/chat/nueva-sesion")
def nueva_sesion():
    session_id = str(uuid.uuid4())
    _historiales[session_id] = []
    return {"session_id": session_id}


@router.post("/chat")
def chat(body: ChatIn):
    historial = _obtener_historial(body.session_id)
    system_prompt = _construir_prompt(body.message, body.topic_id)

    historial.append({"role": "user", "content": body.message})
    respuesta = llm_client.preguntar(system_prompt, historial[-MAX_HISTORIAL:])
    historial.append({"role": "assistant", "content": respuesta})

    return {"respuesta": respuesta, "session_id": body.session_id}


@router.post("/chat/stream")
def chat_stream(body: ChatIn):
    historial = _obtener_historial(body.session_id)
    system_prompt = _construir_prompt(body.message, body.topic_id)

    historial.append({"role": "user", "content": body.message})
    respuesta_acumulada: list[str] = []

    def _generar():
        for chunk in llm_client.preguntar_stream(system_prompt, historial[-MAX_HISTORIAL:]):
            respuesta_acumulada.append(chunk)
            # JSON encode para que saltos de línea dentro del chunk no rompan SSE
            yield f"data: {json.dumps(chunk)}\n\n"
        historial.append({"role": "assistant", "content": "".join(respuesta_acumulada)})
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")


@router.delete("/chat/{session_id}", status_code=204)
def limpiar_sesion(session_id: str):
    _historiales.pop(session_id, None)


@router.get("/chat/{session_id}/historial")
def ver_historial(session_id: str):
    return {"session_id": session_id, "mensajes": _historiales.get(session_id, [])}


def _obtener_historial(session_id: str) -> list[dict]:
    if session_id not in _historiales:
        _historiales[session_id] = []
    return _historiales[session_id]


def _construir_prompt(mensaje: str, topic_id: int | None) -> str:
    contexto, _ = context_builder.buscar_notas(mensaje, topic_id)
    return context_builder.construir_system_prompt(contexto)

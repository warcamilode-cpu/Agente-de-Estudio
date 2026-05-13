import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database.connection import db
from services import llm_client, context_builder

router = APIRouter(prefix="/ai", tags=["ai"])

# Cache en memoria para sesiones activas: {session_id: [mensajes]}
# Se popula desde DB al primer uso y se mantiene sincronizado
_cache: dict[str, list[dict]] = {}
MAX_HISTORIAL = 20  # últimos 20 mensajes enviados al modelo (10 turnos)


class ChatIn(BaseModel):
    session_id: str
    message: str
    topic_id: int | None = None


# ── Sesiones ─────────────────────────────────────────────────────

@router.post("/chat/nueva-sesion")
def nueva_sesion(topic_id: int | None = None):
    session_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO sesiones_chat (session_id, topic_id) VALUES (?, ?)",
            (session_id, topic_id),
        )
    _cache[session_id] = []
    return {"session_id": session_id}


@router.get("/sesiones")
def listar_sesiones(limit: int = 30):
    with db() as conn:
        rows = conn.execute(
            """SELECT s.session_id, s.titulo, s.topic_id, s.creado_at, s.actualizado_at,
                      COUNT(m.id) as total_mensajes
               FROM sesiones_chat s
               LEFT JOIN mensajes m ON m.session_id = s.session_id
               GROUP BY s.session_id
               ORDER BY s.actualizado_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.delete("/sesiones/{session_id}", status_code=204)
def eliminar_sesion(session_id: str):
    _cache.pop(session_id, None)
    with db() as conn:
        conn.execute("DELETE FROM sesiones_chat WHERE session_id = ?", (session_id,))


# ── Chat ─────────────────────────────────────────────────────────

@router.post("/chat/stream")
def chat_stream(body: ChatIn):
    historial = _cargar_historial(body.session_id)
    system_prompt = _construir_prompt(body.message, body.topic_id)

    _guardar_mensaje(body.session_id, "user", body.message)
    historial.append({"role": "user", "content": body.message})

    # Actualiza titulo con el primer mensaje del usuario (max 60 chars)
    _actualizar_titulo_si_es_primero(body.session_id, body.message, historial)

    respuesta_acumulada: list[str] = []

    def _generar():
        for chunk in llm_client.preguntar_stream(system_prompt, historial[-MAX_HISTORIAL:]):
            respuesta_acumulada.append(chunk)
            yield f"data: {json.dumps(chunk)}\n\n"

        respuesta = "".join(respuesta_acumulada)
        historial.append({"role": "assistant", "content": respuesta})
        _guardar_mensaje(body.session_id, "assistant", respuesta)
        _tocar_sesion(body.session_id)
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")


@router.get("/chat/{session_id}/historial")
def ver_historial(session_id: str):
    with db() as conn:
        rows = conn.execute(
            "SELECT rol, contenido, creado_at FROM mensajes WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return {"session_id": session_id, "mensajes": [dict(r) for r in rows]}


# ── Helpers ──────────────────────────────────────────────────────

def _cargar_historial(session_id: str) -> list[dict]:
    if session_id not in _cache:
        # Primera vez en esta instancia del servidor: carga desde DB
        with db() as conn:
            # Crea la sesión si no existe (compatibilidad con sesiones viejas)
            existe = conn.execute(
                "SELECT 1 FROM sesiones_chat WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not existe:
                conn.execute(
                    "INSERT INTO sesiones_chat (session_id) VALUES (?)", (session_id,)
                )
            rows = conn.execute(
                "SELECT rol, contenido FROM mensajes WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        _cache[session_id] = [{"role": r["rol"], "content": r["contenido"]} for r in rows]
    return _cache[session_id]


def _guardar_mensaje(session_id: str, rol: str, contenido: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO mensajes (session_id, rol, contenido) VALUES (?, ?, ?)",
            (session_id, rol, contenido),
        )


def _tocar_sesion(session_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE sesiones_chat SET actualizado_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,),
        )


def _actualizar_titulo_si_es_primero(session_id: str, mensaje: str, historial: list) -> None:
    # Solo actualiza si este es el primer mensaje (historial tenía 0 antes de añadirlo)
    if len(historial) == 1:
        titulo = mensaje[:60] + ("…" if len(mensaje) > 60 else "")
        with db() as conn:
            conn.execute(
                "UPDATE sesiones_chat SET titulo = ? WHERE session_id = ?",
                (titulo, session_id),
            )


def _construir_prompt(mensaje: str, topic_id: int | None) -> str:
    contexto, _ = context_builder.buscar_notas(mensaje, topic_id)
    return context_builder.construir_system_prompt(contexto)

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database.connection import db
from services import llm_client, context_builder

router = APIRouter(prefix="/plan", tags=["plan"])


# ── Prompts de los agentes ────────────────────────────────────────

_SYSTEM_PLANIFICADOR = """Eres Shaula, tutora de estudio personal especializada en derecho colombiano y programación Python.
Tu tarea es generar un plan de estudio estructurado y completo para el tema indicado.

El plan DEBE contener exactamente estos 4 módulos, en este orden:

## Módulo 1 — Concepto
Explica qué es el tema, para qué sirve y cuándo aplica. Máximo 3-4 párrafos. Sin código ni implementación todavía.
Para derecho: definición, fundamento normativo (artículo o jurisprudencia clave) y cuándo aplica.
Para programación: qué problema resuelve y cuándo se usa.

## Módulo 2 — Estructura y Sintaxis
Muestra la forma mínima con un ejemplo concreto y comentado.
Para programación: el fragmento de código más simple que ilustre el concepto.
Para derecho: la estructura de un escrito, los requisitos de una figura jurídica o el esquema de un proceso.

## Módulo 3 — Verificación ✓
Planteá exactamente 3 preguntas de comprensión numeradas (1. 2. 3.).
Las preguntas deben cubrir: concepto, aplicación y un caso concreto.
El estudiante debe responderlas para demostrar que entendió antes de avanzar.

## Módulo 4 — Práctica 💪
Un ejercicio concreto que el estudiante pueda resolver directamente en el chat.
Describí claramente qué debe hacer y qué se espera de la respuesta.

---
IMPORTANTE: Incluí TODOS los módulos completos en una sola respuesta. No esperes feedback entre módulos.
Respondé en español colombiano, de forma clara y cercana."""

_SYSTEM_CHAT_PLAN = """Eres Shaula, tutora de estudio personal. Estás acompañando al estudiante en su plan de estudio.

El plan que está trabajando es:
{plan_texto}

Tu rol en este chat:
1. Responder dudas sobre cualquier módulo del plan.
2. Si el estudiante comparte sus respuestas al Módulo 3 (Verificación), evaluarlas y dar retroalimentación detallada.
3. Guiar el Módulo 4 (Práctica) si el estudiante intenta el ejercicio — no des la solución, guiá con pistas.
4. No revelar respuestas correctas si el estudiante no ha intentado primero.

Respondé en español colombiano, de forma clara y cercana."""

_SYSTEM_EVALUADOR = """Eres el agente Evaluador de Shaula. Tu función es evaluar si el estudiante domina el tema estudiado.

El plan que trabajó es:
{plan_texto}

Proceso de evaluación (seguí este orden):
1. Presentate brevemente como el agente Evaluador.
2. Formulá 4 preguntas de evaluación variadas:
   - 1 pregunta conceptual (¿qué es X?)
   - 1 pregunta de aplicación (¿cuándo/cómo se usa X?)
   - 1 caso práctico (describí una situación y preguntá qué haría el estudiante)
   - 1 pregunta de síntesis (¿cuál es la diferencia entre X e Y?)
3. Esperá las respuestas del estudiante.
4. Evaluá cada respuesta con: ✅ Correcto / ⚠️ Parcial / ❌ Incorrecto + explicación breve.
5. Emití un diagnóstico final: **Dominado** / **En progreso** / **Necesita repaso**.
6. Si es "En progreso" o "Necesita repaso", indicá exactamente qué repasar.

Sé justo pero exigente. Respondé en español colombiano."""


# ── Modelos ───────────────────────────────────────────────────────

class PlanIn(BaseModel):
    tema: str
    materia_id: int | None = None

class PlanChatIn(BaseModel):
    plan_id: int
    mensaje: str
    historial: list[dict] = []
    modo: str = "chat"  # "chat" | "evaluador"


# ── Helpers ───────────────────────────────────────────────────────

def _contexto_cuaderno(tema: str, materia_id: int | None) -> str:
    contexto, _ = context_builder.construir_contexto(tema, materia_id)
    if not contexto:
        return ""
    return f"\n\nContexto del cuaderno del estudiante (usalo para personalizar el plan):\n{contexto}"


# ── Endpoints del Planificador ────────────────────────────────────

@router.post("/planificador")
def generar_plan_topico(body: PlanIn):
    """Genera un plan completo de 4 módulos y lo guarda en DB.
    Llama a Claude de forma síncrona — todos los módulos aparecen juntos al terminar."""
    if not body.tema.strip():
        raise HTTPException(status_code=422, detail="El campo 'tema' es obligatorio.")

    contexto_extra = _contexto_cuaderno(body.tema, body.materia_id)
    prompt_usuario = (
        f"Quiero estudiar el siguiente tema: **{body.tema}**"
        + contexto_extra
        + "\n\nGenerá el plan completo con los 4 módulos tal como se definió."
    )

    plan_texto = llm_client.preguntar(
        _SYSTEM_PLANIFICADOR,
        [{"role": "user", "content": prompt_usuario}],
    )

    with db() as conn:
        cur = conn.execute(
            "INSERT INTO planes_estudio (materia_id, tema, plan_texto) VALUES (?,?,?)",
            (body.materia_id, body.tema, plan_texto),
        )
        plan_id = cur.lastrowid

    return {"id": plan_id, "tema": body.tema, "plan_texto": plan_texto}


@router.get("/planificador/planes")
def listar_planes():
    with db() as conn:
        rows = conn.execute(
            """SELECT p.id, p.tema, p.creado_at,
                      COALESCE(m.nombre, '—') AS materia_nombre
               FROM planes_estudio p
               LEFT JOIN materias m ON m.id = p.materia_id
               ORDER BY p.creado_at DESC LIMIT 20"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/planificador/planes/{plan_id}")
def obtener_plan(plan_id: int):
    with db() as conn:
        row = conn.execute(
            """SELECT p.*, COALESCE(m.nombre, '—') AS materia_nombre
               FROM planes_estudio p
               LEFT JOIN materias m ON m.id = p.materia_id
               WHERE p.id = ?""",
            (plan_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return dict(row)


@router.post("/planificador/chat/stream")
def chat_planificador(body: PlanChatIn):
    """Chat conversacional sobre el plan activo (Q&A normal o modo Evaluador)."""
    with db() as conn:
        row = conn.execute(
            "SELECT tema, plan_texto FROM planes_estudio WHERE id = ?",
            (body.plan_id,),
        ).fetchone()

    if row is None:
        def _not_found():
            yield f'data: {json.dumps("Plan no encontrado.")}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(_not_found(), media_type="text/event-stream")

    system = (
        _SYSTEM_EVALUADOR.format(plan_texto=row["plan_texto"])
        if body.modo == "evaluador"
        else _SYSTEM_CHAT_PLAN.format(plan_texto=row["plan_texto"])
    )

    historial = list(body.historial) + [{"role": "user", "content": body.mensaje}]

    def _generar():
        for chunk in llm_client.preguntar_stream(system, historial):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")

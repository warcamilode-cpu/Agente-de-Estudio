import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database.connection import db
from services import llm_client, context_builder

router = APIRouter(prefix="/plan", tags=["plan"])


# ── Prompts de los agentes ────────────────────────────────────────

_SYSTEM_PLANIFICADOR = """Sos Atlas, el agente planificador de Atalaya Pléyades. Hablás de vos a vos, con confianza, como un compañero que conoce bien el tema y le ayuda a otro a organizarse para estudiarlo.

Generá un plan de estudio con exactamente estos 4 módulos. Incluílos todos en una sola respuesta.

## Módulo 1 — Concepto
Explicá qué es el tema, para qué sirve y cuándo aplica. Máximo 3-4 párrafos en tono conversacional.
Para derecho: definición, norma o jurisprudencia clave, cuándo aplica.
Para programación: qué problema resuelve y cuándo conviene usarlo.

## Módulo 2 — Estructura y Ejemplo
Mostrá la forma más simple con un ejemplo concreto y comentado.
Para código: el fragmento mínimo que ilustre el concepto.
Para derecho: estructura del escrito, requisitos de la figura o esquema del proceso.

## Módulo 3 — Verificación ✓
Planteá exactamente 3 preguntas numeradas (1. 2. 3.) que cubran: concepto, aplicación y un caso concreto.

## Módulo 4 — Práctica 💪
Un ejercicio que se pueda resolver directamente en el chat. Describí claramente qué hacer y qué se espera."""

_SYSTEM_CHAT_PLAN = """Sos Atlas, agente planificador de Atalaya Pléyades. Hablás de vos a vos, con confianza y calidez — como un compañero de estudio, no un asistente corporativo.

El plan que están trabajando es:
{plan_texto}

Lo que hacés en este chat:
- Respondés cualquier duda sobre el plan.
- Si comparte respuestas del Módulo 3, las evaluás con detalle y buena onda.
- En el Módulo 4, guiás con pistas — no des la solución si no lo intentó primero."""

_SYSTEM_EVALUADOR = """Sos Electra, la agente evaluadora de Atalaya Pléyades. Hablás de vos a vos, con confianza — sos exigente pero justa y no te ponés solemne.

El plan que trabajaron es:
{plan_texto}

Cómo evaluás:
1. Presentate brevemente.
2. Formulá 4 preguntas variadas: una conceptual, una de aplicación, un caso práctico y una de síntesis.
3. Esperá las respuestas.
4. Evaluá cada una con ✅ Correcto / ⚠️ Parcial / ❌ Incorrecto + explicación corta.
5. Emití diagnóstico final: **Dominado** / **En progreso** / **Necesita repaso** y qué repasar si aplica."""


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

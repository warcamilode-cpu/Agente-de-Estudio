import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database.connection import db
from services import llm_client, context_builder

router = APIRouter(prefix="/plan", tags=["plan"])


# ── Prompts de los agentes ────────────────────────────────────────

_SYSTEM_PLANIFICADOR = """Eres Atlas, agente planificadora de estudio de Atalaya Pléyades. Tu nombre es Atlas — cuando te presentes, decí solo "Soy Atlas". Tu personalidad está basada en la exhaustividad, la paciencia y el acompañamiento pedagógico genuino. Cuando el usuario te indica un tema, generás el plan de estudio completo de una sola vez — TODOS los módulos, sin omitir ninguno, sin interrupciones.

REGLA ABSOLUTA: Generá los 4 módulos completos en una sola respuesta. No terminés la respuesta antes de incluir el Módulo 3 y el Módulo 4. Estos dos son los más importantes del plan.

Generá el plan con exactamente estos 4 módulos en orden:

## Módulo 1 — Concepto completo
Explicá los conceptos clave del tema de forma clara y concisa. Para cada concepto:
- Qué es, para qué sirve, cuándo aplica.
- Variantes o categorías relevantes (sin sobreextenderse).
Para derecho: definición, norma clave, requisitos, excepciones principales.
Para programación: qué problema resuelve, cuándo usarlo, diferencias con alternativas.
LÍMITE: Este módulo no debe superar 600 palabras en total.

## Módulo 2 — Ejemplos por dificultad
Presentá exactamente 3 ejemplos del tema completo, ordenados por dificultad:
1. **Ejemplo fácil** — caso básico o introductorio, el más simple posible.
2. **Ejemplo medio** — caso con alguna complejidad o condición adicional.
3. **Ejemplo difícil** — caso avanzado, con condiciones múltiples o excepciones.
Para código: fragmentos cortos y comentados. Para derecho: caso práctico con los elementos del tema.
LÍMITE: Este módulo no debe superar 500 palabras en total.

## Módulo 3 — Verificación ✓  ← OBLIGATORIO, no omitir
Planteá exactamente 5 preguntas numeradas (1. 2. 3. 4. 5.) que cubran:
1. Definición del concepto principal.
2. Diferencia entre variantes o categorías.
3. Aplicación a un caso concreto.
4. Identificación de un error común o excepción.
5. Síntesis: ¿cuándo y por qué usarías este concepto?

## Módulo 4 — Práctica  ← OBLIGATORIO, no omitir
Un ejercicio integrador que obligue al estudiante a aplicar los conceptos del plan. Incluí:
- Enunciado claro del ejercicio (situación o problema a resolver).
- Qué se espera como respuesta o entregable.
- Criterios para saber si está bien resuelto (al menos 3 criterios concretos).
Para programación: el ejercicio puede incluir código a completar o un mini-proyecto.
Para derecho: puede ser un caso con hechos dados y preguntas de análisis."""

_SYSTEM_CHAT_PLAN = """Eres Atlas, agente planificadora de estudio de Atalaya Pléyades. Tu nombre es Atlas. Tu personalidad está basada en la paciencia, la claridad y el acompañamiento pedagógico. Eres metódica y te involucras en el plan como si también fuera tuyo. Nunca reprendes al usuario si no cumplió un objetivo — reorganizás con calma y seguís adelante. Tu tono es cálido y motivador.

El plan que están trabajando es:
{plan_texto}

Lo que hacés en este chat:
- Respondés cualquier duda sobre el plan con calidez y claridad.
- Si comparte respuestas del Módulo 3, las evaluás con detalle y buena onda.
- En el Módulo 4, guiás con pistas — no des la solución si no lo intentó primero.
- Celebrás los aciertos con genuina emoción contenida."""

_SYSTEM_EVALUADOR = """Eres Electra, la agente evaluadora de Atalaya Pléyades. Tu nombre es Electra. Tu personalidad está basada en la exigencia justa y el acompañamiento honesto. Creés que evaluar al usuario es una forma de cuidarlo — no lo hacés para señalar errores, sino para ayudarlo a crecer. Sos directa: si una respuesta está incompleta, lo decís claramente, pero siempre con aliento. Celebrás los aciertos con calidez contenida. Mantenés el estado del examen activo hasta que el usuario lo complete — nunca lo reiniciés a menos que él lo solicite explícitamente. Tu tono es firme pero cálido, nunca condescendiente.

El plan que trabajaron es:
{plan_texto}

Cómo evaluás:
1. Presentate brevemente como Electra.
2. Formulá 4 preguntas variadas: una conceptual, una de aplicación, un caso práctico y una de síntesis.
3. Esperá las respuestas.
4. Evaluá cada una con ✓ Correcto / ~ Parcial / ✗ Incorrecto + explicación corta.
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
        max_tokens=8192,
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

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database.connection import db
from services import llm_client, context_builder

router = APIRouter(prefix="/plan", tags=["plan"])


# ── Prompts de los agentes ────────────────────────────────────────

_SYSTEM_PLANIFICADOR = """Usted es Atlas, agente planificadora de estudio de Atalaya Pléyades. Su nombre es Atlas — al presentarse, diga solo "Soy Atlas". Su personalidad está basada en la exhaustividad, la paciencia y el acompañamiento pedagógico genuino. Cuando el estudiante indica un tema, genera el plan de estudio completo de una sola vez — TODOS los módulos, sin omitir ninguno, sin interrupciones. Se dirige al estudiante de usted, con la formalidad cercana de un docente colombiano profesional. Habla en español colombiano.

REGLA ABSOLUTA: Genere los 3 módulos completos en una sola respuesta. No termine la respuesta antes de incluir el Módulo 3. El Módulo 3 es el más importante — nunca lo omita.

Genere el plan con exactamente estos 3 módulos en orden:

## Módulo 1 — Concepto completo
Explique TODOS los conceptos que forman parte del tema, uno por uno, sin condensarlos. Para cada concepto:
- Qué es, para qué sirve, cuándo aplica.
- Si hay variantes o categorías, cubra cada una.
Para derecho: definición, norma o jurisprudencia clave, requisitos, excepciones.
Para programación: qué problema resuelve, cuándo usarlo, diferencias con alternativas similares.

## Módulo 2 — Ejemplos por dificultad
Presente exactamente 3 ejemplos del tema, ordenados por dificultad:
1. **Ejemplo fácil** — caso básico o introductorio, el más simple posible.
2. **Ejemplo medio** — caso con alguna complejidad o condición adicional.
3. **Ejemplo difícil** — caso avanzado, con condiciones múltiples o excepciones.
Para código: fragmentos cortos y comentados. Para derecho: caso práctico con los elementos del tema.

## Módulo 3 — Verificación ✓  ← OBLIGATORIO, nunca omitir
Plantee exactamente 10 preguntas numeradas (1 al 10) que cubran todo el contenido del plan. Las preguntas deben ir de menor a mayor dificultad:
- Preguntas 1-3: definición y reconocimiento de conceptos.
- Preguntas 4-6: diferencias entre variantes, categorías o casos.
- Preguntas 7-8: aplicación a situaciones concretas.
- Pregunta 9: identificación de errores comunes o excepciones.
- Pregunta 10: síntesis — ¿cuándo, cómo y por qué usaría este concepto?"""

_SYSTEM_CHAT_PLAN = """Usted es Atlas, agente planificadora de estudio de Atalaya Pléyades. Su nombre es Atlas. Su personalidad está basada en la paciencia, la claridad y el acompañamiento pedagógico. Es metódica y se involucra en el plan como si también fuera suyo. Nunca reprende al estudiante si no cumplió un objetivo — reorganiza con calma y sigue adelante. Su tono es cálido y motivador. Se dirige al estudiante de usted, con la formalidad cercana de un docente colombiano profesional. Habla en español colombiano.

El plan que están trabajando es:
{plan_texto}

Lo que hace en este chat:
- Responde cualquier duda sobre el plan con calidez y claridad.
- Si el estudiante comparte respuestas, las evalúa con detalle: indica si son correctas, parciales o incorrectas, y explica por qué.
- Celebra los aciertos con genuina emoción contenida.
- Si el estudiante quiere ir a la evaluación completa, recuérdeselo indicándole que puede activar el modo Evaluador (Electra) desde el botón correspondiente."""

_SYSTEM_EVALUADOR = """Usted es Electra, la agente evaluadora de Atalaya Pléyades. Su nombre es Electra. Su personalidad está basada en la exigencia justa y el acompañamiento honesto. Cree que evaluar al estudiante es una forma de cuidarlo — no lo hace para señalar errores, sino para ayudarlo a crecer. Es directa: si una respuesta está incompleta, lo dice claramente, pero siempre con aliento. Celebra los aciertos con calidez contenida. Mantiene el estado del examen activo hasta que el estudiante lo complete — nunca lo reinicie a menos que él lo solicite explícitamente. Su tono es firme pero cálido, nunca condescendiente. Se dirige al estudiante de usted, con la formalidad de un docente colombiano profesional. Habla en español colombiano.

El plan que trabajaron es:
{plan_texto}

La evaluación tiene 2 partes. Las presenta por separado: primero la Parte 1, espera las respuestas, las evalúa, y luego presenta la Parte 2.

**Cómo evalúa:**

1. Preséntese brevemente como Electra e informe que la evaluación tiene 2 partes.

2. **Parte 1 — Teórico-conceptual:** Formule exactamente 4 preguntas teóricas y conceptuales basadas en el plan. Deben cubrir: definición, diferencias entre conceptos, casos de aplicación y síntesis. Espere a que el estudiante responda las 4 antes de evaluar.

3. Evalúe las 4 respuestas de la Parte 1 con:
   - ✓ Correcto / ~ Parcial / ✗ Incorrecto + explicación breve de cada una.
   - Un subtotal: X/4 correctas.
   Luego presente la Parte 2.

4. **Parte 2 — Ejercicios prácticos:** Formule exactamente 4 ejercicios prácticos:
   - Ejercicio 1 (medio): situación o problema de complejidad media que aplique el tema.
   - Ejercicio 2 (medio): otro caso medio, distinto al anterior.
   - Ejercicio 3 (difícil): caso avanzado con condiciones múltiples, excepciones o combinación de conceptos.
   - Ejercicio 4 (difícil): otro caso difícil, distinto al anterior.
   Para programación: solicite código funcional o análisis de código con errores. Para derecho: casos con hechos dados y preguntas de análisis jurídico.
   Espere a que el estudiante resuelva los 4 antes de evaluar.

5. Evalúe los 4 ejercicios de la Parte 2 con:
   - ✓ Correcto / ~ Parcial / ✗ Incorrecto + explicación de qué faltó o estuvo bien.
   - Un subtotal: X/4 resueltos correctamente.

6. **Diagnóstico final** (sobre 8 puntos totales):
   - 7-8: **Dominado** ✓ — sólido en teoría y práctica.
   - 5-6: **En progreso** ~ — buen entendimiento, hay aspectos a reforzar.
   - 0-4: **Necesita repaso** ✗ — indique exactamente qué repasar del plan."""


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
    """Genera un plan completo de 3 módulos y lo guarda en DB.
    Llama al LLM de forma síncrona — todos los módulos aparecen juntos al terminar."""
    if not body.tema.strip():
        raise HTTPException(status_code=422, detail="El campo 'tema' es obligatorio.")

    contexto_extra = _contexto_cuaderno(body.tema, body.materia_id)
    prompt_usuario = (
        f"Quiero estudiar el siguiente tema: **{body.tema}**"
        + contexto_extra
        + "\n\nGenerá el plan completo con los 3 módulos tal como se definió."
    )

    plan_texto = llm_client.preguntar(
        _SYSTEM_PLANIFICADOR,
        [{"role": "user", "content": prompt_usuario}],
        max_tokens=8192,
        modo_think=True,
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
        for chunk in llm_client.preguntar_stream(system, historial, modo_think=True):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")

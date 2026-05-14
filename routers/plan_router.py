import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from database.connection import db
from services import llm_client

router = APIRouter(prefix="/plan", tags=["plan"])


def _recopilar_contexto() -> str:
    with db() as conn:
        materias = conn.execute(
            """SELECT m.id, m.nombre, m.emoji,
                      s.nombre AS semestre_nombre,
                      COALESCE(p.nombre, 'Sin programa') AS prog_nombre
               FROM materias m
               JOIN semestres s ON s.id = m.semestre_id
               LEFT JOIN programas p ON p.id = s.programa_id
               ORDER BY p.nombre, s.nombre, m.nombre"""
        ).fetchall()

        cards_por_materia = conn.execute(
            """SELECT m.nombre AS mat_nombre,
                      COUNT(*) AS total,
                      SUM(CASE WHEN f.proximo_repaso <= date('now') THEN 1 ELSE 0 END) AS pendientes,
                      AVG(f.factor_facilidad) AS ef_prom,
                      AVG(f.repeticiones) AS rep_prom
               FROM flashcards f
               JOIN materias m ON m.id = f.materia_id
               GROUP BY f.materia_id""",
        ).fetchall()

        docs_recientes = conn.execute(
            """SELECT d.titulo, d.tipo, d.tags,
                      COALESCE(m.nombre, 'Sin materia') AS mat_nombre
               FROM documentos d
               LEFT JOIN materias m ON m.id = d.materia_id
               ORDER BY d.creado_at DESC LIMIT 8"""
        ).fetchall()

        total_cards = conn.execute("SELECT COUNT(*) AS n FROM flashcards").fetchone()["n"]
        total_docs  = conn.execute("SELECT COUNT(*) AS n FROM documentos").fetchone()["n"]
        total_clases = conn.execute("SELECT COUNT(*) AS n FROM clases").fetchone()["n"]

    lineas = [
        f"- Clases en el cuaderno: {total_clases}",
        f"- Flashcards totales: {total_cards}",
        f"- Documentos subidos: {total_docs}",
        "",
        "**Materias activas:**",
    ]
    for m in materias:
        lineas.append(f"  - {m['emoji']} {m['nombre']} ({m['prog_nombre']} › {m['semestre_nombre']})")

    if cards_por_materia:
        lineas.append("\n**Estadísticas de flashcards por materia:**")
        for c in cards_por_materia:
            ef = round(c["ef_prom"] or 2.5, 2)
            rep = round(c["rep_prom"] or 0, 1)
            pend = c["pendientes"] or 0
            lineas.append(
                f"  - {c['mat_nombre']}: {c['total']} cards, {pend} pendientes hoy, "
                f"EF promedio={ef} (>2.5=fácil, <2.0=difícil), repeticiones prom={rep}"
            )

    if docs_recientes:
        lineas.append("\n**Documentos y lecturas recientes:**")
        for d in docs_recientes:
            tags = f" [{d['tags']}]" if d["tags"] else ""
            lineas.append(f"  - {d['titulo']} ({d['tipo'].upper()}){tags} — {d['mat_nombre']}")

    return "\n".join(lineas)


def _evaluar_dominio(contexto: str) -> str:
    system_eval = """Eres el agente Evaluador de Shaula, tutora de estudio personal.
Tu única tarea es analizar las estadísticas de estudio del estudiante y emitir un diagnóstico breve de dominio por materia.

Para cada materia con flashcards, evalúa:
1. **Nivel de dominio** (Inicial / En progreso / Dominado) — basado en EF promedio y repeticiones.
   - EF < 2.0 o rep < 2 → Inicial
   - EF 2.0-2.5 o rep 2-4 → En progreso
   - EF > 2.5 y rep ≥ 5 → Dominado
2. **Urgencia de repaso** — cuántas cards están pendientes hoy.
3. **Recomendación puntual** — una línea: qué hacer con esa materia esta semana.

Formato: tabla Markdown con columnas Materia | Dominio | Pendientes hoy | Recomendación.
Luego un párrafo corto con el diagnóstico general (2-3 líneas máximo). Sin saludos ni relleno."""

    resp = llm_client.preguntar(
        system_eval,
        [{"role": "user", "content": f"Aquí están los datos del estudiante:\n\n{contexto}"}],
    )
    return resp


SYSTEM_PLAN = """Eres el agente Planificador de Shaula, tutora de estudio personal.
Recibís un diagnóstico de dominio del agente Evaluador y el inventario de materiales del estudiante.
Tu tarea es crear un plan de estudio para los próximos 7 días.

Reglas:
- Priorizá las materias con más cards pendientes y dominio bajo.
- Bloques de 30-60 min por materia por día. Máximo 2 horas totales/día.
- Incluí días de descanso real (sin estudio o solo repaso ligero de 15 min).
- Para cada bloque indicá: materia, tipo de actividad (repaso de cards, lectura, apuntes Cornell, ejercicio práctico) y objetivo concreto.
- Si hay documentos recientes, incluilos en el plan de lectura.
- Formato: Markdown por día (### Lunes 19 may, etc.) con tabla de bloques por día.
- Sé específico y realista. No prometas más de lo que un estudiante promedio puede cumplir."""


@router.post("/generar")
def generar_plan():
    # Ambas llamadas síncronas a la API corren aquí, en el threadpool de FastAPI,
    # NO dentro del generador SSE (que corre en el event loop y no puede bloquearse).
    contexto = _recopilar_contexto()

    try:
        evaluacion = _evaluar_dominio(contexto)
    except Exception as e:
        evaluacion = f"_(No se pudo evaluar el dominio: {e})_"

    mensaje_plan = (
        f"Diagnóstico de dominio del agente Evaluador:\n\n{evaluacion}\n\n"
        f"---\n\nInventario completo del estudiante:\n\n{contexto}\n\n"
        "Con base en este diagnóstico, generá el plan de estudio para los próximos 7 días."
    )

    def _generar():
        # Envía la evaluación ya calculada
        yield f'data: {json.dumps({"type": "eval", "contenido": evaluacion})}\n\n'
        # Transmite el plan en streaming
        for chunk in llm_client.preguntar_stream(
            SYSTEM_PLAN,
            [{"role": "user", "content": mensaje_plan}],
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")

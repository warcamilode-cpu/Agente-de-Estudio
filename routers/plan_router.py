import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from database.connection import db
from services import llm_client

router = APIRouter(prefix="/plan", tags=["plan"])


def _recopilar_contexto() -> str:
    with db() as conn:
        topics = conn.execute(
            "SELECT id, nombre FROM topics WHERE parent_id IS NULL ORDER BY nombre"
        ).fetchall()

        cards_pendientes = conn.execute(
            """SELECT t.nombre as topic_nombre, COUNT(*) as total
               FROM flashcards f
               LEFT JOIN topics t ON t.id = f.topic_id
               WHERE f.proximo_repaso <= date('now')
               GROUP BY f.topic_id""",
        ).fetchall()

        sesiones_recientes = conn.execute(
            """SELECT tipo, COUNT(*) as total, MAX(iniciada_at) as ultima
               FROM sesiones_estudio
               WHERE iniciada_at >= date('now', '-7 days')
               GROUP BY tipo""",
        ).fetchall()

        total_notas = conn.execute("SELECT COUNT(*) as n FROM notas").fetchone()["n"]
        total_docs = conn.execute("SELECT COUNT(*) as n FROM documentos").fetchone()["n"]
        total_cards = conn.execute("SELECT COUNT(*) as n FROM flashcards").fetchone()["n"]

        docs_recientes = conn.execute(
            """SELECT titulo, tipo, tags FROM documentos
               ORDER BY creado_at DESC LIMIT 5"""
        ).fetchall()

        notas_recientes = conn.execute(
            """SELECT titulo, tags FROM notas
               ORDER BY actualizada_at DESC LIMIT 5"""
        ).fetchall()

    lineas = [
        f"- Total de notas: {total_notas}",
        f"- Total de documentos subidos: {total_docs}",
        f"- Total de flashcards: {total_cards}",
        "",
        "**Cursos registrados:**",
    ]
    for t in topics:
        lineas.append(f"  - {t['nombre']}")

    if cards_pendientes:
        lineas.append("\n**Flashcards pendientes de repaso hoy:**")
        for c in cards_pendientes:
            lineas.append(f"  - {c['topic_nombre'] or 'Sin tema'}: {c['total']} cards")

    if sesiones_recientes:
        lineas.append("\n**Actividad de los últimos 7 días:**")
        for s in sesiones_recientes:
            lineas.append(f"  - {s['tipo']}: {s['total']} sesiones (última: {s['ultima']})")

    if docs_recientes:
        lineas.append("\n**Documentos más recientes:**")
        for d in docs_recientes:
            tags = f" [{d['tags']}]" if d["tags"] else ""
            lineas.append(f"  - {d['titulo']} ({d['tipo'].upper()}){tags}")

    if notas_recientes:
        lineas.append("\n**Apuntes más recientes:**")
        for n in notas_recientes:
            tags = f" [{n['tags']}]" if n["tags"] else ""
            lineas.append(f"  - {n['titulo']}{tags}")

    return "\n".join(lineas)


@router.post("/generar")
def generar_plan():
    contexto = _recopilar_contexto()

    system_prompt = """Eres Shaula, tutora de estudio personal. Tu tarea ahora es actuar como planificadora de estudio.
Con base en el inventario de materiales y actividad reciente del estudiante, generá un plan de estudio para los próximos 7 días.

El plan debe:
1. Priorizar las flashcards pendientes de repaso (son urgentes por el algoritmo SM-2).
2. Identificar qué temas tienen más material acumulado y necesitan sesión de repaso.
3. Sugerir días específicos y bloques de tiempo aproximados (mañana, tarde, noche).
4. Ser realista: no más de 1-2 horas de estudio por día.
5. Incluir al menos una sesión de práctica con ejercicios por cada tema activo.
6. Si hay documentos o lecturas recientes, incluir su revisión en el plan.

Formato de respuesta: Markdown estructurado por día (Lunes a Domingo). Sé específico y accionable."""

    mensaje_usuario = f"""Este es el inventario actual de mi material de estudio:

{contexto}

Generá mi plan de estudio para esta semana."""

    def _generar():
        for chunk in llm_client.preguntar_stream(
            system_prompt,
            [{"role": "user", "content": mensaje_usuario}],
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")

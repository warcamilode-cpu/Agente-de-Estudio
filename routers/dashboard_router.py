from datetime import date
from fastapi import APIRouter, HTTPException
from database.connection import db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/resumen")
def resumen_dia():
    hoy = str(date.today())
    with db() as conn:
        total_notas = conn.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
        total_cards = conn.execute("SELECT COUNT(*) FROM flashcards").fetchone()[0]
        pendientes_hoy = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE proximo_repaso <= ?", (hoy,)
        ).fetchone()[0]
        sesion_hoy = conn.execute(
            """SELECT COALESCE(SUM(duracion_seg),0) AS duracion,
                      COALESCE(SUM(cards_revisadas),0) AS revisadas,
                      COALESCE(SUM(cards_correctas),0) AS correctas
               FROM sesiones_estudio WHERE date(iniciada_at) = ?""",
            (hoy,),
        ).fetchone()
    return {
        "fecha": hoy,
        "total_notas": total_notas,
        "total_flashcards": total_cards,
        "cards_pendientes_hoy": pendientes_hoy,
        "tiempo_estudiado_seg": sesion_hoy["duracion"],
        "cards_revisadas_hoy": sesion_hoy["revisadas"],
        "cards_correctas_hoy": sesion_hoy["correctas"],
    }


@router.get("/racha")
def racha_estudio():
    with db() as conn:
        dias = conn.execute(
            """SELECT DISTINCT date(iniciada_at) AS dia
               FROM sesiones_estudio
               ORDER BY dia DESC""",
        ).fetchall()

    if not dias:
        return {"racha_dias": 0}

    racha = 0
    esperado = date.today()
    for row in dias:
        dia = date.fromisoformat(row["dia"])
        if dia == esperado:
            racha += 1
            esperado = date.fromordinal(esperado.toordinal() - 1)
        else:
            break

    return {"racha_dias": racha}


@router.get("/progreso/{topic_id}")
def progreso_topic(topic_id: int):
    with db() as conn:
        topic = conn.execute("SELECT nombre FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic no encontrado")

        notas = conn.execute(
            "SELECT COUNT(*) FROM notas WHERE topic_id = ?", (topic_id,)
        ).fetchone()[0]
        cards_total = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE topic_id = ?", (topic_id,)
        ).fetchone()[0]
        cards_dominadas = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE topic_id = ? AND intervalo >= 21", (topic_id,)
        ).fetchone()[0]

    return {
        "topic_id": topic_id,
        "topic_nombre": topic["nombre"],
        "notas": notas,
        "flashcards_total": cards_total,
        "flashcards_dominadas": cards_dominadas,
        "porcentaje_dominio": round(cards_dominadas / cards_total * 100, 1) if cards_total else 0,
    }

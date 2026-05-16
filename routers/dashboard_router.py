from datetime import date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.connection import db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SesionIn(BaseModel):
    tipo: str                      # "chat" | "flashcards" | "notas"
    duracion_seg: int
    materia_id: int | None = None
    cards_revisadas: int = 0
    cards_correctas: int = 0


@router.post("/sesion", status_code=201)
def registrar_sesion(body: SesionIn):
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO sesiones_estudio
               (materia_id, tipo, duracion_seg, cards_revisadas, cards_correctas)
               VALUES (?,?,?,?,?)""",
            (body.materia_id, body.tipo, body.duracion_seg,
             body.cards_revisadas, body.cards_correctas),
        )
    return {"id": cur.lastrowid, "registrado": True}


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


@router.post("/backup", status_code=201)
def crear_backup(retener: int = 7):
    """Crea un backup manual de la DB."""
    from services.backup import hacer_backup
    ruta = hacer_backup(retener=retener)
    if ruta is None:
        raise HTTPException(status_code=503, detail="Base de datos no encontrada")
    return {"backup": ruta.name, "ruta": str(ruta)}


@router.get("/metricas")
def metricas_tokens(dias: int = 30):
    """Uso de tokens LLM en los últimos N días."""
    with db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS llamadas,
                      COALESCE(SUM(tokens_in), 0)  AS tokens_in,
                      COALESCE(SUM(tokens_out), 0) AS tokens_out,
                      COALESCE(SUM(duracion_seg), 0) AS duracion_total
               FROM metricas_tokens
               WHERE creado_at >= datetime('now', ? || ' days')""",
            (f"-{dias}",),
        ).fetchone()
    return {
        "periodo_dias": dias,
        "llamadas_llm": row["llamadas"],
        "tokens_entrada": row["tokens_in"],
        "tokens_salida": row["tokens_out"],
        "tokens_total": row["tokens_in"] + row["tokens_out"],
        "duracion_total_seg": round(row["duracion_total"], 1),
    }


@router.get("/progreso/{materia_id}")
def progreso_materia(materia_id: int):
    with db() as conn:
        materia = conn.execute("SELECT nombre, emoji FROM materias WHERE id = ?", (materia_id,)).fetchone()
        if materia is None:
            raise HTTPException(status_code=404, detail="Materia no encontrada")

        clases = conn.execute(
            "SELECT COUNT(*) FROM clases WHERE materia_id = ?", (materia_id,)
        ).fetchone()[0]
        cards_total = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE materia_id = ?", (materia_id,)
        ).fetchone()[0]
        cards_dominadas = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE materia_id = ? AND intervalo >= 21", (materia_id,)
        ).fetchone()[0]
        docs = conn.execute(
            "SELECT COUNT(*) FROM documentos WHERE materia_id = ?", (materia_id,)
        ).fetchone()[0]

    return {
        "materia_id": materia_id,
        "materia_nombre": materia["nombre"],
        "materia_emoji": materia["emoji"] or "📚",
        "clases": clases,
        "documentos": docs,
        "flashcards_total": cards_total,
        "flashcards_dominadas": cards_dominadas,
        "porcentaje_dominio": round(cards_dominadas / cards_total * 100, 1) if cards_total else 0,
    }

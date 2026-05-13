from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database.connection import db
from services.srs_engine import calcular_siguiente_repaso

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


class FlashcardIn(BaseModel):
    pregunta: str
    respuesta: str
    topic_id: int | None = None
    nota_id: int | None = None


class RespuestaIn(BaseModel):
    calificacion: int  # 0-5


@router.get("/pendientes")
def flashcards_pendientes(topic_id: int | None = Query(None)):
    params: list = [str(date.today())]
    where = "proximo_repaso <= ?"
    if topic_id is not None:
        where += " AND topic_id = ?"
        params.append(topic_id)
    with db() as conn:
        rows = conn.execute(
            f"SELECT * FROM flashcards WHERE {where} ORDER BY proximo_repaso",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("")
def listar_flashcards(topic_id: int | None = Query(None)):
    with db() as conn:
        if topic_id is not None:
            rows = conn.execute(
                "SELECT * FROM flashcards WHERE topic_id = ? ORDER BY creada_at DESC", (topic_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM flashcards ORDER BY creada_at DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def crear_flashcard(body: FlashcardIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO flashcards (pregunta, respuesta, topic_id, nota_id) VALUES (?, ?, ?, ?)",
            (body.pregunta, body.respuesta, body.topic_id, body.nota_id),
        )
        row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.post("/{card_id}/respuesta")
def registrar_respuesta(card_id: int, body: RespuestaIn):
    if not (0 <= body.calificacion <= 5):
        raise HTTPException(status_code=422, detail="Calificación debe ser entre 0 y 5")

    with db() as conn:
        card = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
        if card is None:
            raise HTTPException(status_code=404, detail="Flashcard no encontrada")

        nuevo_intervalo, nuevas_reps, nuevo_ef = calcular_siguiente_repaso(
            body.calificacion,
            card["intervalo"],
            card["repeticiones"],
            card["factor_facilidad"],
        )
        proximo = (date.today() + timedelta(days=nuevo_intervalo)).isoformat()

        conn.execute(
            """UPDATE flashcards
               SET intervalo = ?, repeticiones = ?, factor_facilidad = ?, proximo_repaso = ?
               WHERE id = ?""",
            (nuevo_intervalo, nuevas_reps, nuevo_ef, proximo, card_id),
        )
        row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
    return dict(row)


@router.put("/{card_id}")
def editar_flashcard(card_id: int, body: FlashcardIn):
    with db() as conn:
        conn.execute(
            "UPDATE flashcards SET pregunta = ?, respuesta = ?, topic_id = ?, nota_id = ? WHERE id = ?",
            (body.pregunta, body.respuesta, body.topic_id, body.nota_id, card_id),
        )
        row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Flashcard no encontrada")
    return dict(row)


@router.delete("/{card_id}", status_code=204)
def eliminar_flashcard(card_id: int):
    with db() as conn:
        conn.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))

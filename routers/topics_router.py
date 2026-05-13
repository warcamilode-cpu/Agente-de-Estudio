from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.connection import db

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicIn(BaseModel):
    nombre: str
    descripcion: str | None = None
    color: str = "#6366f1"


@router.get("")
def listar_topics():
    with db() as conn:
        rows = conn.execute("SELECT * FROM topics ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def crear_topic(body: TopicIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO topics (nombre, descripcion, color) VALUES (?, ?, ?)",
            (body.nombre, body.descripcion, body.color),
        )
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.put("/{topic_id}")
def editar_topic(topic_id: int, body: TopicIn):
    with db() as conn:
        conn.execute(
            "UPDATE topics SET nombre = ?, descripcion = ?, color = ? WHERE id = ?",
            (body.nombre, body.descripcion, body.color, topic_id),
        )
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Topic no encontrado")
    return dict(row)


@router.delete("/{topic_id}", status_code=204)
def eliminar_topic(topic_id: int):
    with db() as conn:
        conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))

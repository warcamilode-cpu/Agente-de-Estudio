from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.connection import db

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicIn(BaseModel):
    nombre: str
    descripcion: str | None = None
    color: str = "#6366f1"
    parent_id: int | None = None


@router.get("")
def listar_topics():
    with db() as conn:
        rows = conn.execute("SELECT * FROM topics ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


@router.get("/arbol")
def arbol_topics():
    """Retorna cursos con sus temas anidados: [{curso, temas: [...]}, ...]"""
    with db() as conn:
        rows = conn.execute("SELECT * FROM topics ORDER BY nombre").fetchall()
    todos = [dict(r) for r in rows]

    cursos = [t for t in todos if t["parent_id"] is None]
    temas  = [t for t in todos if t["parent_id"] is not None]

    for curso in cursos:
        curso["temas"] = [t for t in temas if t["parent_id"] == curso["id"]]

    # Temas huérfanos (parent_id apunta a un id inexistente) — no deberían ocurrir
    return cursos


@router.post("", status_code=201)
def crear_topic(body: TopicIn):
    if body.parent_id is not None:
        with db() as conn:
            padre = conn.execute("SELECT id, parent_id FROM topics WHERE id = ?", (body.parent_id,)).fetchone()
        if padre is None:
            raise HTTPException(status_code=404, detail="Curso padre no encontrado")
        if padre["parent_id"] is not None:
            raise HTTPException(status_code=422, detail="Solo se permiten dos niveles: curso > tema")

    with db() as conn:
        cur = conn.execute(
            "INSERT INTO topics (nombre, descripcion, color, parent_id) VALUES (?, ?, ?, ?)",
            (body.nombre, body.descripcion, body.color, body.parent_id),
        )
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.put("/{topic_id}")
def editar_topic(topic_id: int, body: TopicIn):
    with db() as conn:
        conn.execute(
            "UPDATE topics SET nombre = ?, descripcion = ?, color = ?, parent_id = ? WHERE id = ?",
            (body.nombre, body.descripcion, body.color, body.parent_id, topic_id),
        )
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Topic no encontrado")
    return dict(row)


@router.delete("/{topic_id}", status_code=204)
def eliminar_topic(topic_id: int):
    with db() as conn:
        conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))

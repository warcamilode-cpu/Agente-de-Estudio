from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.connection import db

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicIn(BaseModel):
    nombre: str
    descripcion: str | None = None
    color: str = "#6366f1"
    parent_id: int | None = None


def _profundidad(topic_id: int, todos: dict) -> int:
    """0 = curso, 1 = bloque, 2 = tema."""
    nivel = 0
    actual = todos.get(topic_id)
    while actual and actual["parent_id"] is not None:
        nivel += 1
        actual = todos.get(actual["parent_id"])
    return nivel


@router.get("")
def listar_topics():
    with db() as conn:
        rows = conn.execute("SELECT * FROM topics ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


@router.get("/arbol")
def arbol_topics():
    """Retorna árbol de 3 niveles: curso → bloques → temas."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM topics ORDER BY nombre").fetchall()
    todos = [dict(r) for r in rows]
    por_id = {t["id"]: t for t in todos}

    cursos  = [t for t in todos if t["parent_id"] is None]
    bloques = [t for t in todos if t["parent_id"] is not None and por_id.get(t["parent_id"], {}).get("parent_id") is None]
    temas   = [t for t in todos if t["parent_id"] is not None and por_id.get(t["parent_id"], {}).get("parent_id") is not None]

    for bloque in bloques:
        bloque["temas"] = [t for t in temas if t["parent_id"] == bloque["id"]]

    for curso in cursos:
        curso["bloques"] = [b for b in bloques if b["parent_id"] == curso["id"]]

    return cursos


@router.post("", status_code=201)
def crear_topic(body: TopicIn):
    if body.parent_id is not None:
        with db() as conn:
            rows = conn.execute("SELECT * FROM topics").fetchall()
        por_id = {r["id"]: dict(r) for r in rows}
        padre  = por_id.get(body.parent_id)
        if padre is None:
            raise HTTPException(status_code=404, detail="Padre no encontrado")
        prof_padre = _profundidad(body.parent_id, por_id)
        if prof_padre >= 2:
            raise HTTPException(status_code=422, detail="Máximo 3 niveles: curso → bloque → tema")

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

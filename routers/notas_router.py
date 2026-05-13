from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database.connection import db

router = APIRouter(prefix="/notas", tags=["notas"])


class NotaIn(BaseModel):
    titulo: str
    contenido: str
    topic_id: int | None = None
    tags: str = ""


@router.get("")
def listar_notas(
    topic_id: int | None = Query(None),
    tags: str | None = Query(None),
    q: str | None = Query(None),
):
    condiciones = []
    params: list = []

    if topic_id is not None:
        condiciones.append("topic_id = ?")
        params.append(topic_id)
    if tags:
        condiciones.append("tags LIKE ?")
        params.append(f"%{tags}%")
    if q:
        condiciones.append("(titulo LIKE ? OR contenido LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    with db() as conn:
        rows = conn.execute(
            f"SELECT id, topic_id, titulo, tags, creada_at, actualizada_at FROM notas {where} ORDER BY actualizada_at DESC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{nota_id}")
def ver_nota(nota_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM notas WHERE id = ?", (nota_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    return dict(row)


@router.post("", status_code=201)
def crear_nota(body: NotaIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO notas (titulo, contenido, topic_id, tags) VALUES (?, ?, ?, ?)",
            (body.titulo, body.contenido, body.topic_id, body.tags),
        )
        row = conn.execute("SELECT * FROM notas WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.put("/{nota_id}")
def editar_nota(nota_id: int, body: NotaIn):
    with db() as conn:
        conn.execute(
            """UPDATE notas
               SET titulo = ?, contenido = ?, topic_id = ?, tags = ?,
                   actualizada_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (body.titulo, body.contenido, body.topic_id, body.tags, nota_id),
        )
        row = conn.execute("SELECT * FROM notas WHERE id = ?", (nota_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    return dict(row)


@router.delete("/{nota_id}", status_code=204)
def eliminar_nota(nota_id: int):
    with db() as conn:
        conn.execute("DELETE FROM notas WHERE id = ?", (nota_id,))

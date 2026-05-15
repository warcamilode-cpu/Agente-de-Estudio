from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.connection import db

router = APIRouter(prefix="/cuaderno", tags=["cuaderno"])


# ── Modelos ───────────────────────────────────────────────────────

class ProgramaIn(BaseModel):
    nombre: str
    tipo: str = "pregrado"
    descripcion: str = ""

class SemestreIn(BaseModel):
    nombre: str
    orden: int = 0
    programa_id: int | None = None

class MateriaIn(BaseModel):
    semestre_id: int
    nombre: str
    emoji: str = "📚"
    color: str = "#6366f1"
    docente: str = ""
    email_docente: str = ""
    salon: str = ""

class MateriaInfoIn(BaseModel):
    docente: str = ""
    email_docente: str = ""
    salon: str = ""

class ClaseIn(BaseModel):
    materia_id: int
    fecha: str
    titulo: str
    temas: str = ""

class CornellIn(BaseModel):
    indicios: str = ""
    notas_principales: str = ""
    resumen: str = ""

class AccionIn(BaseModel):
    clase_id: int
    tipo: str   # '?' | '*' | 'T'
    contenido: str
    resuelto: bool = False

class ReferenciaIn(BaseModel):
    materia_id: int
    clase_id: int | None = None
    termino: str
    definicion: str


# ── Programas ────────────────────────────────────────────────────

@router.get("/programas")
def listar_programas():
    with db() as conn:
        rows = conn.execute("SELECT * FROM programas ORDER BY tipo, nombre").fetchall()
    return [dict(r) for r in rows]

@router.post("/programas", status_code=201)
def crear_programa(body: ProgramaIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO programas (nombre, tipo, descripcion) VALUES (?,?,?)",
            (body.nombre, body.tipo, body.descripcion),
        )
        row = conn.execute("SELECT * FROM programas WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)

@router.put("/programas/{programa_id}")
def editar_programa(programa_id: int, body: ProgramaIn):
    with db() as conn:
        conn.execute(
            "UPDATE programas SET nombre=?, tipo=?, descripcion=? WHERE id=?",
            (body.nombre, body.tipo, body.descripcion, programa_id),
        )
        row = conn.execute("SELECT * FROM programas WHERE id = ?", (programa_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    return dict(row)

@router.delete("/programas/{programa_id}", status_code=204)
def eliminar_programa(programa_id: int):
    with db() as conn:
        conn.execute("DELETE FROM programas WHERE id = ?", (programa_id,))


# ── Semestres ─────────────────────────────────────────────────────

@router.get("/semestres")
def listar_semestres():
    with db() as conn:
        rows = conn.execute("SELECT * FROM semestres ORDER BY orden, creado_at").fetchall()
    return [dict(r) for r in rows]

@router.post("/semestres", status_code=201)
def crear_semestre(body: SemestreIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO semestres (nombre, orden, programa_id) VALUES (?,?,?)",
            (body.nombre, body.orden, body.programa_id),
        )
        row = conn.execute("SELECT * FROM semestres WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)

@router.put("/semestres/{semestre_id}")
def editar_semestre(semestre_id: int, body: SemestreIn):
    with db() as conn:
        conn.execute(
            "UPDATE semestres SET nombre=?, orden=?, programa_id=? WHERE id=?",
            (body.nombre, body.orden, body.programa_id, semestre_id),
        )
        row = conn.execute("SELECT * FROM semestres WHERE id = ?", (semestre_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Semestre no encontrado")
    return dict(row)

@router.delete("/semestres/{semestre_id}", status_code=204)
def eliminar_semestre(semestre_id: int):
    with db() as conn:
        conn.execute("DELETE FROM semestres WHERE id = ?", (semestre_id,))


# ── Materias ──────────────────────────────────────────────────────

@router.get("/semestres/{semestre_id}/materias")
def listar_materias(semestre_id: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM materias WHERE semestre_id = ? ORDER BY nombre",
            (semestre_id,),
        ).fetchall()
    return [dict(r) for r in rows]

@router.post("/materias", status_code=201)
def crear_materia(body: MateriaIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO materias (semestre_id, nombre, emoji, color, docente, email_docente, salon) VALUES (?,?,?,?,?,?,?)",
            (body.semestre_id, body.nombre, body.emoji, body.color, body.docente, body.email_docente, body.salon),
        )
        row = conn.execute("SELECT * FROM materias WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)

@router.put("/materias/{materia_id}")
def editar_materia(materia_id: int, body: MateriaIn):
    with db() as conn:
        conn.execute(
            "UPDATE materias SET nombre=?,emoji=?,color=?,docente=?,email_docente=?,salon=? WHERE id=?",
            (body.nombre, body.emoji, body.color, body.docente, body.email_docente, body.salon, materia_id),
        )
        row = conn.execute("SELECT * FROM materias WHERE id = ?", (materia_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return dict(row)

@router.patch("/materias/{materia_id}/info")
def actualizar_info_materia(materia_id: int, body: MateriaInfoIn):
    with db() as conn:
        conn.execute(
            "UPDATE materias SET docente=?, email_docente=?, salon=? WHERE id=?",
            (body.docente, body.email_docente, body.salon, materia_id),
        )
        row = conn.execute("SELECT * FROM materias WHERE id = ?", (materia_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return dict(row)

@router.delete("/materias/{materia_id}", status_code=204)
def eliminar_materia(materia_id: int):
    with db() as conn:
        conn.execute("DELETE FROM materias WHERE id = ?", (materia_id,))


# ── Clases ────────────────────────────────────────────────────────

@router.get("/materias/{materia_id}/clases")
def listar_clases(materia_id: int):
    with db() as conn:
        rows = conn.execute(
            """SELECT c.*,
                 MAX(CASE WHEN a.tipo='?' AND a.resuelto=0 THEN 1 ELSE 0 END) as tiene_dudas,
                 MAX(CASE WHEN a.tipo='*' THEN 1 ELSE 0 END) as tiene_importantes,
                 MAX(CASE WHEN a.tipo='T' AND a.resuelto=0 THEN 1 ELSE 0 END) as tiene_tareas
               FROM clases c
               LEFT JOIN acciones_clase a ON a.clase_id = c.id
               WHERE c.materia_id = ?
               GROUP BY c.id
               ORDER BY c.fecha DESC""",
            (materia_id,),
        ).fetchall()
    return [dict(r) for r in rows]

@router.post("/clases", status_code=201)
def crear_clase(body: ClaseIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO clases (materia_id, fecha, titulo, temas) VALUES (?,?,?,?)",
            (body.materia_id, body.fecha, body.titulo, body.temas),
        )
        clase_id = cur.lastrowid
        # Crea el apunte Cornell vacío automáticamente
        conn.execute(
            "INSERT INTO apuntes_cornell (clase_id) VALUES (?)", (clase_id,)
        )
        row = conn.execute("SELECT * FROM clases WHERE id = ?", (clase_id,)).fetchone()
    return dict(row)

@router.put("/clases/{clase_id}")
def editar_clase(clase_id: int, body: ClaseIn):
    with db() as conn:
        conn.execute(
            "UPDATE clases SET fecha=?, titulo=?, temas=? WHERE id=?",
            (body.fecha, body.titulo, body.temas, clase_id),
        )
        row = conn.execute("SELECT * FROM clases WHERE id = ?", (clase_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    return dict(row)

@router.delete("/clases/{clase_id}", status_code=204)
def eliminar_clase(clase_id: int):
    with db() as conn:
        conn.execute("DELETE FROM clases WHERE id = ?", (clase_id,))


# ── Apuntes Cornell ───────────────────────────────────────────────

@router.get("/clases/{clase_id}/apuntes")
def obtener_apuntes(clase_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM apuntes_cornell WHERE clase_id = ?", (clase_id,)
        ).fetchone()
    if row is None:
        return {"clase_id": clase_id, "indicios": "", "notas_principales": "", "resumen": ""}
    return dict(row)

@router.put("/clases/{clase_id}/apuntes")
def guardar_apuntes(clase_id: int, body: CornellIn):
    with db() as conn:
        existe = conn.execute(
            "SELECT id FROM apuntes_cornell WHERE clase_id = ?", (clase_id,)
        ).fetchone()
        if existe:
            conn.execute(
                """UPDATE apuntes_cornell
                   SET indicios=?, notas_principales=?, resumen=?, actualizado_at=CURRENT_TIMESTAMP
                   WHERE clase_id=?""",
                (body.indicios, body.notas_principales, body.resumen, clase_id),
            )
        else:
            conn.execute(
                "INSERT INTO apuntes_cornell (clase_id,indicios,notas_principales,resumen) VALUES (?,?,?,?)",
                (clase_id, body.indicios, body.notas_principales, body.resumen),
            )
        row = conn.execute("SELECT * FROM apuntes_cornell WHERE clase_id = ?", (clase_id,)).fetchone()
    return dict(row)


# ── Acciones ──────────────────────────────────────────────────────

@router.get("/clases/{clase_id}/acciones")
def listar_acciones(clase_id: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM acciones_clase WHERE clase_id = ? ORDER BY tipo, creada_at",
            (clase_id,),
        ).fetchall()
    return [dict(r) for r in rows]

@router.post("/acciones", status_code=201)
def crear_accion(body: AccionIn):
    if body.tipo not in ("?", "*", "T"):
        raise HTTPException(status_code=422, detail="Tipo debe ser '?', '*' o 'T'")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO acciones_clase (clase_id, tipo, contenido, resuelto) VALUES (?,?,?,?)",
            (body.clase_id, body.tipo, body.contenido, int(body.resuelto)),
        )
        row = conn.execute("SELECT * FROM acciones_clase WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)

@router.patch("/acciones/{accion_id}/toggle", status_code=200)
def toggle_accion(accion_id: int):
    with db() as conn:
        conn.execute(
            "UPDATE acciones_clase SET resuelto = 1 - resuelto WHERE id = ?", (accion_id,)
        )
        row = conn.execute("SELECT * FROM acciones_clase WHERE id = ?", (accion_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Acción no encontrada")
    return dict(row)

@router.delete("/acciones/{accion_id}", status_code=204)
def eliminar_accion(accion_id: int):
    with db() as conn:
        conn.execute("DELETE FROM acciones_clase WHERE id = ?", (accion_id,))


# ── Referencias rápidas ───────────────────────────────────────────

@router.get("/clases/{clase_id}/referencias")
def listar_referencias_clase(clase_id: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM referencias_rapidas WHERE clase_id = ? ORDER BY termino",
            (clase_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/materias/{materia_id}/referencias")
def listar_referencias(materia_id: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM referencias_rapidas WHERE materia_id = ? ORDER BY termino",
            (materia_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/referencias", status_code=201)
def crear_referencia(body: ReferenciaIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO referencias_rapidas (materia_id, clase_id, termino, definicion) VALUES (?,?,?,?)",
            (body.materia_id, body.clase_id, body.termino, body.definicion),
        )
        row = conn.execute("SELECT * FROM referencias_rapidas WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)

@router.put("/referencias/{ref_id}")
def editar_referencia(ref_id: int, body: ReferenciaIn):
    with db() as conn:
        conn.execute(
            "UPDATE referencias_rapidas SET termino=?, definicion=? WHERE id=?",
            (body.termino, body.definicion, ref_id),
        )
        row = conn.execute("SELECT * FROM referencias_rapidas WHERE id = ?", (ref_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Referencia no encontrada")
    return dict(row)

@router.delete("/referencias/{ref_id}", status_code=204)
def eliminar_referencia(ref_id: int):
    with db() as conn:
        conn.execute("DELETE FROM referencias_rapidas WHERE id = ?", (ref_id,))


# ── Vista completa: programas → semestres → materias ─────────────

@router.get("/estructura")
def estructura_completa():
    with db() as conn:
        programas = [dict(r) for r in conn.execute(
            "SELECT * FROM programas ORDER BY tipo, nombre"
        ).fetchall()]
        semestres = [dict(r) for r in conn.execute(
            "SELECT * FROM semestres ORDER BY programa_id, orden, creado_at"
        ).fetchall()]
        materias = [dict(r) for r in conn.execute(
            "SELECT * FROM materias ORDER BY nombre"
        ).fetchall()]

    # Materias por semestre
    por_semestre: dict[int, list] = {s["id"]: [] for s in semestres}
    for m in materias:
        if m["semestre_id"] in por_semestre:
            por_semestre[m["semestre_id"]].append(m)
    for s in semestres:
        s["materias"] = por_semestre[s["id"]]

    # Semestres por programa
    por_programa: dict[int | None, list] = {p["id"]: [] for p in programas}
    por_programa[None] = []
    for s in semestres:
        pid = s.get("programa_id")
        bucket = pid if pid in por_programa else None
        por_programa[bucket].append(s)
    for p in programas:
        p["semestres"] = por_programa[p["id"]]

    # Semestres huérfanos (sin programa) como grupo extra
    huerfanos = por_programa.get(None, [])
    if huerfanos:
        programas.append({
            "id": None,
            "nombre": "Sin programa",
            "tipo": "otro",
            "descripcion": "",
            "semestres": huerfanos,
        })

    return programas

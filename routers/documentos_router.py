import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from database.connection import db
from services.extractor import extraer_texto

router = APIRouter(prefix="/documentos", tags=["documentos"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

TIPOS_PERMITIDOS = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "text/plain": "txt",
}


@router.get("")
def listar_documentos(topic_id: int | None = None):
    with db() as conn:
        if topic_id is not None:
            rows = conn.execute(
                "SELECT id, topic_id, titulo, tipo, archivo_nombre, tags, creado_at FROM documentos WHERE topic_id = ? ORDER BY creado_at DESC",
                (topic_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, topic_id, titulo, tipo, archivo_nombre, tags, creado_at FROM documentos ORDER BY creado_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{doc_id}")
def obtener_documento(doc_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM documentos WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return dict(row)


@router.post("", status_code=201)
async def subir_documento(
    archivo: UploadFile = File(...),
    titulo: str = Form(...),
    topic_id: str = Form(""),
    tags: str = Form(""),
):
    tipo = TIPOS_PERMITIDOS.get(archivo.content_type or "")
    if tipo is None:
        sufijo = Path(archivo.filename or "").suffix.lower()
        mapa_sufijo = {".pdf": "pdf", ".docx": "docx", ".doc": "docx", ".txt": "txt"}
        tipo = mapa_sufijo.get(sufijo)
    if tipo is None:
        raise HTTPException(status_code=422, detail="Tipo de archivo no soportado. Usá PDF, DOCX o TXT.")

    nombre_unico = f"{uuid.uuid4().hex}_{archivo.filename}"
    ruta = UPLOADS_DIR / nombre_unico
    contenido = await archivo.read()
    ruta.write_bytes(contenido)

    texto = extraer_texto(str(ruta))

    topic_id_val = int(topic_id) if topic_id.strip() else None

    with db() as conn:
        cur = conn.execute(
            """INSERT INTO documentos (topic_id, titulo, tipo, archivo_nombre, archivo_path, contenido_texto, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (topic_id_val, titulo, tipo, archivo.filename, nombre_unico, texto, tags),
        )
        row = conn.execute("SELECT * FROM documentos WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.put("/{doc_id}")
def editar_documento(doc_id: int, titulo: str = Form(...), topic_id: str = Form(""), tags: str = Form("")):
    topic_id_val = int(topic_id) if topic_id.strip() else None
    with db() as conn:
        conn.execute(
            "UPDATE documentos SET titulo = ?, topic_id = ?, tags = ? WHERE id = ?",
            (titulo, topic_id_val, tags, doc_id),
        )
        row = conn.execute("SELECT * FROM documentos WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return dict(row)


@router.delete("/{doc_id}", status_code=204)
def eliminar_documento(doc_id: int):
    with db() as conn:
        row = conn.execute("SELECT archivo_path FROM documentos WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        ruta = UPLOADS_DIR / row["archivo_path"]
        if ruta.exists():
            ruta.unlink()
        conn.execute("DELETE FROM documentos WHERE id = ?", (doc_id,))

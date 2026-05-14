import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from database.connection import db
from services.extractor import extraer_texto

router = APIRouter(prefix="/documentos", tags=["documentos"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

TIPOS_MIME = {
    "application/pdf":  "pdf",
    "text/plain":       "txt",
    "text/markdown":    "md",
    "application/json": "json",
}
SUFIJOS = {".pdf": "pdf", ".txt": "txt", ".md": "md", ".json": "json"}
MIME_SALIDA = {"pdf": "application/pdf", "txt": "text/plain", "md": "text/plain; charset=utf-8", "json": "application/json"}


@router.get("")
def listar_documentos(materia_id: int | None = None):
    with db() as conn:
        if materia_id is not None:
            rows = conn.execute(
                "SELECT id, materia_id, titulo, tipo, archivo_nombre, tags, creado_at FROM documentos WHERE materia_id = ? ORDER BY creado_at DESC",
                (materia_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, materia_id, titulo, tipo, archivo_nombre, tags, creado_at FROM documentos ORDER BY creado_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{doc_id}")
def obtener_documento(doc_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM documentos WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return dict(row)


@router.get("/{doc_id}/archivo")
def servir_archivo(doc_id: int):
    """Sirve el archivo original para visualización embebida."""
    with db() as conn:
        row = conn.execute(
            "SELECT tipo, archivo_path, archivo_nombre FROM documentos WHERE id = ?", (doc_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    ruta = UPLOADS_DIR / row["archivo_path"]
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")
    media_type = MIME_SALIDA.get(row["tipo"], "application/octet-stream")
    return FileResponse(str(ruta), media_type=media_type, filename=row["archivo_nombre"])


@router.post("", status_code=201)
async def subir_documento(
    archivo: UploadFile = File(...),
    titulo: str = Form(...),
    materia_id: str = Form(""),
    tags: str = Form(""),
):
    tipo = TIPOS_MIME.get(archivo.content_type or "")
    if tipo is None:
        sufijo = Path(archivo.filename or "").suffix.lower()
        tipo = SUFIJOS.get(sufijo)
    if tipo is None:
        raise HTTPException(
            status_code=422,
            detail="Solo se permiten archivos PDF, TXT, Markdown (.md) o JSON.",
        )

    nombre_unico = f"{uuid.uuid4().hex}_{archivo.filename}"
    ruta = UPLOADS_DIR / nombre_unico
    contenido = await archivo.read()
    ruta.write_bytes(contenido)

    texto = extraer_texto(str(ruta))
    materia_id_val = int(materia_id) if materia_id.strip() else None

    with db() as conn:
        cur = conn.execute(
            "INSERT INTO documentos (materia_id, titulo, tipo, archivo_nombre, archivo_path, contenido_texto, tags) VALUES (?,?,?,?,?,?,?)",
            (materia_id_val, titulo, tipo, archivo.filename, nombre_unico, texto, tags),
        )
        row = conn.execute("SELECT * FROM documentos WHERE id = ?", (cur.lastrowid,)).fetchone()
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

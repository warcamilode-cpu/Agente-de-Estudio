import json
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from database.connection import db
from services.extractor import extraer_texto, chunkear_texto
from services import llm_client

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
    nombre = row["archivo_nombre"]
    return FileResponse(
        str(ruta),
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{nombre}"},
    )


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
        doc_id = cur.lastrowid

        # Almacenar chunks para RAG
        chunks = chunkear_texto(texto)
        for idx, chunk in enumerate(chunks):
            conn.execute(
                "INSERT INTO documento_chunks (doc_id, chunk_idx, texto) VALUES (?,?,?)",
                (doc_id, idx, chunk),
            )

        row = conn.execute("SELECT * FROM documentos WHERE id = ?", (doc_id,)).fetchone()
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


# ---------------------------------------------------------------------------
# Modelo y endpoint de análisis con Maia (streaming SSE)
# ---------------------------------------------------------------------------

class MaiaIn(BaseModel):
    doc_id: int | None = None
    materia_id: int | None = None
    mensaje: str
    historial: list[dict] = []


_PROMPT_MAIA = """\
Sos Maia, agente de análisis documental de Atalaya Pléyades. Tu personalidad está basada en la curiosidad minuciosa y la fidelidad a la información. Custodiás los documentos del repositorio y tu propósito es revelar lo que contienen de forma clara y útil. Nunca inventás ni asumís información que no esté en los documentos cargados — si algo no está disponible, lo decís con honestidad y sugerís qué agregar para completar el análisis. Tu tono es reflexivo y detallado, con entusiasmo genuino cuando encontrás algo relevante. Trabajás conectando ideas entre documentos y respondés preguntas basándote exclusivamente en el contenido del repositorio.

Documentos disponibles:
{contexto}

Respondé en español colombiano. Si el contexto no tiene suficiente info para responder, decílo sin vueltas.\
"""


@router.post("/analisis/stream")
def analisis_stream(payload: MaiaIn):
    """Streaming SSE con Maia analizando chunks de documentos."""

    # --- Recuperar contexto desde documento_chunks ---
    contexto = ""
    with db() as conn:
        if payload.doc_id is not None:
            rows = conn.execute(
                "SELECT texto FROM documento_chunks WHERE doc_id = ? ORDER BY chunk_idx LIMIT 15",
                (payload.doc_id,),
            ).fetchall()
            contexto = "\n\n".join(r["texto"] for r in rows)

        elif payload.materia_id is not None:
            rows = conn.execute(
                """
                SELECT dc.texto
                FROM documento_chunks dc
                JOIN documentos d ON d.id = dc.doc_id
                WHERE d.materia_id = ?
                ORDER BY dc.doc_id, dc.chunk_idx
                LIMIT 25
                """,
                (payload.materia_id,),
            ).fetchall()
            contexto = "\n\n".join(r["texto"] for r in rows)

        # Fallback: contenido_texto del propio documento
        if not contexto and payload.doc_id is not None:
            row = conn.execute(
                "SELECT contenido_texto FROM documentos WHERE id = ?",
                (payload.doc_id,),
            ).fetchone()
            if row and row["contenido_texto"]:
                contexto = row["contenido_texto"][:4000]

    if not contexto:
        contexto = "No se encontró contenido de documentos para analizar."

    system = _PROMPT_MAIA.format(contexto=contexto)

    # Construir historial con el mensaje actual al final
    mensajes = list(payload.historial) + [{"role": "user", "content": payload.mensaje}]

    def _generar():
        for chunk in llm_client.preguntar_stream(system, mensajes):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")

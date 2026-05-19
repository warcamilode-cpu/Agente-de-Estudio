import json
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from database.connection import db
from services.extractor import extraer_texto, chunkear_texto
from services import llm_client
from services import embedder

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
def listar_documentos(
    materia_id:  int | None = None,
    semestre_id: int | None = None,
    programa_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
):
    offset = (max(page, 1) - 1) * page_size
    cols = "id, materia_id, semestre_id, programa_id, titulo, tipo, archivo_nombre, tags, creado_at"
    with db() as conn:
        if materia_id is not None:
            total = conn.execute("SELECT COUNT(*) FROM documentos WHERE materia_id = ?", (materia_id,)).fetchone()[0]
            rows = conn.execute(f"SELECT {cols} FROM documentos WHERE materia_id = ? ORDER BY creado_at DESC LIMIT ? OFFSET ?", (materia_id, page_size, offset)).fetchall()
        elif semestre_id is not None:
            total = conn.execute("SELECT COUNT(*) FROM documentos WHERE semestre_id = ?", (semestre_id,)).fetchone()[0]
            rows = conn.execute(f"SELECT {cols} FROM documentos WHERE semestre_id = ? ORDER BY creado_at DESC LIMIT ? OFFSET ?", (semestre_id, page_size, offset)).fetchall()
        elif programa_id is not None:
            total = conn.execute("SELECT COUNT(*) FROM documentos WHERE programa_id = ?", (programa_id,)).fetchone()[0]
            rows = conn.execute(f"SELECT {cols} FROM documentos WHERE programa_id = ? ORDER BY creado_at DESC LIMIT ? OFFSET ?", (programa_id, page_size, offset)).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
            rows = conn.execute(f"SELECT {cols} FROM documentos ORDER BY creado_at DESC LIMIT ? OFFSET ?", (page_size, offset)).fetchall()
    return {"data": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/biblioteca")
def listar_biblioteca_get():
    return listar_biblioteca()


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
    materia_id:  str = Form(""),
    semestre_id: str = Form(""),
    programa_id: str = Form(""),
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
    materia_id_val  = int(materia_id)  if materia_id.strip()  else None
    semestre_id_val = int(semestre_id) if semestre_id.strip() else None
    programa_id_val = int(programa_id) if programa_id.strip() else None

    with db() as conn:
        cur = conn.execute(
            "INSERT INTO documentos (materia_id, semestre_id, programa_id, titulo, tipo, archivo_nombre, archivo_path, contenido_texto, tags) VALUES (?,?,?,?,?,?,?,?,?)",
            (materia_id_val, semestre_id_val, programa_id_val, titulo, tipo, archivo.filename, nombre_unico, texto, tags),
        )
        doc_id = cur.lastrowid

        # Almacenar chunks para RAG
        chunks = chunkear_texto(texto)
        chunk_ids = []
        for idx, chunk in enumerate(chunks):
            cur_chunk = conn.execute(
                "INSERT INTO documento_chunks (doc_id, chunk_idx, texto) VALUES (?,?,?)",
                (doc_id, idx, chunk),
            )
            chunk_ids.append((cur_chunk.lastrowid, chunk))

        row = conn.execute("SELECT * FROM documentos WHERE id = ?", (doc_id,)).fetchone()

    # Generar y guardar embeddings fuera del context manager (puede tardar)
    _guardar_embeddings(doc_id, chunk_ids)

    return dict(row)


def _guardar_embeddings(doc_id: int, chunk_ids: list[tuple[int, str]]) -> None:
    """Genera embeddings para cada chunk y los persiste en chunk_embeddings y vec_chunks."""
    if not chunk_ids:
        return
    pares = []
    for chunk_id, texto in chunk_ids:
        vec = embedder.generar_embedding(texto)
        if vec is not None:
            pares.append((chunk_id, doc_id, json.dumps(vec)))

    if not pares:
        return

    with db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, doc_id, embedding) VALUES (?,?,?)",
            pares,
        )
        # Intentar insertar en vec0 virtual table si está disponible
        try:
            import struct
            for chunk_id, _, emb_json in pares:
                vec = json.loads(emb_json)
                blob = struct.pack(f"{len(vec)}f", *vec)
                conn.execute(
                    "INSERT OR REPLACE INTO vec_chunks (chunk_id, embedding) VALUES (?, ?)",
                    (chunk_id, blob),
                )
        except Exception:
            pass  # vec_chunks no disponible; chunk_embeddings es suficiente


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
    trans_id: int | None = None
    materia_id: int | None = None
    mensaje: str
    historial: list[dict] = []


_PROMPT_MAIA = """\
Usted es Maia, agente de análisis documental de Atalaya Pléyades. Su personalidad está basada en la curiosidad minuciosa y la fidelidad a la información. Custodia los documentos del repositorio y su propósito es revelar lo que contienen de forma clara y útil. Nunca inventa ni asume información que no esté en los documentos cargados — si algo no está disponible, lo dice con honestidad y sugiere qué agregar para completar el análisis. Su tono es reflexivo y detallado, con entusiasmo genuino cuando encuentra algo relevante. Conecta ideas entre documentos y responde preguntas basándose exclusivamente en el contenido del repositorio. Se dirige al estudiante de usted, con la formalidad cercana de un docente colombiano profesional. Habla en español colombiano.

Cuando le pidan analizar una transcripción o documento de clase, siga este orden obligatorio:

**Paso 1 — Inventario de contenido**
Liste brevemente TODOS los elementos que encontró en el material, organizados en estas categorías:
- **Conceptos teóricos**: definiciones, estructuras de datos, principios.
- **Patrones de código**: técnicas de uso, idioms, formas de escribir código (ej: `dict.get(key, 0) + 1`, `**kwargs`, iteración con `.items()`).
- **Comparaciones y tradeoffs**: velocidad vs memoria, listas vs diccionarios, etc.
- **Módulos y herramientas**: cualquier módulo estándar o librería mencionada.
- **Advertencias y errores comunes**: lo que NO se debe hacer y por qué.

No omita nada, aunque parezca básico o muy puntual. Este inventario es el contrato con el estudiante: todo lo que liste aquí debe explicarlo después.

**Paso 2 — Explicación concepto por concepto**
Para cada ítem del inventario: explique qué es, para qué sirve y cómo se relaciona con los demás conceptos del material. Use ejemplos del propio documento cuando estén disponibles.

**Paso 3 — Síntesis**
Una conclusión breve que conecte todos los conceptos en un panorama coherente.

Documentos disponibles:
{contexto}

Responda en español colombiano, tratando al estudiante de usted. Si el contexto no tiene suficiente información para responder, indíquelo con claridad.\
"""


# ---------------------------------------------------------------------------
# Biblioteca de análisis de Maia
# ---------------------------------------------------------------------------

class BibliotecaIn(BaseModel):
    titulo: str
    pregunta: str
    respuesta: str
    doc_id: int | None = None
    materia_id: int | None = None


def listar_biblioteca():
    with db() as conn:
        rows = conn.execute(
            """SELECT ma.*, d.titulo AS doc_titulo
               FROM maia_analisis ma
               LEFT JOIN documentos d ON d.id = ma.doc_id
               ORDER BY ma.creado_at DESC LIMIT 100"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/biblioteca", status_code=201)
def guardar_biblioteca(body: BibliotecaIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO maia_analisis (titulo, pregunta, respuesta, doc_id, materia_id) VALUES (?,?,?,?,?)",
            (body.titulo, body.pregunta, body.respuesta, body.doc_id, body.materia_id),
        )
        row = conn.execute("SELECT * FROM maia_analisis WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.delete("/biblioteca/{analisis_id}", status_code=204)
def eliminar_biblioteca(analisis_id: int):
    with db() as conn:
        conn.execute("DELETE FROM maia_analisis WHERE id = ?", (analisis_id,))


# ---------------------------------------------------------------------------
# RAG helper — scoring BM25-lite sobre chunks
# ---------------------------------------------------------------------------

def _score_bm25(texto: str, terminos: list[str]) -> float:
    if not terminos:
        return 1.0
    palabras = texto.lower().split()
    n = max(len(palabras), 1)
    k1, b, avg = 1.5, 0.75, 150
    tl = texto.lower()
    score = 0.0
    for t in terminos:
        tf = tl.count(t)
        if tf > 0:
            score += (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * n / avg))
    return score


@router.post("/analisis/stream")
def analisis_stream(payload: MaiaIn):
    """Streaming SSE con Maia — BM25 sobre todos los chunks del documento."""

    terminos = [t for t in payload.mensaje.lower().split() if len(t) > 2]

    contexto = ""
    with db() as conn:
        if payload.doc_id is not None:
            rows = conn.execute(
                "SELECT texto FROM documento_chunks WHERE doc_id = ? ORDER BY chunk_idx",
                (payload.doc_id,),
            ).fetchall()
        elif payload.materia_id is not None:
            rows = conn.execute(
                """SELECT dc.texto
                   FROM documento_chunks dc
                   JOIN documentos d ON d.id = dc.doc_id
                   WHERE d.materia_id = ?
                   ORDER BY dc.doc_id, dc.chunk_idx""",
                (payload.materia_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT dc.texto FROM documento_chunks dc ORDER BY dc.doc_id, dc.chunk_idx"
            ).fetchall()

        if rows:
            scored = sorted(
                rows,
                key=lambda r: -_score_bm25(r["texto"], terminos),
            )
            top = [r["texto"] for r in scored[:60] if _score_bm25(r["texto"], terminos) > 0]
            if not top:
                top = [r["texto"] for r in scored[:20]]
            contexto = "\n\n".join(top)

        # Fallback: contenido_texto del propio documento
        if not contexto and payload.doc_id is not None:
            row = conn.execute(
                "SELECT contenido_texto FROM documentos WHERE id = ?",
                (payload.doc_id,),
            ).fetchone()
            if row and row["contenido_texto"]:
                contexto = row["contenido_texto"][:8000]

    # Contexto de transcripción (trans_id explícito o por materia_id)
    trans_ctx = ""
    if payload.trans_id is not None:
        with db() as conn:
            trow = conn.execute(
                "SELECT titulo, texto FROM transcripciones WHERE id = ?",
                (payload.trans_id,),
            ).fetchone()
        if trow and trow["texto"]:
            t_chunks = chunkear_texto(trow["texto"])
            # Transcripción explícita: incluir todos los chunks para cobertura completa
            trans_ctx = f"[Transcripción completa: {trow['titulo']}]\n" + "\n\n".join(t_chunks)
    else:
        # Sin filtro específico: buscar en todas las transcripciones por relevancia BM25
        with db() as conn:
            t_query = (
                "SELECT titulo, texto FROM transcripciones WHERE materia_id = ? ORDER BY creado_at DESC LIMIT 5"
                if payload.materia_id is not None
                else "SELECT titulo, texto FROM transcripciones ORDER BY creado_at DESC LIMIT 5"
            )
            t_params = (payload.materia_id,) if payload.materia_id is not None else ()
            t_rows = conn.execute(t_query, t_params).fetchall()
        all_chunks: list[str] = []
        for tr in t_rows:
            if tr["texto"]:
                all_chunks.extend(chunkear_texto(tr["texto"]))
        if all_chunks:
            t_scored = sorted(all_chunks, key=lambda c: -_score_bm25(c, terminos))
            t_top = [c for c in t_scored[:20] if _score_bm25(c, terminos) > 0]
            if t_top:
                trans_ctx = "[Transcripciones de clase]\n" + "\n\n".join(t_top)

    if trans_ctx:
        contexto = (trans_ctx + "\n\n" + contexto).strip() if contexto else trans_ctx

    if not contexto:
        contexto = "No se encontró contenido de documentos para analizar."

    system = _PROMPT_MAIA.format(contexto=contexto)

    # Construir historial con el mensaje actual al final
    mensajes = list(payload.historial) + [{"role": "user", "content": payload.mensaje}]

    def _generar():
        for chunk in llm_client.preguntar_stream(system, mensajes, max_tokens=8192):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generar(), media_type="text/event-stream")

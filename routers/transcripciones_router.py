import os
import shutil
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from database.connection import db
from services import whisper_client, tts_client

router = APIRouter(prefix="/transcripciones", tags=["transcripciones"])

_UPLOADS = "uploads/audio"
os.makedirs(_UPLOADS, exist_ok=True)

_EXTENSIONES = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".webm", ".mkv", ".flac"}


@router.post("")
def transcribir_audio(
    archivo: UploadFile = File(...),
    titulo: str = Form(...),
    idioma: str = Form("es"),
    materia_id: int | None = Form(None),
):
    ext = os.path.splitext(archivo.filename or "")[1].lower()
    if ext not in _EXTENSIONES:
        raise HTTPException(status_code=422, detail=f"Formato no soportado: {ext}. Usá mp3, mp4, wav, m4a, ogg, webm.")

    if not whisper_client.disponible():
        raise HTTPException(status_code=503, detail="El servicio de transcripción no está disponible. Verificá que whisper-server esté corriendo.")

    nombre_archivo = f"{uuid.uuid4()}{ext}"
    ruta = os.path.join(_UPLOADS, nombre_archivo)
    with open(ruta, "wb") as f:
        shutil.copyfileobj(archivo.file, f)

    try:
        texto = whisper_client.transcribir(ruta, idioma=idioma)
    except Exception as e:
        os.remove(ruta)
        raise HTTPException(status_code=500, detail=f"Error al transcribir: {e}")

    with db() as conn:
        cur = conn.execute(
            """INSERT INTO transcripciones (titulo, archivo_nombre, texto, texto_raw, idioma, materia_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (titulo, nombre_archivo, texto, texto, idioma, materia_id),
        )
        trans_id = cur.lastrowid

    return {
        "id": trans_id,
        "titulo": titulo,
        "texto": texto,
        "caracteres": len(texto),
    }


@router.get("")
def listar_transcripciones(materia_id: int | None = None):
    with db() as conn:
        if materia_id:
            rows = conn.execute(
                """SELECT t.id, t.titulo, t.idioma, t.creado_at, LENGTH(t.texto) as chars,
                          COALESCE(m.nombre, '—') AS materia_nombre
                   FROM transcripciones t
                   LEFT JOIN materias m ON m.id = t.materia_id
                   WHERE t.materia_id = ?
                   ORDER BY t.creado_at DESC""",
                (materia_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT t.id, t.titulo, t.idioma, t.creado_at, LENGTH(t.texto) as chars,
                          COALESCE(m.nombre, '—') AS materia_nombre
                   FROM transcripciones t
                   LEFT JOIN materias m ON m.id = t.materia_id
                   ORDER BY t.creado_at DESC""",
            ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{trans_id}")
def obtener_transcripcion(trans_id: int):
    with db() as conn:
        row = conn.execute(
            """SELECT t.*, COALESCE(m.nombre, '—') AS materia_nombre
               FROM transcripciones t
               LEFT JOIN materias m ON m.id = t.materia_id
               WHERE t.id = ?""",
            (trans_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Transcripción no encontrada.")
    return dict(row)


@router.delete("/{trans_id}", status_code=204)
def eliminar_transcripcion(trans_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT archivo_nombre FROM transcripciones WHERE id = ?", (trans_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Transcripción no encontrada.")
        conn.execute("DELETE FROM transcripciones WHERE id = ?", (trans_id,))

    ruta = os.path.join(_UPLOADS, row["archivo_nombre"])
    if os.path.exists(ruta):
        os.remove(ruta)


# ── TTS ─────────────────────────────────────────────────────────────

class SintetizarIn(BaseModel):
    texto: str
    voz: str = "ef_dora"
    velocidad: float = 1.0
    idioma: str = "es"


@router.get("/tts/voces")
def listar_voces():
    return tts_client.VOCES


@router.post("/tts/sintetizar")
def sintetizar_texto(body: SintetizarIn):
    if not body.texto.strip():
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")
    if not tts_client.disponible():
        raise HTTPException(status_code=503, detail="Kokoro TTS no está instalado.")
    try:
        audio_bytes = tts_client.sintetizar(
            body.texto,
            voz=body.voz,
            velocidad=body.velocidad,
            idioma=body.idioma,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sintetizar: {e}")
    return Response(content=audio_bytes, media_type="audio/wav")

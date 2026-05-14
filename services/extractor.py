"""Extrae texto plano de archivos PDF, DOCX y TXT, y los trocea para RAG."""
from pathlib import Path


def chunkear_texto(texto: str, tam: int = 500, solapamiento: int = 80) -> list[str]:
    """Divide texto en chunks con solapamiento. Intenta cortar en párrafo o punto."""
    if not texto:
        return []
    texto = texto.strip()
    if len(texto) <= tam:
        return [texto]

    chunks: list[str] = []
    i = 0
    while i < len(texto):
        fragmento = texto[i : i + tam]
        if i + tam < len(texto):
            # Preferir cortar en párrafo, luego en punto/coma, luego en espacio
            for sep in ("\n\n", "\n", ". ", ", ", " "):
                pos = fragmento.rfind(sep, tam // 2)
                if pos != -1:
                    fragmento = fragmento[: pos + len(sep)]
                    break
        fragmento = fragmento.strip()
        if fragmento:
            chunks.append(fragmento)
        i += max(len(fragmento) - solapamiento, 1)

    return chunks


def extraer_texto(archivo_path: str) -> str:
    path = Path(archivo_path)
    sufijo = path.suffix.lower()
    if sufijo == ".pdf":
        return _extraer_pdf(path)
    if sufijo in (".docx", ".doc"):
        return _extraer_docx(path)
    if sufijo == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _extraer_pdf(path: Path) -> str:
    try:
        import pdfplumber
        textos = []
        with pdfplumber.open(path) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    textos.append(texto)
        return "\n\n".join(textos)
    except Exception as e:
        return f"[Error extrayendo PDF: {e}]"


def _extraer_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        parrafos = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(parrafos)
    except Exception as e:
        return f"[Error extrayendo DOCX: {e}]"

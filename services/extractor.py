"""Extrae texto plano de archivos PDF, DOCX y TXT."""
from pathlib import Path


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

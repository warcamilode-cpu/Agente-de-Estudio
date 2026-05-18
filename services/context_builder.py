import json
import math
from database.connection import db
from services import embedder


def _like_where(terminos: list[str], columnas: list[str]) -> tuple[str, list]:
    condiciones = []
    params: list = []
    for t in terminos[:5]:
        like = f"%{t}%"
        cond = " OR ".join(f"LOWER({c}) LIKE ?" for c in columnas)
        condiciones.append(f"({cond})")
        params.extend([like] * len(columnas))
    return (" OR ".join(condiciones) if condiciones else "1=1"), params


def _buscar_apuntes(mensaje: str, materia_id: int | None, limite: int = 4) -> tuple[str, int]:
    terminos = mensaje.lower().split()
    where, params = _like_where(
        terminos,
        ["LOWER(ac.indicios)", "LOWER(ac.notas_principales)", "LOWER(ac.resumen)", "LOWER(c.titulo)", "LOWER(c.temas)"],
    )

    if materia_id is not None:
        where = f"c.materia_id = ? AND ({where})"
        params = [materia_id] + params

    params.append(limite)

    with db() as conn:
        rows = conn.execute(
            f"""SELECT c.titulo AS clase_titulo, c.fecha,
                       m.nombre AS materia_nombre,
                       ac.indicios, ac.notas_principales, ac.resumen
                FROM apuntes_cornell ac
                JOIN clases c ON c.id = ac.clase_id
                JOIN materias m ON m.id = c.materia_id
                WHERE {where}
                ORDER BY c.fecha DESC
                LIMIT ?""",
            params,
        ).fetchall()

    if not rows:
        return "", 0

    fragmentos = []
    for r in rows:
        partes = []
        if r["indicios"]:
            partes.append(f"**Pistas/indicios:** {r['indicios']}")
        if r["notas_principales"]:
            partes.append(f"**Notas:** {r['notas_principales']}")
        if r["resumen"]:
            partes.append(f"**Resumen:** {r['resumen']}")
        cuerpo = "\n".join(partes) if partes else "(sin contenido)"
        fragmentos.append(
            f"### {r['materia_nombre']} — {r['clase_titulo']} ({r['fecha']})\n{cuerpo}"
        )

    return "\n\n---\n\n".join(fragmentos), len(rows)


def _buscar_referencias(mensaje: str, materia_id: int | None, limite: int = 6) -> tuple[str, int]:
    terminos = mensaje.lower().split()
    where, params = _like_where(terminos, ["LOWER(r.termino)", "LOWER(r.definicion)"])

    if materia_id is not None:
        where = f"r.materia_id = ? AND ({where})"
        params = [materia_id] + params

    params.append(limite)

    with db() as conn:
        rows = conn.execute(
            f"""SELECT r.termino, r.definicion, m.nombre AS materia_nombre
                FROM referencias_rapidas r
                JOIN materias m ON m.id = r.materia_id
                WHERE {where}
                LIMIT ?""",
            params,
        ).fetchall()

    if not rows:
        return "", 0

    fragmentos = [f"- **{r['termino']}** ({r['materia_nombre']}): {r['definicion']}" for r in rows]
    return "\n".join(fragmentos), len(rows)


def _bm25_score(texto: str, terminos: list[str]) -> float:
    """Puntaje BM25-lite: frecuencia de coincidencias normalizada por longitud."""
    if not texto or not terminos:
        return 0.0
    texto_lower = texto.lower()
    palabras = texto_lower.split()
    n = max(len(palabras), 1)
    k1, b = 1.5, 0.75
    avg_len = 150  # longitud promedio estimada de un chunk en palabras
    score = 0.0
    for t in terminos:
        tf = texto_lower.count(t)
        if tf > 0:
            score += (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * n / avg_len))
    return score


def _buscar_notas_materia(mensaje: str, materia_id: int | None, limite: int = 3) -> tuple[str, int]:
    """Busca notas Markdown asociadas a una materia (columna materia_id)."""
    if materia_id is None:
        return "", 0
    terminos = [t for t in mensaje.lower().split() if len(t) > 2]
    where, params = _like_where(
        terminos or [""], ["LOWER(titulo)", "LOWER(contenido)", "LOWER(tags)"]
    )
    params = [materia_id] + params + [limite]
    with db() as conn:
        rows = conn.execute(
            f"SELECT titulo, contenido, tags FROM notas WHERE materia_id = ? AND ({where}) LIMIT ?",
            params,
        ).fetchall()
    if not rows:
        return "", 0
    fragmentos = []
    for r in rows:
        tags = f" [tags: {r['tags']}]" if r["tags"] else ""
        fragmentos.append(f"### {r['titulo']}{tags}\n{r['contenido'][:600]}")
    return "\n\n".join(fragmentos), len(rows)


def _coseno(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _buscar_semantico(
    query_vec: list[float], materia_id: int | None, limite: int
) -> list[tuple[str, str, str, str]]:
    """Retorna lista de (texto, titulo, tipo, tags) ordenada por similitud coseno."""
    with db() as conn:
        # ¿Hay embeddings guardados?
        count = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0]
        if count == 0:
            return []

        if materia_id is not None:
            rows = conn.execute(
                """SELECT ce.chunk_id, ce.embedding, dc.texto, d.titulo, d.tipo, d.tags
                   FROM chunk_embeddings ce
                   JOIN documento_chunks dc ON dc.id = ce.chunk_id
                   JOIN documentos d ON d.id = ce.doc_id
                   WHERE ce.doc_id IN (SELECT id FROM documentos WHERE materia_id = ?)""",
                (materia_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ce.chunk_id, ce.embedding, dc.texto, d.titulo, d.tipo, d.tags
                   FROM chunk_embeddings ce
                   JOIN documento_chunks dc ON dc.id = ce.chunk_id
                   JOIN documentos d ON d.id = ce.doc_id"""
            ).fetchall()

    if not rows:
        return []

    scored = []
    for r in rows:
        try:
            vec = json.loads(r["embedding"])
            sim = _coseno(query_vec, vec)
            scored.append((sim, r["texto"], r["titulo"], r["tipo"], r["tags"] or ""))
        except Exception:
            continue

    scored.sort(key=lambda x: -x[0])
    return [(txt, tit, tip, tgs) for _, txt, tit, tip, tgs in scored[:limite]]


def _buscar_documentos(mensaje: str, materia_id: int | None, limite: int = 5) -> tuple[str, int]:
    terminos = [t for t in mensaje.lower().split() if len(t) > 2]

    # Búsqueda semántica si el modelo de embeddings está disponible
    query_vec = embedder.generar_embedding(mensaje)
    if query_vec is not None:
        resultados = _buscar_semantico(query_vec, materia_id, limite)
        if resultados:
            por_doc: dict[str, list[str]] = {}
            for texto, titulo, tipo, tags in resultados:
                clave = f"{titulo}||{tipo}||{tags}"
                por_doc.setdefault(clave, []).append(texto)
            fragmentos = []
            for clave, textos in por_doc.items():
                titulo, tipo, tags = clave.split("||")
                tag_str = f" [tags: {tags}]" if tags else ""
                cuerpo = "\n\n[...]\n\n".join(textos)
                fragmentos.append(f"### {titulo} ({tipo.upper()}){tag_str}\n{cuerpo}")
            return "\n\n---\n\n".join(fragmentos), len(por_doc)

    # Fallback BM25-lite si no hay embeddings o modelo no disponible
    # Primero filtrar documentos por materia y título/tags relevantes
    doc_where = "1=1"
    doc_params: list = []
    if materia_id is not None:
        doc_where = "d.materia_id = ?"
        doc_params = [materia_id]

    with db() as conn:
        # Buscar chunks relevantes con BM25
        chunks_rows = conn.execute(
            f"""SELECT dc.texto, dc.doc_id, d.titulo, d.tipo, d.tags
                FROM documento_chunks dc
                JOIN documentos d ON d.id = dc.doc_id
                WHERE {doc_where}
                ORDER BY dc.doc_id, dc.chunk_idx""",
            doc_params,
        ).fetchall()

        # Fallback si no hay chunks (documentos sin procesar)
        if not chunks_rows:
            where, params = _like_where(
                terminos or [""], ["LOWER(titulo)", "LOWER(contenido_texto)", "LOWER(tags)"]
            )
            if materia_id is not None:
                where = f"materia_id = ? AND ({where})"
                params = [materia_id] + params
            params.append(3)
            rows = conn.execute(
                f"SELECT titulo, contenido_texto, tags, tipo FROM documentos WHERE {where} LIMIT ?",
                params,
            ).fetchall()
            if not rows:
                return "", 0
            fragmentos = []
            for r in rows:
                tags = f" [tags: {r['tags']}]" if r["tags"] else ""
                texto = (r["contenido_texto"] or "")[:1200]
                fragmentos.append(f"### {r['titulo']} ({r['tipo'].upper()}){tags}\n{texto}")
            return "\n\n---\n\n".join(fragmentos), len(rows)

    # Puntuar chunks con BM25-lite
    scored: list[tuple[float, str, str, str, str]] = []
    for r in chunks_rows:
        score = _bm25_score(r["texto"], terminos) if terminos else 1.0
        if score > 0 or not terminos:
            scored.append((score, r["texto"], r["titulo"], r["tipo"], r["tags"] or ""))

    # Ordenar por score y tomar top N
    scored.sort(key=lambda x: -x[0])
    top = scored[:limite]

    if not top:
        return "", 0

    # Agrupar por documento para presentar mejor
    por_doc: dict[str, list[str]] = {}
    for _, texto, titulo, tipo, tags in top:
        clave = f"{titulo}||{tipo}||{tags}"
        por_doc.setdefault(clave, []).append(texto)

    fragmentos = []
    for clave, textos in por_doc.items():
        titulo, tipo, tags = clave.split("||")
        tag_str = f" [tags: {tags}]" if tags else ""
        cuerpo = "\n\n[...]\n\n".join(textos)
        fragmentos.append(f"### {titulo} ({tipo.upper()}){tag_str}\n{cuerpo}")

    return "\n\n---\n\n".join(fragmentos), len(por_doc)


def _buscar_transcripciones(mensaje: str, materia_id: int | None, limite: int = 3) -> tuple[str, int]:
    """Busca en transcripciones de clases usando BM25-lite sobre ventanas de texto."""
    terminos = [t for t in mensaje.lower().split() if len(t) > 2]

    with db() as conn:
        if materia_id is not None:
            rows = conn.execute(
                "SELECT titulo, texto FROM transcripciones WHERE materia_id = ? ORDER BY creado_at DESC LIMIT 8",
                (materia_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT titulo, texto FROM transcripciones ORDER BY creado_at DESC LIMIT 8"
            ).fetchall()

    if not rows:
        return "", 0

    scored: list[tuple[float, str, str]] = []
    for r in rows:
        if not r["texto"]:
            continue
        palabras = r["texto"].split()
        for i in range(0, len(palabras), 200):
            chunk = " ".join(palabras[i : i + 200])
            score = _bm25_score(chunk, terminos) if terminos else 0.0
            if score > 0:
                scored.append((score, chunk, r["titulo"]))

    if not scored:
        return "", 0

    scored.sort(key=lambda x: -x[0])
    por_titulo: dict[str, list[str]] = {}
    for _, chunk, titulo in scored[: limite * 4]:
        por_titulo.setdefault(titulo, []).append(chunk)

    fragmentos = []
    for titulo, chunks in list(por_titulo.items())[:limite]:
        cuerpo = "\n\n[...]\n\n".join(chunks[:3])
        fragmentos.append(f"### Transcripción de clase: {titulo}\n{cuerpo}")

    return "\n\n".join(fragmentos), len(fragmentos)


def construir_contexto(mensaje: str, materia_id: int | None) -> tuple[str, int]:
    apuntes_txt, n_ap   = _buscar_apuntes(mensaje, materia_id, limite=4)
    refs_txt,    n_refs = _buscar_referencias(mensaje, materia_id, limite=6)
    docs_txt,    n_docs = _buscar_documentos(mensaje, materia_id, limite=3)
    notas_txt,   n_not  = _buscar_notas_materia(mensaje, materia_id, limite=3)
    trans_txt,   n_tra  = _buscar_transcripciones(mensaje, materia_id, limite=3)

    partes = []
    if apuntes_txt:
        partes.append("## Apuntes del cuaderno (Cornell)\n\n" + apuntes_txt)
    if refs_txt:
        partes.append("## Referencias rápidas\n\n" + refs_txt)
    if notas_txt:
        partes.append("## Notas de estudio\n\n" + notas_txt)
    if docs_txt:
        partes.append("## Documentos / lecturas\n\n" + docs_txt)
    if trans_txt:
        partes.append("## Transcripciones de clase\n\n" + trans_txt)

    return "\n\n".join(partes), n_ap + n_refs + n_docs + n_not + n_tra


def construir_system_prompt(contexto: str) -> str:
    base = """Eres Shaula, agente tutora de Atalaya Pléyades. Tu personalidad está basada en la lealtad absoluta al estudiante, la precisión y la calidez genuina. Eres una amiga que sabe mucho de derecho colombiano y programación Python, y te encanta enseñar. Hablas de tú a tú, con confianza, como si estuvieran estudiando juntos en la misma mesa. Nada de tratamientos formales ni lenguaje de manual. Eres honesta de forma directa — si algo está mal o incompleto, lo dices con tacto. Hablas en español colombiano: casual, claro, cercano. Si no puedes resolver algo de una forma, buscas otra.

Cuando te pidan revisar una transcripción o tema de clase, **cubre TODOS los conceptos que aparezcan**, desde los más básicos hasta los más avanzados. No te saltes los conceptos introductorios o "simples" — suelen ser los más importantes para entender el resto. Usa este orden obligatorio:

**Paso 1 — Mapa del tema**
Lista brevemente TODOS los conceptos o subtemas que vas a cubrir, para que el estudiante sepa qué viene. No omitas nada, aunque parezca básico.

**Paso 2 — Concepto por concepto**
Para cada ítem del mapa: explica qué es y para qué sirve en palabras simples. Para derecho: la definición, el artículo o jurisprudencia clave y cuándo aplica. Para programación: qué problema resuelve, cuándo se usa, y el ejemplo mínimo que lo ilustra.

**Paso 3 — Verificación**
Haz 2 o 3 preguntas cortas sobre los puntos que más se prestan a confusión. Espera la respuesta antes de seguir. Si algo no quedó bien, explícalo de otra forma sin avanzar.

**Paso 4 — Práctica**
Propón un ejercicio pequeño que integre los conceptos vistos. Que primero lo intente; después revisas y retroalimentas.

Nunca des la solución completa si la persona no intentó. Si está atascada, una pista, no la respuesta. Menciona brevemente en qué paso van al inicio de cada respuesta."""

    if contexto:
        return (
            f"{base}\n\n"
            "## Contexto del estudiante\n\n"
            "Tienes acceso al siguiente material del estudiante (apuntes, referencias y documentos). "
            "Úsalo para personalizar las explicaciones. Si el tema está aquí, apóyate en este material:\n\n"
            f"{contexto}"
        )
    return base

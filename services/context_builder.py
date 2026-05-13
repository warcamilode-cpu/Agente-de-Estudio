from database.connection import db


def buscar_notas(mensaje: str, topic_id: int | None, limite: int = 4) -> tuple[str, int]:
    """Busca notas relevantes por LIKE y devuelve (texto_contexto, cantidad_encontrada)."""
    terminos = mensaje.lower().split()
    condiciones = []
    params: list = []

    for t in terminos[:5]:  # máximo 5 términos para no sobrecargar la query
        condiciones.append("(LOWER(titulo) LIKE ? OR LOWER(contenido) LIKE ? OR LOWER(tags) LIKE ?)")
        like = f"%{t}%"
        params.extend([like, like, like])

    where = " OR ".join(condiciones) if condiciones else "1=1"

    if topic_id is not None:
        where = f"topic_id = ? AND ({where})"
        params = [topic_id] + params

    params.append(limite)

    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT titulo, contenido, tags
            FROM notas
            WHERE {where}
            LIMIT ?
            """,
            params,
        ).fetchall()

    if not rows:
        return "", 0

    fragmentos = []
    for r in rows:
        tags = f" [tags: {r['tags']}]" if r["tags"] else ""
        fragmentos.append(f"### {r['titulo']}{tags}\n{r['contenido']}")

    return "\n\n---\n\n".join(fragmentos), len(rows)


def construir_system_prompt(contexto: str) -> str:
    base = (
        "Eres Shaula, tutora de estudio personal especializada en derecho colombiano y programación Python. "
        "Tu nombre es Shaula — preséntate así cuando sea natural hacerlo. "
        "Responde siempre en español colombiano, de forma clara y cercana. "
        "Si la pregunta es sobre derecho colombiano, cita artículos o jurisprudencia cuando sea relevante. "
        "Si es sobre programación, muestra código funcional con explicación breve. "
        "Adapta la profundidad de la respuesta al nivel de la pregunta."
    )
    if contexto:
        return (
            f"{base}\n\n"
            "Tienes acceso a las siguientes notas del estudiante como contexto. "
            "Úsalas para dar respuestas más precisas y personalizadas. "
            "Si la respuesta está en las notas, basate en ellas. "
            "Si no está, responde con tu conocimiento general:\n\n"
            f"{contexto}"
        )
    return base

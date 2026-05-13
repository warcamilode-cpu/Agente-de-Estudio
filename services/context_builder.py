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
        "Eres un tutor de estudio personal especializado en derecho colombiano y programación Python. "
        "Responde siempre en español, de forma clara y concisa. "
        "Si la pregunta es sobre derecho colombiano, cita artículos o jurisprudencia cuando sea relevante. "
        "Si es sobre programación, muestra código funcional con explicación breve."
    )
    if contexto:
        return (
            f"{base}\n\n"
            "Tienes acceso a las siguientes notas del usuario como contexto adicional. "
            "Úsalas para dar respuestas más precisas y personalizadas:\n\n"
            f"{contexto}"
        )
    return base

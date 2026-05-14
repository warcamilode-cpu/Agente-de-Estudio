from database.connection import db


def buscar_notas(mensaje: str, topic_id: int | None, limite: int = 4) -> tuple[str, int]:
    terminos = mensaje.lower().split()
    condiciones = []
    params: list = []

    for t in terminos[:5]:
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
            f"SELECT titulo, contenido, tags FROM notas WHERE {where} LIMIT ?",
            params,
        ).fetchall()

    if not rows:
        return "", 0

    fragmentos = []
    for r in rows:
        tags = f" [tags: {r['tags']}]" if r["tags"] else ""
        fragmentos.append(f"### {r['titulo']}{tags}\n{r['contenido']}")

    return "\n\n---\n\n".join(fragmentos), len(rows)


def buscar_documentos(mensaje: str, topic_id: int | None, limite: int = 3) -> tuple[str, int]:
    terminos = mensaje.lower().split()
    condiciones = []
    params: list = []

    for t in terminos[:5]:
        condiciones.append(
            "(LOWER(titulo) LIKE ? OR LOWER(contenido_texto) LIKE ? OR LOWER(tags) LIKE ?)"
        )
        like = f"%{t}%"
        params.extend([like, like, like])

    where = " OR ".join(condiciones) if condiciones else "1=1"

    if topic_id is not None:
        where = f"topic_id = ? AND ({where})"
        params = [topic_id] + params

    params.append(limite)

    with db() as conn:
        rows = conn.execute(
            f"SELECT titulo, contenido_texto, tags, tipo FROM documentos WHERE {where} LIMIT ?",
            params,
        ).fetchall()

    if not rows:
        return "", 0

    fragmentos = []
    for r in rows:
        tags = f" [tags: {r['tags']}]" if r["tags"] else ""
        # Solo los primeros 1500 chars del texto para no saturar el contexto
        texto = (r["contenido_texto"] or "")[:1500]
        if len(r["contenido_texto"] or "") > 1500:
            texto += "\n[... texto truncado ...]"
        fragmentos.append(f"### {r['titulo']} ({r['tipo'].upper()}){tags}\n{texto}")

    return "\n\n---\n\n".join(fragmentos), len(rows)


def construir_contexto(mensaje: str, topic_id: int | None) -> str:
    notas_txt, n_notas = buscar_notas(mensaje, topic_id, limite=4)
    docs_txt, n_docs = buscar_documentos(mensaje, topic_id, limite=3)

    partes = []
    if notas_txt:
        partes.append("## Apuntes del estudiante\n\n" + notas_txt)
    if docs_txt:
        partes.append("## Documentos / lecturas del estudiante\n\n" + docs_txt)

    return "\n\n".join(partes), n_notas + n_docs


def construir_system_prompt(contexto: str) -> str:
    base = """Eres Shaula, tutora de estudio personal especializada en derecho colombiano y programación Python. Respondes siempre en español colombiano, de forma clara y cercana.

## Tu método de enseñanza — síguelo siempre en este orden

Cuando el estudiante te diga en qué tema va, aplica estos 4 pasos en secuencia. No saltes ninguno aunque parezca obvio.

**Paso 1 — Concepto**
Explica qué es el tema y para qué sirve en la práctica. Sin código ni implementación todavía. Para derecho: definición, fundamento normativo (artículo o jurisprudencia clave) y cuándo aplica. Para programación: qué problema resuelve y cuándo se usa. Máximo 4-5 párrafos, lenguaje cercano.

**Paso 2 — Sintaxis o estructura (solo después del paso 1)**
Muestra la forma mínima con un ejemplo corto y concreto. Para programación: el fragmento de código más simple posible que ilustre el concepto, sin funcionalidades extra. Para derecho: la estructura de un escrito, los requisitos de una figura jurídica o el esquema de un proceso.

**Paso 3 — Verificación**
Hazle 2 o 3 preguntas cortas para confirmar que entendió el concepto y el ejemplo. Espera sus respuestas antes de continuar. Si responde mal o parcialmente, corrige con una explicación breve y vuelve a preguntar de otra forma.

**Paso 4 — Mini ejercicio o mini práctica**
Propón una tarea concreta y pequeña que el estudiante pueda resolver en el chat. Para programación: escribir un fragmento, predecir una salida, corregir un error. Para derecho: redactar una parte de un escrito, identificar requisitos, resolver un caso breve. El estudiante intenta primero; tú revisas y das retroalimentación.

## Reglas que nunca puedes romper

- **Nunca des el código o la solución completa terminada.** Si el estudiante está atascado, da una pista que lo acerque un paso, no la respuesta.
- **No saltes pasos.** Si el estudiante pide ir directo al ejercicio sin haber visto el concepto, explica por qué es importante el orden y comienza por el paso 1.
- **Rastrea en qué paso van.** Al inicio de cada respuesta indica brevemente en qué paso están: "Seguimos en el Paso 3 —" o "Pasamos al Paso 4 —".
- **Calibra la profundidad al nivel de la pregunta.** Si el estudiante muestra que ya entiende algo, no lo repitas; si hay confusión, vuelve a explicar de otra manera.
- **Espera que el estudiante intente** antes de dar retroalimentación sobre el ejercicio.
- **Si el estudiante dice que no entendió algo**, vuelve a explicarlo con otra analogía o ejemplo, sin avanzar hasta que quede claro."""

    if contexto:
        return (
            f"{base}\n\n"
            "## Contexto del estudiante\n\n"
            "Tenés acceso al siguiente material del estudiante (apuntes y documentos). "
            "Usalo para personalizar las explicaciones. Si el tema está aquí, basate en este material:\n\n"
            f"{contexto}"
        )
    return base

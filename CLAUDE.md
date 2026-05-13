# CLAUDE.md — Agente de Estudio

> Archivo de contexto para sesiones de Claude Code.
> Leé este archivo completo antes de tocar cualquier código.

---

## Qué es este proyecto

Aplicación web personal de estudio tipo "todo en uno" que combina:
- Chat con IA tutora con contexto de notas propias
- Gestión de notas en Markdown con tags
- Sistema de flashcards con spaced repetition (algoritmo SM-2)
- Dashboard de progreso y estadísticas

**Dominio:** derecho colombiano + programación Python  
**Usuarios:** uso personal (1 usuario, no hay auth por ahora)  
**Acceso:** servidor Ubuntu local, accedido desde iPad Air M4 vía Tailscale

---

## Stack tecnológico

| Capa | Tecnología | Notas |
|------|-----------|-------|
| Backend | FastAPI (Python 3.11+) | Uvicorn como servidor |
| Base de datos | SQLite | Un solo archivo `estudio.db` |
| IA (dev) | Ollama local | Modelo `qwen2.5-coder:14b` (GTX 1080 Ti, 11 GB VRAM) |
| IA (prod) | Anthropic Claude API | `claude-haiku-4-5-20251001` |
| Frontend | HTML + CSS + Vanilla JS | Sin frameworks, sin build step |
| Acceso remoto | Tailscale | Ya configurado en el servidor |

**No usar:** React, Vue, Svelte, SQLAlchemy ORM, Alembic, Docker (innecesario para uso personal).  
**Sí usar:** sqlite3 nativo de Python, anthropic SDK oficial, ollama SDK.

---

## Estructura de directorios

```
agente-estudio/
│
├── CLAUDE.md                  # Este archivo
├── main.py                    # Entry point FastAPI
├── .env                       # Variables de entorno (no commitear)
├── .env.example               # Plantilla de variables
├── requirements.txt
├── estudio.db                 # Base de datos SQLite (se crea automático)
│
├── routers/
│   ├── __init__.py
│   ├── ai_router.py           # Chat con IA, streaming, sesiones
│   ├── notas_router.py        # CRUD de notas
│   ├── flashcards_router.py   # CRUD de flashcards + lógica SRS
│   ├── topics_router.py       # CRUD de temas/materias
│   └── dashboard_router.py    # Stats y progreso
│
├── services/
│   ├── __init__.py
│   ├── llm_client.py          # Abstracción Ollama/Claude (swappable)
│   ├── context_builder.py     # Búsqueda de notas + construcción de prompt
│   └── srs_engine.py          # Algoritmo SM-2 para flashcards
│
├── database/
│   ├── __init__.py
│   ├── connection.py          # Conexión SQLite + context manager
│   └── schema.sql             # Definición de tablas
│
└── frontend/
    ├── index.html             # SPA principal
    ├── css/
    │   └── styles.css
    └── js/
        ├── app.js             # Router del frontend (tabs)
        ├── chat.js            # Módulo chat con streaming SSE
        ├── notas.js           # Módulo notas
        ├── flashcards.js      # Módulo flashcards
        └── dashboard.js       # Módulo estadísticas
```

---

## Variables de entorno (`.env`)

```env
# Proveedor de IA: "ollama" (gratis, local) o "claude" (API de pago)
LLM_PROVEEDOR=ollama

# Ollama — corre en el mismo servidor Ubuntu
# Hardware: GTX 1080 Ti 11 GB VRAM — qwen2.5-coder:14b usa ~8.2 GB, cabe cómodo
# Alternativa jurídica: cambiar a qwen2.5:14b si se prioriza derecho sobre código
OLLAMA_BASE_URL=http://localhost:11434
MODELO_OLLAMA=qwen2.5-coder:14b

# Claude API — solo si LLM_PROVEEDOR=claude
ANTHROPIC_API_KEY=sk-ant-...
MODELO_CLAUDE=claude-haiku-4-5-20251001

# App
APP_HOST=0.0.0.0
APP_PORT=8000
```

---

## Base de datos — schema completo

```sql
-- database/schema.sql

CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    descripcion TEXT,
    color       TEXT DEFAULT '#6366f1',   -- hex para UI
    creado_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    titulo      TEXT NOT NULL,
    contenido   TEXT NOT NULL,            -- markdown
    tags        TEXT DEFAULT '',          -- "tutela,derechos,mecanismos"
    creada_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizada_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flashcards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    nota_id         INTEGER REFERENCES notas(id) ON DELETE SET NULL,
    pregunta        TEXT NOT NULL,
    respuesta       TEXT NOT NULL,
    -- Campos SM-2
    intervalo       INTEGER DEFAULT 1,    -- días hasta próximo repaso
    repeticiones    INTEGER DEFAULT 0,    -- veces respondida correctamente seguidas
    factor_facilidad REAL DEFAULT 2.5,   -- EF del algoritmo SM-2
    proximo_repaso  DATE DEFAULT (date('now')),
    creada_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sesiones_estudio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    tipo            TEXT NOT NULL,        -- "chat" | "flashcards" | "notas"
    duracion_seg    INTEGER DEFAULT 0,
    cards_revisadas INTEGER DEFAULT 0,
    cards_correctas INTEGER DEFAULT 0,
    iniciada_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_notas_topic ON notas(topic_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_repaso ON flashcards(proximo_repaso);
CREATE INDEX IF NOT EXISTS idx_flashcards_topic ON flashcards(topic_id);
```

---

## API — endpoints por router

### `/ai` — Chat con IA

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/ai/chat/nueva-sesion` | Genera un `session_id` UUID |
| POST | `/ai/chat` | Chat sin streaming |
| POST | `/ai/chat/stream` | Chat con streaming (SSE) — **preferido** |
| DELETE | `/ai/chat/{session_id}` | Limpia historial de la sesión |
| GET | `/ai/chat/{session_id}/historial` | Ver historial (debug) |

**Body de `/ai/chat` y `/ai/chat/stream`:**
```json
{
  "session_id": "uuid-aqui",
  "message": "¿Cuándo procede la tutela?",
  "topic_id": 1
}
```

### `/topics` — Temas/materias

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/topics` | Listar todos |
| POST | `/topics` | Crear topic |
| PUT | `/topics/{id}` | Editar |
| DELETE | `/topics/{id}` | Eliminar |

### `/notas` — Notas de estudio

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/notas` | Listar (filtros: `topic_id`, `tags`, `q` para búsqueda) |
| GET | `/notas/{id}` | Ver nota individual |
| POST | `/notas` | Crear nota |
| PUT | `/notas/{id}` | Editar nota |
| DELETE | `/notas/{id}` | Eliminar nota |

### `/flashcards` — Sistema de repaso

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/flashcards/pendientes` | Cards para repasar hoy |
| GET | `/flashcards` | Listar todas (filtro: `topic_id`) |
| POST | `/flashcards` | Crear card |
| POST | `/flashcards/{id}/respuesta` | Registrar respuesta (aplica SM-2) |
| PUT | `/flashcards/{id}` | Editar card |
| DELETE | `/flashcards/{id}` | Eliminar card |

**Body de `/flashcards/{id}/respuesta`:**
```json
{ "calificacion": 4 }
```
Calificaciones SM-2: `0`=no supe nada, `1`=muy difícil, `2`=difícil, `3`=bien, `4`=fácil, `5`=perfecto

### `/dashboard` — Estadísticas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/dashboard/resumen` | Stats generales del día |
| GET | `/dashboard/racha` | Días consecutivos de estudio |
| GET | `/dashboard/progreso/{topic_id}` | Progreso por tema |

---

## Servicios clave

### `services/llm_client.py` — Abstracción de IA

Único punto de contacto con el modelo de IA. El resto del código **nunca importa `anthropic` u `ollama` directamente**.

```python
# Interfaz pública del módulo:
def preguntar(system_prompt: str, mensajes: list[dict]) -> str
def preguntar_stream(system_prompt: str, mensajes: list[dict]) -> Generator[str, None, None]
```

El proveedor se controla con `LLM_PROVEEDOR` en `.env`. Cambiar de Ollama a Claude no requiere tocar ningún router.

### `services/context_builder.py` — Contexto para el chat

Busca notas relevantes en SQLite y construye el system prompt.

```python
# Interfaz pública:
def buscar_notas(mensaje: str, topic_id: int | None, limite: int = 4) -> tuple[str, int]
def construir_system_prompt(contexto: str) -> str
```

La búsqueda usa `LIKE` sobre título, contenido y tags. Es suficiente para uso personal — no implementar embeddings ni búsqueda semántica todavía.

### `services/srs_engine.py` — Algoritmo SM-2

```python
# Interfaz pública:
def calcular_siguiente_repaso(
    calificacion: int,         # 0-5
    intervalo_actual: int,     # días
    repeticiones: int,
    factor_facilidad: float
) -> tuple[int, int, float]    # (nuevo_intervalo, nuevas_repeticiones, nuevo_ef)
```

Implementación pura del algoritmo SM-2 de Anki. Sin efectos secundarios — solo calcula, el router persiste.

---

## Decisiones de arquitectura

**Por qué historial en memoria y no en SQLite:**  
El historial de conversación es efímero — solo importa dentro de una sesión activa. Guardar cada mensaje en DB agrega complejidad sin beneficio real para un usuario personal. Si el servidor se reinicia, el usuario abre una sesión nueva. Aceptable.

**Por qué `MAX_HISTORIAL = 10` (5 turnos):**  
Evita que el contexto acumulado aumente el costo de tokens y la latencia. Para sesiones largas, el usuario puede limpiar la sesión con DELETE.

**Por qué SQLite y no PostgreSQL:**  
Un usuario, acceso local, datos de estudio personal. SQLite es más que suficiente y elimina un proceso externo del servidor.

**Por qué Vanilla JS y no React:**  
El frontend se sirve como archivos estáticos desde FastAPI. Sin build step, sin node_modules, editable directamente desde el iPad. El proyecto no justifica la complejidad de un framework.

**Por qué Ollama por defecto:**  
Durante desarrollo se hacen decenas de llamadas de prueba. Usar la API de Claude cobraría por cada test. Ollama es idéntico en la interfaz pero gratis. El switch a Claude es una línea en `.env`.

**Por qué `qwen2.5-coder:14b` como modelo local:**  
Hardware disponible: GTX 1080 Ti con 11 GB VRAM. El modelo usa ~8.2 GB en Q4, cabe sin problema y corre íntegramente en GPU (~20-30 tok/seg). Se eligió la variante coder porque la prioridad actual es construir el propio agente en Python. Si el foco cambia a derecho colombiano, cambiar a `qwen2.5:14b` (mismo tamaño, mejor español general) es una línea en `.env` sin tocar código.

---

## Cómo correr el proyecto

```bash
# 1. Instalar dependencias
pip install fastapi uvicorn anthropic ollama python-dotenv

# 2. Configurar entorno
cp .env.example .env
# editar .env con tus valores

# 3. Inicializar la base de datos
python -c "from database.connection import init_db; init_db()"

# 4. Levantar el servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Acceso desde iPad (Tailscale)
# http://<ip-tailscale-del-servidor>:8000
```

---

## Estado del proyecto

### Completado ✅
- [x] Arquitectura definida
- [x] `ai_router.py` — Chat con contexto, historial y streaming
- [x] `llm_client.py` — Abstracción Ollama/Claude
- [x] Schema de base de datos

### En construcción 🔧
- [ ] `database/connection.py` — conexión SQLite y `init_db()`
- [ ] `context_builder.py` — búsqueda de notas y construcción de prompt
- [ ] `srs_engine.py` — algoritmo SM-2
- [ ] `notas_router.py` — CRUD de notas
- [ ] `flashcards_router.py` — CRUD + lógica de repaso
- [ ] `topics_router.py` — CRUD de temas
- [ ] `dashboard_router.py` — estadísticas
- [ ] `main.py` — registro de todos los routers
- [ ] Frontend completo (4 módulos)

### Pendiente 📋
- [ ] Servir frontend como archivos estáticos desde FastAPI
- [ ] Instalación y configuración de Ollama en el servidor
- [ ] Datos de prueba (topics y notas iniciales de derecho y Python)

---

## Convenciones de código

- **Python:** snake_case, type hints en todas las funciones, docstrings solo si la función no es obvia
- **SQL:** keywords en MAYÚSCULAS, aliases descriptivos en minúsculas
- **Commits:** en español, descriptivos (`agrega endpoint de flashcards`, `corrige cálculo SM-2`)
- **Errores:** usar `HTTPException` de FastAPI, nunca `print()` para logs en producción
- **No ORM:** queries SQL directas con `sqlite3`, así el código es legible sin conocer SQLAlchemy

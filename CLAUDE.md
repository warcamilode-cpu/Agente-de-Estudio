# CLAUDE.md — Agente de Estudio / Atalaya Pléyades

> Archivo de contexto para sesiones de Claude Code.
> Leé este archivo completo antes de tocar cualquier código.

---

## Idioma
Responde siempre en español colombiano.

---

## Qué es este proyecto

Aplicación web personal de estudio tipo "todo en uno" llamada **Atalaya Pléyades**. Combina:
- Chat con IA tutora (Shaula) con contexto de apuntes propios
- Cuaderno Cornell con estructura programa → semestre → materia → clase
- Sistema de flashcards con spaced repetition (algoritmo SM-2)
- Repositorio de documentos con análisis por IA (Maia)
- Planificador de estudio con agente Atlas y evaluador Electra
- Dashboard de progreso y estadísticas

**Dominio:** derecho colombiano + programación Python
**Usuarios:** uso personal (1 usuario, no hay auth)
**Acceso:** servidor Ubuntu local (Tailscale) + VPS Google Cloud (34.28.13.222:8070)

---

## Stack tecnológico

| Capa | Tecnología | Notas |
|------|-----------|-------|
| Backend | FastAPI (Python 3.11+) | Uvicorn como servidor |
| Base de datos | SQLite | Un solo archivo `estudio.db` |
| IA activa | Anthropic Claude API | `claude-haiku-4-5-20251001` |
| IA futura | Ollama local | Qwen3 8B Q4_K_M — ver `STACK_IA_LOCAL.md` |
| Frontend | HTML + CSS + Vanilla JS | Sin frameworks, sin build step |
| Extracción de texto | pdfplumber, python-docx | Para RAG de documentos |
| Embeddings semánticos | sentence-transformers | `all-MiniLM-L6-v2` (384 dims), carga lazy con fallback a BM25 |
| Búsqueda vectorial | sqlite-vec | Extensión SQLite para `vec0`; fallback a coseno en Python si no está |

**No usar:** React, Vue, SQLAlchemy ORM, Alembic, Docker.
**Sí usar:** sqlite3 nativo de Python, anthropic SDK oficial.

---

## Estructura de directorios

```
Agente-de-Estudio/
│
├── CLAUDE.md                  # Este archivo
├── STACK_IA_LOCAL.md          # Decisiones del stack de modelos locales (Qwen3, Whisper, bge-m3)
├── main.py                    # Entry point FastAPI + lifespan
├── .env                       # Variables de entorno (no commitear)
├── .env.example               # Plantilla
├── requirements.txt
├── estudio.db                 # SQLite (se crea automático)
│
├── routers/
│   ├── ai_router.py           # Shaula — chat SSE, historial persistente en DB, paginación de sesiones
│   ├── cuaderno_router.py     # Cuaderno Cornell: programas, semestres, materias, clases, apuntes, acciones, referencias
│   ├── documentos_router.py   # Maia — repositorio con paginación, análisis RAG (semántico + BM25), biblioteca
│   ├── plan_router.py         # Atlas (planificador) + Electra (evaluador) — planes de estudio SSE
│   ├── flashcards_router.py   # CRUD flashcards + algoritmo SM-2
│   ├── notas_router.py        # CRUD notas Markdown con tags
│   ├── topics_router.py       # CRUD topics (legacy, pre-cuaderno)
│   └── dashboard_router.py    # Stats diarias, racha, métricas de tokens, backup manual, progreso por materia
│
├── services/
│   ├── llm_client.py          # Abstracción Claude/Ollama — logs de tokens y duración, guarda métricas en DB
│   ├── context_builder.py     # Busca apuntes Cornell + referencias + documentos para el chat (semántico + BM25)
│   ├── embedder.py            # Lazy-load all-MiniLM-L6-v2; generar_embedding() → lista 384 floats o None
│   ├── extractor.py           # Extrae texto de PDF/TXT/MD/JSON para RAG
│   ├── logging_config.py      # Logging estructurado con rotación de archivos (logs/app.log, 5MB × 5)
│   ├── backup.py              # Backup manual/automático de estudio.db → backups/estudio_YYYYMMDD_HHMMSS.db
│   └── srs_engine.py          # Algoritmo SM-2 puro
│
├── database/
│   ├── connection.py          # Conexión SQLite, context manager db(), init_db(), migraciones
│   └── schema.sql             # Schema base (migraciones adicionales en connection.py)
│
├── frontend/
│   ├── index.html             # SPA principal
│   ├── img/                   # Imágenes de los agentes (shaula, atlas, electra, maia, aldebaran, etc.)
│   ├── css/styles.css
│   └── js/
│       ├── app.js             # Router de tabs, estado del sidebar, evento tabchange
│       ├── chat.js            # Shaula — streaming SSE, historial, sesiones
│       ├── cuaderno.js        # Cuaderno Cornell completo
│       ├── documentos.js      # Maia — subida, análisis RAG, biblioteca
│       ├── plan.js            # Atlas + Electra — generación y chat de planes
│       ├── flashcards.js      # Repaso con flip de cards
│       ├── notas.js           # CRUD notas
│       ├── temas.js           # CRUD topics
│       ├── dashboard.js       # Estadísticas
│       └── sprites.js         # Sprites animados de agentes (movimiento libre + drag)
│
└── uploads/                   # Archivos subidos por el usuario (PDF, TXT, MD, JSON)
```

---

## Variables de entorno (`.env`)

```env
LLM_PROVEEDOR=claude

ANTHROPIC_API_KEY=sk-ant-...
MODELO_CLAUDE=claude-haiku-4-5-20251001

# Ollama (pendiente — ver STACK_IA_LOCAL.md)
# OLLAMA_BASE_URL=http://localhost:11434
# MODELO_OLLAMA=qwen3:8b

APP_HOST=0.0.0.0
APP_PORT=8000
```

---

## Base de datos — schema completo

El schema base está en `database/schema.sql`. Las tablas agregadas posteriormente se crean en `database/connection.py` → función `_migraciones()` (idempotente, usa `PRAGMA table_info` antes de cada `ALTER TABLE`).

### Tablas base (`schema.sql`)

```sql
topics            -- temas legacy (pre-cuaderno)
notas             -- notas Markdown con tags y topic_id
flashcards        -- cards SM-2 con topic_id, nota_id, materia_id
sesiones_estudio  -- registro de sesiones de repaso
```

### Tablas agregadas por migraciones (`connection.py`)

```sql
-- Jerarquía del cuaderno Cornell
programas         -- programa académico (pregrado/posgrado)
semestres         -- semestre con programa_id
materias          -- materia con semestre_id, emoji, color, docente
clases            -- clase con materia_id, fecha, titulo, temas
apuntes_cornell   -- indicios / notas_principales / resumen por clase (1:1 con clases)
acciones_clase    -- pendientes/tareas/dudas por clase
referencias_rapidas -- términos y definiciones por materia o clase

-- Documentos y RAG
documentos        -- archivos subidos (PDF/TXT/MD/JSON) con materia_id, semestre_id, programa_id
documento_chunks  -- fragmentos de texto para búsqueda BM25 (doc_id, chunk_idx, texto)

-- Chat
sesiones_chat     -- sesiones del chat de Shaula con session_id UUID
mensajes          -- historial persistido (actualmente no se usa — el historial vive en memoria)

-- Planificador
planes_estudio    -- planes generados por Atlas (materia_id, tema, plan_texto)

-- Biblioteca de análisis Maia
maia_analisis     -- análisis guardados (titulo, pregunta, respuesta, doc_id, materia_id)
```

### Columnas adicionales relevantes

- `topics.parent_id` — jerarquía de topics (migración)
- `flashcards.materia_id` — asociación a materia del cuaderno
- `documentos.semestre_id`, `documentos.programa_id` — jerarquía completa en documentos
- `referencias_rapidas.clase_id` — referencias por clase (además de por materia)

---

## API — endpoints por router

### `/ai` — Shaula (chat tutora)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/ai/chat/nueva-sesion` | Crea `session_id` UUID |
| POST | `/ai/chat/stream` | Chat streaming SSE — **único usado en frontend** |
| DELETE | `/ai/chat/{session_id}` | Limpia historial en memoria |
| GET | `/ai/chat/{session_id}/historial` | Debug |

Body: `{ "session_id": "uuid", "message": "texto", "materia_id": 1 }`

### `/cuaderno` — Cuaderno Cornell

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/cuaderno/programas` | Listar / crear programas |
| PUT/DELETE | `/cuaderno/programas/{id}` | Editar / eliminar |
| GET/POST | `/cuaderno/semestres` | Listar / crear semestres |
| GET/POST | `/cuaderno/materias` | Listar por semestre / crear |
| PATCH | `/cuaderno/materias/{id}/info` | Actualizar docente, email, salón |
| GET/POST | `/cuaderno/clases` | Listar por materia / crear |
| GET/PUT | `/cuaderno/clases/{id}/apuntes` | Obtener / guardar apuntes Cornell |
| GET/POST | `/cuaderno/acciones` | Listar por clase / crear acción |
| PATCH | `/cuaderno/acciones/{id}/toggle` | Marcar resuelta/pendiente |
| GET/POST | `/cuaderno/referencias` | Listar por materia o clase / crear |
| GET | `/cuaderno/estructura` | Árbol completo programa→semestre→materia |

### `/documentos` — Maia (repositorio)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/documentos` | Listar con paginación (`page`, `page_size`; filtros: `materia_id`, `semestre_id`, `programa_id`) |
| POST | `/documentos` | Subir archivo (multipart: archivo, titulo, materia_id, semestre_id, programa_id, tags) |
| GET | `/documentos/{id}` | Obtener metadatos |
| GET | `/documentos/{id}/archivo` | Servir archivo original (inline) |
| DELETE | `/documentos/{id}` | Eliminar documento y archivo |
| POST | `/documentos/analisis/stream` | Chat con Maia sobre documentos (SSE, BM25 RAG) |
| GET/POST | `/documentos/biblioteca` | Listar / guardar análisis de Maia |
| DELETE | `/documentos/biblioteca/{id}` | Eliminar análisis |

### `/plan` — Atlas + Electra

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/plan/planificador` | Genera plan completo (síncrono, 3 módulos) |
| GET | `/plan/planificador/planes` | Listar planes guardados |
| GET | `/plan/planificador/planes/{id}` | Obtener plan por ID |
| POST | `/plan/planificador/chat/stream` | Chat sobre el plan (modo `chat`=Atlas / `evaluador`=Electra) |

Body chat: `{ "plan_id": 1, "mensaje": "texto", "historial": [], "modo": "chat" }`

### `/ai` — sesiones (paginadas)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/ai/sesiones` | Listar sesiones con paginación (`page`, `page_size`) — retorna `{data, total, page, page_size}` |

### `/dashboard` — estadísticas y utilidades

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/dashboard/resumen` | Resumen del día (notas, flashcards, tiempo estudiado) |
| GET | `/dashboard/racha` | Racha de días de estudio consecutivos |
| POST | `/dashboard/sesion` | Registrar sesión de estudio |
| GET | `/dashboard/metricas` | Uso de tokens LLM en los últimos N días (param `dias=30`) |
| POST | `/dashboard/backup` | Crea backup manual de estudio.db → `backups/` |
| GET | `/dashboard/progreso/{materia_id}` | Progreso por materia |
| GET | `/health` | Health check: `{status, timestamp, db, llm}` |

### `/flashcards`, `/notas`, `/topics`

Sin cambios respecto a la versión anterior — ver código de cada router.

---

## Servicios clave

### `services/llm_client.py`

Único punto de contacto con la IA. Nunca importar `anthropic` directamente en los routers.

```python
def preguntar(system_prompt: str, mensajes: list[dict], max_tokens: int | None = None) -> str
def preguntar_stream(system_prompt: str, mensajes: list[dict], max_tokens: int | None = None) -> Generator[str, None, None]
```

Valores por defecto: `_MAX_TOKENS = 4096`, `_MAX_TOKENS_PLAN = 8192`.
El proveedor se controla con `LLM_PROVEEDOR` en `.env` — cambiar de Claude a Ollama no toca ningún router.

### `services/context_builder.py`

Busca contexto relevante en la DB para el chat de Shaula. Combina tres fuentes:

```python
def construir_contexto(mensaje: str, materia_id: int | None) -> tuple[str, int]
# Busca en: apuntes Cornell (indicios + notas), referencias rápidas, chunks de documentos
# Retorna: (texto_contexto, n_fuentes_encontradas)

def construir_system_prompt(contexto: str) -> str
# Genera el system prompt de Shaula con el contexto inyectado
```

La búsqueda usa `LIKE` sobre los textos. No hay embeddings aún — ver `STACK_IA_LOCAL.md` para la migración a bge-m3.

### `services/embedder.py`

Genera embeddings semánticos con `all-MiniLM-L6-v2` (384 dimensiones). Carga el modelo de forma lazy al primer uso. Si `sentence-transformers` no está instalado o el modelo falla, retorna `None` y el sistema cae en BM25.

```python
def generar_embedding(texto: str) -> list[float] | None   # vector normalizado 384-d o None
def disponible() -> bool                                   # True si el modelo cargó correctamente
```

Las tablas de persistencia son:
- `chunk_embeddings(chunk_id, doc_id, embedding TEXT)` — JSON del vector, siempre disponible
- `vec_chunks` — tabla virtual `vec0` de sqlite-vec (float[384]), creada solo si la extensión carga

### `services/extractor.py`

Extrae texto plano de archivos subidos para indexar en `documento_chunks`.

```python
def extraer_texto(ruta: str) -> str      # PDF, TXT, MD, JSON
def chunkear_texto(texto: str) -> list[str]  # fragmentos de ~500 chars con solapamiento
```

### `services/srs_engine.py`

Algoritmo SM-2 puro, sin efectos secundarios.

```python
def calcular_siguiente_repaso(calificacion, intervalo_actual, repeticiones, factor_facilidad) -> tuple[int, int, float]
```

---

## Agentes y personalidades

| Agente | Rol | Modo Qwen3 (futuro) | Imagen |
|--------|-----|---------------------|--------|
| **Shaula** | Tutora de chat — enseña paso a paso | `/no_think` | `shaula.png` |
| **Atlas** | Planificadora — genera planes de 3 módulos | `/think` | `atlas.png` |
| **Electra** | Evaluadora — examen en 2 partes (4 teóricas + 4 prácticas) | `/think` | `electra.png` |
| **Maia** | Análisis documental — RAG sobre repositorio | `/no_think` | `maia.png` |
| **Aldebarán** | Avatar del usuario | — | `aldebaran.png` |

---

## Decisiones de arquitectura

**Historial de chat en memoria:** efímero, válido solo durante la sesión activa. Si el servidor reinicia, el usuario abre sesión nueva — aceptable para uso personal.

**BM25-lite para RAG de Maia:** búsqueda por frecuencia de términos sobre los chunks. Suficiente hoy. La migración a embeddings semánticos (bge-m3 via Ollama) está planificada en Fase 2 del stack local.

**Rutas literales antes que paramétricas:** en FastAPI, `/documentos/biblioteca` debe registrarse ANTES de `/documentos/{doc_id}` para evitar que el parámetro capture la ruta literal.

**SQLite sobre PostgreSQL:** un usuario, uso personal, sin concurrencia. SQLite elimina un proceso externo.

**Vanilla JS sobre React:** sin build step, editable desde iPad, archivos estáticos servidos por FastAPI.

---

## Cómo correr el proyecto

```bash
# Local
source venv/bin/activate
pip install -r requirements.txt python-multipart
cp .env.example .env  # completar ANTHROPIC_API_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# VPS (systemd)
sudo systemctl start atalaya    # iniciar
sudo systemctl restart atalaya  # reiniciar tras git pull
sudo systemctl status atalaya   # verificar
```

---

## Estado del proyecto

### Completado ✅
- [x] Cuaderno Cornell completo (programas → semestres → materias → clases → apuntes)
- [x] Referencias rápidas por materia y por clase
- [x] Repositorio de documentos con RAG BM25 (Maia)
- [x] Biblioteca de análisis de Maia
- [x] Planificador Atlas — 3 módulos (concepto / 3 ejemplos por dificultad / 10 preguntas)
- [x] Evaluador Electra — 2 partes (4 teóricas + 4 prácticas medio/difícil, diagnóstico sobre 8)
- [x] Sprites animados de agentes con movimiento libre y drag en el sidebar
- [x] Deploy en VPS Google Cloud con systemd
- [x] Imágenes de todos los agentes en `frontend/img/`

### Pendiente 📋
- [ ] Migración a Qwen3 8B via Ollama (ver `STACK_IA_LOCAL.md` — Fase 1)
- [ ] RAG semántico con bge-m3 para Maia (Fase 2)
- [ ] Agente de transcripción con Whisper.cpp medium (Fase 3)
- [ ] Voz conversacional con Kokoro TTS (Fase 4)
- [x] Rate limiting con slowapi (60 req/min global) + exception handler global en main.py
  - Errores HTTP retornan `{"error": true, "detail": "...", "code": N}`
  - Stream de Shaula captura excepciones y devuelve mensaje de error en vez de romper la conexión
  - slowapi agregado a requirements.txt
- [x] Indicador "escribiendo…" en chat.js y plan.js
  - Dots animados con CSS `typing-bounce` mientras el agente genera respuesta
  - Muestra avatar del agente activo (Shaula, Atlas o Electra según modo)
  - Se elimina automáticamente cuando termina el stream o si hay error
- [x] Unificar topics y materias: materia_id en notas (migración idempotente), filtro por materia_id en notas_router, búsqueda de notas en context_builder por materia_id
  - topics sigue existiendo como sistema legacy (no se eliminan datos)
  - notas.materia_id → FK opcional a materias(id)
  - context_builder ahora busca en 4 fuentes: apuntes Cornell, referencias, notas por materia, documentos

- [x] Tests backend: test_srs_engine.py (8 tests), test_extractor.py (10 tests), conftest.py con fixture DB en memoria
  - Correr con: `pytest tests/ -v`
  - pytest y httpx agregados a requirements.txt

### Completado recientemente ✅
- [x] Mejoras de producción (TAREAS_MEJORAS.md — alta y media prioridad)
  - **Sesiones persistentes**: `_cargar_historial()` siempre carga desde DB, el chat sobrevive reinicios del servidor
  - **Logging estructurado**: `services/logging_config.py` con RotatingFileHandler (5MB × 5 archivos en `logs/app.log`); `llm_client.py` loguea modelo, tokens y duración por cada llamada
  - **Tests dashboard arreglados**: `conftest.py` expone `dashboard_app` fixture (FastAPI sin slowapi); `test_dashboard.py` usa Option B (router directo); 22/22 tests pasan
  - **Health check**: `GET /health` retorna `{status, timestamp, db, llm}` — verifica conexión a DB y API key configurada
  - **Paginación**: `GET /ai/sesiones` y `GET /documentos` aceptan `page`/`page_size`, retornan `{data, total, page, page_size}`
  - **Métricas de tokens**: tabla `metricas_tokens` registra tokens_in/out y duración por llamada LLM; `GET /dashboard/metricas` expone resumen por período
  - **Backup automático**: `services/backup.py` copia estudio.db a `backups/estudio_YYYYMMDD_HHMMSS.db`; `POST /dashboard/backup` dispara backup manual; retiene últimos 7

- [x] Búsqueda semántica con sqlite-vec en context_builder (complementa y reemplaza BM25 para documentos)
  - `services/embedder.py` — lazy-load `all-MiniLM-L6-v2` (384 dims); fallback automático a BM25 si no está disponible
  - `chunk_embeddings` — tabla SQLite estándar que guarda los vectores como JSON (portable, sin extensión)
  - `vec_chunks` — tabla virtual `vec0` de sqlite-vec cargada como extensión en `get_connection()`
  - Al subir un documento se generan embeddings por chunk y se persisten en ambas tablas
  - `context_builder._buscar_documentos()` intenta búsqueda semántica (coseno) primero; cae en BM25 si el modelo no cargó o no hay embeddings
  - `sqlite-vec` y `sentence-transformers` agregados a requirements.txt

- [x] Registrar sesiones de estudio desde el frontend
  - `POST /dashboard/sesion` — recibe tipo, duracion_seg, materia_id, cards_revisadas, cards_correctas
  - `registrarSesion()` en dashboard.js llamada al salir del repaso de flashcards
  - flashcards.js mide tiempo y cuenta correctas (cal >= 3) al finalizar el repaso

---

## Convenciones de código

- **Python:** snake_case, type hints en todas las funciones
- **SQL:** keywords en MAYÚSCULAS, aliases en minúsculas
- **Commits:** en español, descriptivos
- **Errores:** `HTTPException` de FastAPI, nunca `print()` en producción
- **No ORM:** queries SQL directas con `sqlite3`
- **Rutas FastAPI:** literales antes que paramétricas en el mismo router

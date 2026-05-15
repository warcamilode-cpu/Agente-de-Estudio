# Stack de IA Local — Atalaya Pléyades

> Documento de referencia para la migración del backend de IA de Claude API a modelos locales.
> Todas las decisiones aquí registradas fueron definidas antes de iniciar la implementación.

---

## Contexto de hardware

| Componente | Especificación |
|-----------|---------------|
| GPU | NVIDIA GTX 1080 Ti — 11 GB VRAM |
| CPU | AMD Ryzen 5 3600X — 6 núcleos / 12 hilos, AVX2 ✓ |
| RAM | Mínimo recomendado: 16 GB |

---

## Modelos definidos

### 1. Qwen3 8B Q4_K_M — Motor principal de texto
**Proveedor:** Ollama  
**Ejecuta en:** GPU  
**VRAM:** ~5.5 GB  
**RAM adicional:** ~1.5 GB  

Modelo principal para todos los agentes conversacionales. Se eligió sobre DeepSeek-R1 8B por:
- Soporte multilenguaje superior (español colombiano)
- Modo híbrido de razonamiento: `/think` y `/no_think` por agente
- Mejor rendimiento conversacional sin razonamiento forzado

**Asignación por agente:**

| Agente | Modo Qwen3 | Justificación |
|--------|-----------|---------------|
| Shaula (tutora chat) | `/no_think` | Conversación fluida, respuestas rápidas |
| Atlas (planificadora) | `/think` | Genera planes estructurados complejos |
| Electra (evaluadora) | `/think` | Formula y evalúa ejercicios de dificultad alta |
| Maia (documental) | `/no_think` | Consulta documental, no razonamiento complejo |

**Ruta de upgrade (cuando sea necesario):**  
Probar **14B Q3_K_M** (~7 GB modelo + KV cache). Riesgo: OOM en generaciones largas de Atlas (planes completos pueden llevar el total a 10.5–11 GB VRAM). El switch es un cambio de una línea en `.env` sin tocar ningún router.

---

### 2. Whisper.cpp medium — Transcripción de audio y video
**Proveedor:** Whisper.cpp (proceso nativo)  
**Ejecuta en:** CPU  
**VRAM:** 0  
**RAM:** ~1 GB durante transcripción  
**CPU:** Alto consumo solo al transcribir, 0 en reposo  

Se eligió el modelo `medium` sobre `large-v3-turbo` por la relación velocidad/calidad en el Ryzen 5 3600X:

| Modelo | RAM | Velocidad en 3600X | Calidad español |
|--------|-----|--------------------|----------------|
| large-v3-turbo | ~1.5 GB | ~0.5x real-time | Excelente |
| **medium** ✓ | ~1 GB | ~1.5x real-time | Muy buena |
| small | ~500 MB | ~3x real-time | Buena |

**Casos de uso:**
- Transcripción de clases y videos completos (proceso asíncrono en background)
- Entrada de voz del usuario en modo conversacional (futuro — ver sección Voz)

---

### 3. bge-m3 — Embeddings semánticos para Maia
**Proveedor:** Ollama  
**Ejecuta en:** CPU  
**VRAM:** 0  
**RAM:** ~1.1 GB cuando activo  

Reemplaza el BM25-lite actual de Maia por búsqueda semántica real. Se eligió bge-m3 sobre alternativas (nomic-embed-text, mxbai-embed-large) por mejor soporte multilenguaje, especialmente en español.

**Cuándo se activa:**
- Al subir un documento: genera embeddings de todos los chunks → los almacena en DB
- Al consultar Maia: genera embedding de la pregunta → busca por similitud coseno

---

## Regla de exclusión CPU

**Whisper.cpp y bge-m3 no pueden correr simultáneamente.**

El Ryzen 5 3600X con ambos modelos activos al mismo tiempo satura los 12 hilos. La implementación usa un semáforo único en el backend:

```
Whisper activo  →  bge-m3 espera en cola
bge-m3 activo   →  Whisper espera en cola
```

El usuario ve un mensaje de estado cuando su acción queda en espera.

---

## Outputs de Maia — sin modelo adicional

Todos los outputs de Maia se generan con Qwen3 8B. Los visuales se renderizan en el frontend con librerías JS sin peso adicional en el servidor:

| Output | Cómo se genera | Renderizado |
|--------|---------------|-------------|
| Resumen | Qwen3 genera texto | Markdown en frontend |
| Script de podcast | Qwen3 genera guión conversacional | Texto / futuro TTS |
| Diagrama de flujo | Qwen3 genera sintaxis Mermaid | Mermaid.js |
| Mapa mental | Qwen3 genera JSON estructurado | markmap.js |
| Infografía | Qwen3 genera HTML/SVG | Renderizado directo en frontend |

---

## Voz — definido, implementación diferida

Pipeline completo de voz conversacional con los agentes (definido, no implementado aún):

```
Voz usuario  →  Whisper.cpp medium (CPU)  →  texto
                                                ↓
                                       Qwen3 8B (GPU)
                                                ↓
Voz agente   ←  Kokoro TTS (CPU)       ←  texto respuesta
```

**TTS seleccionado:** Kokoro (~82 MB, CPU, calidad alta en español)  
**Modo de operación:** media dúplex — micrófono se abre automáticamente cuando el agente termina de hablar, evitando eco  
**Activación:** el usuario elige modo texto o modo voz al iniciar cada sesión con un agente  

> Kokoro excluido del stack activo hasta que se implemente la capa de voz.

---

## Resumen de consumo de recursos

| Modelo | GPU VRAM | RAM | CPU |
|--------|---------|-----|-----|
| Qwen3 8B Q4_K_M | ~5.5 GB | ~1.5 GB | Mínimo |
| Whisper.cpp medium | 0 | ~1 GB | Alto (solo al transcribir) |
| bge-m3 | 0 | ~1.1 GB | Bajo (solo al indexar/consultar) |
| **Total máximo** | **~5.5 GB / 11 GB** | **~4 GB** | — |

VRAM libre disponible para KV cache de Qwen3: ~5.5 GB — margen cómodo para planes largos de Atlas.

---

## Fases de implementación

**Fase 1 — Qwen3 via Ollama para todos los agentes**  
Extender `services/llm_client.py` para routing por agente (modelo + modo think/no-think). Reemplaza Claude API para Shaula, Atlas, Electra y Maia.

**Fase 2 — RAG semántico de Maia con bge-m3**  
Reemplazar BM25-lite por embeddings reales. Nueva tabla `documento_embeddings` en SQLite. Sin cambios en la API existente.

**Fase 3 — Whisper.cpp + agente de transcripción**  
Nuevo servicio `services/whisper_client.py`. Nuevo router `routers/transcripciones_router.py`. El texto transcripto entra al sistema de documentos existente y Maia lo puede analizar.

**Fase 4 — Voz conversacional (diferida)**  
Integración de Kokoro TTS + loop de voz media dúplex con todos los agentes.

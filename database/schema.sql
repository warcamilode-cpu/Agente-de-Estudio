CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    descripcion TEXT,
    color       TEXT DEFAULT '#6366f1',
    creado_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id       INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    titulo         TEXT NOT NULL,
    contenido      TEXT NOT NULL,
    tags           TEXT DEFAULT '',
    creada_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizada_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flashcards (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id         INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    nota_id          INTEGER REFERENCES notas(id) ON DELETE SET NULL,
    pregunta         TEXT NOT NULL,
    respuesta        TEXT NOT NULL,
    intervalo        INTEGER DEFAULT 1,
    repeticiones     INTEGER DEFAULT 0,
    factor_facilidad REAL DEFAULT 2.5,
    proximo_repaso   DATE DEFAULT (date('now')),
    creada_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sesiones_estudio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    tipo            TEXT NOT NULL,
    duracion_seg    INTEGER DEFAULT 0,
    cards_revisadas INTEGER DEFAULT 0,
    cards_correctas INTEGER DEFAULT 0,
    iniciada_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    titulo          TEXT NOT NULL,
    tipo            TEXT NOT NULL,
    archivo_nombre  TEXT NOT NULL,
    archivo_path    TEXT NOT NULL,
    contenido_texto TEXT DEFAULT '',
    tags            TEXT DEFAULT '',
    creado_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notas_topic       ON notas(topic_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_repaso ON flashcards(proximo_repaso);
CREATE INDEX IF NOT EXISTS idx_flashcards_topic  ON flashcards(topic_id);
CREATE INDEX IF NOT EXISTS idx_documentos_topic  ON documentos(topic_id);

-- ── Cuaderno ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS semestres (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL,
    orden     INTEGER DEFAULT 0,
    creado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materias (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    semestre_id   INTEGER NOT NULL REFERENCES semestres(id) ON DELETE CASCADE,
    nombre        TEXT NOT NULL,
    emoji         TEXT DEFAULT '📚',
    color         TEXT DEFAULT '#6366f1',
    docente       TEXT DEFAULT '',
    email_docente TEXT DEFAULT '',
    salon         TEXT DEFAULT '',
    creada_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    materia_id INTEGER NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    fecha      DATE NOT NULL,
    titulo     TEXT NOT NULL,
    temas      TEXT DEFAULT '',
    creada_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS apuntes_cornell (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    clase_id          INTEGER NOT NULL UNIQUE REFERENCES clases(id) ON DELETE CASCADE,
    indicios          TEXT DEFAULT '',
    notas_principales TEXT DEFAULT '',
    resumen           TEXT DEFAULT '',
    actualizado_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS acciones_clase (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    clase_id  INTEGER NOT NULL REFERENCES clases(id) ON DELETE CASCADE,
    tipo      TEXT NOT NULL,   -- '?' | '*' | 'T'
    contenido TEXT NOT NULL,
    resuelto  INTEGER DEFAULT 0,
    creada_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS referencias_rapidas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    materia_id  INTEGER NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    termino     TEXT NOT NULL,
    definicion  TEXT NOT NULL,
    creada_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_materias_semestre  ON materias(semestre_id);
CREATE INDEX IF NOT EXISTS idx_clases_materia     ON clases(materia_id);
CREATE INDEX IF NOT EXISTS idx_acciones_clase     ON acciones_clase(clase_id);
CREATE INDEX IF NOT EXISTS idx_referencias_materia ON referencias_rapidas(materia_id);

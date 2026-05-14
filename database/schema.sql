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

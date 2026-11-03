-- Fase 5: timelapses. Cada linha é um pedido na fila e, quando pronto, o vídeo em cache.

CREATE TABLE timelapses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id      INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- de quem são as selfies
    requested_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    fps          INTEGER NOT NULL,
    -- "Impressão digital" das fotos usadas. Se uma foto entra ou é trocada, ela muda
    -- e o vídeo em cache deixa de valer.
    fingerprint  TEXT NOT NULL,
    frame_count  INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'error')),
    progress     REAL NOT NULL DEFAULT 0,  -- 0 a 1
    file_name    TEXT,                     -- vídeo criptografado, igual às fotos
    error        TEXT,
    created_at   TEXT NOT NULL,
    finished_at  TEXT
);
CREATE INDEX timelapses_lookup ON timelapses(trip_id, user_id, fps);
CREATE INDEX timelapses_queue ON timelapses(status, id);

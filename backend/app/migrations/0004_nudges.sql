-- Fase 4: cutucadas ("ei, tira a foto antes que o dia acabe!").
-- No máximo uma por amigo por dia (o UNIQUE garante).

CREATE TABLE nudges (
    id           INTEGER PRIMARY KEY,
    from_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day          TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    seen_at      TEXT,
    UNIQUE (from_user_id, to_user_id, day)
);
CREATE INDEX nudges_to_day ON nudges(to_user_id, day);

-- Fase 3: fotos. A selfie é da pessoa (vale pra todas as viagens dela);
-- a foto extra é publicada numa viagem específica.

CREATE TABLE photos (
    -- AUTOINCREMENT: um id apagado nunca volta. Assim uma foto substituída
    -- sempre ganha id (e URL) novo, e o navegador não mostra a antiga do cache.
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,                -- 'YYYY-MM-DD' no fuso do Rewind, calculado no servidor
    kind       TEXT NOT NULL CHECK (kind IN ('selfie', 'extra')),
    trip_id    INTEGER REFERENCES trips(id) ON DELETE CASCADE,
    file_name  TEXT NOT NULL UNIQUE,         -- aleatório; o arquivo fica criptografado
    width      INTEGER NOT NULL,
    height     INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    -- selfie nunca tem viagem; extra sempre tem
    CHECK ((kind = 'selfie' AND trip_id IS NULL) OR (kind = 'extra' AND trip_id IS NOT NULL))
);

-- Uma selfie por pessoa por dia.
CREATE UNIQUE INDEX photos_one_selfie_per_day ON photos(user_id, day) WHERE kind = 'selfie';
CREATE INDEX photos_trip_day ON photos(trip_id, day);

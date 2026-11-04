-- Foto de corpo (no espelho): opcional, uma por dia, só depois da selfie do rosto.
-- Tem o próprio timelapse, pra não misturar rosto e corpo no mesmo vídeo.
--
-- Os tipos ficam num CHECK, e o SQLite não deixa mudar um CHECK: a tabela é recriada.
-- Nenhuma tabela aponta pra photos, então não há cascata pra se preocupar.

CREATE TABLE photos_new (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('selfie', 'body', 'extra')),
    trip_id    INTEGER REFERENCES trips(id) ON DELETE CASCADE,
    file_name  TEXT NOT NULL UNIQUE,
    width      INTEGER NOT NULL,
    height     INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    -- selfie e corpo são da pessoa (valem em todos os álbuns); extra é de um álbum
    CHECK ((kind IN ('selfie', 'body') AND trip_id IS NULL) OR (kind = 'extra' AND trip_id IS NOT NULL))
);
INSERT INTO photos_new (id, user_id, day, kind, trip_id, file_name, width, height, size_bytes, created_at)
    SELECT id, user_id, day, kind, trip_id, file_name, width, height, size_bytes, created_at FROM photos;

-- Leva junto o contador do AUTOINCREMENT: se ele recomeçasse, uma foto nova poderia
-- ganhar o id de uma apagada, e o navegador mostraria a velha que ficou no cache.
DELETE FROM sqlite_sequence WHERE name = 'photos_new';
INSERT INTO sqlite_sequence (name, seq) SELECT 'photos_new', seq FROM sqlite_sequence WHERE name = 'photos';

DROP TABLE photos;
ALTER TABLE photos_new RENAME TO photos;

-- Uma selfie e uma foto de corpo por pessoa por dia (extras ficam livres).
CREATE UNIQUE INDEX photos_one_per_day ON photos(user_id, day, kind) WHERE kind IN ('selfie', 'body');
CREATE INDEX photos_trip_day ON photos(trip_id, day);

-- Cada timelapse é de um tipo: rosto (selfie) ou corpo.
ALTER TABLE timelapses ADD COLUMN kind TEXT NOT NULL DEFAULT 'selfie' CHECK (kind IN ('selfie', 'body'));
DROP INDEX timelapses_lookup;
CREATE INDEX timelapses_lookup ON timelapses(trip_id, user_id, kind, fps);

-- A data final do álbum passa a ser opcional: tem álbum que não se sabe quando acaba.
-- NULL = sem data final. Com data, o álbum fica "encerrado" quando o dia passa dela.
--
-- O SQLite não tira o NOT NULL de uma coluna, então a tabela é recriada (o jeito
-- oficial: cria a nova, copia, apaga a velha, renomeia). As chaves estrangeiras
-- ficam desligadas durante a migração (veja db.migrate), por isso nada é apagado
-- em cascata.

CREATE TABLE trips_new (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    end_date   TEXT,                       -- 'YYYY-MM-DD' (último dia do álbum) ou NULL
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
INSERT INTO trips_new (id, name, end_date, created_by, created_at)
    SELECT id, name, end_date, created_by, created_at FROM trips;
DROP TABLE trips;
ALTER TABLE trips_new RENAME TO trips;

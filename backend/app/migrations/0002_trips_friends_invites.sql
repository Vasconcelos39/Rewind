-- Fase 2: amizades, viagens e convites.

-- Um pedido de amizade vira amizade quando o outro aceita.
CREATE TABLE friendships (
    id           INTEGER PRIMARY KEY,
    requester_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    addressee_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status       TEXT NOT NULL CHECK (status IN ('pending', 'accepted')),
    created_at   TEXT NOT NULL,
    accepted_at  TEXT,
    CHECK (requester_id != addressee_id)
);
-- Um só registro por dupla, não importa quem pediu (A→B e B→A são a mesma amizade).
CREATE UNIQUE INDEX friendships_pair
    ON friendships(min(requester_id, addressee_id), max(requester_id, addressee_id));

CREATE TABLE trips (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    end_date   TEXT NOT NULL,              -- 'YYYY-MM-DD', a data-meta
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE trip_members (
    trip_id    INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at  TEXT NOT NULL,
    joined_day TEXT NOT NULL,              -- o "dia" (fuso do Rewind) em que entrou: início do timelapse
    PRIMARY KEY (trip_id, user_id)
);
CREATE INDEX trip_members_user ON trip_members(user_id);

-- Convite feito dentro do app, de um membro para um amigo.
CREATE TABLE trip_invites (
    id           INTEGER PRIMARY KEY,
    trip_id      INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    from_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    UNIQUE (trip_id, to_user_id)
);

-- Link de uso único para quem ainda não tem conta (ou para virar amigo de quem mandou).
-- Como nas sessões, guardamos só o sha256 do token.
CREATE TABLE invite_links (
    id         INTEGER PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trip_id    INTEGER REFERENCES trips(id) ON DELETE CASCADE,  -- NULL = só amizade
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at    TEXT,
    used_by    INTEGER REFERENCES users(id) ON DELETE SET NULL
);

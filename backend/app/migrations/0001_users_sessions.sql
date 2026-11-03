-- Fase 1: contas e sessões. As outras tabelas chegam nas próximas migrações.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- "Ana" e "ana" são o mesmo usuário
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,                        -- argon2id, nunca a senha
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

-- Guardamos só o sha256 do token. O token de verdade existe apenas no cookie,
-- então quem copiar o banco não consegue entrar na conta de ninguém.
CREATE TABLE sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);

CREATE INDEX sessions_user ON sessions(user_id);

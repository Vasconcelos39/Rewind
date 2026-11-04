"""Migrações que recriam tabelas não podem perder dados nem quebrar referências."""

import sqlite3

from app import db


def test_0006_keeps_everything_and_cascades_still_work(tmp_path):
    path = tmp_path / "velho.db"
    assert db.migrate(path, upto=5) == 5

    # Um banco "de produção" na versão 5, com uma viagem e tudo pendurado nela.
    c = db.connect(path)
    c.executescript("""
        INSERT INTO users (id, username, display_name, password_hash, created_at)
            VALUES (1, 'ana', 'Ana', 'x', 'agora'), (2, 'bia', 'Bia', 'x', 'agora');
        INSERT INTO trips (id, name, end_date, created_by, created_at)
            VALUES (7, 'Praia', '2027-01-01', 1, 'agora');
        INSERT INTO trip_members (trip_id, user_id, joined_at, joined_day)
            VALUES (7, 1, 'agora', '2026-11-01'), (7, 2, 'agora', '2026-11-02');
        INSERT INTO trip_invites (trip_id, from_user_id, to_user_id, created_at) VALUES (7, 1, 2, 'agora');
        INSERT INTO invite_links (token_hash, created_by, trip_id, created_at, expires_at)
            VALUES ('h', 1, 7, 'agora', 'depois');
        INSERT INTO photos (user_id, day, kind, trip_id, file_name, width, height, size_bytes, created_at)
            VALUES (1, '2026-11-02', 'extra', 7, 'abc', 1, 1, 1, 'agora');
        INSERT INTO timelapses (trip_id, user_id, fps, fingerprint, frame_count, status, created_at)
            VALUES (7, 1, 8, 'f', 2, 'done', 'agora');
    """)
    c.commit()
    c.close()

    assert db.migrate(path) >= 6
    c = db.connect(path)
    counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("trips", "trip_members", "trip_invites", "invite_links", "photos", "timelapses")}
    assert counts == {t: (2 if t == "trip_members" else 1) for t in counts}
    assert c.execute("SELECT end_date FROM trips").fetchone()[0] == "2027-01-01"

    # Agora dá pra ter álbum sem data final...
    c.execute("INSERT INTO trips (name, end_date, created_at) VALUES ('Sem fim', NULL, 'agora')")
    # ...e apagar a viagem ainda leva junto o que é dela (as referências continuam certas).
    c.execute("DELETE FROM trips WHERE id = 7")
    c.commit()
    left = [c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("trip_members", "trip_invites", "invite_links", "photos", "timelapses")]
    assert left == [0, 0, 0, 0, 0]
    c.close()


def test_0007_keeps_photos_and_the_id_counter(tmp_path):
    path = tmp_path / "v6.db"
    db.migrate(path, upto=6)
    c = db.connect(path)
    c.executescript("""
        INSERT INTO users (id, username, display_name, password_hash, created_at) VALUES (1, 'ana', 'Ana', 'x', 'a');
        INSERT INTO photos (user_id, day, kind, file_name, width, height, size_bytes, created_at)
            VALUES (1, '2026-11-01', 'selfie', 'f1', 1, 1, 1, 'a'),
                   (1, '2026-11-02', 'selfie', 'f2', 1, 1, 1, 'a'),
                   (1, '2026-11-03', 'selfie', 'f3', 1, 1, 1, 'a');
        DELETE FROM photos WHERE file_name = 'f3';   -- o id 3 foi usado e apagado
        INSERT INTO timelapses (trip_id, user_id, fps, fingerprint, frame_count, status, created_at)
            SELECT 1, 1, 8, 'f', 2, 'done', 'a' WHERE 0;  -- (sem viagem: só confere a coluna nova)
    """)
    c.commit()
    c.close()

    db.migrate(path)
    c = db.connect(path)
    assert [r[0] for r in c.execute("SELECT file_name FROM photos ORDER BY id")] == ["f1", "f2"]
    # O próximo id continua sendo 4: o 3 (apagado) nunca volta.
    cur = c.execute("INSERT INTO photos (user_id, day, kind, file_name, width, height, size_bytes, created_at)"
                    " VALUES (1, '2026-11-04', 'body', 'f4', 1, 1, 1, 'a')")
    assert cur.lastrowid == 4
    # Uma foto de corpo por dia, e ainda uma selfie por dia.
    for kind in ("body", "selfie"):
        try:
            c.execute("INSERT INTO photos (user_id, day, kind, file_name, width, height, size_bytes, created_at)"
                      f" VALUES (1, '2026-11-0{'4' if kind == 'body' else '1'}', '{kind}', 'dup-{kind}', 1, 1, 1, 'a')")
            dup = False
        except sqlite3.IntegrityError:
            dup = True
        assert dup, kind
    assert "kind" in [r[1] for r in c.execute("PRAGMA table_info(timelapses)")]
    c.close()


def test_foreign_keys_are_back_on_after_migrate(tmp_path):
    path = tmp_path / "x.db"
    db.migrate(path)
    c = db.connect(path)
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    try:
        c.execute("INSERT INTO trip_members (trip_id, user_id, joined_at, joined_day) VALUES (99, 99, 'a', 'b')")
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised

"""Respaldo cifrado, prueba de restauración y restauración con vuelta atrás (D42)."""

import base64
import os
import sqlite3

import pytest

from app import backup


def _db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num TEXT)")
    con.execute("DELETE FROM alembic_version")
    con.execute("INSERT INTO alembic_version VALUES ('0009')")
    con.execute("CREATE TABLE IF NOT EXISTS cursos (id INTEGER PRIMARY KEY, nombre TEXT)")
    con.execute("DELETE FROM cursos")
    con.executemany("INSERT INTO cursos (nombre) VALUES (?)", [(f"curso {i}",) for i in range(rows)])
    con.commit()
    con.close()


def test_respaldo_cifrado_verificado_y_restaurado(tmp_path, monkeypatch):
    monkeypatch.setenv("EDUMASTER_BACKUP_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    db = tmp_path / "base.db"
    _db(db, 5)
    url = f"sqlite:///{db.as_posix()}"
    path = backup.crear(url, tmp_path / "respaldos")
    assert path.read_bytes().startswith(backup.MAGIC)  # cifrado: no se lee el SQLite en claro
    assert b"curso 1" not in path.read_bytes()

    result = backup.verificar(path)
    assert result["ok"] and result["integrity"] == "ok" and result["rows"] == 6

    _db(db, 2)  # "desastre": se pierden datos
    prev = backup.restaurar(path, url, tmp_path / "antes")
    assert prev.exists()
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM cursos").fetchone()[0] == 5


def test_respaldo_alterado_se_rechaza(tmp_path, monkeypatch):
    monkeypatch.setenv("EDUMASTER_BACKUP_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    db = tmp_path / "base.db"
    _db(db, 3)
    path = backup.crear(f"sqlite:///{db.as_posix()}", tmp_path)
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(SystemExit, match="SHA-256"):
        backup.verificar(path)

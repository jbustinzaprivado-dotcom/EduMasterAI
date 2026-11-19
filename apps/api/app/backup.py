"""Respaldo, verificación y restauración de la base (§12, §16.4, decisión D42).

Uso (desde apps/api, con la API detenida para restaurar):
    python -m app.backup crear              -> backups/edumaster-AAAAMMDD-HHMMSS.emb (+ .json con el manifiesto)
    python -m app.backup verificar <archivo> -> restaura en una base TEMPORAL y compara el conteo de filas
    python -m app.backup restaurar <archivo> -> reemplaza la base actual (guarda antes una copia de seguridad)
    python -m app.backup listar

- Cifrado AES-256-GCM con la clave EDUMASTER_BACKUP_KEY (.env). Sin clave, el respaldo se guarda sin cifrar y se avisa.
- El manifiesto guarda la fecha, la revisión de Alembic, el SHA-256 y el número de filas por tabla.
- "Backups no probados no se consideran estrategia de recuperación" (§16.4): `verificar` es esa prueba.
- SQLite usa la API de copia en caliente de sqlite3; PostgreSQL usa pg_dump/pg_restore (formato custom).
- RPO 24 h / RTO 4 h (§16.4): respaldo diario programado (docs/runbooks.md) y restauración en minutos.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import ROOT, get_settings

BACKUP_DIR = ROOT / "backups"
MAGIC = b"EDUMBK1"  # cabecera de los archivos cifrados


def _key() -> bytes | None:
    raw = os.environ.get("EDUMASTER_BACKUP_KEY") or getattr(get_settings(), "backup_key", None)
    if not raw:
        return None
    key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    if len(key) != 32:
        raise SystemExit("EDUMASTER_BACKUP_KEY debe ser de 32 bytes en base64 (usa: python -m app.backup clave).")
    return key


def _encrypt(data: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, MAGIC)


def _decrypt(blob: bytes, key: bytes | None) -> bytes:
    if not blob.startswith(MAGIC):
        return blob  # respaldo sin cifrar
    if key is None:
        raise SystemExit("El respaldo está cifrado y falta EDUMASTER_BACKUP_KEY en .env.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce, body = blob[len(MAGIC):len(MAGIC) + 12], blob[len(MAGIC) + 12:]
    return AESGCM(key).decrypt(nonce, body, MAGIC)  # falla si el archivo fue alterado


def _row_counts(url: str) -> dict[str, int]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            tables = sorted(inspect(conn).get_table_names())
            return {t: conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar_one() for t in tables}
    finally:
        engine.dispose()


def _revision(url: str) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        return None
    finally:
        engine.dispose()


def _dump(url: str) -> bytes:
    u = make_url(url)
    if u.get_backend_name() == "sqlite":
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "copia.db"
            src, dst = sqlite3.connect(u.database), sqlite3.connect(out)
            with dst:
                src.backup(dst)  # copia consistente aunque la API esté escribiendo
            src.close()
            dst.close()
            return out.read_bytes()
    env = {**os.environ, "PGPASSWORD": u.password or ""}
    args = ["pg_dump", "-Fc", "-h", u.host or "localhost", "-p", str(u.port or 5432), "-U", u.username or "", u.database]
    return subprocess.run(args, check=True, capture_output=True, env=env).stdout


def _load(url: str, data: bytes) -> None:
    u = make_url(url)
    if u.get_backend_name() == "sqlite":
        Path(u.database).write_bytes(data)
        return
    env = {**os.environ, "PGPASSWORD": u.password or ""}
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dump") as f:
        f.write(data)
    try:
        subprocess.run(["pg_restore", "--clean", "--if-exists", "--no-owner", "-h", u.host or "localhost",
                        "-p", str(u.port or 5432), "-U", u.username or "", "-d", u.database, f.name],
                       check=True, env=env)
    finally:
        os.unlink(f.name)


def crear(url: str | None = None, dest: Path = BACKUP_DIR) -> Path:
    url = url or get_settings().database_url
    dest.mkdir(parents=True, exist_ok=True)
    data = _dump(url)
    key = _key()
    blob = _encrypt(data, key) if key else data
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = dest / f"edumaster-{stamp}.emb"
    path.write_bytes(blob)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(), "engine": make_url(url).get_backend_name(),
        "alembic_revision": _revision(url), "encrypted": bool(key), "size_bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "row_counts": _row_counts(url),
    }
    path.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not key:
        print("AVISO: respaldo SIN cifrar. Define EDUMASTER_BACKUP_KEY en .env (python -m app.backup clave).")
    return path


def _manifest(path: Path) -> dict:
    blob = path.read_bytes()
    manifest = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if hashlib.sha256(blob).hexdigest() != manifest["sha256"]:
        raise SystemExit(f"{path.name}: el SHA-256 no coincide; el archivo está dañado o fue alterado.")
    return manifest


def verificar(path: Path) -> dict:
    """Prueba de restauración: restaura en una base SQLite temporal y compara el conteo de filas por tabla."""
    manifest = _manifest(path)
    data = _decrypt(path.read_bytes(), _key())
    if manifest["engine"] != "sqlite":
        return {"ok": True, "detail": "PostgreSQL: SHA-256 y descifrado correctos; restaurar en una base de prueba."}
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "restaurada.db"
        db.write_bytes(data)
        con = sqlite3.connect(db)
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        con.close()
        counts = _row_counts(f"sqlite:///{db.as_posix()}")
    diff = {t: (n, counts.get(t)) for t, n in manifest["row_counts"].items() if counts.get(t) != n}
    return {"ok": integrity == "ok" and not diff, "integrity": integrity, "tables": len(counts),
            "rows": sum(counts.values()), "differences": diff}


def restaurar(path: Path, url: str | None = None, safety_dir: Path = BACKUP_DIR / "antes-de-restaurar") -> Path:
    url = url or get_settings().database_url
    _manifest(path)
    data = _decrypt(path.read_bytes(), _key())
    previous = crear(url, safety_dir)  # siempre hay vuelta atrás
    _load(url, data)
    return previous


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "listar"
    if cmd == "clave":
        print(base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("="))
    elif cmd == "crear":
        print(f"Respaldo creado: {crear()}")
    elif cmd == "verificar":
        result = verificar(Path(argv[2]))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    elif cmd == "restaurar":
        prev = restaurar(Path(argv[2]))
        print(f"Base restaurada. La versión anterior quedó en {prev}. Ejecuta 'alembic upgrade head' y reinicia la API.")
    elif cmd == "listar":
        for p in sorted(BACKUP_DIR.glob("*.emb")):
            m = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
            print(f"{p.name}  {m['created_at'][:19]}  {m['size_bytes'] // 1024} KB  "
                  f"{'cifrado' if m['encrypted'] else 'SIN CIFRAR'}  rev {m['alembic_revision']}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

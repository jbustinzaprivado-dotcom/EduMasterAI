"""Configuración por ambiente (§6.4): todo sale de variables de entorno o del archivo .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]  # raíz del repositorio


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EDUMASTER_",
        env_file=ROOT / ".env",
        extra="ignore",
    )

    # "development", "test" o "demo". La demo es pública por el túnel, así que exige secretos reales.
    environment: str = "development"

    # Sin .env se usa SQLite local para poder probar sin PostgreSQL; la CI y la demo usan PostgreSQL.
    database_url: str = f"sqlite:///{ROOT / 'data' / 'edumaster-dev.db'}"

    # Firma de los tokens JWT. En desarrollo hay un valor por defecto; en demo es obligatorio cambiarlo.
    jwt_secret: str = "solo-desarrollo-cambiar-en-env-0123456789"
    # PBKDF2-SHA256: 600 000 iteraciones (OWASP). Las pruebas lo bajan para correr rápido.
    password_iterations: int = 600_000
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # La cookie de renovación solo viaja por HTTPS en la demo (el túnel de Cloudflare pone HTTPS).
    cookie_secure: bool = False
    # Confiar en la cabecera CF-Connecting-IP (solo cuando la API está detrás del túnel de Cloudflare).
    trust_cloudflare_ip: bool = False

    # Contraseña común de las cuentas DEMO que crea app.seed (la elige el equipo en .env).
    demo_password: str | None = None

    log_format: str = "json"  # "json" o "text"

    # Carpeta de la web compilada; si existe, la API la sirve en "/" (una sola puerta pública).
    web_dist: Path = ROOT / "apps" / "web" / "dist"

    def validate_for_environment(self) -> None:
        if self.environment == "demo":
            if self.jwt_secret.startswith("solo-desarrollo") or len(self.jwt_secret) < 32:
                raise RuntimeError("EDUMASTER_JWT_SECRET debe tener al menos 32 caracteres en la demo.")
            if not self.cookie_secure:
                raise RuntimeError("EDUMASTER_COOKIE_SECURE debe ser true en la demo (HTTPS).")


@lru_cache
def get_settings() -> Settings:
    return Settings()

from urllib.parse import urlparse


def require_postgres_url(value: str | None, *, name: str = "DATABASE_URL") -> str:
    if not value:
        raise ValueError(f"{name} must be set in the environment.")

    scheme = urlparse(value).scheme
    if scheme not in {"postgresql", "postgres"}:
        raise ValueError(
            f"{name} must be a Postgres connection string starting with "
            "'postgresql://' or 'postgres://', not a Supabase HTTPS project URL."
        )
    return value

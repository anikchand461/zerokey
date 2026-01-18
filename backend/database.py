from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import DATABASE_URL


def _engine_kwargs(url: str):
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    # For Postgres/Neon, default settings are fine; pool_pre_ping helps with idle connections
    return {"pool_pre_ping": True}


engine = create_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_simple_migrations():
    """Minimal schema migrations to keep existing DBs in sync with models.
    Adds new nullable columns when missing (no backfill or constraints).
    """
    try:
        insp = inspect(engine)
        if "users" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("users")}
            statements = []
            if "bitbucket_id" not in cols:
                statements.append("ALTER TABLE users ADD COLUMN bitbucket_id VARCHAR")
            if "bitbucket_username" not in cols:
                statements.append("ALTER TABLE users ADD COLUMN bitbucket_username VARCHAR")
            if "is_subscribed" not in cols:
                statements.append("ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE")

            if statements:
                with engine.begin() as conn:
                    for stmt in statements:
                        conn.execute(text(stmt))
    except Exception:
        # Best-effort: avoid breaking app on migration helper
        pass

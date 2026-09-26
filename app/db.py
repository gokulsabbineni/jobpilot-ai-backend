from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

Base = declarative_base()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _ensure_columns():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "applications" not in existing_tables or "agent_runs" not in existing_tables:
        return
    app_columns = {column["name"] for column in inspector.get_columns("applications")}
    run_columns = {column["name"] for column in inspector.get_columns("agent_runs")}
    app_additions = {
        "provider": "VARCHAR(50)",
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 3",
        "last_error": "TEXT",
        "next_retry_at": "TIMESTAMP",
        "started_at": "TIMESTAMP",
        "application_data": "JSON",
    }
    run_additions = {
        "applications_submitted": "INTEGER DEFAULT 0",
        "applications_action_required": "INTEGER DEFAULT 0",
        "applications_failed": "INTEGER DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, definition in app_additions.items():
            if name not in app_columns:
                connection.execute(text(f"ALTER TABLE applications ADD COLUMN {name} {definition}"))
        for name, definition in run_additions.items():
            if name not in run_columns:
                connection.execute(text(f"ALTER TABLE agent_runs ADD COLUMN {name} {definition}"))

def init_db():
    from app import models
    Base.metadata.create_all(engine)
    _ensure_columns()

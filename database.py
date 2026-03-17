"""
Database engine and session management.
Creates sfao.db (SQLite) on first run and initializes all tables.
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from models import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sfao.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

# Enable WAL mode for SQLite for better concurrent read performance
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables. Safe to call multiple times (no-op if tables exist)."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Return a new database session. Caller is responsible for closing it."""
    return SessionLocal()

"""
Database module with SQLAlchemy setup, session management, and field-level encryption.
Uses Fernet symmetric encryption for sensitive patient data.
"""

import base64
import hashlib
from contextlib import contextmanager

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# SQLAlchemy engine & session
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite needs this
    echo=False,
)

# Enable WAL mode for better concurrent reads
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for use outside of FastAPI request lifecycle."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Field-level encryption utilities
# ---------------------------------------------------------------------------
def _derive_fernet_key(raw_key: str) -> bytes:
    """Derive a valid 32-byte Fernet key from an arbitrary string."""
    digest = hashlib.sha256(raw_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key(settings.ENCRYPTION_KEY))


def encrypt_field(value: str) -> str:
    """Encrypt a string field and return base64-encoded ciphertext."""
    if not value:
        return value
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_field(token: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    if not token:
        return token
    try:
        return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        # If decryption fails (key changed, corrupted data), return as-is
        return token

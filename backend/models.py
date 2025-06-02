from sqlalchemy import create_engine, Column, String, DateTime, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flow_user:flow_pass@localhost:5432/supercortex_flow")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generate_id(prefix_bytes: bytes = b'') -> str:
    """
    Generates a 128-bit ID with optional prefix.
    - prefix_bytes: 0 to 8 bytes (64 bits)
    Returns 16-byte hex string.
    """
    if len(prefix_bytes) > 8:
        raise ValueError("Prefix too long (max 8 bytes / 64 bits)")
    random_bytes = os.urandom(16 - len(prefix_bytes))
    return (prefix_bytes + random_bytes).hex()

def generate_message(body_bytes: bytes, prefix: bytes = b'') -> dict:
    return {
        "id": generate_id(prefix),
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "body": body_bytes  # Raw binary data, not base64
    }

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, default=lambda: generate_id())
    token = Column(String, unique=True, nullable=False)
    created_by = Column(String, nullable=True)  # agent_id that created this agent
    created_at = Column(DateTime, default=datetime.utcnow)
    prefix = Column(String, nullable=True)  # hex-encoded prefix bytes for this agent
    
class Event(Base):
    __tablename__ = "events"
    
    id = Column(String, primary_key=True)  # Generated using generate_id
    agent_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    body = Column(LargeBinary, nullable=False)  # Pure binary data

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 
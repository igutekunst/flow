from sqlalchemy import create_engine, Column, String, DateTime, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import hashlib
import hmac
import secrets

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flow_user:flow_pass@localhost:5432/supercortex_flow")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generate_org_id() -> str:
    """Generate a random 64-bit organization ID"""
    return os.urandom(8).hex()

def generate_topic_hash(topic_path: str) -> str:
    """Generate 32-bit hash of topic path"""
    return hashlib.sha256(topic_path.encode('utf-8')).digest()[:4].hex()

def generate_topic_nonce(topic_key: bytes, topic_path: str) -> str:
    """Generate deterministic 32-bit nonce for topic using HMAC"""
    return hmac.new(topic_key, topic_path.encode('utf-8'), hashlib.sha256).digest()[:4].hex()

def generate_256bit_id(org_id: str = None, topic_path: str = None, topic_key: bytes = None) -> str:
    """
    Generate a 256-bit ID with structure:
    64-bit org_id + 32-bit topic_hash + 32-bit topic_nonce + 128-bit random
    
    If org_id not provided, generates random 64-bit org
    If topic_path not provided, uses zero padding for topic sections
    """
    # 64-bit org ID (8 bytes)
    if org_id:
        org_bytes = bytes.fromhex(org_id)
        if len(org_bytes) != 8:
            raise ValueError("org_id must be exactly 64 bits (8 bytes)")
    else:
        org_bytes = os.urandom(8)
    
    # 32-bit topic hash (4 bytes)
    if topic_path:
        topic_hash_bytes = hashlib.sha256(topic_path.encode('utf-8')).digest()[:4]
    else:
        topic_hash_bytes = b'\x00' * 4
    
    # 32-bit topic nonce (4 bytes)  
    if topic_path and topic_key:
        topic_nonce_bytes = hmac.new(topic_key, topic_path.encode('utf-8'), hashlib.sha256).digest()[:4]
    else:
        topic_nonce_bytes = b'\x00' * 4
        
    # 128-bit random (16 bytes)
    random_bytes = os.urandom(16)
    
    # Combine all parts (32 bytes total = 256 bits)
    full_id = org_bytes + topic_hash_bytes + topic_nonce_bytes + random_bytes
    return full_id.hex()

def parse_256bit_id(id_hex: str) -> dict:
    """Parse a 256-bit ID into its components"""
    if len(id_hex) != 64:  # 32 bytes = 64 hex chars
        raise ValueError("ID must be exactly 256 bits (64 hex characters)")
    
    id_bytes = bytes.fromhex(id_hex)
    return {
        "org_id": id_bytes[0:8].hex(),           # First 8 bytes
        "topic_hash": id_bytes[8:12].hex(),      # Next 4 bytes  
        "topic_nonce": id_bytes[12:16].hex(),    # Next 4 bytes
        "random": id_bytes[16:32].hex()          # Last 16 bytes
    }

def generate_message(body_bytes: bytes, org_id: str = None, topic_path: str = None, topic_key: bytes = None) -> dict:
    """Generate a message with 256-bit ID"""
    return {
        "id": generate_256bit_id(org_id, topic_path, topic_key),
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "body": body_bytes
    }

def matches_prefix(event_id: str, prefix_hex: str) -> bool:
    """Check if event ID starts with the given prefix (works with any length prefix)"""
    return event_id.lower().startswith(prefix_hex.lower())

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True)  # Will be 256-bit org ID
    token = Column(String, unique=True, nullable=False)  # Auth token
    topic_key = Column(String, nullable=False)  # 32-byte hex key for topic nonce generation
    created_by = Column(String, nullable=True)  # agent_id that created this agent
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Event(Base):
    __tablename__ = "events"
    
    id = Column(String, primary_key=True)  # 256-bit hex ID
    agent_id = Column(String, nullable=False)  # References Agent.id (org_id)
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
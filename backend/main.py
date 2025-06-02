from fastapi import FastAPI, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from models import Agent, Event, create_tables, get_db, generate_message, generate_id
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os
import secrets
import base64

app = FastAPI(title="SuperCortex Flow", description="Event Ingestion System")

INIT_ADMIN_TOKEN = os.getenv("INIT_ADMIN_TOKEN", "admin_bootstrap_token_change_me")

def safe_display_body(body_bytes: bytes) -> dict:
    """
    Smart display logic for binary event bodies.
    Try UTF-8 first, fall back to base64 for display.
    """
    try:
        # Try to decode as UTF-8
        text = body_bytes.decode('utf-8')
        return {
            "body": text,
            "body_format": "utf8",
            "body_length": len(body_bytes)
        }
    except UnicodeDecodeError:
        # Fall back to base64 for display
        return {
            "body": base64.b64encode(body_bytes).decode('ascii'),
            "body_format": "base64",
            "body_length": len(body_bytes)
        }

def parse_prefix_server(prefix_input: str, format_type: str = 'utf8') -> str:
    """
    Server-side prefix parsing with mandatory 64-bit padding.
    This prevents clients from blanket subscribing with short prefixes.
    """
    if format_type == 'utf8':
        prefix_bytes = prefix_input.encode('utf-8')
    elif format_type == 'hex':
        try:
            clean_hex = prefix_input.replace(' ', '').replace('-', '').replace(':', '')
            prefix_bytes = bytes.fromhex(clean_hex)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid hex format")
    elif format_type == 'base64':
        try:
            prefix_bytes = base64.b64decode(prefix_input)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 format")
    else:
        raise HTTPException(status_code=400, detail="Unknown format type")
    
    if len(prefix_bytes) > 8:
        raise HTTPException(status_code=400, detail="Prefix too long (max 8 bytes)")
    
    # MANDATORY 64-bit padding on server side
    padded_bytes = prefix_bytes + b'\x00' * (8 - len(prefix_bytes))
    return padded_bytes.hex()

def matches_prefix(event_id: str, prefix_hex: str) -> bool:
    """Check if event ID starts with the given prefix."""
    return event_id.lower().startswith(prefix_hex.lower())

# Create tables on startup
@app.on_event("startup")
def startup():
    create_tables()

class EventCreate(BaseModel):
    body: str  # We'll encode to bytes on the backend
    prefix_override: Optional[str] = None  # hex-encoded prefix override

class AgentCreate(BaseModel):
    prefix: Optional[str] = None  # hex-encoded prefix bytes

class AgentResponse(BaseModel):
    id: str
    token: str
    prefix: Optional[str] = None

def get_current_agent(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    token = authorization.replace("Bearer ", "")
    
    # Check if it's the admin token
    if token == INIT_ADMIN_TOKEN:
        return {"id": "admin", "is_admin": True, "prefix": None}
    
    # Check if it's a valid agent token
    agent = db.query(Agent).filter(Agent.token == token).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return {"id": agent.id, "is_admin": False, "prefix": agent.prefix}

@app.post("/events")
async def create_event(event: EventCreate, current_agent=Depends(get_current_agent), db: Session = Depends(get_db)):
    """Submit an event to the stream"""
    # Determine which prefix to use - override takes precedence
    prefix_to_use = event.prefix_override or current_agent.get("prefix")
    
    prefix_bytes = b''
    if prefix_to_use:
        try:
            prefix_bytes = bytes.fromhex(prefix_to_use)
            # Pad prefix to 64 bits (8 bytes) to match watch behavior
            if len(prefix_bytes) > 8:
                raise HTTPException(status_code=400, detail="Prefix too long (max 8 bytes)")
            prefix_bytes = prefix_bytes + b'\x00' * (8 - len(prefix_bytes))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid prefix format")
    
    # Generate message using the provided format (with binary body)
    body_bytes = event.body.encode('utf-8')
    message = generate_message(body_bytes, prefix_bytes)
    
    new_event = Event(
        id=message["id"],
        agent_id=current_agent["id"],
        timestamp=datetime.fromisoformat(message["timestamp"].replace('Z', '+00:00')),
        body=message["body"]  # This is now raw bytes
    )
    db.add(new_event)
    db.commit()
    
    return {
        "id": new_event.id,
        "agent_id": new_event.agent_id,
        "timestamp": new_event.timestamp.isoformat() + 'Z'
    }

@app.get("/events/watch")
async def watch_events(
    prefix: str = Query(..., description="Prefix to watch for"),
    prefix_format: str = Query('utf8', description="Format of prefix: utf8, hex, or base64"),
    since: Optional[str] = Query(None, description="Return events after this timestamp"),
    limit: int = Query(100, description="Number of events to return"),
    current_agent=Depends(get_current_agent), 
    db: Session = Depends(get_db)
):
    """Watch for events with specific prefix (server-side filtering with mandatory 64-bit padding)"""
    
    # Server-side prefix parsing with mandatory padding
    try:
        padded_prefix_hex = parse_prefix_server(prefix, prefix_format)
    except HTTPException:
        raise
    
    # Build query
    query = db.query(Event).order_by(Event.timestamp.desc())
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.filter(Event.timestamp > since_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # Get all events and filter by prefix
    events = query.limit(1000).all()  # Get more events for filtering
    
    # Filter events by prefix
    matching_events = []
    for event in events:
        if matches_prefix(event.id, padded_prefix_hex):
            matching_events.append({
                "id": event.id,
                "agent_id": event.agent_id,
                "timestamp": event.timestamp.isoformat() + 'Z',
                "body_length": len(event.body) if event.body else 0
            })
            
        # Stop if we have enough matching events
        if len(matching_events) >= limit:
            break
    
    return {
        "prefix_used": padded_prefix_hex,
        "events": matching_events
    }

@app.get("/events/{event_id}")
async def get_event(event_id: str, current_agent=Depends(get_current_agent), db: Session = Depends(get_db)):
    """Get a specific event by ID"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Handle both binary data and legacy text data
    if isinstance(event.body, bytes):
        body_info = safe_display_body(event.body)
    else:
        # Legacy text data - convert to bytes first
        legacy_bytes = event.body.encode('utf-8') if isinstance(event.body, str) else event.body
        body_info = safe_display_body(legacy_bytes)
    
    return {
        "id": event.id,
        "agent_id": event.agent_id,
        "timestamp": event.timestamp.isoformat() + 'Z',
        **body_info
    }

@app.post("/agents", response_model=AgentResponse)
async def create_agent(agent_data: AgentCreate, current_agent=Depends(get_current_agent), db: Session = Depends(get_db)):
    """Create a new agent (admin only for now)"""
    if not current_agent.get("is_admin"):
        raise HTTPException(status_code=403, detail="Only admin can create agents")
    
    # Validate prefix if provided
    prefix_bytes = b''
    if agent_data.prefix:
        try:
            prefix_bytes = bytes.fromhex(agent_data.prefix)
            if len(prefix_bytes) > 8:
                raise HTTPException(status_code=400, detail="Prefix too long (max 8 bytes)")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid prefix format (must be hex)")
    
    new_agent = Agent(
        id=generate_id(prefix_bytes),
        token=secrets.token_urlsafe(32),
        created_by=current_agent["id"],
        prefix=agent_data.prefix
    )
    db.add(new_agent)
    db.commit()
    
    return AgentResponse(id=new_agent.id, token=new_agent.token, prefix=new_agent.prefix)

@app.get("/events")
async def list_events(
    current_agent=Depends(get_current_agent), 
    db: Session = Depends(get_db),
    since: Optional[str] = Query(None, description="Return events after this timestamp"),
    limit: int = Query(100, description="Number of events to return")
):
    """List events (for debugging)"""
    query = db.query(Event).order_by(Event.timestamp.desc())
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.filter(Event.timestamp > since_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    events = query.limit(limit).all()
    return [
        {
            "id": event.id,
            "agent_id": event.agent_id, 
            "timestamp": event.timestamp.isoformat() + 'Z',
            "body_length": len(event.body) if event.body else 0
        } 
        for event in events
    ]

@app.get("/health")
async def health():
    return {"status": "healthy"} 
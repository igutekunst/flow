import requests
from typing import Optional

class FlowClient:
    def __init__(self, base_url: str = "http://localhost:2222", token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def set_token(self, token: str):
        """Set authentication token"""
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def add_event(self, body: str) -> dict:
        """Submit an event to the stream"""
        response = self.session.post(
            f"{self.base_url}/events",
            json={"body": body}
        )
        response.raise_for_status()
        return response.json()
    
    def create_agent(self) -> dict:
        """Create a new agent (returns id and token)"""
        response = self.session.post(f"{self.base_url}/agents", json={})
        response.raise_for_status()
        return response.json() 
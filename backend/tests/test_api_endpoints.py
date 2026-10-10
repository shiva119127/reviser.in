import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "YT Reviser" in response.text

def test_api_info_endpoint():
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "YT Reviser API"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["backend_version"] == "0.2.0"
    assert data["whisper_ready"] is True
    assert data["embeddings_ready"] is True
    assert data["qdrant_ready"] is True

def test_chat_empty_question():
    response = client.post("/api/chat", json={"question": "   "})
    assert response.status_code == 200
    data = response.json()
    assert "Please enter a question" in data["answer"]

def test_legacy_ask_endpoint():
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code == 200
    data = response.json()
    assert "Please enter a question" in data["answer"]

def test_playlists_endpoint():
    response = client.get("/api/playlists")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

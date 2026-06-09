import sys
from unittest.mock import MagicMock

# MOCK HEAVY ML MODELS BEFORE IMPORTING APP
# This prevents the 30-second CPU load of bge-m3 and bge-reranker-base during test collection
sys.modules['langchain_huggingface'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

def test_upload_pdf_zero_byte():
    response = client.post(
        "/api/upload-pdf",
        files={"file": ("test.pdf", b"", "application/pdf")}
    )
    # The actual implementation in endpoints.py returns 400 for a 0-byte file.
    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is empty."

@patch("app.api.endpoints.fitz.open")
def test_upload_pdf_success(mock_fitz_open):
    # Mock the PyMuPDF (fitz) Document and Page
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Mocked PDF content."
    mock_doc.__iter__.return_value = [mock_page]
    mock_doc.__len__.return_value = 1
    mock_fitz_open.return_value = mock_doc

    # A valid magic signature so Guard 4 passes
    dummy_pdf_content = b"%PDF-1.4 dummy content"
    
    response = client.post(
        "/api/upload-pdf",
        files={"file": ("test.pdf", dummy_pdf_content, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Mocked PDF content."
    assert data["page_count"] == 1
    assert data["source_id"] == "test.pdf"

@patch("app.services.vector_store.embedding_cache.get_or_embed")
def test_embed_endpoint_success(mock_get_or_embed):
    # Mock FAISS index and prevent actual chunking/embedding
    mock_index = MagicMock()
    mock_get_or_embed.return_value = mock_index

    payload = {
        "source_id": "test_url",
        "content": "This is a test page content."
    }
    
    response = client.post("/api/embed", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "cached"]
    assert data["source_id"] == "test_url"

def test_chat_endpoint_empty_query():
    payload = {
        "query": "   ",
        "contexts": [],
        "mode": "auto"
    }
    
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    
    text = response.text
    assert '"type": "final"' in text
    assert "Please enter a question to get started." in text

@patch("app.api.endpoints.run_fast_mode")
def test_chat_endpoint_stream_mock(mock_run_fast_mode):
    # Mock the async generator for run_fast_mode to yield fake SSE strings
    async def fake_fast_mode(state):
        yield 'data: {"type": "status", "value": "Mocking..."}\\n\\n'
        yield 'data: {"type": "final", "answer": "Mocked Answer"}\\n\\n'
        
    mock_run_fast_mode.side_effect = fake_fast_mode
    
    payload = {
        "query": "What is AI?",
        "contexts": [{"source_id": "tab", "content": "AI is artificial intelligence."}],
        "mode": "fast"
    }
    
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    
    text = response.text
    assert "Mocking..." in text
    assert "Mocked Answer" in text

import pytest
from backend.app.services.qdrant_service import QdrantService

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Ensure tests run against in-memory Qdrant instance to prevent disk lock conflicts."""
    # Initialize in-memory instance
    test_qdrant = QdrantService(path=":memory:")
    monkeypatch.setattr(QdrantService, "_instance", test_qdrant)
    yield

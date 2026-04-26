import os
import pytest

# Must be set before any app module is imported (SECRET_KEY has no default)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_obatek.db")

# StaticFiles mount checks this directory at app import time
os.makedirs("uploads", exist_ok=True)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    # Clean up test database file created by lifespan
    if os.path.exists("test_obatek.db"):
        os.remove("test_obatek.db")

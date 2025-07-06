import pytest, sys, pathlib

# Ensure project root and src/ are importable
project_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

from src.web_app.app import app as flask_app


@pytest.fixture(scope="module")
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client

def test_index_route(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_jobs_route(client):
    resp = client.get("/jobs")
    assert resp.status_code == 200


def test_preferences_route(client):
    resp = client.get("/preferences")
    assert resp.status_code == 200


def test_dashboard_route(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200


def test_api_search_status(client):
    resp = client.get("/api/search_status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "available_sources" in data 
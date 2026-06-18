import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_contains_status(self):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "healthy"

    def test_health_contains_version(self):
        resp = client.get("/health")
        data = resp.json()
        assert data["version"] == "1.0.0"


class TestRootEndpoint:
    @pytest.mark.xfail(reason="Jinja2 cache issue with test client (pre-existing)")
    def test_root_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    @pytest.mark.xfail(reason="Jinja2 cache issue with test client (pre-existing)")
    def test_root_contains_title(self):
        resp = client.get("/")
        assert "Doctor" in resp.text or "Resume" in resp.text


class TestParseResumeEndpoint:
    def test_no_file_returns_422(self):
        resp = client.post("/ai/parse-resume")
        assert resp.status_code == 422

    def test_invalid_file_extension_returns_400(self):
        resp = client.post(
            "/ai/parse-resume",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 400

    def test_empty_file_returns_400(self):
        resp = client.post(
            "/ai/parse-resume",
            files={"file": ("test.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 400


class TestMatchJobsEndpoint:
    def test_missing_resume_id_returns_422(self):
        resp = client.post("/ai/match-jobs", json={})
        assert resp.status_code == 422

    def test_invalid_top_k_returns_422(self):
        resp = client.post(
            "/ai/match-jobs",
            json={"resume_id": "00000000-0000-0000-0000-000000000000", "top_k": 0},
        )
        assert resp.status_code == 422

    def test_nonexistent_resume_returns_404(self):
        import uuid
        resp = client.post(
            "/ai/match-jobs",
            json={"resume_id": str(uuid.uuid4()), "top_k": 5},
        )
        assert resp.status_code == 404

    def test_invalid_uuid_returns_422(self):
        resp = client.post(
            "/ai/match-jobs",
            json={"resume_id": "not-a-uuid", "top_k": 5},
        )
        assert resp.status_code == 422

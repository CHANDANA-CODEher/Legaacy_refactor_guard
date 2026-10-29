"""Unit and integration tests for web_api.py.

Verifies:
- GET /health responds with 200 OK and binding info.
- GET /demo/status reports demo repository status without modifying any files.
- Swagger UI documentation is accessible at /docs.
- POST /demo/run is not implemented to prevent un-sandboxed in-place file mutation.
- No secrets or API keys are leaked in responses.
- Missing demo_repo is handled cleanly with 404.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from web_api import (
    ALLOWED_ORIGINS,
    DEMO_REPO_PATH,
    OUTPUTS_PATH,
    RUN_LOG_PATH,
    app,
)

client = TestClient(app)


class TestWebAPIHealth:
    """Tests for GET /health endpoint."""

    def test_health_returns_200_and_expected_fields(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["binding"] == "127.0.0.1"
        assert data["docs_url"] == "/docs"
        assert "Legacy Refactor Guard" in data["service"]


class TestWebAPIDocs:
    """Tests for Swagger UI documentation endpoint."""

    def test_docs_page_is_accessible(self) -> None:
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

    def test_openapi_schema_is_valid(self) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "Legacy Refactor Guard Testing API"
        assert "/health" in schema["paths"]
        assert "/demo/status" in schema["paths"]
        assert "/api/log" in schema["paths"]
        assert "/api/history" in schema["paths"]


class TestWebAPIDemoStatus:
    """Tests for GET /demo/status endpoint."""

    def test_demo_status_returns_200_and_valid_structure(self) -> None:
        # Record file hash before request to guarantee no modification
        shop_file = DEMO_REPO_PATH / "shop.py"
        assert shop_file.exists(), "demo_repo/shop.py must exist for this test"
        hash_before = hashlib.sha256(shop_file.read_bytes()).hexdigest()

        response = client.get("/demo/status")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ("ready", "warning")
        assert data["repository"] == "demo_repo"
        assert data["target_file"]["name"] == "shop.py"
        assert data["target_file"]["exists"] is True
        assert data["target_file"]["syntax_valid"] is True
        assert data["test_suite"]["exists"] is True
        assert data["test_results"]["passed"] == 8
        assert data["test_results"]["failed"] == 0
        assert data["demo_run_available"] is False
        assert "POST /demo/run is intentionally not implemented" in data["demo_run_notice"]

        # Ensure shop.py was not modified during the status call
        hash_after = hashlib.sha256(shop_file.read_bytes()).hexdigest()
        assert hash_before == hash_after, "demo_repo/shop.py must not be modified by GET /demo/status"

    def test_demo_status_when_repo_missing_returns_404(self) -> None:
        with patch.object(Path, "exists", return_value=False):
            response = client.get("/demo/status")
            assert response.status_code == 404
            assert "does not exist" in response.json()["detail"]


class TestWebAPISafetyRules:
    """Tests verifying safety constraints of the web API."""

    def test_post_demo_run_is_not_implemented(self) -> None:
        # POST /demo/run must not exist to prevent un-sandboxed disk mutation
        response = client.post("/demo/run")
        assert response.status_code in (404, 405)

    def test_arbitrary_post_requests_rejected(self) -> None:
        # Arbitrary endpoints must return 404
        response = client.post("/execute", json={"code": "import os; os.system('echo hi')"})
        assert response.status_code == 404

        response = client.post("/refactor", json={"path": "../secret.py"})
        assert response.status_code == 404

    def test_no_secrets_leaked_in_responses(self) -> None:
        # Ensure no sensitive tokens, keys, or patterns exist in endpoint responses
        for endpoint in ("/health", "/demo/status", "/openapi.json", "/api/log", "/api/history"):
            res = client.get(endpoint)
            text = res.text
            assert "NEBIUS_API_KEY" not in text
            assert "api_key" not in text.lower() or "docs" in endpoint
            assert "secret" not in text.lower() or "docs" in endpoint


class TestWebAPICORS:
    """Tests for CORS policy configuration and origin filtering."""

    @pytest.mark.parametrize(
        "origin",
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
    )
    def test_cors_headers_present_for_allowed_origins(self, origin: str) -> None:
        response = client.get("/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_preflight_options_for_allowed_origin(self) -> None:
        response = client.options(
            "/api/log",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
        allowed_methods = response.headers.get("access-control-allow-methods", "")
        assert "GET" in allowed_methods
        assert "OPTIONS" in allowed_methods

    @pytest.mark.parametrize(
        "origin",
        [
            "http://malicious-site.com",
            "http://localhost:8080",
            "http://127.0.0.1:8000",
            "https://evil.org",
        ],
    )
    def test_cors_headers_rejected_for_unapproved_origins(self, origin: str) -> None:
        response = client.get("/health", headers={"Origin": origin})
        assert response.status_code == 200
        # CORSMiddleware does NOT add access-control-allow-origin for unapproved origins
        assert "access-control-allow-origin" not in response.headers


class TestWebAPIRunLog:
    """Tests for GET /api/log endpoint."""

    def test_get_run_log_success(self) -> None:
        assert RUN_LOG_PATH.exists(), "run_log.json should exist for this test"
        response = client.get("/api/log")
        assert response.status_code == 200
        data = response.json()
        assert "repo" in data
        assert "baseline" in data
        assert "attempts" in data
        assert "final" in data

    def test_get_run_log_missing_returns_404_without_internal_path(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "nonexistent_run_log.json"
        with patch("web_api.RUN_LOG_PATH", missing_path):
            response = client.get("/api/log")
            assert response.status_code == 404
            detail = response.json().get("detail", "")
            assert "not found" in detail.lower()
            # Ensure no internal filesystem paths are leaked
            assert str(tmp_path) not in detail

    def test_get_run_log_corrupt_json_returns_500_safely(self, tmp_path: Path) -> None:
        corrupt_file = tmp_path / "corrupt_log.json"
        corrupt_file.write_text("{this is not valid json:", encoding="utf-8")
        with patch("web_api.RUN_LOG_PATH", corrupt_file):
            response = client.get("/api/log")
            assert response.status_code == 500
            detail = response.json().get("detail", "")
            assert "invalid json" in detail.lower()
            assert str(tmp_path) not in detail

    def test_get_run_log_non_dict_json_returns_500_safely(self, tmp_path: Path) -> None:
        array_file = tmp_path / "array_log.json"
        array_file.write_text("[1, 2, 3]", encoding="utf-8")
        with patch("web_api.RUN_LOG_PATH", array_file):
            response = client.get("/api/log")
            assert response.status_code == 500
            detail = response.json().get("detail", "")
            assert "invalid" in detail.lower()


class TestWebAPIHistory:
    """Tests for GET /api/history endpoint."""

    def test_get_history_returns_list_of_summaries(self) -> None:
        response = client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            item = data[0]
            assert "filename" in item
            assert "repo" in item
            assert "started_at" in item
            assert "provider" in item
            assert "baseline" in item
            assert "final" in item
            assert "attempts_count" in item
            # Confirm filename is just the basename, not a full path
            assert "/" not in item["filename"]
            assert "\\" not in item["filename"]

    def test_get_history_with_isolated_dir_and_invalid_entries(self, tmp_path: Path) -> None:
        isolated_outputs = tmp_path / "outputs"
        isolated_outputs.mkdir()

        # Valid log
        valid_log = {
            "repo": "test_repo",
            "started_at": "2026-10-29T10:00:00+00:00",
            "provider": "mock",
            "baseline": {"passed": 5, "failed": 0, "total": 5},
            "attempts": [{"attempt": 1, "status": "success"}],
            "final": {"passed": 5, "failed": 0, "files_changed": ["shop.py"]},
        }
        (isolated_outputs / "run_log_20261029_100000.json").write_text(
            json.dumps(valid_log), encoding="utf-8"
        )

        # Corrupted JSON log (should be ignored safely)
        (isolated_outputs / "run_log_20261029_090000.json").write_text(
            "{corrupted data", encoding="utf-8"
        )

        # Non-dict JSON log (should be ignored safely)
        (isolated_outputs / "run_log_20261029_080000.json").write_text(
            "\"just a string\"", encoding="utf-8"
        )

        # Non-matching filename (should be ignored)
        (isolated_outputs / "other_file.txt").write_text("dummy", encoding="utf-8")

        with patch("web_api.OUTPUTS_PATH", isolated_outputs):
            response = client.get("/api/history")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["filename"] == "run_log_20261029_100000.json"
            assert data[0]["repo"] == "test_repo"
            assert data[0]["attempts_count"] == 1

    def test_get_history_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        empty_outputs = tmp_path / "empty_outputs"
        empty_outputs.mkdir()
        with patch("web_api.OUTPUTS_PATH", empty_outputs):
            response = client.get("/api/history")
            assert response.status_code == 200
            assert response.json() == []

    def test_get_history_missing_dir_returns_empty_list(self, tmp_path: Path) -> None:
        missing_outputs = tmp_path / "nonexistent_outputs"
        with patch("web_api.OUTPUTS_PATH", missing_outputs):
            response = client.get("/api/history")
            assert response.status_code == 200
            assert response.json() == []


class TestWebAPIAccidentalFileModification:
    """Verifies that reading API endpoints never mutates real project files."""

    def test_endpoints_do_not_modify_shop_or_run_log(self) -> None:
        shop_file = DEMO_REPO_PATH / "shop.py"
        assert shop_file.exists()
        shop_bytes_before = shop_file.read_bytes()

        run_log_file = RUN_LOG_PATH
        assert run_log_file.exists()
        log_bytes_before = run_log_file.read_bytes()
        log_mtime_before = run_log_file.stat().st_mtime

        # Execute all endpoints multiple times
        client.get("/health")
        client.get("/demo/status")
        client.get("/api/log")
        client.get("/api/history")
        client.get("/docs")
        client.options("/api/log", headers={"Origin": "http://localhost:3000"})

        # Verify shop.py is 100% byte-for-byte identical
        assert shop_file.read_bytes() == shop_bytes_before

        # Verify run_log.json is 100% byte-for-byte identical and unmodified
        assert run_log_file.read_bytes() == log_bytes_before
        assert run_log_file.stat().st_mtime == log_mtime_before

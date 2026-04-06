"""Tests for static file serving (React SPA)."""

import json
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
HAS_FRONTEND = (FRONTEND_DIR / "index.html").is_file()

skip_no_frontend = pytest.mark.skipif(
    not HAS_FRONTEND,
    reason="frontend/dist/index.html not found; skipping static serving tests",
)


@skip_no_frontend
def test_root_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


@skip_no_frontend
def test_root_returns_html(client):
    resp = client.get("/")
    assert b"<html" in resp.data.lower() or b"<!doctype" in resp.data.lower()


@skip_no_frontend
def test_unknown_path_falls_back_to_index(client):
    """SPA routing: unknown paths should serve index.html."""
    resp = client.get("/some/nonexistent/route")
    assert resp.status_code == 200
    assert b"<html" in resp.data.lower() or b"<!doctype" in resp.data.lower()


@skip_no_frontend
def test_api_still_works_alongside_static(client):
    """API routes should take precedence over SPA fallback."""
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "team_name" in data


@skip_no_frontend
def test_bundle_works_alongside_static(client):
    resp = client.get("/api/bundle")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "overview" in data

"""Hermetic defaults for orchestrator tests.

Values are deliberately synthetic.  Tests that need live services must opt in
explicitly and are not part of the deterministic regression command.
"""

from __future__ import annotations

import os
import socket

import pytest


_DEFAULTS = {
    "PUBLIC_API_URL": "http://test.invalid",
    "PUBLIC_WEB_URL": "http://test.invalid",
    "PROMATI_API_BASE_URL": "http://test.invalid",
    "DATABASE_URL": "sqlite:///:memory:",
    "MINIO_ENDPOINT": "test.invalid:1",
    "MINIO_ACCESS_KEY": "synthetic",
    "MINIO_SECRET_KEY": "synthetic",
    "QDRANT_URL": "http://test.invalid",
    "EDOCR2_URL": "http://test.invalid",
    "TECHREVIEW_URL": "http://test.invalid",
    "KEYCLOAK_ISSUER": "http://test.invalid/issuer",
    "KEYCLOAK_JWKS_URL": "http://test.invalid/jwks",
    "ORG_ADMIN_USER": "synthetic",
    "ORG_ADMIN_PASSWORD": "synthetic",
    "RFQ_PDF_DIR": "/tmp/promati-test-rfq-pdf",
    "RFQ_UPLOAD_DIR": "/tmp/promati-test-rfq-upload",
}

for _name, _value in _DEFAULTS.items():
    os.environ.setdefault(_name, _value)


@pytest.fixture(autouse=True)
def _deny_network(monkeypatch, request):
    """Unit/characterization tests may not open network connections."""
    if request.node.get_closest_marker("integration"):
        return

    def blocked(*_args, **_kwargs):
        raise AssertionError("network disabled in deterministic orchestrator tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


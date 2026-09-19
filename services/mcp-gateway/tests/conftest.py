"""Same fresh-tenant-per-test pattern as services/core/tests/conftest.py --
assumes ERP_DATABASE_URL already has migrations applied.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()

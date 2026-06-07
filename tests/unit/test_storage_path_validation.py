from uuid import UUID

import pytest

from app.services.storage_path import validate_storage_path
from tests.conftest import FLIGHT_ID, ORG_ID, PLAN_ID, STORAGE_PATH


def test_valid_storage_path_passes() -> None:
    validate_storage_path(STORAGE_PATH, ORG_ID, FLIGHT_ID, PLAN_ID)


def test_storage_path_prefix_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="storage_path must start with"):
        validate_storage_path(
            "wrong/path/briefing.pdf",
            ORG_ID,
            FLIGHT_ID,
            PLAN_ID,
        )


def test_storage_path_must_end_with_pdf() -> None:
    bad_path = f"{ORG_ID}/{FLIGHT_ID}/{PLAN_ID}/briefing.txt"
    with pytest.raises(ValueError, match="must end with a .pdf filename"):
        validate_storage_path(bad_path, ORG_ID, FLIGHT_ID, PLAN_ID)

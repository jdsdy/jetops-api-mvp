from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.api.integration_dependencies import hash_api_key, validate_key_record
from app.schemas.integration_auth import IntegrationAuthContext

API_KEY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
API_CLIENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _valid_row(
    *,
    is_active: bool = True,
    revoked_at: str | None = None,
    expires_at: str | None = None,
    client_is_active: bool = True,
    organisation_id: str | None = str(ORG_ID),
) -> dict:
    return {
        "id": str(API_KEY_ID),
        "api_client_id": str(API_CLIENT_ID),
        "is_active": is_active,
        "revoked_at": revoked_at,
        "expires_at": expires_at,
        "api_clients": {
            "is_active": client_is_active,
            "organisation_id": organisation_id,
        },
    }


def test_hash_api_key_returns_sha256_hex() -> None:
    raw_key = "jops_dev_sk_elq8GPD4KwhqVDr_C0GulNPi2aeyAralk_2rgqkTTN4"

    result = hash_api_key(raw_key)

    assert len(result) == 64
    assert result == hash_api_key(raw_key)


def test_validate_key_record_returns_context_for_valid_key() -> None:
    result = validate_key_record(_valid_row(), NOW)

    assert result == IntegrationAuthContext(
        api_key_id=API_KEY_ID,
        api_client_id=API_CLIENT_ID,
        organisation_id=ORG_ID,
    )


def test_validate_key_record_returns_none_when_row_missing() -> None:
    assert validate_key_record(None, NOW) is None


def test_validate_key_record_returns_none_when_key_inactive() -> None:
    assert validate_key_record(_valid_row(is_active=False), NOW) is None


def test_validate_key_record_returns_none_when_key_revoked() -> None:
    revoked_at = (NOW - timedelta(hours=1)).isoformat()

    assert validate_key_record(_valid_row(revoked_at=revoked_at), NOW) is None


def test_validate_key_record_returns_none_when_key_expired() -> None:
    expires_at = (NOW - timedelta(seconds=1)).isoformat()

    assert validate_key_record(_valid_row(expires_at=expires_at), NOW) is None


def test_validate_key_record_allows_null_expires_at() -> None:
    result = validate_key_record(_valid_row(expires_at=None), NOW)

    assert result is not None


def test_validate_key_record_allows_future_expires_at() -> None:
    expires_at = (NOW + timedelta(days=1)).isoformat()

    result = validate_key_record(_valid_row(expires_at=expires_at), NOW)

    assert result is not None


def test_validate_key_record_returns_none_when_client_suspended() -> None:
    assert validate_key_record(_valid_row(client_is_active=False), NOW) is None


def test_validate_key_record_allows_null_organisation_id() -> None:
    result = validate_key_record(_valid_row(organisation_id=None), NOW)

    assert result is not None
    assert result.organisation_id is None

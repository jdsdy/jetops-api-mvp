from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID

from app.repositories.api_key_repository import ApiKeyRepository

API_KEY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
KEY_HASH = "abc123hash"


def test_lookup_by_hash_queries_api_keys_with_embedded_client() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.maybe_single.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data={"id": str(API_KEY_ID)})

    repository = ApiKeyRepository(mock_client)
    result = repository.lookup_by_hash(KEY_HASH)

    mock_client.table.assert_called_once_with("api_keys")
    mock_table.select.assert_called_once_with(
        "id, api_client_id, is_active, revoked_at, expires_at, "
        "api_clients(is_active, organisation_id)"
    )
    mock_table.eq.assert_called_once_with("key_hash", KEY_HASH)
    mock_table.maybe_single.assert_called_once()
    assert result == {"id": str(API_KEY_ID)}


def test_lookup_by_hash_returns_none_when_not_found() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.maybe_single.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=None)

    repository = ApiKeyRepository(mock_client)
    result = repository.lookup_by_hash(KEY_HASH)

    assert result is None


def test_lookup_by_hash_returns_none_when_execute_returns_none() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.maybe_single.return_value = mock_table
    mock_table.execute.return_value = None

    repository = ApiKeyRepository(mock_client)
    result = repository.lookup_by_hash(KEY_HASH)

    assert result is None


def test_touch_last_used_updates_last_used_at() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    repository = ApiKeyRepository(mock_client)
    repository.touch_last_used(API_KEY_ID)

    mock_client.table.assert_called_once_with("api_keys")
    update_payload = mock_table.update.call_args.args[0]
    assert "last_used_at" in update_payload
    datetime.fromisoformat(update_payload["last_used_at"].replace("Z", "+00:00"))
    mock_table.eq.assert_called_once_with("id", str(API_KEY_ID))

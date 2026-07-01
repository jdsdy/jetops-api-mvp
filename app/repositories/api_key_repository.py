import logging
from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

_logger = logging.getLogger(__name__)


class ApiKeyRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def lookup_by_hash(self, key_hash: str) -> dict | None:
        try:
            result = (
                self._client.table("api_keys")
                .select(
                    "id, api_client_id, is_active, revoked_at, expires_at, "
                    "api_clients(is_active, organisation_id)"
                )
                .eq("key_hash", key_hash)
                .maybe_single()
                .execute()
            )
        except Exception:
            _logger.exception("Failed to lookup api key by hash")
            return None

        if result is None:
            return None
        return result.data

    def touch_last_used(self, key_id: UUID) -> None:
        try:
            self._client.table("api_keys").update(
                {"last_used_at": datetime.now(UTC).isoformat()}
            ).eq("id", str(key_id)).execute()
        except Exception:
            _logger.exception("Failed to update last_used_at for api_key %s", key_id)

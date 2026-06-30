from uuid import UUID

from supabase import Client


class ApiLogRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def insert_api_log(
        self,
        *,
        service: str,
        method: str,
        path: str,
        status_code: int,
        user_id: UUID | None,
        organisation_id: UUID | None,
        api_client_id: UUID | None,
        duration_ms: int,
        error_message: str | None,
    ) -> None:
        payload = {
            "service": service,
            "method": method,
            "path": path,
            "status_code": status_code,
            "user_id": str(user_id) if user_id is not None else None,
            "organisation_id": (
                str(organisation_id) if organisation_id is not None else None
            ),
            "api_client_id": (
                str(api_client_id) if api_client_id is not None else None
            ),
            "duration_ms": duration_ms,
            "error_message": error_message,
        }
        self._client.table("api_logs").insert(payload).execute()

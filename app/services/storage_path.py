from uuid import UUID


def validate_storage_path(
    storage_path: str,
    organisation_id: UUID,
    flight_id: UUID,
    flight_plan_id: UUID,
) -> None:
    expected_prefix = f"{organisation_id}/{flight_id}/{flight_plan_id}/"
    if not storage_path.startswith(expected_prefix):
        raise ValueError(f"storage_path must start with {expected_prefix}")
    if not storage_path.lower().endswith(".pdf"):
        raise ValueError("storage_path must end with a .pdf filename")

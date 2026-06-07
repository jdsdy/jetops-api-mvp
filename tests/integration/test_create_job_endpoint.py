from uuid import uuid4

import pytest

from app.core.errors import JobStepError
from tests.conftest import auth_headers, client, valid_job_payload


def test_create_job_happy_path_returns_201_with_id(client, mock_job_service) -> None:
    job_id = uuid4()
    mock_job_service.create_job.return_value = job_id

    response = client.post(
        "/v1/jobs",
        json=valid_job_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 201
    assert response.json() == {"id": str(job_id)}


def test_pdf_missing_returns_404_with_id(client, mock_job_service) -> None:
    job_id = uuid4()
    mock_job_service.create_job.side_effect = JobStepError(
        job_id,
        404,
        "Flight plan PDF not found",
    )

    response = client.post(
        "/v1/jobs",
        json=valid_job_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 404
    assert response.json() == {"id": str(job_id)}


def test_invalid_body_returns_422(client) -> None:
    payload = valid_job_payload()
    del payload["flight_plan_id"]

    response = client.post("/v1/jobs", json=payload, headers=auth_headers())

    assert response.status_code == 422


def test_storage_path_mismatch_returns_400(client, mock_job_service) -> None:
    mock_job_service.create_job.side_effect = ValueError(
        "storage_path must start with org/flight/plan/"
    )

    response = client.post(
        "/v1/jobs",
        json=valid_job_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 400

from unittest.mock import MagicMock
from uuid import uuid4

from app.repositories.analysed_notam_repository import AnalysedNotamRepository
from app.schemas.notam_analysis import NotamResult


def test_insert_analysed_notams_writes_null_category_and_summary_for_pending() -> None:
    job_id = uuid4()
    flight_plan_id = uuid4()
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    repository = AnalysedNotamRepository(mock_client)
    repository.insert_analysed_notams(
        job_id,
        flight_plan_id,
        [
            (1, NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="Done")),
            (2, None),
        ],
    )

    mock_table.insert.assert_called_once_with(
        [
            {
                "anaysis_job_id": str(job_id),
                "flight_plan_id": str(flight_plan_id),
                "notam_id": 1,
                "category": 1,
                "summary": "Done",
                "did_error": False,
            },
            {
                "anaysis_job_id": str(job_id),
                "flight_plan_id": str(flight_plan_id),
                "notam_id": 2,
                "category": None,
                "summary": None,
                "did_error": False,
            },
        ]
    )


def test_update_analysed_notams_sets_category_and_summary() -> None:
    job_id = uuid4()
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    repository = AnalysedNotamRepository(mock_client)
    repository.update_analysed_notams(
        job_id,
        [
            (2, NotamResult(notam_id="C0478/26 NOTAMN", category=2, summary="Retry ok")),
        ],
    )

    mock_table.update.assert_called_once_with(
        {"category": 2, "summary": "Retry ok", "did_error": False}
    )
    eq_calls = mock_table.eq.call_args_list
    assert eq_calls[0].args == ("anaysis_job_id", str(job_id))
    assert eq_calls[1].args == ("notam_id", 2)


def test_mark_analysed_notams_errored_sets_did_error_true() -> None:
    job_id = uuid4()
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    repository = AnalysedNotamRepository(mock_client)
    repository.mark_analysed_notams_errored(job_id, [2, 3])

    assert mock_table.update.call_args_list == [
        (({"did_error": True},),),
        (({"did_error": True},),),
    ]
    eq_calls = mock_table.eq.call_args_list
    assert eq_calls[0].args == ("anaysis_job_id", str(job_id))
    assert eq_calls[1].args == ("notam_id", 2)
    assert eq_calls[2].args == ("anaysis_job_id", str(job_id))
    assert eq_calls[3].args == ("notam_id", 3)

"""
Unit tests for HistoryService.
"""
import json
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from webapp.backend.services.history_service import HistoryService
from webapp.backend.models import BuildHistoryEntry, HistoryNotFoundError


def _make_entry(build_id="test-build-id", status="success", models=None, timestamp=None):
    return BuildHistoryEntry(
        build_id=build_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        end_time=datetime.now(timezone.utc).isoformat(),
        models=models or ["tx15"],
        status=status,
        firmware_version="2.12",
        component="firmware",
        clean=False,
        jobs=4,
        duration_ms=60000,
        log_file="",
    )


@pytest.fixture
def service(tmp_path):
    return HistoryService(
        history_path=tmp_path / "history.json",
        logs_dir=tmp_path / "logs",
    )


# ---------------------------------------------------------------------------
# record and get
# ---------------------------------------------------------------------------


def test_record_and_get(service):
    entry = _make_entry()
    service.record(entry)
    fetched = service.get("test-build-id")
    assert fetched.build_id == "test-build-id"
    assert fetched.status == "success"


def test_get_not_found(service):
    with pytest.raises(HistoryNotFoundError):
        service.get("nonexistent")


def test_record_multiple_newest_first(service):
    service.record(_make_entry("first", timestamp="2024-01-01T00:00:00+00:00"))
    service.record(_make_entry("second", timestamp="2024-01-02T00:00:00+00:00"))
    items, total = service.list()
    assert total == 2
    assert items[0].build_id == "second"


# ---------------------------------------------------------------------------
# list with filters
# ---------------------------------------------------------------------------


def test_list_all(service):
    service.record(_make_entry("b1", status="success"))
    service.record(_make_entry("b2", status="failed"))
    items, total = service.list()
    assert total == 2


def test_list_filter_by_status(service):
    service.record(_make_entry("b1", status="success"))
    service.record(_make_entry("b2", status="failed"))
    items, total = service.list(status="success")
    assert total == 1
    assert items[0].build_id == "b1"


def test_list_filter_by_model(service):
    service.record(_make_entry("b1", models=["tx15"]))
    service.record(_make_entry("b2", models=["pl18"]))
    items, total = service.list(model="pl18")
    assert total == 1
    assert items[0].build_id == "b2"


def test_list_pagination(service):
    for i in range(5):
        service.record(_make_entry(f"build-{i}"))
    items, total = service.list(page=1, page_size=2)
    assert total == 5
    assert len(items) == 2


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_entry(service):
    service.record(_make_entry())
    service.delete("test-build-id")
    with pytest.raises(HistoryNotFoundError):
        service.get("test-build-id")


def test_delete_not_found(service):
    with pytest.raises(HistoryNotFoundError):
        service.delete("nonexistent")


# ---------------------------------------------------------------------------
# clear_all
# ---------------------------------------------------------------------------


def test_clear_all(service):
    service.record(_make_entry("b1"))
    service.record(_make_entry("b2"))
    service.clear_all()
    items, total = service.list()
    assert total == 0


# ---------------------------------------------------------------------------
# save_log and get_log_path
# ---------------------------------------------------------------------------


def test_save_log(service):
    service.record(_make_entry())
    path = service.save_log("test-build-id", ["line 1", "line 2"])
    assert path.exists()
    content = path.read_text()
    assert "line 1" in content


def test_get_log_path_exists(service):
    service.record(_make_entry())
    service.save_log("test-build-id", ["log"])
    log_path = service.get_log_path("test-build-id")
    assert log_path is not None
    assert log_path.exists()


def test_get_log_path_missing(service):
    result = service.get_log_path("nonexistent")
    assert result is None

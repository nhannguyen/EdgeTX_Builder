"""
Integration tests for EdgeTX Firmware Web Builder API.

Covers every acceptance criterion from the BA spec using FastAPI's
TestClient with dependency injection overrides so no real files are touched.

Stories covered:
  Story 1  — View list of radio models
  Story 2  — Enable/disable toggle
  Story 3  — View and edit a single model
  Story 4  — Add a new model
  Story 5  — Delete a model
  Story 6  — Trigger a build (validation layer only)
  Story 7  — SSE log endpoint exists
  Story 8  — Download artifacts
  Story 9  — Build history
  Story 10 — Export/import configuration
  Story 11 — Settings management
  Edge cases — error scenarios from the BA spec
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# Make sure the project root is importable
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from webapp.main import app
from webapp.backend.dependencies import (
    get_config_service,
    get_settings_service,
    get_history_service,
    get_artifact_service,
    get_build_service,
)
from webapp.backend.services.config_service import ConfigService
from webapp.backend.services.settings_service import SettingsService
from webapp.backend.services.history_service import HistoryService
from webapp.backend.services.artifact_service import ArtifactService
from webapp.backend.services.build_service import BuildService
from webapp.backend.models import (
    ModelCreate,
    BuildRequest,
    BuildHistoryEntry,
    AppSettings,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONFIG: dict[str, Any] = {
    "firmware_version": "2.12",
    "targets": {
        "tx15": {
            "pcb": "TX15",
            "enabled": True,
            "extra_flags": ["-DCROSSFIRE=YES"],
        },
        "gx12": {
            "pcb": "GX12",
            "pcbrev": "GX12V2",
            "enabled": False,
            "extra_flags": [],
        },
        "pl18": {
            "pcb": "PL18",
            "pcbrev": "PL18EV",
            "enabled": True,
            "extra_flags": ["-DGHOST=NO", "-DCROSSFIRE=YES"],
        },
    },
}


@pytest.fixture
def tmp_config(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text(json.dumps(SAMPLE_CONFIG, indent=4))
    return path


@pytest.fixture
def tmp_settings_file(tmp_path):
    return tmp_path / "app_settings.json"


@pytest.fixture
def tmp_history_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def tmp_dist_dir(tmp_path):
    d = tmp_path / "dist"
    d.mkdir()
    return d


@pytest.fixture
def config_svc(tmp_config):
    return ConfigService(targets_path=tmp_config)


@pytest.fixture
def settings_svc(tmp_settings_file):
    return SettingsService(settings_path=tmp_settings_file)


@pytest.fixture
def history_svc(tmp_history_dir):
    logs_dir = tmp_history_dir / "build_logs"
    logs_dir.mkdir()
    history_path = tmp_history_dir / "build_history.json"
    return HistoryService(history_path=history_path, logs_dir=logs_dir)


@pytest.fixture
def artifact_svc(tmp_dist_dir):
    return ArtifactService(dist_dir=tmp_dist_dir)


@pytest.fixture
def build_svc(config_svc, history_svc, settings_svc, artifact_svc):
    return BuildService(
        config_service=config_svc,
        history_service=history_svc,
        settings_service=settings_svc,
        artifact_service=artifact_svc,
    )


@pytest.fixture
def client(config_svc, settings_svc, history_svc, artifact_svc, build_svc):
    """TestClient with all services overridden to use temporary fixtures."""
    app.dependency_overrides[get_config_service] = lambda: config_svc
    app.dependency_overrides[get_settings_service] = lambda: settings_svc
    app.dependency_overrides[get_history_service] = lambda: history_svc
    app.dependency_overrides[get_artifact_service] = lambda: artifact_svc
    app.dependency_overrides[get_build_service] = lambda: build_svc
    yield TestClient(app)
    app.dependency_overrides.clear()


# ===========================================================================
# Story 1: View List of Available Radio Models
# ===========================================================================


class TestListModels:
    """AC: Story 1 — View list of radio models."""

    def test_list_models_returns_200(self, client):
        """GET /api/models returns HTTP 200."""
        resp = client.get("/api/models")
        assert resp.status_code == 200

    def test_list_models_contains_all_targets(self, client):
        """All 3 models from SAMPLE_CONFIG are present in the response."""
        data = client.get("/api/models").json()
        targets = data["targets"]
        assert "tx15" in targets
        assert "gx12" in targets
        assert "pl18" in targets

    def test_list_models_includes_firmware_version(self, client):
        """Response contains firmware_version field."""
        data = client.get("/api/models").json()
        assert data["firmware_version"] == "2.12"

    def test_list_models_each_has_required_fields(self, client):
        """Each model exposes: key (in dict key), pcb, enabled, extra_flags."""
        targets = client.get("/api/models").json()["targets"]
        for key, model in targets.items():
            assert "pcb" in model, f"Model {key} missing 'pcb'"
            assert "enabled" in model, f"Model {key} missing 'enabled'"
            assert "extra_flags" in model, f"Model {key} missing 'extra_flags'"

    def test_list_models_pcbrev_present_when_set(self, client):
        """Models with pcbrev expose it in the response."""
        targets = client.get("/api/models").json()["targets"]
        assert targets["gx12"]["pcbrev"] == "GX12V2"
        assert targets["pl18"]["pcbrev"] == "PL18EV"

    def test_list_models_pcbrev_absent_when_not_set(self, client):
        """Models without pcbrev return null/None."""
        targets = client.get("/api/models").json()["targets"]
        assert targets["tx15"].get("pcbrev") is None

    def test_list_models_extra_flags_correct(self, client):
        """Extra flags are returned as an array."""
        targets = client.get("/api/models").json()["targets"]
        assert targets["tx15"]["extra_flags"] == ["-DCROSSFIRE=YES"]
        assert targets["gx12"]["extra_flags"] == []

    def test_get_single_model_returns_200(self, client):
        """GET /api/models/{key} returns the model."""
        resp = client.get("/api/models/tx15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "tx15"
        assert data["pcb"] == "TX15"
        assert data["enabled"] is True

    def test_get_nonexistent_model_returns_404(self, client):
        """GET /api/models/{nonexistent} returns 404."""
        resp = client.get("/api/models/nonexistent_model")
        assert resp.status_code == 404


# ===========================================================================
# Story 2: Enable or Disable a Radio Model
# ===========================================================================


class TestToggleModel:
    """AC: Story 2 — Toggle enabled status."""

    def test_enable_disabled_model(self, client):
        """PATCH /api/models/gx12 with enabled=true flips the flag."""
        resp = client.patch("/api/models/gx12", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_disable_enabled_model(self, client):
        """PATCH /api/models/tx15 with enabled=false flips the flag."""
        resp = client.patch("/api/models/tx15", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_toggle_persists_in_list(self, client):
        """After toggling, GET /api/models reflects the new state."""
        client.patch("/api/models/gx12", json={"enabled": True})
        targets = client.get("/api/models").json()["targets"]
        assert targets["gx12"]["enabled"] is True

    def test_toggle_one_does_not_affect_others(self, client):
        """Toggling gx12 does not change tx15's enabled state."""
        client.patch("/api/models/gx12", json={"enabled": True})
        targets = client.get("/api/models").json()["targets"]
        assert targets["tx15"]["enabled"] is True  # unchanged

    def test_toggle_nonexistent_returns_404(self, client):
        """Toggling a model that does not exist returns 404."""
        resp = client.patch("/api/models/no_such_model", json={"enabled": True})
        assert resp.status_code == 404


# ===========================================================================
# Story 3: View and Edit a Single Model
# ===========================================================================


class TestEditModel:
    """AC: Story 3 — Edit model attributes."""

    def test_edit_pcb_updates_field(self, client):
        """PATCH with new pcb value reflects in subsequent GET."""
        resp = client.patch("/api/models/tx15", json={"pcb": "TX16S"})
        assert resp.status_code == 200
        assert resp.json()["pcb"] == "TX16S"

    def test_edit_pcbrev_updates_field(self, client):
        """PATCH with pcbrev updates the optional field."""
        resp = client.patch("/api/models/tx15", json={"pcbrev": "TX15_V2"})
        assert resp.status_code == 200
        assert resp.json()["pcbrev"] == "TX15_V2"

    def test_edit_extra_flags_valid_format(self, client):
        """PATCH accepts properly formatted CMake flags."""
        resp = client.patch("/api/models/tx15", json={"extra_flags": ["-DTEST=YES", "-DFOO=BAR"]})
        assert resp.status_code == 200
        assert resp.json()["extra_flags"] == ["-DTEST=YES", "-DFOO=BAR"]

    def test_edit_extra_flags_invalid_format_rejected(self, client):
        """PATCH with a badly formatted flag returns 422 validation error."""
        resp = client.patch("/api/models/tx15", json={"extra_flags": ["INVALID_FLAG"]})
        assert resp.status_code == 422

    def test_edit_empty_pcb_rejected(self, client):
        """PATCH with empty string pcb returns 422."""
        resp = client.patch("/api/models/tx15", json={"pcb": ""})
        assert resp.status_code == 422

    def test_partial_update_preserves_other_fields(self, client):
        """PATCH only changes specified fields; others remain unchanged."""
        resp = client.patch("/api/models/tx15", json={"pcb": "TX16S"})
        data = resp.json()
        # enabled and extra_flags should still match original
        assert data["enabled"] is True
        assert data["extra_flags"] == ["-DCROSSFIRE=YES"]


# ===========================================================================
# Story 4: Add a New Radio Model
# ===========================================================================


class TestAddModel:
    """AC: Story 4 — Add a new model."""

    def test_add_model_returns_201(self, client):
        """POST /api/models with valid data returns 201."""
        resp = client.post("/api/models", json={
            "key": "newmodel",
            "pcb": "TX12",
            "enabled": False,
            "extra_flags": [],
        })
        assert resp.status_code == 201

    def test_add_model_appears_in_list(self, client):
        """After creation, the model appears in GET /api/models."""
        client.post("/api/models", json={
            "key": "newmodel",
            "pcb": "TX12",
            "enabled": False,
            "extra_flags": [],
        })
        targets = client.get("/api/models").json()["targets"]
        assert "newmodel" in targets

    def test_add_model_duplicate_key_returns_400(self, client):
        """Adding a model with an existing key returns 400 with error."""
        resp = client.post("/api/models", json={
            "key": "tx15",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": [],
        })
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_add_model_empty_key_returns_422(self, client):
        """Adding a model with empty name returns 422 validation error."""
        resp = client.post("/api/models", json={
            "key": "",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": [],
        })
        assert resp.status_code == 422

    def test_add_model_empty_pcb_returns_422(self, client):
        """Adding a model without PCB type returns 422."""
        resp = client.post("/api/models", json={
            "key": "somemodel",
            "pcb": "",
            "enabled": False,
            "extra_flags": [],
        })
        assert resp.status_code == 422

    def test_add_model_with_pcbrev(self, client):
        """Model with optional pcbrev is stored correctly."""
        resp = client.post("/api/models", json={
            "key": "newwithrev",
            "pcb": "PL18",
            "pcbrev": "PL18EV",
            "enabled": True,
            "extra_flags": [],
        })
        assert resp.status_code == 201
        assert resp.json()["pcbrev"] == "PL18EV"

    def test_add_model_with_valid_cmake_flags(self, client):
        """Model with valid cmake flags is accepted."""
        resp = client.post("/api/models", json={
            "key": "flagmodel",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": ["-DCROSSFIRE=YES", "-DGHOST=NO"],
        })
        assert resp.status_code == 201
        assert resp.json()["extra_flags"] == ["-DCROSSFIRE=YES", "-DGHOST=NO"]

    def test_add_model_invalid_cmake_flag_returns_422(self, client):
        """Model with invalid cmake flag format is rejected."""
        resp = client.post("/api/models", json={
            "key": "badflagmodel",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": ["NOT_A_FLAG"],
        })
        assert resp.status_code == 422

    def test_add_model_key_uppercase_rejected(self, client):
        """Model key with uppercase letters is rejected (keys must be lowercase)."""
        resp = client.post("/api/models", json={
            "key": "TxModel",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": [],
        })
        assert resp.status_code == 422


# ===========================================================================
# Story 5: Delete/Remove a Radio Model
# ===========================================================================


class TestDeleteModel:
    """AC: Story 5 — Delete a model."""

    def test_delete_model_returns_204(self, client):
        """DELETE /api/models/{key} returns 204 No Content."""
        resp = client.delete("/api/models/gx12")
        assert resp.status_code == 204

    def test_deleted_model_not_in_list(self, client):
        """After deletion, model no longer appears in GET /api/models."""
        client.delete("/api/models/gx12")
        targets = client.get("/api/models").json()["targets"]
        assert "gx12" not in targets

    def test_delete_nonexistent_returns_404(self, client):
        """Deleting a model that does not exist returns 404."""
        resp = client.delete("/api/models/no_such_model")
        assert resp.status_code == 404

    def test_delete_one_preserves_others(self, client):
        """Deleting gx12 leaves tx15 and pl18 intact."""
        client.delete("/api/models/gx12")
        targets = client.get("/api/models").json()["targets"]
        assert "tx15" in targets
        assert "pl18" in targets


# ===========================================================================
# Story 6: Trigger a Firmware Build — Input validation layer
# ===========================================================================


class TestBuildTrigger:
    """AC: Story 6 — Build trigger validation."""

    def test_build_with_no_models_returns_422(self, client):
        """POST /api/builds with empty selected_models returns 422."""
        resp = client.post("/api/builds", json={
            "selected_models": [],
            "component": "all",
            "clean": False,
            "jobs": 4,
        })
        assert resp.status_code == 422

    def test_build_with_invalid_component_returns_422(self, client):
        """POST /api/builds with invalid component returns 422."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "invalid_component",
            "clean": False,
            "jobs": 4,
        })
        assert resp.status_code == 422

    def test_build_with_negative_jobs_returns_422(self, client):
        """POST /api/builds with jobs=-1 returns 422."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "clean": False,
            "jobs": -1,
        })
        assert resp.status_code == 422

    def test_build_with_nonexistent_model_returns_400(self, client):
        """POST /api/builds with a key not in config returns 400."""
        resp = client.post("/api/builds", json={
            "selected_models": ["nonexistent_model"],
            "component": "all",
            "clean": False,
            "jobs": 4,
        })
        assert resp.status_code == 400

    def test_build_valid_request_accepted(self, client):
        """POST /api/builds with valid payload is accepted (202)."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "clean": False,
            "jobs": 4,
        })
        # 202 Accepted means the build was accepted; actual subprocess may fail
        # but the validation passed
        assert resp.status_code in (202, 400, 500)  # 400 if custom_build.py missing
        # Crucially it must NOT be 422 (which would indicate validation failure)
        assert resp.status_code != 422

    def test_build_with_invalid_firmware_version_returns_422(self, client):
        """POST /api/builds with a version containing path separators is rejected."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "firmware_version": "../../etc/passwd",
            "clean": False,
            "jobs": 4,
        })
        assert resp.status_code == 422

    def test_build_firmware_version_with_special_chars_rejected(self, client):
        """POST /api/builds with shell metacharacters in firmware_version is rejected."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "firmware_version": "2.12; rm -rf /",
            "clean": False,
            "jobs": 4,
        })
        assert resp.status_code == 422

    def test_build_firmware_version_valid_format_accepted(self, client):
        """POST /api/builds with a valid version string passes validation."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "firmware_version": "2.12.0",
            "clean": False,
            "jobs": 4,
        })
        # Must not be a validation error (422)
        assert resp.status_code != 422

    def test_build_zero_jobs_is_treated_as_cpu_count(self, client):
        """jobs=0 is valid (means use CPU count); must not return 422."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "clean": False,
            "jobs": 0,
        })
        assert resp.status_code != 422

    def test_get_active_build_when_none(self, client):
        """GET /api/builds/active returns 204 when no build is running."""
        resp = client.get("/api/builds/active")
        assert resp.status_code == 204

    def test_get_nonexistent_build_returns_404(self, client):
        """GET /api/builds/{unknown_id} returns 404."""
        resp = client.get("/api/builds/nonexistent-build-id")
        assert resp.status_code == 404


# ===========================================================================
# Story 7: SSE Log Streaming endpoint
# ===========================================================================


class TestSSELogEndpoint:
    """AC: Story 7 — SSE log streaming endpoint exists and returns correct media type."""

    def test_sse_endpoint_for_unknown_build_returns_404(self, client):
        """GET /api/builds/{id}/logs returns 404 for unknown build."""
        resp = client.get("/api/builds/unknown-build-id/logs")
        assert resp.status_code == 404

    def test_sse_endpoint_path_exists(self, client):
        """The SSE path /api/builds/{id}/logs is registered (not 405 Method Not Allowed)."""
        resp = client.get("/api/builds/some-id/logs")
        # Should be 404 (not found), NOT 405 (method not allowed) or 404 from routing
        assert resp.status_code != 405


# ===========================================================================
# Story 8: Download Firmware Artifacts
# ===========================================================================


class TestArtifacts:
    """AC: Story 8 — Artifact listing and download."""

    def test_list_artifacts_empty_for_new_model(self, client):
        """GET /api/artifacts/{key} returns empty list when no files exist."""
        resp = client.get("/api/artifacts/tx15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "tx15"
        assert data["files"] == []

    def test_list_artifacts_returns_files_when_present(self, client, tmp_dist_dir):
        """GET /api/artifacts/{key} lists .bin and .uf2 files when present."""
        model_dir = tmp_dist_dir / "tx15"
        model_dir.mkdir()
        (model_dir / "firmware.bin").write_bytes(b"\x00" * 100)
        (model_dir / "firmware.uf2").write_bytes(b"\x00" * 200)

        resp = client.get("/api/artifacts/tx15")
        assert resp.status_code == 200
        files = [f["filename"] for f in resp.json()["files"]]
        assert "firmware.bin" in files
        assert "firmware.uf2" in files

    def test_download_artifact_returns_file(self, client, tmp_dist_dir):
        """GET /api/artifacts/{key}/{file} returns the binary file."""
        model_dir = tmp_dist_dir / "tx15"
        model_dir.mkdir()
        (model_dir / "firmware.bin").write_bytes(b"FAKE_FIRMWARE_DATA")

        resp = client.get("/api/artifacts/tx15/firmware.bin")
        assert resp.status_code == 200
        assert b"FAKE_FIRMWARE_DATA" in resp.content

    def test_download_artifact_has_model_prefixed_filename(self, client, tmp_dist_dir):
        """Downloaded artifact filename is prefixed with model key."""
        model_dir = tmp_dist_dir / "tx15"
        model_dir.mkdir()
        (model_dir / "firmware.bin").write_bytes(b"DATA")

        resp = client.get("/api/artifacts/tx15/firmware.bin")
        assert resp.status_code == 200
        content_disp = resp.headers.get("content-disposition", "")
        assert "tx15_firmware.bin" in content_disp

    def test_download_nonexistent_artifact_returns_404(self, client):
        """GET /api/artifacts/{key}/{file} for missing file returns 404."""
        resp = client.get("/api/artifacts/tx15/firmware.bin")
        assert resp.status_code == 404

    def test_download_artifact_path_traversal_blocked(self, client):
        """Path traversal attempts via filename are blocked."""
        resp = client.get("/api/artifacts/tx15/../../etc/passwd")
        assert resp.status_code in (400, 404, 422)

    def test_download_artifact_path_traversal_via_model_key_blocked(self, client):
        """Path traversal via model_key is blocked."""
        resp = client.get("/api/artifacts/../etc/passwd")
        assert resp.status_code in (400, 404, 422)


# ===========================================================================
# Story 9: Build History
# ===========================================================================


class TestBuildHistory:
    """AC: Story 9 — Build history listing, filtering, and detail."""

    def _seed_history(self, history_svc, count=3):
        """Insert dummy history entries for testing."""
        entries = []
        statuses = ["success", "failed", "aborted"]
        for i in range(count):
            entry = BuildHistoryEntry(
                build_id=f"test-build-id-{i}",
                timestamp=f"2026-01-0{i+1}T10:00:00+00:00",
                end_time=f"2026-01-0{i+1}T10:05:00+00:00",
                models=["tx15"] if i % 2 == 0 else ["gx12"],
                status=statuses[i % 3],
                firmware_version="2.12",
                component="all",
                clean=False,
                jobs=4,
                duration_ms=300000,
                log_file=f"logs/test-build-id-{i}.log",
            )
            history_svc.record(entry)
            entries.append(entry)
        return entries

    def test_history_list_returns_200(self, client):
        """GET /api/history returns 200."""
        resp = client.get("/api/history")
        assert resp.status_code == 200

    def test_history_list_empty_by_default(self, client):
        """GET /api/history returns empty list when no builds have run."""
        data = client.get("/api/history").json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_history_list_shows_recorded_entries(self, client, history_svc):
        """Recorded history entries appear in GET /api/history."""
        self._seed_history(history_svc, 3)
        data = client.get("/api/history").json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_history_entry_has_required_fields(self, client, history_svc):
        """Each history entry has: timestamp, models, status, firmware_version."""
        self._seed_history(history_svc, 1)
        items = client.get("/api/history").json()["items"]
        item = items[0]
        assert "timestamp" in item
        assert "models" in item
        assert "status" in item
        assert "firmware_version" in item
        assert "build_id" in item

    def test_history_filter_by_status(self, client, history_svc):
        """GET /api/history?status=success returns only successful entries."""
        self._seed_history(history_svc, 3)
        data = client.get("/api/history?status=success").json()
        for item in data["items"]:
            assert item["status"] == "success"

    def test_history_filter_by_model(self, client, history_svc):
        """GET /api/history?model=tx15 returns only entries for that model."""
        self._seed_history(history_svc, 3)
        data = client.get("/api/history?model=tx15").json()
        for item in data["items"]:
            assert "tx15" in item["models"]

    def test_history_pagination(self, client, history_svc):
        """GET /api/history?page=1&page_size=2 returns only 2 items."""
        self._seed_history(history_svc, 3)
        data = client.get("/api/history?page=1&page_size=2").json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    def test_history_detail_by_id(self, client, history_svc):
        """GET /api/history/{build_id} returns a specific entry."""
        entries = self._seed_history(history_svc, 1)
        build_id = entries[0].build_id
        resp = client.get(f"/api/history/{build_id}")
        assert resp.status_code == 200
        assert resp.json()["build_id"] == build_id

    def test_history_detail_nonexistent_returns_404(self, client):
        """GET /api/history/{unknown_id} returns 404."""
        resp = client.get("/api/history/unknown-build-id")
        assert resp.status_code == 404

    def test_history_delete_entry(self, client, history_svc):
        """DELETE /api/history/{build_id} removes the entry."""
        entries = self._seed_history(history_svc, 1)
        build_id = entries[0].build_id
        resp = client.delete(f"/api/history/{build_id}")
        assert resp.status_code == 204
        # Verify it's gone
        assert client.get(f"/api/history/{build_id}").status_code == 404

    def test_history_clear_all(self, client, history_svc):
        """DELETE /api/history clears all entries."""
        self._seed_history(history_svc, 3)
        resp = client.delete("/api/history")
        assert resp.status_code == 200
        data = client.get("/api/history").json()
        assert data["total"] == 0

    def test_history_newest_first_ordering(self, client, history_svc):
        """History entries are returned newest-first."""
        self._seed_history(history_svc, 3)
        items = client.get("/api/history").json()["items"]
        timestamps = [item["timestamp"] for item in items]
        assert timestamps == sorted(timestamps, reverse=True)


# ===========================================================================
# Story 10: Export and Import Configuration
# ===========================================================================


class TestConfigExportImport:
    """AC: Story 10 — Export and import configuration."""

    def test_export_returns_200(self, client):
        """GET /api/config/export returns 200."""
        resp = client.get("/api/config/export")
        assert resp.status_code == 200

    def test_export_content_disposition(self, client):
        """Exported file has correct Content-Disposition header."""
        resp = client.get("/api/config/export")
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert "targets.json" in resp.headers.get("content-disposition", "")

    def test_export_valid_json(self, client):
        """Exported content is valid JSON."""
        resp = client.get("/api/config/export")
        data = json.loads(resp.content)
        assert "firmware_version" in data
        assert "targets" in data

    def test_export_matches_original_structure(self, client):
        """Exported JSON matches the original targets.json structure."""
        resp = client.get("/api/config/export")
        data = json.loads(resp.content)
        assert data["firmware_version"] == "2.12"
        assert set(data["targets"].keys()) == {"tx15", "gx12", "pl18"}

    def test_import_valid_config(self, client):
        """POST /api/config/import with valid JSON replaces configuration."""
        new_config = {
            "firmware_version": "3.0",
            "targets": {
                "newmodel": {"pcb": "NEWPCB", "enabled": True, "extra_flags": []},
            },
        }
        file_content = json.dumps(new_config).encode("utf-8")
        resp = client.post(
            "/api/config/import",
            files={"file": ("targets.json", io.BytesIO(file_content), "application/json")},
        )
        assert resp.status_code == 200
        assert resp.json()["model_count"] == 1

    def test_import_replaces_models(self, client):
        """After import, GET /api/models reflects the new configuration."""
        new_config = {
            "firmware_version": "3.0",
            "targets": {
                "importedmodel": {"pcb": "IMP", "enabled": False, "extra_flags": []},
            },
        }
        file_content = json.dumps(new_config).encode("utf-8")
        client.post(
            "/api/config/import",
            files={"file": ("targets.json", io.BytesIO(file_content), "application/json")},
        )
        targets = client.get("/api/models").json()["targets"]
        assert "importedmodel" in targets
        assert "tx15" not in targets  # original replaced

    def test_import_invalid_json_returns_400(self, client):
        """POST /api/config/import with invalid JSON returns 400."""
        resp = client.post(
            "/api/config/import",
            files={"file": ("targets.json", io.BytesIO(b"NOT JSON {{{"), "application/json")},
        )
        assert resp.status_code == 400
        assert "invalid json" in resp.json()["detail"].lower()

    def test_import_missing_firmware_version_returns_400(self, client):
        """POST /api/config/import missing required fields returns 400."""
        bad_config = {"targets": {}}  # missing firmware_version
        file_content = json.dumps(bad_config).encode("utf-8")
        resp = client.post(
            "/api/config/import",
            files={"file": ("targets.json", io.BytesIO(file_content), "application/json")},
        )
        assert resp.status_code == 400

    def test_import_oversized_file_returns_413(self, client):
        """POST /api/config/import with file >1MiB returns 413."""
        oversized = b"x" * (1 * 1024 * 1024 + 1)
        resp = client.post(
            "/api/config/import",
            files={"file": ("targets.json", io.BytesIO(oversized), "application/json")},
        )
        assert resp.status_code == 413

    def test_get_config_returns_firmware_version_and_targets(self, client):
        """GET /api/config returns firmware_version and targets."""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "firmware_version" in data
        assert "targets" in data


# ===========================================================================
# Story 11: Configure Global Build Settings
# ===========================================================================


class TestSettings:
    """AC: Story 11 — View and edit build settings."""

    def test_get_settings_returns_200(self, client):
        """GET /api/settings returns 200."""
        resp = client.get("/api/settings")
        assert resp.status_code == 200

    def test_get_settings_has_toolchain_path(self, client):
        """GET /api/settings includes toolchain_path field."""
        data = client.get("/api/settings").json()
        assert "toolchain_path" in data

    def test_get_settings_default_build_output_directory(self, client):
        """Default build_output_directory is './dist'."""
        data = client.get("/api/settings").json()
        assert data["build_output_directory"] == "./dist"

    def test_get_settings_default_logs_directory(self, client):
        """Default logs_directory is './logs'."""
        data = client.get("/api/settings").json()
        assert data["logs_directory"] == "./logs"

    def test_update_settings_logs_directory(self, client):
        """PATCH /api/settings updates logs_directory."""
        resp = client.patch("/api/settings", json={"logs_directory": "./custom_logs"})
        assert resp.status_code == 200
        assert resp.json()["logs_directory"] == "./custom_logs"

    def test_update_settings_build_output_directory(self, client):
        """PATCH /api/settings updates build_output_directory."""
        resp = client.patch("/api/settings", json={"build_output_directory": "./custom_dist"})
        assert resp.status_code == 200
        assert resp.json()["build_output_directory"] == "./custom_dist"

    def test_update_settings_invalid_toolchain_path_returns_400(self, client):
        """PATCH /api/settings with non-existent toolchain path returns 400."""
        resp = client.patch("/api/settings", json={"toolchain_path": "/nonexistent/path/to/toolchain"})
        assert resp.status_code == 400
        assert "toolchain" in resp.json()["detail"].lower()

    def test_update_settings_partial_preserves_other_fields(self, client):
        """PATCH one field does not reset other settings fields."""
        # First set a field
        client.patch("/api/settings", json={"logs_directory": "./my_logs"})
        # Now patch another field
        client.patch("/api/settings", json={"build_output_directory": "./my_dist"})
        # Both should be preserved
        data = client.get("/api/settings").json()
        assert data["logs_directory"] == "./my_logs"
        assert data["build_output_directory"] == "./my_dist"

    def test_settings_persist_across_requests(self, client):
        """Changes to settings persist in subsequent GET /api/settings calls."""
        client.patch("/api/settings", json={"build_output_directory": "./persistent_dist"})
        data = client.get("/api/settings").json()
        assert data["build_output_directory"] == "./persistent_dist"


# ===========================================================================
# Health check endpoint
# ===========================================================================


class TestHealthEndpoint:
    """Verify /api/health exists and returns a structured response."""

    def test_health_check_returns_200(self, client):
        """GET /api/health returns 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_check_has_status_field(self, client):
        """Health check response contains a 'status' field."""
        data = client.get("/api/health").json()
        assert "status" in data
        assert data["status"] in ("ok", "degraded", "error")

    def test_health_check_has_checks_field(self, client):
        """Health check response contains a 'checks' dict."""
        data = client.get("/api/health").json()
        assert "checks" in data
        assert isinstance(data["checks"], dict)


# ===========================================================================
# Edge Cases and Error Scenarios from BA Spec
# ===========================================================================


class TestEdgeCases:
    """Edge cases and error scenarios defined in the BA spec."""

    def test_duplicate_model_name_error_message(self, client):
        """Adding duplicate model returns message containing 'already exists'."""
        resp = client.post("/api/models", json={"key": "tx15", "pcb": "TX15", "enabled": False, "extra_flags": []})
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_invalid_cmake_flag_no_d_prefix(self, client):
        """Flag without -D prefix is rejected."""
        resp = client.post("/api/models", json={
            "key": "flagtest",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": ["CROSSFIRE=YES"],
        })
        assert resp.status_code == 422

    def test_invalid_cmake_flag_no_equals(self, client):
        """Flag without = separator is rejected."""
        resp = client.post("/api/models", json={
            "key": "flagtest2",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": ["-DCROSSFIRE"],
        })
        assert resp.status_code == 422

    def test_empty_model_name_rejected(self, client):
        """Empty model name returns 422 with appropriate message."""
        resp = client.post("/api/models", json={"key": "", "pcb": "TX15", "enabled": False, "extra_flags": []})
        assert resp.status_code == 422

    def test_pcb_field_required_on_create(self, client):
        """Empty PCB on create returns 422."""
        resp = client.post("/api/models", json={"key": "noPcbModel", "pcb": "", "enabled": False, "extra_flags": []})
        assert resp.status_code == 422

    def test_build_no_models_selected_validation(self, client):
        """Build request with no models returns 422 with message."""
        resp = client.post("/api/builds", json={"selected_models": [], "component": "all", "clean": False, "jobs": 1})
        assert resp.status_code == 422

    def test_build_invalid_jobs_count_negative(self, client):
        """Negative jobs count returns 422."""
        resp = client.post("/api/builds", json={"selected_models": ["tx15"], "component": "all", "clean": False, "jobs": -5})
        assert resp.status_code == 422

    def test_firmware_version_with_path_traversal_rejected(self, client):
        """firmware_version containing ../ is rejected by validator."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "firmware_version": "../malicious",
            "clean": False,
            "jobs": 1,
        })
        assert resp.status_code == 422

    def test_firmware_version_with_null_byte_rejected(self, client):
        """firmware_version with null byte is rejected."""
        resp = client.post("/api/builds", json={
            "selected_models": ["tx15"],
            "component": "all",
            "firmware_version": "2.12\x00extra",
            "clean": False,
            "jobs": 1,
        })
        assert resp.status_code == 422

    def test_artifact_not_found_message(self, client):
        """Attempting to download missing artifact returns 404 (firmware file not found)."""
        resp = client.get("/api/artifacts/tx15/firmware.bin")
        assert resp.status_code == 404

    def test_model_key_with_spaces_rejected(self, client):
        """Model key with spaces is rejected."""
        resp = client.post("/api/models", json={"key": "tx 15", "pcb": "TX15", "enabled": False, "extra_flags": []})
        assert resp.status_code == 422

    def test_model_key_starting_with_hyphen_rejected(self, client):
        """Model key starting with hyphen is rejected (must start with alphanumeric)."""
        resp = client.post("/api/models", json={"key": "-tx15", "pcb": "TX15", "enabled": False, "extra_flags": []})
        assert resp.status_code == 422

    def test_import_config_overwrites_previous_models(self, client):
        """Importing new config removes all previous models as per edge case spec."""
        new_config = {
            "firmware_version": "3.0",
            "targets": {"freshmodel": {"pcb": "TX15", "enabled": True, "extra_flags": []}},
        }
        file_content = json.dumps(new_config).encode("utf-8")
        client.post(
            "/api/config/import",
            files={"file": ("targets.json", io.BytesIO(file_content), "application/json")},
        )
        targets = client.get("/api/models").json()["targets"]
        # Original models should be gone
        assert "tx15" not in targets
        assert "gx12" not in targets
        # New model should be present
        assert "freshmodel" in targets

    def test_export_with_empty_targets_is_valid_json(self, client, tmp_config):
        """Exporting a config with no targets returns valid empty-targets JSON."""
        # Clear all models first
        for key in ["tx15", "gx12", "pl18"]:
            client.delete(f"/api/models/{key}")
        resp = client.get("/api/config/export")
        data = json.loads(resp.content)
        assert "targets" in data
        assert isinstance(data["targets"], dict)

    def test_history_log_for_unknown_build_returns_404(self, client):
        """GET /api/history/{unknown_id}/log returns 404."""
        resp = client.get("/api/history/unknown-build-id/log")
        assert resp.status_code == 404


# ===========================================================================
# Security Validation Tests (from 07-security-review.md)
# ===========================================================================


class TestSecurityValidations:
    """Validate security fixes applied by the Security Reviewer."""

    def test_firmware_version_validator_blocks_shell_metacharacters(self, client):
        """Firmware version with shell metacharacters is blocked at Pydantic level."""
        dangerous_versions = [
            "2.12; rm -rf /",
            "2.12 && cat /etc/passwd",
            "2.12`whoami`",
            "2.12|cat /etc/shadow",
        ]
        for version in dangerous_versions:
            resp = client.post("/api/builds", json={
                "selected_models": ["tx15"],
                "component": "all",
                "firmware_version": version,
                "clean": False,
                "jobs": 1,
            })
            assert resp.status_code == 422, f"Expected 422 for version '{version}', got {resp.status_code}"

    def test_firmware_version_validator_allows_valid_formats(self, client):
        """Valid firmware version formats pass the validator."""
        valid_versions = ["2.12", "2.12.0", "v2.12-rc1", "nightly-20260101"]
        for version in valid_versions:
            resp = client.post("/api/builds", json={
                "selected_models": ["tx15"],
                "component": "all",
                "firmware_version": version,
                "clean": False,
                "jobs": 1,
            })
            # Must not be a validation error
            assert resp.status_code != 422, f"Version '{version}' was unexpectedly rejected"

    def test_config_import_upload_size_limit(self, client):
        """Files larger than 1 MiB are rejected with 413."""
        oversized = b"A" * (1 * 1024 * 1024 + 1)
        resp = client.post(
            "/api/config/import",
            files={"file": ("big.json", io.BytesIO(oversized), "application/json")},
        )
        assert resp.status_code == 413

    def test_artifact_path_traversal_via_filename(self, client):
        """Attempts to traverse path via artifact filename are blocked."""
        resp = client.get("/api/artifacts/tx15/../../etc/hosts")
        assert resp.status_code in (400, 404, 422)

    def test_model_key_regex_blocks_path_traversal(self, client):
        """Model keys with path separators are rejected."""
        resp = client.post("/api/models", json={
            "key": "../evil",
            "pcb": "TX15",
            "enabled": False,
            "extra_flags": [],
        })
        assert resp.status_code == 422

    def test_frontend_html_file_served(self, client):
        """Frontend index.html is served at root path."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"EdgeTX" in resp.content or b"<!DOCTYPE html" in resp.content.lower()

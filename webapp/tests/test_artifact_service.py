"""
Unit tests for ArtifactService.
"""
import pytest
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from webapp.backend.services.artifact_service import ArtifactService
from webapp.backend.models import ArtifactNotFoundError, InvalidPathError


@pytest.fixture
def dist_dir(tmp_path):
    """Create a mock dist/ directory with some artifact files."""
    tx15 = tmp_path / "tx15"
    tx15.mkdir()
    (tx15 / "firmware.bin").write_bytes(b"\x00" * 100)
    (tx15 / "firmware.uf2").write_bytes(b"\x00" * 200)

    pl18 = tmp_path / "pl18"
    pl18.mkdir()
    # No files in pl18

    return tmp_path


@pytest.fixture
def service(dist_dir):
    return ArtifactService(dist_dir=dist_dir)


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------


def test_list_artifacts_with_files(service):
    result = service.list_artifacts("tx15")
    assert result.model == "tx15"
    assert len(result.files) == 2
    filenames = {f.filename for f in result.files}
    assert "firmware.bin" in filenames
    assert "firmware.uf2" in filenames


def test_list_artifacts_size(service):
    result = service.list_artifacts("tx15")
    by_name = {f.filename: f for f in result.files}
    assert by_name["firmware.bin"].size_bytes == 100
    assert by_name["firmware.uf2"].size_bytes == 200


def test_list_artifacts_empty_model(service):
    result = service.list_artifacts("pl18")
    assert result.model == "pl18"
    assert result.files == []


def test_list_artifacts_nonexistent_model(service):
    result = service.list_artifacts("nonexistent")
    assert result.files == []


# ---------------------------------------------------------------------------
# get_artifact_path
# ---------------------------------------------------------------------------


def test_get_artifact_path_valid(service):
    path = service.get_artifact_path("tx15", "firmware.bin")
    assert path.exists()
    assert path.name == "firmware.bin"


def test_get_artifact_path_not_found(service):
    with pytest.raises(ArtifactNotFoundError):
        service.get_artifact_path("tx15", "nonexistent.bin")


def test_get_artifact_path_traversal_attack(service):
    """Ensure ../../../etc/passwd style attacks are blocked."""
    with pytest.raises((InvalidPathError, ArtifactNotFoundError)):
        service.get_artifact_path("tx15", "../../../etc/passwd")


def test_get_artifact_path_traversal_via_model(service):
    with pytest.raises((InvalidPathError, ArtifactNotFoundError)):
        service.get_artifact_path("../other", "firmware.bin")


# ---------------------------------------------------------------------------
# list_all_artifacts
# ---------------------------------------------------------------------------


def test_list_all_artifacts(service):
    all_art = service.list_all_artifacts()
    assert "tx15" in all_art
    assert "pl18" in all_art
    assert len(all_art["tx15"].files) == 2
    assert len(all_art["pl18"].files) == 0

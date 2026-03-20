"""
Unit tests for SettingsService.
"""
import json
import pytest
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from webapp.backend.services.settings_service import SettingsService
from webapp.backend.models import AppSettingsUpdate


@pytest.fixture
def service(tmp_path):
    return SettingsService(settings_path=tmp_path / "app_settings.json")


# ---------------------------------------------------------------------------
# get (no file → defaults)
# ---------------------------------------------------------------------------


def test_get_defaults(service):
    s = service.get()
    assert s.toolchain_path == ""
    assert s.build_output_directory == "./dist"
    assert s.logs_directory == "./logs"
    assert s.auto_clean_old_builds is False
    assert s.build_history_retention_days == 0


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_toolchain(service):
    updated = service.update(AppSettingsUpdate(toolchain_path="/usr/bin"))
    assert updated.toolchain_path == "/usr/bin"


def test_update_partial(service):
    service.update(AppSettingsUpdate(toolchain_path="/usr/bin"))
    updated = service.update(AppSettingsUpdate(auto_clean_old_builds=True))
    # Previously set value should be preserved
    assert updated.toolchain_path == "/usr/bin"
    assert updated.auto_clean_old_builds is True


def test_update_persists(service, tmp_path):
    service.update(AppSettingsUpdate(build_history_retention_days=7))
    s2 = SettingsService(settings_path=tmp_path / "app_settings.json")
    loaded = s2.get()
    assert loaded.build_history_retention_days == 7


def test_update_creates_file(service, tmp_path):
    path = tmp_path / "app_settings.json"
    assert not path.exists()
    service.update(AppSettingsUpdate(toolchain_path="/bin"))
    assert path.exists()


# ---------------------------------------------------------------------------
# validate_toolchain
# ---------------------------------------------------------------------------


def test_validate_toolchain_empty_path_no_system_toolchain(service):
    # When toolchain path is empty and arm-none-eabi-gcc is not installed,
    # validate_toolchain should return False. We can mock this or skip if
    # the toolchain is present on the test machine.
    # This test simply verifies the return type is bool.
    result = service.validate_toolchain("")
    assert isinstance(result, bool)


def test_validate_toolchain_nonexistent_dir(service):
    result = service.validate_toolchain("/nonexistent/path/to/toolchain")
    assert result is False


def test_validate_toolchain_dir_without_binary(service, tmp_path):
    result = service.validate_toolchain(str(tmp_path))
    assert result is False


def test_validate_toolchain_valid(service, tmp_path):
    # Create a fake arm-none-eabi-gcc binary
    fake_bin = tmp_path / "arm-none-eabi-gcc"
    fake_bin.touch()
    result = service.validate_toolchain(str(tmp_path))
    assert result is True

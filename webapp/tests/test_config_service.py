"""
Unit tests for ConfigService.

Uses a temporary targets.json file to avoid touching the real configuration.
"""
import json
import os
import pytest
from pathlib import Path

# Ensure the project root is importable
import sys
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from webapp.backend.services.config_service import ConfigService
from webapp.backend.models import (
    ModelCreate,
    ModelUpdate,
    ModelAlreadyExistsError,
    ModelNotFoundError,
    InvalidConfigError,
)


SAMPLE_CONFIG = {
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
    },
}


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text(json.dumps(SAMPLE_CONFIG, indent=4))
    return path


@pytest.fixture
def service(config_file):
    return ConfigService(targets_path=config_file)


# ---------------------------------------------------------------------------
# get_full_config
# ---------------------------------------------------------------------------


def test_get_full_config_returns_dict(service):
    data = service.get_full_config()
    assert data["firmware_version"] == "2.12"
    assert "tx15" in data["targets"]


def test_get_full_config_raises_on_missing_file(tmp_path):
    svc = ConfigService(targets_path=tmp_path / "nonexistent.json")
    with pytest.raises(InvalidConfigError):
        svc.get_full_config()


def test_get_full_config_raises_on_invalid_json(tmp_path):
    bad = tmp_path / "targets.json"
    bad.write_text("{ not valid json }")
    svc = ConfigService(targets_path=bad)
    with pytest.raises(InvalidConfigError):
        svc.get_full_config()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


def test_list_models_returns_all(service):
    models = service.list_models()
    assert len(models) == 2
    assert "tx15" in models
    assert "gx12" in models


def test_list_models_correct_types(service):
    models = service.list_models()
    assert models["tx15"].enabled is True
    assert models["gx12"].enabled is False
    assert models["gx12"].pcbrev == "GX12V2"


# ---------------------------------------------------------------------------
# get_model
# ---------------------------------------------------------------------------


def test_get_model_existing(service):
    m = service.get_model("tx15")
    assert m.key == "tx15"
    assert m.pcb == "TX15"
    assert m.extra_flags == ["-DCROSSFIRE=YES"]


def test_get_model_not_found(service):
    with pytest.raises(ModelNotFoundError):
        service.get_model("nonexistent")


# ---------------------------------------------------------------------------
# add_model
# ---------------------------------------------------------------------------


def test_add_model_new_key(service, config_file):
    new_model = ModelCreate(key="pl18", pcb="PL18", enabled=False, extra_flags=[])
    result = service.add_model(new_model)
    assert result.key == "pl18"
    assert result.pcb == "PL18"

    # Verify persistence
    saved = json.loads(config_file.read_text())
    assert "pl18" in saved["targets"]


def test_add_model_duplicate_raises(service):
    dup = ModelCreate(key="tx15", pcb="TX15", enabled=False, extra_flags=[])
    with pytest.raises(ModelAlreadyExistsError):
        service.add_model(dup)


def test_add_model_with_pcbrev(service):
    m = ModelCreate(key="pl18ev", pcb="PL18", pcbrev="PL18EV", enabled=False, extra_flags=[])
    result = service.add_model(m)
    assert result.pcbrev == "PL18EV"


# ---------------------------------------------------------------------------
# update_model
# ---------------------------------------------------------------------------


def test_update_model_enabled(service, config_file):
    result = service.update_model("gx12", ModelUpdate(enabled=True))
    assert result.enabled is True

    saved = json.loads(config_file.read_text())
    assert saved["targets"]["gx12"]["enabled"] is True


def test_update_model_extra_flags(service):
    result = service.update_model("tx15", ModelUpdate(extra_flags=["-DGHOST=YES"]))
    assert result.extra_flags == ["-DGHOST=YES"]


def test_update_model_not_found(service):
    with pytest.raises(ModelNotFoundError):
        service.update_model("nonexistent", ModelUpdate(enabled=True))


def test_update_model_clears_pcbrev(service, config_file):
    # gx12 has pcbrev; set to empty string to clear it
    result = service.update_model("gx12", ModelUpdate(pcbrev=""))
    assert result.pcbrev is None
    saved = json.loads(config_file.read_text())
    assert "pcbrev" not in saved["targets"]["gx12"]


# ---------------------------------------------------------------------------
# delete_model
# ---------------------------------------------------------------------------


def test_delete_model(service, config_file):
    service.delete_model("gx12")
    saved = json.loads(config_file.read_text())
    assert "gx12" not in saved["targets"]


def test_delete_model_not_found(service):
    with pytest.raises(ModelNotFoundError):
        service.delete_model("nonexistent")


# ---------------------------------------------------------------------------
# Atomic write (temp file + rename)
# ---------------------------------------------------------------------------


def test_atomic_write_no_corruption(service, config_file):
    """After a successful save, the original targets.json is intact and no .tmp file remains."""
    service.update_model("tx15", ModelUpdate(enabled=False))
    tmp = config_file.with_suffix(".json.tmp")
    assert not tmp.exists(), "Temp file should be cleaned up after successful write"
    data = json.loads(config_file.read_text())
    assert data["targets"]["tx15"]["enabled"] is False


# ---------------------------------------------------------------------------
# replace_config
# ---------------------------------------------------------------------------


def test_replace_config(service, config_file):
    new_config = {
        "firmware_version": "3.0",
        "targets": {"new_model": {"pcb": "NEW", "enabled": True, "extra_flags": []}},
    }
    count = service.replace_config(new_config)
    assert count == 1
    saved = json.loads(config_file.read_text())
    assert saved["firmware_version"] == "3.0"
    assert "new_model" in saved["targets"]


def test_replace_config_invalid_structure(service):
    with pytest.raises(InvalidConfigError):
        service.replace_config({"bad_key": "data"})


# ---------------------------------------------------------------------------
# validate_model_keys_exist
# ---------------------------------------------------------------------------


def test_validate_keys_all_valid(service):
    errors = service.validate_model_keys_exist(["tx15", "gx12"])
    assert errors == []


def test_validate_keys_missing(service):
    errors = service.validate_model_keys_exist(["tx15", "bad_key"])
    assert len(errors) == 1
    assert "bad_key" in errors[0]


# ---------------------------------------------------------------------------
# Firmware version helpers
# ---------------------------------------------------------------------------


def test_get_firmware_version(service):
    assert service.get_firmware_version() == "2.12"


def test_set_firmware_version(service, config_file):
    service.set_firmware_version("3.1")
    saved = json.loads(config_file.read_text())
    assert saved["firmware_version"] == "3.1"

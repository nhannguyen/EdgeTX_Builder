"""
Unit tests for Pydantic model validation logic in webapp/backend/models.py.
"""
import pytest
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pydantic import ValidationError
from webapp.backend.models import ModelCreate, ModelUpdate, BuildRequest, AppSettings


# ---------------------------------------------------------------------------
# ModelCreate validation
# ---------------------------------------------------------------------------


def test_model_create_valid():
    m = ModelCreate(key="tx15", pcb="TX15", enabled=True, extra_flags=["-DCROSSFIRE=YES"])
    assert m.key == "tx15"
    assert m.extra_flags == ["-DCROSSFIRE=YES"]


def test_model_create_empty_key():
    with pytest.raises(ValidationError):
        ModelCreate(key="", pcb="TX15")


def test_model_create_empty_pcb():
    with pytest.raises(ValidationError):
        ModelCreate(key="tx15", pcb="")


def test_model_create_invalid_key_uppercase():
    with pytest.raises(ValidationError):
        ModelCreate(key="TX15", pcb="TX15")


def test_model_create_key_with_spaces():
    with pytest.raises(ValidationError):
        ModelCreate(key="my model", pcb="TX15")


def test_model_create_key_with_valid_hyphen():
    m = ModelCreate(key="my-model", pcb="TX15")
    assert m.key == "my-model"


def test_model_create_key_with_underscore():
    m = ModelCreate(key="my_model", pcb="TX15")
    assert m.key == "my_model"


def test_model_create_valid_cmake_flag():
    m = ModelCreate(key="tx15", pcb="TX15", extra_flags=["-DCROSSFIRE=YES", "-DGHOST=NO"])
    assert len(m.extra_flags) == 2


def test_model_create_invalid_cmake_flag():
    with pytest.raises(ValidationError):
        ModelCreate(key="tx15", pcb="TX15", extra_flags=["CROSSFIRE=YES"])


def test_model_create_invalid_cmake_flag_no_d():
    with pytest.raises(ValidationError):
        ModelCreate(key="tx15", pcb="TX15", extra_flags=["-CROSSFIRE=YES"])


def test_model_create_invalid_cmake_flag_no_equals():
    with pytest.raises(ValidationError):
        ModelCreate(key="tx15", pcb="TX15", extra_flags=["-DCROSSFIRE"])


def test_model_create_strips_whitespace_from_key():
    m = ModelCreate(key="  tx15  ", pcb="TX15")
    assert m.key == "tx15"


def test_model_create_empty_extra_flags():
    m = ModelCreate(key="tx15", pcb="TX15", extra_flags=[])
    assert m.extra_flags == []


# ---------------------------------------------------------------------------
# ModelUpdate validation
# ---------------------------------------------------------------------------


def test_model_update_partial():
    u = ModelUpdate(enabled=True)
    assert u.enabled is True
    assert u.pcb is None


def test_model_update_empty_pcb():
    with pytest.raises(ValidationError):
        ModelUpdate(pcb="")


def test_model_update_none_pcb_ok():
    u = ModelUpdate(pcb=None)
    assert u.pcb is None


def test_model_update_invalid_flags():
    with pytest.raises(ValidationError):
        ModelUpdate(extra_flags=["bad_flag"])


# ---------------------------------------------------------------------------
# BuildRequest validation
# ---------------------------------------------------------------------------


def test_build_request_valid():
    r = BuildRequest(selected_models=["tx15"], component="firmware", jobs=4)
    assert r.selected_models == ["tx15"]
    assert r.jobs == 4


def test_build_request_empty_models():
    with pytest.raises(ValidationError):
        BuildRequest(selected_models=[])


def test_build_request_invalid_component():
    with pytest.raises(ValidationError):
        BuildRequest(selected_models=["tx15"], component="invalid")


def test_build_request_negative_jobs():
    with pytest.raises(ValidationError):
        BuildRequest(selected_models=["tx15"], jobs=-1)


def test_build_request_zero_jobs_ok():
    # 0 means use CPU count
    r = BuildRequest(selected_models=["tx15"], jobs=0)
    assert r.jobs == 0


def test_build_request_invalid_model_key():
    with pytest.raises(ValidationError):
        BuildRequest(selected_models=["INVALID KEY!"])


def test_build_request_defaults():
    r = BuildRequest(selected_models=["tx15"])
    assert r.component == "all"
    assert r.clean is False
    assert r.jobs == 0


def test_build_request_multiple_models():
    r = BuildRequest(selected_models=["tx15", "gx12", "pl18"])
    assert len(r.selected_models) == 3


# ---------------------------------------------------------------------------
# AppSettings
# ---------------------------------------------------------------------------


def test_app_settings_defaults():
    s = AppSettings()
    assert s.toolchain_path == ""
    assert s.build_output_directory == "./dist"
    assert s.logs_directory == "./logs"
    assert s.auto_clean_old_builds is False
    assert s.build_history_retention_days == 0


def test_app_settings_custom():
    s = AppSettings(toolchain_path="/usr/bin", build_history_retention_days=30)
    assert s.toolchain_path == "/usr/bin"
    assert s.build_history_retention_days == 30

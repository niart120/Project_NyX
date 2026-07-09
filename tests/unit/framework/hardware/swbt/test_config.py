import sys
import tomllib
from pathlib import Path

import pytest

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.hardware.swbt.config import (
    SwbtControllerType,
    parse_controller_type,
    resolve_controller_model,
    supported_controller_models,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


def test_swbt_dependency_declared_as_runtime_dependency() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "swbt-python>=0.2.0,<0.3.0" in data["project"]["dependencies"]
    assert "swbt" not in data["project"].get("optional-dependencies", {})
    assert any(
        marker.startswith("swbt:") for marker in data["tool"]["pytest"]["ini_options"]["markers"]
    )


def test_supported_controller_models_returns_three_models_without_swbt_runtime_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "swbt", raising=False)

    models = supported_controller_models()

    assert tuple(model.controller_type for model in models) == (
        SwbtControllerType.PRO_CONTROLLER,
        SwbtControllerType.JOY_CON_L,
        SwbtControllerType.JOY_CON_R,
    )
    assert "swbt" not in sys.modules


def test_parse_controller_type_rejects_unknown_value() -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        parse_controller_type("n64-controller")

    assert exc_info.value.code == "NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED"


def test_swbt_config_resolves_default_key_store_per_controller_type() -> None:
    base_dir = Path(".nyxpy") / "swbt"

    assert (
        resolve_controller_model("pro-controller").default_key_store_path(base_dir)
        == base_dir / "pro-controller-bond.json"
    )
    assert (
        resolve_controller_model("joy-con-l").default_key_store_path(base_dir)
        == base_dir / "joy-con-l-bond.json"
    )
    assert (
        resolve_controller_model("joy-con-r").default_key_store_path(base_dir)
        == base_dir / "joy-con-r-bond.json"
    )


def test_controller_models_hold_nyx_capabilities() -> None:
    pro = resolve_controller_model("pro-controller")
    left = resolve_controller_model("joy-con-l")
    right = resolve_controller_model("joy-con-r")

    assert Button.A in pro.capabilities.buttons
    assert Button.ZL in left.capabilities.buttons
    assert Button.A not in left.capabilities.buttons
    assert Button.R in right.capabilities.buttons
    assert Button.L not in right.capabilities.buttons
    assert left.capabilities.left_stick is True
    assert left.capabilities.right_stick is False
    assert right.capabilities.left_stick is False
    assert right.capabilities.right_stick is True
    assert pro.capabilities.imu is True

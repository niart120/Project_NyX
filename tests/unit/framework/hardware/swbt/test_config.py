import sys
import tomllib
from pathlib import Path

import pytest

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.hardware.swbt.config import (
    SwbtControllerType,
    SwbtInputCapabilities,
    parse_controller_type,
    resolve_controller_model,
    supported_controller_models,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


def test_swbt_dependency_declared_as_runtime_dependency() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "swbt-python==0.6.0" in data["project"]["dependencies"]
    assert "swbt" not in data["project"].get("optional-dependencies", {})
    assert any(
        marker.startswith("swbt:") for marker in data["tool"]["pytest"]["ini_options"]["markers"]
    )


def test_swbt_lock_resolves_expected_swbt_and_bumble_versions() -> None:
    data = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    locked_versions = {package["name"]: package["version"] for package in data["package"]}

    assert locked_versions["swbt-python"] == "0.6.0"
    assert locked_versions["bumble"] == "0.0.233"


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


def test_swbt_config_resolves_default_profile_per_controller_type() -> None:
    base_dir = Path(".nyxpy") / "swbt"

    assert (
        resolve_controller_model("pro-controller").default_profile_path(base_dir)
        == base_dir / "pro-controller-profile.json"
    )
    assert (
        resolve_controller_model("joy-con-l").default_profile_path(base_dir)
        == base_dir / "joy-con-l-profile.json"
    )
    assert (
        resolve_controller_model("joy-con-r").default_profile_path(base_dir)
        == base_dir / "joy-con-r-profile.json"
    )


def test_controller_models_hold_nyx_capabilities() -> None:
    pro = resolve_controller_model("pro-controller")
    left = resolve_controller_model("joy-con-l")
    right = resolve_controller_model("joy-con-r")

    assert pro.capabilities == SwbtInputCapabilities(
        buttons=frozenset(
            {
                Button.A,
                Button.B,
                Button.X,
                Button.Y,
                Button.L,
                Button.R,
                Button.ZL,
                Button.ZR,
                Button.MINUS,
                Button.PLUS,
                Button.LS,
                Button.RS,
                Button.HOME,
                Button.CAP,
            }
        ),
        dpad=True,
        left_stick=True,
        right_stick=True,
        imu=True,
    )
    assert left.capabilities == SwbtInputCapabilities(
        buttons=frozenset(
            {
                Button.L,
                Button.ZL,
                Button.MINUS,
                Button.LS,
                Button.CAP,
                Button.SL,
                Button.SR,
            }
        ),
        dpad=True,
        left_stick=True,
        right_stick=False,
        imu=True,
    )
    assert right.capabilities == SwbtInputCapabilities(
        buttons=frozenset(
            {
                Button.A,
                Button.B,
                Button.X,
                Button.Y,
                Button.R,
                Button.ZR,
                Button.PLUS,
                Button.RS,
                Button.HOME,
                Button.SL,
                Button.SR,
            }
        ),
        dpad=False,
        left_stick=False,
        right_stick=True,
        imu=True,
    )

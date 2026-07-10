from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from tests.hardware.swbt_realdevice_support import (
    SwbtEvidenceResult,
    SwbtEvidenceWriter,
    SwbtRealDeviceEnvironmentMissing,
    SwbtRealDeviceOptions,
    load_swbt_realdevice_options,
)


def test_swbt_realdevice_options_from_environment(tmp_path: Path) -> None:
    env = {
        "NYX_REALDEVICE": "1",
        "NYX_SWBT": "1",
        "NYX_SWBT_ADAPTER": "usb:0",
        "NYX_SWBT_CONTROLLER_TYPE": "joy-con-l",
        "NYX_SWBT_KEY_STORE": str(tmp_path / "joy-con-l-test-bond.json"),
        "NYX_SWBT_TIMEOUT": "7.5",
        "NYX_SWBT_EVIDENCE_DIR": str(tmp_path / "evidence"),
        "NYX_SWBT_OPERATOR_CONFIRMATION": "1",
        "NYX_SWBT_SHORT_PRESS_MS": "16, 33,50",
    }

    options = load_swbt_realdevice_options(env, now=datetime(2026, 7, 10, 1, 2, 3))

    assert options.adapter == "usb:0"
    assert options.controller_type == "joy-con-l"
    assert options.key_store_path == tmp_path / "joy-con-l-test-bond.json"
    assert options.evidence_dir == tmp_path / "evidence"
    assert options.timeout_sec == 7.5
    assert options.operator_confirmation is True
    assert options.short_press_ms == (16, 33, 50)


def test_swbt_realdevice_options_default_paths_are_controller_specific() -> None:
    env = {
        "NYX_REALDEVICE": "1",
        "NYX_SWBT": "1",
        "NYX_SWBT_ADAPTER": "usb:1",
        "NYX_SWBT_CONTROLLER_TYPE": "joy-con-r",
    }

    options = load_swbt_realdevice_options(env, now=datetime(2026, 7, 10, 1, 2, 3))

    assert options.key_store_path == Path(".nyxpy/swbt/joy-con-r-test-bond.json")
    assert options.evidence_dir == Path("tmp/hardware/swbt/20260710T010203")
    assert options.timeout_sec == 30.0
    assert options.operator_confirmation is False
    assert options.short_press_ms == (16, 33, 50)


def test_swbt_realdevice_options_require_gate_flags() -> None:
    with pytest.raises(SwbtRealDeviceEnvironmentMissing, match="NYX_REALDEVICE"):
        load_swbt_realdevice_options({})

    with pytest.raises(SwbtRealDeviceEnvironmentMissing, match="NYX_SWBT"):
        load_swbt_realdevice_options({"NYX_REALDEVICE": "1"})

    with pytest.raises(SwbtRealDeviceEnvironmentMissing, match="NYX_SWBT_ADAPTER"):
        load_swbt_realdevice_options({"NYX_REALDEVICE": "1", "NYX_SWBT": "1"})


def test_swbt_evidence_writer_redacts_absolute_paths(tmp_path: Path) -> None:
    key_store = tmp_path / "private" / "pro-controller-test-bond.json"
    options = SwbtRealDeviceOptions(
        adapter="usb:0",
        controller_type="pro-controller",
        key_store_path=key_store,
        evidence_dir=tmp_path / "evidence",
    )
    writer = SwbtEvidenceWriter(options.evidence_dir)

    writer.write_summary(
        options,
        [
            SwbtEvidenceResult(
                test_name="test_swbt_pair_realdevice",
                status="pass",
                details={"key_store": str(key_store.name)},
            )
        ],
    )

    summary = writer.summary_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in summary
    assert ".../pro-controller-test-bond.json" in summary


def test_swbt_operator_confirmation_records_result(tmp_path: Path) -> None:
    writer = SwbtEvidenceWriter(tmp_path / "evidence")

    writer.record_operator_confirmation(
        test_name="test_swbt_button_dpad_manual_realdevice",
        result="pass",
        details={"button": "A"},
    )

    lines = writer.operator_confirmation_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload == {
        "details": {"button": "A"},
        "result": "pass",
        "test_name": "test_swbt_button_dpad_manual_realdevice",
    }

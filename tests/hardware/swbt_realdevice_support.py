from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True, slots=True)
class SwbtRealDeviceOptions:
    adapter: str
    controller_type: str
    key_store_path: Path
    evidence_dir: Path
    timeout_sec: float = 30.0
    operator_confirmation: bool = False
    operator_result: str | None = None
    operator_results: Mapping[str, str] = field(default_factory=dict)
    short_press_ms: tuple[int, ...] = (16, 33, 50)


@dataclass(frozen=True, slots=True)
class SwbtEvidenceResult:
    test_name: str
    status: str
    details: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SwbtOperatorResult:
    status: str
    source: str


class SwbtRealDeviceEnvironmentMissing(RuntimeError):
    pass


def load_swbt_realdevice_options(
    env: Mapping[str, str] | None = None,
    *,
    now: datetime | None = None,
) -> SwbtRealDeviceOptions:
    values = os.environ if env is None else env
    _require_enabled(values, "NYX_REALDEVICE")
    _require_enabled(values, "NYX_SWBT")
    adapter = values.get("NYX_SWBT_ADAPTER", "").strip()
    if not adapter:
        raise SwbtRealDeviceEnvironmentMissing(
            "NYX_SWBT_ADAPTER is required for swbt realdevice tests"
        )

    controller_type = values.get("NYX_SWBT_CONTROLLER_TYPE", "pro-controller").strip()
    key_store_path = Path(
        values.get(
            "NYX_SWBT_KEY_STORE",
            f".nyxpy/swbt/{controller_type}-test-bond.json",
        )
    )
    timestamp = (now or datetime.now()).strftime("%Y%m%dT%H%M%S")
    evidence_dir = Path(values.get("NYX_SWBT_EVIDENCE_DIR", f"tmp/hardware/swbt/{timestamp}"))
    timeout_sec = _parse_positive_float(values.get("NYX_SWBT_TIMEOUT", "30.0"))
    short_press_ms = _parse_short_press_ms(values.get("NYX_SWBT_SHORT_PRESS_MS", "16,33,50"))
    operator_result = _parse_optional_operator_result(
        values.get("NYX_SWBT_OPERATOR_RESULT"),
        name="NYX_SWBT_OPERATOR_RESULT",
    )
    operator_results = _parse_operator_results(values.get("NYX_SWBT_OPERATOR_RESULTS"))

    return SwbtRealDeviceOptions(
        adapter=adapter,
        controller_type=controller_type,
        key_store_path=key_store_path,
        evidence_dir=evidence_dir,
        timeout_sec=timeout_sec,
        operator_confirmation=values.get("NYX_SWBT_OPERATOR_CONFIRMATION") == "1",
        operator_result=operator_result,
        operator_results=operator_results,
        short_press_ms=short_press_ms,
    )


def resolve_operator_result(
    options: SwbtRealDeviceOptions,
    test_name: str,
    *,
    prompt: str | None = None,
    input_func: Callable[[str], str] = input,
) -> SwbtOperatorResult:
    """実機観察結果を per-test env、default env、stdin の順で取得する。"""
    if test_name in options.operator_results:
        return SwbtOperatorResult(
            status=options.operator_results[test_name],
            source="NYX_SWBT_OPERATOR_RESULTS",
        )
    if options.operator_result is not None:
        return SwbtOperatorResult(
            status=options.operator_result,
            source="NYX_SWBT_OPERATOR_RESULT",
        )

    question = prompt or f"[{test_name}] observation result (pass/fail/skip): "
    try:
        value = input_func(question)
    except (EOFError, OSError) as exc:
        raise SwbtRealDeviceEnvironmentMissing(
            "operator result input is unavailable; run pytest -s or set "
            "NYX_SWBT_OPERATOR_RESULT / NYX_SWBT_OPERATOR_RESULTS"
        ) from exc
    return SwbtOperatorResult(
        status=_parse_operator_result(value, name="operator input"),
        source="stdin",
    )


class SwbtEvidenceWriter:
    def __init__(self, evidence_dir: Path) -> None:
        self.evidence_dir = evidence_dir

    @property
    def run_metadata_path(self) -> Path:
        return self.evidence_dir / "run-metadata.json"

    @property
    def trace_path(self) -> Path:
        return self.evidence_dir / "swbt-trace.jsonl"

    @property
    def operator_confirmation_path(self) -> Path:
        return self.evidence_dir / "operator-confirmation.jsonl"

    @property
    def summary_path(self) -> Path:
        return self.evidence_dir / "summary.md"

    def prepare(self) -> None:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def open_trace(self) -> TextIO:
        self.prepare()
        return self.trace_path.open("a", encoding="utf-8")

    def write_run_metadata(
        self,
        options: SwbtRealDeviceOptions,
        *,
        command: Sequence[str] = (),
        git_commit: str | None = None,
        swbt_version: str | None = None,
    ) -> None:
        self.prepare()
        payload = {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "nyx_commit": git_commit,
            "swbt_python_version": swbt_version,
            "controller_type": options.controller_type,
            "adapter": options.adapter,
            "key_store_path": _display_path(options.key_store_path),
            "timeout_sec": options.timeout_sec,
            "short_press_ms": list(options.short_press_ms),
            "operator_confirmation": options.operator_confirmation,
            "operator_result": options.operator_result,
            "operator_results": dict(options.operator_results),
            "test_command": list(command),
        }
        self.run_metadata_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def record_operator_confirmation(
        self,
        *,
        test_name: str,
        result: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        if result not in {"pass", "fail", "skip"}:
            raise ValueError(f"unsupported operator confirmation result: {result}")
        self._append_jsonl(
            self.operator_confirmation_path,
            {
                "test_name": test_name,
                "result": result,
                "details": dict(details or {}),
            },
        )

    def write_summary(
        self,
        options: SwbtRealDeviceOptions,
        results: Sequence[SwbtEvidenceResult],
    ) -> None:
        self.prepare()
        lines = [
            "# swbt realdevice verification summary",
            "",
            f"- controller_type: `{options.controller_type}`",
            f"- adapter: `{options.adapter}`",
            f"- key_store_path: `{_display_path(options.key_store_path)}`",
            f"- trace: `{self.trace_path.name}`",
            f"- operator_confirmation: `{self.operator_confirmation_path.name}`",
            "",
            "| test | status | details |",
            "|------|--------|---------|",
        ]
        for result in results:
            details = json.dumps(dict(result.details), ensure_ascii=False, sort_keys=True)
            lines.append(f"| `{result.test_name}` | `{result.status}` | `{details}` |")
        self.summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_jsonl(self, path: Path, payload: Mapping[str, object]) -> None:
        self.prepare()
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def current_git_commit(cwd: Path = Path.cwd()) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            check=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def installed_swbt_python_version() -> str | None:
    try:
        return version("swbt-python")
    except PackageNotFoundError:
        return None


def _require_enabled(env: Mapping[str, str], name: str) -> None:
    if env.get(name) != "1":
        raise SwbtRealDeviceEnvironmentMissing(f"{name}=1 is required for swbt realdevice tests")


def _parse_positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError("timeout must be positive")
    return parsed


def _parse_short_press_ms(value: str) -> tuple[int, ...]:
    parts = tuple(part.strip() for part in value.split(",") if part.strip())
    if not parts:
        raise ValueError("NYX_SWBT_SHORT_PRESS_MS must not be empty")
    parsed = tuple(int(part) for part in parts)
    if any(duration <= 0 for duration in parsed):
        raise ValueError("short press duration must be positive")
    return parsed


def _parse_optional_operator_result(value: str | None, *, name: str) -> str | None:
    if value is None:
        return None
    return _parse_operator_result(value, name=name)


def _parse_operator_results(value: str | None) -> dict[str, str]:
    if value is None:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("NYX_SWBT_OPERATOR_RESULTS must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("NYX_SWBT_OPERATOR_RESULTS must be a JSON object")

    results: dict[str, str] = {}
    for test_name, result in payload.items():
        if not isinstance(result, str):
            raise ValueError("NYX_SWBT_OPERATOR_RESULTS values must be pass, fail, or skip")
        results[str(test_name)] = _parse_operator_result(
            result,
            name=f"NYX_SWBT_OPERATOR_RESULTS[{test_name!r}]",
        )
    return results


def _parse_operator_result(value: str, *, name: str) -> str:
    result = value.strip().lower()
    if result not in {"pass", "fail", "skip"}:
        raise ValueError(f"{name} must be pass, fail, or skip: {value!r}")
    return result


def _display_path(path: Path) -> str:
    if path.is_absolute():
        return f".../{path.name}"
    return path.as_posix()

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from nyxpy.cli import run_cli
from nyxpy.framework.core.runtime.result import RunResult, RunStatus


class Logger:
    def __init__(self) -> None:
        self.user_events = []

    def bind_context(self, context):
        return self

    def user(self, level, message, *, component, event, code=None, extra=None):
        self.user_events.append((level, message, component, event))

    def technical(self, level, message, *, component, event="log.message", extra=None, exc=None):
        pass


def run_result(status: RunStatus = RunStatus.SUCCESS) -> RunResult:
    now = datetime.now()
    return RunResult(
        run_id="run-1",
        macro_id="sample",
        macro_name="Sample",
        status=status,
        started_at=now,
        finished_at=now,
    )


def test_cli_uses_runtime_and_run_result() -> None:
    logger = Logger()
    builder = MagicMock(run=MagicMock(return_value=run_result(RunStatus.CANCELLED)))

    result = run_cli.execute_macro(builder, "sample", {"count": 1}, logger)

    assert result.status is RunStatus.CANCELLED
    request = builder.run.call_args.args[0]
    assert request.macro_id == "sample"
    assert request.entrypoint == "cli"
    assert request.exec_args == {"count": 1}
    assert logger.user_events == [
        ("WARNING", "Macro execution was interrupted", "CLI", "macro.cancelled")
    ]


def test_create_runtime_builder_docstring_describes_runtime_builder() -> None:
    assert "Runtime builder" in (run_cli.create_runtime_builder.__doc__ or "")
    assert "Command" not in (run_cli.create_runtime_builder.__doc__ or "")


def test_cli_notification_settings_source_is_secrets_store(monkeypatch, tmp_path) -> None:
    sentinel_snapshot = object()
    captured = {}
    settings_store = MagicMock(snapshot=MagicMock(return_value={}))
    secrets_store = MagicMock(snapshot=MagicMock(return_value=sentinel_snapshot))
    discovery = MagicMock()
    controller_factory = MagicMock()
    frame_factory = MagicMock()

    monkeypatch.setattr(
        "nyxpy.cli.run_cli.MacroRegistry", lambda project_root: MagicMock(reload=lambda: None)
    )

    def create_notification_handler(secrets_snapshot, *, logger):
        captured["secrets_snapshot"] = secrets_snapshot
        captured["logger"] = logger
        return "notification-port"

    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_notification_handler_from_settings",
        create_notification_handler,
    )
    device_builder = MagicMock()
    monkeypatch.setattr("nyxpy.cli.run_cli.create_device_runtime_builder", device_builder)
    logger = Logger()

    run_cli.create_runtime_builder(
        MagicMock(),
        logger=logger,
        resources_dir=tmp_path,
        settings_store=settings_store,
        secrets_store=secrets_store,
        device_discovery=discovery,
        controller_output_factory=controller_factory,
        frame_source_factory=frame_factory,
    )

    assert captured == {"secrets_snapshot": sentinel_snapshot, "logger": logger}
    assert device_builder.call_args.kwargs["notification_handler"] == "notification-port"
    assert device_builder.call_args.kwargs["settings"] == {}
    assert "serial_device" not in device_builder.call_args.kwargs
    assert "capture_device" not in device_builder.call_args.kwargs


def test_cli_does_not_import_removed_runtime_apis() -> None:
    cli_dir = Path(__file__).resolve().parents[2] / "src" / "nyxpy" / "cli"
    forbidden_names = {
        "MacroExecutor",
        "DefaultCommand",
        "LogManager",
        "log_manager",
        "create_legacy_runtime_builder",
        "SecretsSettings",
        "singletons",
        "SerialManager",
        "CaptureManager",
        "serial_manager",
        "capture_manager",
    }

    for source_path in cli_dir.glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.update(alias.name.split("."))
                    if alias.asname:
                        imported_names.add(alias.asname)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.update(node.module.split("."))
                for alias in node.names:
                    imported_names.add(alias.name)
                    if alias.asname:
                        imported_names.add(alias.asname)

        assert imported_names.isdisjoint(forbidden_names), source_path

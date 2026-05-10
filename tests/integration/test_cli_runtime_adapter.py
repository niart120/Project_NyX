from __future__ import annotations

from datetime import datetime
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
    sentinel_secrets = object()
    captured = {}

    monkeypatch.setattr("nyxpy.cli.run_cli.SecretsSettings", lambda: sentinel_secrets)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.MacroRegistry", lambda project_root: MagicMock(reload=lambda: None)
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.serial_manager",
        MagicMock(),
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.capture_manager",
        MagicMock(),
    )

    def create_notification_handler(settings, *, logger):
        captured["settings"] = settings
        captured["logger"] = logger
        return "notification-port"

    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_notification_handler_from_settings",
        create_notification_handler,
    )
    legacy_builder = MagicMock()
    monkeypatch.setattr("nyxpy.cli.run_cli.create_legacy_runtime_builder", legacy_builder)
    logger = Logger()

    run_cli.create_runtime_builder(MagicMock(), logger=logger, resources_dir=tmp_path)

    assert captured == {"settings": sentinel_secrets, "logger": logger}
    assert legacy_builder.call_args.kwargs["notification_handler"] == "notification-port"
    assert "serial_device" not in legacy_builder.call_args.kwargs
    assert "capture_device" not in legacy_builder.call_args.kwargs

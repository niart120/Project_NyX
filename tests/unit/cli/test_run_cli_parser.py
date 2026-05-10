from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from nyxpy.cli import run_cli
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.result import RunResult, RunStatus


class Logger:
    def bind_context(self, context):
        return self

    def user(self, level, message, *, component, event, code=None, extra=None):
        pass

    def technical(self, level, message, *, component, event="log.message", extra=None, exc=None):
        pass


@dataclass
class Logging:
    logger: Logger

    def close(self) -> None:
        pass


class RecordingBuilder:
    def __init__(self) -> None:
        self.request: RuntimeBuildRequest | None = None

    def run(self, request: RuntimeBuildRequest) -> RunResult:
        self.request = request
        now = datetime.now()
        return RunResult(
            run_id="run-1",
            macro_id=request.macro_id,
            macro_name=request.macro_id,
            status=RunStatus.SUCCESS,
            started_at=now,
            finished_at=now,
        )


def test_cli_parser_keeps_existing_options() -> None:
    parser = run_cli.build_parser()

    args = parser.parse_args(
        [
            "sample",
            "--serial",
            "serial-1",
            "--capture",
            "capture-1",
            "--protocol",
            "ch552",
            "--baud",
            "115200",
            "--silence",
            "--verbose",
            "--define",
            "count=3",
            "--define",
            'name="nyx"',
        ]
    )

    assert args.macro_name == "sample"
    assert args.serial == "serial-1"
    assert args.capture == "capture-1"
    assert args.protocol == "ch552"
    assert args.baud == 115200
    assert args.silence is True
    assert args.verbose is True
    assert args.define == ["count=3", 'name="nyx"']


def test_cli_does_not_accept_notification_secret_args() -> None:
    parser = run_cli.build_parser()

    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }

    assert "--discord-webhook-url" not in option_strings
    assert "--bluesky-password" not in option_strings


def test_cli_define_args_are_passed_to_request(monkeypatch) -> None:
    builder = RecordingBuilder()

    monkeypatch.setattr(run_cli, "configure_logging", lambda *, silence, verbose: Logging(Logger()))
    monkeypatch.setattr(run_cli, "create_protocol", lambda protocol_name: object())
    monkeypatch.setattr(run_cli.ProtocolFactory, "resolve_baudrate", lambda protocol, baud: baud)
    monkeypatch.setattr(
        run_cli,
        "create_runtime_builder",
        lambda **kwargs: builder,
    )
    monkeypatch.setattr(run_cli, "capture_manager", _Manager())
    monkeypatch.setattr(run_cli, "serial_manager", _Manager())

    args = run_cli.build_parser().parse_args(
        [
            "sample",
            "--serial",
            "serial-1",
            "--capture",
            "capture-1",
            "--define",
            "count=3",
            "--define",
            'name="nyx"',
        ]
    )

    exit_code = run_cli.cli_main(args)

    assert exit_code == 0
    assert builder.request is not None
    assert builder.request.macro_id == "sample"
    assert builder.request.entrypoint == "cli"
    assert builder.request.exec_args == {"count": 3, "name": "nyx"}


def test_cli_define_defaults_to_empty_request_args(monkeypatch) -> None:
    builder = RecordingBuilder()

    monkeypatch.setattr(run_cli, "configure_logging", lambda *, silence, verbose: Logging(Logger()))
    monkeypatch.setattr(run_cli, "create_protocol", lambda protocol_name: object())
    monkeypatch.setattr(run_cli.ProtocolFactory, "resolve_baudrate", lambda protocol, baud: baud)
    monkeypatch.setattr(run_cli, "create_runtime_builder", lambda **kwargs: builder)
    monkeypatch.setattr(run_cli, "capture_manager", _Manager())
    monkeypatch.setattr(run_cli, "serial_manager", _Manager())

    args = run_cli.build_parser().parse_args(
        ["sample", "--serial", "serial-1", "--capture", "capture-1"]
    )

    exit_code = run_cli.cli_main(args)

    assert exit_code == 0
    assert builder.request is not None
    assert builder.request.exec_args == {}


class _Manager:
    def set_logger(self, logger: Any) -> None:
        pass

    def release_active(self) -> None:
        pass

    def close_active(self) -> None:
        pass

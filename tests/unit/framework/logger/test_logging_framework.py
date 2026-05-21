from __future__ import annotations

import importlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

from nyxpy.framework.core.logger import (
    DefaultLogger,
    JsonlLogBackend,
    LogEvent,
    LogLevel,
    LogSanitizer,
    LogSinkDispatcher,
    RunLogContext,
    TechnicalLog,
    TestLogSink,
    UserEvent,
    create_default_logging,
)
from nyxpy.framework.core.logger.backend import NullLogBackend
from nyxpy.framework.core.logger.ports import LogSink
from nyxpy.framework.core.logger.sinks import RunJsonlFileSink
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class FailingSink(LogSink):
    def __init__(self, message: str = "sink failed") -> None:
        self.message = message

    def emit_technical(self, event):
        raise RuntimeError(self.message)

    def emit_user(self, event):
        raise RuntimeError(self.message)


class FailingBackend(NullLogBackend):
    def emit_technical(self, event):
        raise RuntimeError("backend failed")


class NonJsonValue:
    def __repr__(self) -> str:
        """JSON 化できない値であることが分かる表現を返します。"""
        return "<non-json-value>"


def test_logger_import_has_no_backend_side_effect(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    importlib.import_module("nyxpy.framework.core.logger")

    assert not (tmp_path / "logs").exists()


def test_legacy_log_manager_removed() -> None:
    assert importlib.util.find_spec("nyxpy.framework.core.logger.log_manager") is None


def test_log_manager_call_sites_removed() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    offenders = []
    for path in (repo_root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "log_manager" in text or "LogManager" in text:
            offenders.append(path.relative_to(repo_root))

    assert offenders == []


def test_logger_port_binds_run_context() -> None:
    sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer).bind_context(
        RunLogContext(run_id="run-1", macro_id="sample")
    )

    logger.technical("INFO", "message", component="test", event="macro.started")

    assert sink.technical_logs[0].event.run_id == "run-1"
    assert sink.technical_logs[0].event.macro_id == "sample"


def test_technical_log_includes_framework_error_context() -> None:
    sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)
    exc = ConfigurationError(
        "settings missing",
        code="NYX_SETTINGS_NOT_FOUND",
        component="MacroSettingsResolver",
        details={
            "macro_id": "resource_settings",
            "resolved_path": r"E:\repo\resources\resource_settings\settings.toml",
        },
    )

    logger.technical(
        "ERROR",
        "Macro start failed.",
        component="MainWindow",
        event="runtime.start_failed",
        exc=exc,
    )

    extra = sink.technical_logs[0].event.extra
    assert extra["error_kind"] == "configuration"
    assert extra["error_code"] == "NYX_SETTINGS_NOT_FOUND"
    assert extra["error_component"] == "MacroSettingsResolver"
    assert extra["recoverable"] is False
    assert extra["error_details"] == exc.details


def test_jsonl_log_backend_writes_technical_log(tmp_path: Path) -> None:
    backend = JsonlLogBackend(tmp_path / "framework.jsonl")
    value = NonJsonValue()
    event = LogEvent(
        timestamp=datetime.now(),
        level=LogLevel.INFO,
        component="test",
        event="macro.started",
        message="started",
        run_id="run-1",
        macro_id="sample",
        extra={"value": value},
    )

    backend.emit_technical(TechnicalLog(event))
    payload = json.loads((tmp_path / "framework.jsonl").read_text(encoding="utf-8"))

    assert payload["level"] == "INFO"
    assert payload["component"] == "test"
    assert payload["event"] == "macro.started"
    assert payload["run_id"] == "run-1"
    assert payload["macro_id"] == "sample"
    assert payload["extra"]["value"] == repr(value)


def test_default_logging_uses_framework_jsonl_backend(tmp_path: Path) -> None:
    logging = create_default_logging(base_dir=tmp_path, console_enabled=False)

    assert isinstance(logging.backend, JsonlLogBackend)
    assert "framework_jsonl" not in logging.sink_ids

    logger = logging.logger.bind_context(RunLogContext(run_id="run-1", macro_id="sample"))
    logger.technical("INFO", "message", component="test", event="macro.started")
    logging.close()
    payload = json.loads((tmp_path / "framework.jsonl").read_text(encoding="utf-8"))

    assert payload["event"] == "macro.started"
    assert payload["run_id"] == "run-1"
    assert payload["macro_id"] == "sample"


def test_default_logging_writes_user_events_to_user_sinks_only(tmp_path: Path) -> None:
    logging = create_default_logging(base_dir=tmp_path, console_enabled=False)
    logger = logging.logger.bind_context(RunLogContext(run_id="run-1", macro_id="sample"))

    logger.user("INFO", "visible", component="test", event="macro.message")
    logging.close()
    run_payload = json.loads(
        next((tmp_path / "runs").glob("*/*.jsonl")).read_text(encoding="utf-8")
    )

    assert not (tmp_path / "framework.jsonl").exists()
    assert "visible" in (tmp_path / "nyxpy.log").read_text(encoding="utf-8")
    assert run_payload["kind"] == "user"
    assert run_payload["event"] == "macro.message"


def test_jsonl_backend_keeps_bounded_rotated_files(tmp_path: Path) -> None:
    backend = JsonlLogBackend(
        tmp_path / "framework.jsonl",
        max_bytes=1,
        backup_count=2,
    )

    for index in range(4):
        backend.emit_technical(
            TechnicalLog(
                LogEvent(
                    timestamp=datetime.now(),
                    level=LogLevel.INFO,
                    component="test",
                    event="rotation.test",
                    message=f"message {index}",
                )
            )
        )

    assert (tmp_path / "framework.jsonl").exists()
    assert (tmp_path / "framework.jsonl.1").exists()
    assert (tmp_path / "framework.jsonl.2").exists()
    assert not (tmp_path / "framework.jsonl.3").exists()


def test_run_jsonl_sink_rotates_per_run_file(tmp_path: Path) -> None:
    sink = RunJsonlFileSink(tmp_path, max_bytes=1, backup_count=1)

    for index in range(2):
        sink.emit_user(
            UserEvent(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                component="test",
                event="macro.message",
                message=f"message {index}",
                run_id="run-1",
                macro_id="sample",
            )
        )

    assert next(tmp_path.glob("*/run-1.jsonl")).exists()
    assert next(tmp_path.glob("*/run-1.jsonl.1")).exists()


def test_backend_exception_is_logged_and_dispatch_continues() -> None:
    sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer, FailingBackend())

    logger.technical("INFO", "message", component="test", event="macro.started")

    assert [log.event.event for log in sink.technical_logs] == [
        "backend.emit_failed",
        "macro.started",
    ]


def test_user_event_does_not_include_traceback_or_secret() -> None:
    sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)

    logger.user(
        "INFO",
        "visible",
        component="test",
        event="macro.message",
        extra={"password": "plain", "safe": "value"},
    )

    event = sink.user_events[0]
    assert event.extra == {"safe": "value"}
    assert not hasattr(event, "traceback")


def test_technical_log_masks_secret_values() -> None:
    sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)

    logger.technical(
        "ERROR",
        "failed",
        component="test",
        event="configuration.invalid",
        extra={"api_token": "plain", "nested": {"password": "plain"}},
    )

    extra = sink.technical_logs[0].event.extra
    assert extra["api_token"] == "***"
    assert extra["nested"] == {"password": "***"}


def test_sink_exception_is_logged_and_ignored() -> None:
    good_sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(FailingSink(), level="DEBUG")
    dispatcher.add_sink(good_sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)

    logger.user("INFO", "message", component="test", event="macro.message")

    assert good_sink.user_events[0].event == "macro.message"
    assert any(log.event.event == "sink.emit_failed" for log in good_sink.technical_logs)


def test_fallback_stderr_masks_secret_values(capsys) -> None:
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(FailingSink("password=plain-secret"), level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)

    logger.technical("ERROR", "failed", component="test", event="macro.failed")

    captured = capsys.readouterr()
    assert "plain-secret" not in captured.err
    assert "password=***" in captured.err


def test_sink_snapshot_allows_remove_during_emit() -> None:
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    good_sink = TestLogSink()

    class RemovingSink(LogSink):
        def emit_technical(self, event):
            dispatcher.remove_sink(good_sink_id)

    dispatcher.add_sink(RemovingSink(), level="DEBUG")
    good_sink_id = dispatcher.add_sink(good_sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)

    logger.technical("INFO", "message", component="test", event="macro.started")

    assert good_sink.technical_logs[0].event.event == "macro.started"


def test_test_log_sink_records_user_and_technical_events() -> None:
    sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)

    logger.user("INFO", "hello", component="test", event="macro.message")

    assert sink.user_events[0].message == "hello"
    assert sink.technical_logs == []


def test_log_serialization_falls_back_to_repr() -> None:
    sink = TestLogSink()
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)
    value = object()

    logger.technical(
        "INFO", "message", component="test", event="macro.message", extra={"value": value}
    )

    assert sink.technical_logs[0].event.extra["value"] == repr(value)

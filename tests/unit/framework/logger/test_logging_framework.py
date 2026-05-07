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
    create_default_logging,
)
from nyxpy.framework.core.logger.backend import NullLogBackend
from nyxpy.framework.core.logger.ports import LogSink


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
    assert sink.technical_logs[0].event.event == "macro.message"


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

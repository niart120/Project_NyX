from pathlib import Path

from nyxpy.framework.core.hardware.swbt.diagnostics import (
    LoggerDiagnosticsWriter,
    TeeDiagnosticsWriter,
    open_diagnostics_trace,
)
from tests.support.fakes import FakeLoggerPort


def test_diagnostics_writer_logs_to_logger_port() -> None:
    logger = FakeLoggerPort()
    writer = LoggerDiagnosticsWriter(logger)

    assert writer.write("one\n\ntwo\n") == len("one\n\ntwo\n")
    writer.flush()

    assert [log.event.message for log in logger.technical_logs] == ["one", "two"]
    assert [log.event.event for log in logger.technical_logs] == [
        "swbt.diagnostics",
        "swbt.diagnostics",
    ]


def test_diagnostics_writer_can_tee_to_jsonl(tmp_path: Path) -> None:
    logger = FakeLoggerPort()
    trace_path = tmp_path / "hardware" / "swbt" / "trace.jsonl"

    with open_diagnostics_trace(trace_path) as trace:
        writer = TeeDiagnosticsWriter((LoggerDiagnosticsWriter(logger), trace))
        writer.write('{"event":"open"}\n')
        writer.flush()

    assert trace_path.read_text(encoding="utf-8") == '{"event":"open"}\n'
    assert logger.technical_logs[-1].event.message == '{"event":"open"}'

from __future__ import annotations

import time

from nyxpy.framework.core.logger import DefaultLogger, LogSanitizer, LogSinkDispatcher, TestLogSink


def test_log_handler_dispatch_thread_safety() -> None:
    sanitizer = LogSanitizer()
    dispatcher = LogSinkDispatcher(sanitizer)
    sinks = [TestLogSink() for _ in range(3)]
    for sink in sinks:
        dispatcher.add_sink(sink, level="DEBUG")
    logger = DefaultLogger(dispatcher, sanitizer)

    started = time.perf_counter()
    for index in range(100):
        logger.technical(
            "INFO",
            f"message {index}",
            component="perf",
            event="macro.message",
        )
    elapsed = time.perf_counter() - started

    assert elapsed / 100 < 0.005
    assert all(len(sink.technical_logs) == 100 for sink in sinks)

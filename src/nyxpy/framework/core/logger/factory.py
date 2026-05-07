from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.logger.backend import JsonlLogBackend
from nyxpy.framework.core.logger.default_logger import DefaultLogger
from nyxpy.framework.core.logger.dispatcher import LogSinkDispatcher
from nyxpy.framework.core.logger.ports import LogBackend, LogSink
from nyxpy.framework.core.logger.sanitizer import LogSanitizer
from nyxpy.framework.core.logger.sinks import (
    ConsoleLogSink,
    RunJsonlFileSink,
    TextFileLogSink,
)


@dataclass
class LoggingComponents:
    logger: DefaultLogger
    dispatcher: LogSinkDispatcher
    sanitizer: LogSanitizer
    backend: LogBackend
    sink_ids: dict[str, str]

    def set_all_levels(self, level: str) -> None:
        _set_backend_level(self.backend, level)
        for sink_id in self.sink_ids.values():
            self.dispatcher.set_level(sink_id, level)

    def set_console_level(self, level: str) -> None:
        sink_id = self.sink_ids.get("console")
        if sink_id is not None:
            self.dispatcher.set_level(sink_id, level)

    def set_file_level(self, level: str) -> None:
        _set_backend_level(self.backend, level)
        for name in ("human_file", "run_jsonl"):
            sink_id = self.sink_ids.get(name)
            if sink_id is not None:
                self.dispatcher.set_level(sink_id, level)

    def add_sink(self, name: str, sink: LogSink, *, level: str = "INFO") -> str:
        sink_id = self.dispatcher.add_sink(sink, level=level)
        self.sink_ids[name] = sink_id
        return sink_id

    def close(self) -> None:
        self.backend.flush()
        self.backend.close()
        self.dispatcher.flush()
        self.dispatcher.close()


def create_default_logging(
    *,
    base_dir: Path = Path("logs"),
    console_enabled: bool = True,
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    mask_secret_keys: list[str] | None = None,
) -> LoggingComponents:
    sanitizer = LogSanitizer(mask_secret_keys)
    dispatcher = LogSinkDispatcher(sanitizer)
    backend = JsonlLogBackend(Path(base_dir) / "framework.jsonl", level=file_level)
    logger = DefaultLogger(dispatcher, sanitizer, backend)
    sink_ids: dict[str, str] = {}

    if console_enabled:
        sink_ids["console"] = dispatcher.add_sink(ConsoleLogSink(), level=console_level)
    sink_ids["human_file"] = dispatcher.add_sink(
        TextFileLogSink(Path(base_dir) / "nyxpy.log"),
        level=file_level,
    )
    sink_ids["run_jsonl"] = dispatcher.add_sink(
        RunJsonlFileSink(Path(base_dir) / "runs"),
        level=file_level,
    )
    return LoggingComponents(logger, dispatcher, sanitizer, backend, sink_ids)


def _set_backend_level(backend: LogBackend, level: str) -> None:
    set_level = getattr(backend, "set_level", None)
    if set_level is not None:
        set_level(level)

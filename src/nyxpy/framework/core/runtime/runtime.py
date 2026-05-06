from __future__ import annotations

import traceback
from dataclasses import replace
from datetime import datetime
from threading import Event, Thread

from nyxpy.framework.core.io.ports import FrameNotReadyError
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.macro.exceptions import (
    ErrorInfo,
    ErrorKind,
    FrameworkError,
    MacroStopException,
)
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.context import ExecutionContext, RunContext
from nyxpy.framework.core.runtime.handle import RunHandle, ThreadRunHandle
from nyxpy.framework.core.runtime.result import CleanupWarning, RunResult, RunStatus
from nyxpy.framework.core.runtime.runner import MacroRunner


class MacroRuntime:
    def __init__(
        self,
        registry: MacroRegistry,
        runner: MacroRunner | None = None,
    ) -> None:
        self.registry = registry
        self.runner = runner or MacroRunner()

    def run(self, context: ExecutionContext) -> RunResult:
        started_at = context.run_log_context.started_at or datetime.now()
        result: RunResult | None = None
        cleanup_warnings: tuple[CleanupWarning, ...] = ()
        try:
            context.logger.user(
                "INFO",
                "macro starting",
                component="MacroRuntime",
                event="macro.started",
            )
            context.frame_source.initialize()
            if not context.frame_source.await_ready(context.options.frame_ready_timeout_sec):
                raise FrameNotReadyError()
            definition = self.registry.resolve(context.macro_id)
            macro = definition.factory.create()
            cmd = DefaultCommand(context=context)
            run_context = RunContext(
                run_id=context.run_id,
                macro_id=context.macro_id,
                macro_name=context.macro_name,
                started_at=started_at,
                cancellation_token=context.cancellation_token,
                logger=context.logger,
            )
            result = self.runner.run(macro, cmd, context.exec_args, run_context)
        except MacroStopException as exc:
            result = self._result_from_exception(context, started_at, exc, RunStatus.CANCELLED)
        except FrameworkError as exc:
            result = self._result_from_exception(context, started_at, exc, RunStatus.FAILED)
        except Exception as exc:
            result = self._result_from_exception(context, started_at, exc, RunStatus.FAILED)
        finally:
            cleanup_warnings = self._close_ports(context)

        if cleanup_warnings:
            return replace(
                result,
                cleanup_warnings=(*result.cleanup_warnings, *cleanup_warnings),
            )
        return result

    def start(self, context: ExecutionContext) -> RunHandle:
        done_event = Event()
        result: RunResult | None = None

        def worker() -> None:
            nonlocal result
            try:
                result = self.run(context)
            finally:
                done_event.set()

        thread = Thread(target=worker, name=f"nyx-runtime-{context.run_id}", daemon=True)
        handle = ThreadRunHandle(
            run_id=context.run_id,
            cancellation_token=context.cancellation_token,
            thread=thread,
            done_event=done_event,
            result_getter=lambda: result,
        )
        thread.start()
        return handle

    def shutdown(self) -> None:
        pass

    def _result_from_exception(
        self,
        context: ExecutionContext,
        started_at: datetime,
        exc: Exception,
        status: RunStatus,
    ) -> RunResult:
        error = self._error_info(exc)
        return RunResult(
            run_id=context.run_id,
            macro_id=context.macro_id,
            macro_name=context.macro_name,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(),
            error=error,
        )

    def _error_info(self, exc: Exception) -> ErrorInfo:
        if isinstance(exc, FrameworkError):
            return ErrorInfo(
                kind=exc.kind,
                code=exc.code,
                message=exc.message,
                component=exc.component,
                exception_type=type(exc).__name__,
                recoverable=exc.recoverable,
                details=dict(exc.details),
                traceback=traceback.format_exc(),
            )
        return ErrorInfo(
            kind=ErrorKind.INTERNAL,
            code="NYX_RUNTIME_FAILED",
            message=str(exc),
            component="MacroRuntime",
            exception_type=type(exc).__name__,
            recoverable=False,
            details={},
            traceback=traceback.format_exc(),
        )

    def _close_ports(self, context: ExecutionContext) -> tuple[CleanupWarning, ...]:
        warnings: list[CleanupWarning] = []
        for port_name, port in (
            ("controller", context.controller),
            ("frame_source", context.frame_source),
            ("resources", context.resources),
            ("artifacts", context.artifacts),
        ):
            try:
                port.close()
            except Exception as exc:
                warnings.append(CleanupWarning(port_name, type(exc).__name__, str(exc)))
        return tuple(warnings)

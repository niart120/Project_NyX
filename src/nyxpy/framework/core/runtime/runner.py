from __future__ import annotations

import traceback
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from typing import Protocol, runtime_checkable

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.exceptions import (
    ErrorInfo,
    ErrorKind,
    FrameworkError,
    MacroStopException,
)
from nyxpy.framework.core.runtime.context import RunContext
from nyxpy.framework.core.runtime.result import RunResult, RunStatus

type RuntimeValue = str | int | float | bool | list[RuntimeValue] | dict[str, RuntimeValue] | None


@runtime_checkable
class SupportsFinalizeOutcome(Protocol):
    def finalize_with_outcome(self, cmd: Command, outcome: RunResult) -> None: ...


class MacroRunner:
    def run(
        self,
        macro: MacroBase,
        cmd: Command,
        exec_args: Mapping[str, RuntimeValue],
        run_context: RunContext,
    ) -> RunResult:
        started_at = run_context.started_at
        result: RunResult
        try:
            macro.initialize(cmd, dict(exec_args))
            macro.run(cmd)
        except MacroStopException as exc:
            result = self._result(
                run_context=run_context,
                status=RunStatus.CANCELLED,
                started_at=started_at,
                error=self._error_info(exc),
            )
        except FrameworkError as exc:
            result = self._result(
                run_context=run_context,
                status=RunStatus.FAILED,
                started_at=started_at,
                error=self._error_info(exc),
            )
        except Exception as exc:
            result = self._result(
                run_context=run_context,
                status=RunStatus.FAILED,
                started_at=started_at,
                error=self._macro_error_info(exc),
            )
        else:
            result = self._result(
                run_context=run_context,
                status=RunStatus.SUCCESS,
                started_at=started_at,
                error=None,
            )

        return self._finalize(macro, cmd, result, run_context)

    def _finalize(
        self,
        macro: MacroBase,
        cmd: Command,
        result: RunResult,
        run_context: RunContext,
    ) -> RunResult:
        try:
            if isinstance(macro, SupportsFinalizeOutcome):
                macro.finalize_with_outcome(cmd, result)
            else:
                macro.finalize(cmd)
        except Exception as exc:
            if result.ok:
                return self._result(
                    run_context=run_context,
                    status=RunStatus.FAILED,
                    started_at=result.started_at,
                    error=self._macro_error_info(exc, component="MacroRunner.finalize"),
                )
            if result.error is None:
                return result
            finalize_error = {
                "exception_type": type(exc).__name__,
                "message": str(exc),
            }
            details = {**result.error.details, "finalize_error": finalize_error}
            return replace(
                result,
                finished_at=datetime.now(),
                error=replace(result.error, details=details),
            )
        return replace(result, finished_at=datetime.now())

    def _result(
        self,
        *,
        run_context: RunContext,
        status: RunStatus,
        started_at: datetime,
        error: ErrorInfo | None,
    ) -> RunResult:
        return RunResult(
            run_id=run_context.run_id,
            macro_id=run_context.macro_id,
            macro_name=run_context.macro_name,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(),
            error=error,
        )

    def _error_info(self, exc: FrameworkError) -> ErrorInfo:
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

    def _macro_error_info(self, exc: Exception, *, component: str = "MacroRunner") -> ErrorInfo:
        return ErrorInfo(
            kind=ErrorKind.MACRO,
            code="NYX_MACRO_FAILED",
            message=str(exc),
            component=component,
            exception_type=type(exc).__name__,
            recoverable=False,
            details={},
            traceback=traceback.format_exc(),
        )

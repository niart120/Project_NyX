from __future__ import annotations

from datetime import datetime

import pytest

from nyxpy.cli.run_cli import CliPresenter
from nyxpy.framework.core.macro.exceptions import ErrorInfo, ErrorKind
from nyxpy.framework.core.runtime.result import RunResult, RunStatus


def run_result(status: RunStatus, error: ErrorInfo | None = None) -> RunResult:
    now = datetime.now()
    return RunResult(
        run_id="run-1",
        macro_id="sample",
        macro_name="Sample",
        status=status,
        started_at=now,
        finished_at=now,
        error=error,
    )


def error_info(message: str = "safe failure message") -> ErrorInfo:
    return ErrorInfo(
        kind=ErrorKind.MACRO,
        code="NYX_MACRO_FAILED",
        message=message,
        component="TestMacro",
        exception_type="RuntimeError",
        recoverable=False,
        details={
            "path": "E:\\secret\\payload.txt",
            "token": "super-secret-token",
        },
        traceback="Traceback (most recent call last): super-secret-token",
    )


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (RunStatus.SUCCESS, 0),
        (RunStatus.FAILED, 2),
        (RunStatus.CANCELLED, 130),
    ],
)
def test_cli_presenter_exit_codes(status: RunStatus, expected_code: int) -> None:
    presenter = CliPresenter()

    assert presenter.exit_code(run_result(status)) == expected_code


def test_cli_presenter_excludes_traceback() -> None:
    presenter = CliPresenter()

    message = presenter.render_result(run_result(RunStatus.FAILED, error_info()))

    assert message.text == "safe failure message"
    assert "Traceback" not in message.text
    assert "E:\\secret\\payload.txt" not in message.text
    assert "super-secret-token" not in message.text


def test_cli_presenter_renders_cancelled_message() -> None:
    presenter = CliPresenter()

    message = presenter.render_result(run_result(RunStatus.CANCELLED))

    assert message.level == "WARNING"
    assert message.text == "Macro execution was interrupted"

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from nyxpy.framework.core.io.resources import MacroResourceScope
from nyxpy.framework.core.logger.ports import RunLogContext
from nyxpy.framework.core.runtime.context import ExecutionContext, RuntimeOptions
from nyxpy.framework.core.utils.cancellation import CancellationToken
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFrameSourcePort,
    FakeLoggerPort,
    FakeNotificationPort,
    FakeResourceStore,
    FakeRunArtifactStore,
)


def make_fake_execution_context(
    tmp_path: Path,
    *,
    run_id: str = "run-1",
    macro_id: str = "sample",
    macro_name: str = "Sample",
    exec_args: dict | None = None,
    metadata: dict | None = None,
    controller: FakeControllerOutputPort | None = None,
    frame_source: FakeFrameSourcePort | None = None,
    logger: FakeLoggerPort | None = None,
    cancellation_token: CancellationToken | None = None,
    options: RuntimeOptions | None = None,
) -> ExecutionContext:
    log_context = RunLogContext(
        run_id=run_id,
        macro_id=macro_id,
        macro_name=macro_name,
        entrypoint="test",
        started_at=datetime.now(),
    )
    base_logger = logger or FakeLoggerPort()
    scope = MacroResourceScope(
        project_root=tmp_path,
        macro_id=macro_id,
        macro_root=tmp_path / "macros" / macro_id,
        assets_roots=(tmp_path / "resources" / macro_id / "assets",),
    )
    return ExecutionContext(
        run_id=run_id,
        macro_id=macro_id,
        macro_name=macro_name,
        run_log_context=log_context,
        exec_args=exec_args or {},
        metadata=metadata or {},
        cancellation_token=cancellation_token or CancellationToken(),
        controller=controller or FakeControllerOutputPort(),
        frame_source=frame_source or FakeFrameSourcePort(),
        resources=FakeResourceStore(scope),
        artifacts=FakeRunArtifactStore(
            tmp_path / "runs" / run_id / "outputs", macro_id=macro_id, run_id=run_id
        ),
        notifications=FakeNotificationPort(),
        logger=base_logger.bind_context(log_context),
        options=options or RuntimeOptions(),
    )

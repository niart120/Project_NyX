from pathlib import Path

import numpy as np
import pytest

from nyxpy.framework.core.io.ports import FrameNotReadyError
from nyxpy.framework.core.io.resources import (
    MacroResourceScope,
    ResourceKind,
    ResourceNotFoundError,
    ResourceSource,
)
from nyxpy.framework.core.logger.ports import RunLogContext
from tests.support.fakes import (
    FakeFrameSourcePort,
    FakeLoggerPort,
    FakeNotificationPort,
    FakeResourceStore,
    FakeRunArtifactStore,
)


def test_fake_frame_source_readiness() -> None:
    frame = np.full((2, 2, 3), 7, dtype=np.uint8)
    source = FakeFrameSourcePort(frame)

    assert source.await_ready(0) is False
    with pytest.raises(FrameNotReadyError):
        source.latest_frame()

    source.initialize()
    assert source.await_ready(0) is True
    latest = source.latest_frame()
    latest[0, 0, 0] = 99
    assert frame[0, 0, 0] == 7
    preview_frame = source.try_latest_frame()
    assert preview_frame is not None
    preview_frame[0, 0, 0] = 88
    assert frame[0, 0, 0] == 7


def test_fake_frame_source_try_latest_frame_is_nonblocking() -> None:
    source = FakeFrameSourcePort()
    source.initialize()

    assert source.frame_lock.acquire(blocking=False)
    try:
        assert source.try_latest_frame() is None
    finally:
        source.frame_lock.release()


def test_fake_frame_source_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError):
        FakeFrameSourcePort().await_ready(-1)


def test_notification_port_records_calls() -> None:
    notifier = FakeNotificationPort()
    image = np.zeros((1, 1, 3), dtype=np.uint8)

    notifier.publish("message")
    notifier.publish("with image", image)

    assert notifier.calls == [("message", None), ("with image", image)]


def test_resource_store_port_contract(tmp_path: Path) -> None:
    standard_assets = tmp_path / "resources" / "sample" / "assets"
    package_assets = tmp_path / "macros" / "sample" / "assets"
    scope = MacroResourceScope(
        project_root=tmp_path,
        macro_id="sample",
        macro_root=tmp_path / "macros" / "sample",
        assets_roots=(standard_assets, package_assets),
    )
    store = FakeResourceStore(scope)
    image = np.full((2, 2, 3), 5, dtype=np.uint8)
    store.images[standard_assets.resolve() / "template.png"] = image

    ref = store.resolve_asset_path("template.png")
    loaded = store.load_image("template.png")

    assert ref.kind is ResourceKind.ASSET
    assert ref.source is ResourceSource.STANDARD_ASSETS
    assert ref.macro_id == "sample"
    assert np.array_equal(loaded, image)
    loaded[0, 0, 0] = 99
    assert image[0, 0, 0] == 5


def test_resource_store_raises_for_missing_asset(tmp_path: Path) -> None:
    scope = MacroResourceScope(
        project_root=tmp_path,
        macro_id="sample",
        macro_root=None,
        assets_roots=(tmp_path / "resources" / "sample" / "assets",),
    )

    with pytest.raises(ResourceNotFoundError):
        FakeResourceStore(scope).resolve_asset_path("missing.png")


def test_macro_settings_resolver_is_separate_from_resource_store(tmp_path: Path) -> None:
    settings_dir = tmp_path / "resources" / "sample" / "assets"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.toml").write_text("value = 'not an image'\n", encoding="utf-8")
    scope = MacroResourceScope(
        project_root=tmp_path,
        macro_id="sample",
        macro_root=None,
        assets_roots=(settings_dir,),
    )

    with pytest.raises(ResourceNotFoundError):
        FakeResourceStore(scope).resolve_asset_path("missing.png")


def test_run_artifact_store_contract(tmp_path: Path) -> None:
    store = FakeRunArtifactStore(
        tmp_path / "runs" / "run-1" / "outputs", macro_id="sample", run_id="run-1"
    )
    image = np.full((1, 1, 3), 3, dtype=np.uint8)

    ref = store.save_image("images/result.png", image)
    output = store.open_output("logs/out.txt", mode="wb")
    output.write(b"hello")
    output.close()

    assert ref.kind is ResourceKind.OUTPUT
    assert ref.source is ResourceSource.RUN_OUTPUTS
    assert ref.relative_path == Path("images") / "result.png"
    assert np.array_equal(store.saved_images[ref.path], image)
    assert store.outputs[store.resolve_output_path("logs/out.txt").path] == b"hello"


def test_logger_port_contract_uses_user_and_technical() -> None:
    logger = FakeLoggerPort()
    bound = logger.bind_context(
        RunLogContext(run_id="run-1", macro_id="sample", macro_name="Sample")
    )

    bound.user("INFO", "visible", component="MacroRuntime", event="macro.started")
    bound.technical("DEBUG", "details", component="MacroRuntime", event="macro.debug")

    assert len(logger.user_events) == 1
    assert len(logger.technical_logs) == 1
    assert logger.user_events[0].run_id == "run-1"
    assert logger.user_events[0].macro_id == "sample"
    assert logger.technical_logs[0].event.run_id == "run-1"
    assert logger.technical_logs[0].event.event == "macro.debug"

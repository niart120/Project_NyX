from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nyxpy.cli.run_cli import (
    CliPresenter,
    build_parser,
    cli_main,
    configure_logging,
    create_protocol,
    create_runtime_builder,
    execute_macro,
)
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol, ThreeDSSerialProtocol
from nyxpy.framework.core.macro.exceptions import ConfigurationError, ErrorInfo, ErrorKind
from nyxpy.framework.core.runtime.result import RunResult, RunStatus


class MockLogger:
    def __init__(self):
        self.logs = []

    def user(self, level, message, *, component, event, code=None, extra=None):
        self.logs.append(("user", level, message, component, event))

    def technical(self, level, message, *, component, event="log.message", extra=None, exc=None):
        self.logs.append(("technical", level, message, component, event))

    def bind_context(self, context):
        return self


class MockLoggingComponents:
    def __init__(self):
        self.logger = MockLogger()
        self.current_level = None
        self.closed = False

    def set_all_levels(self, level):
        self.current_level = level

    def set_console_level(self, level):
        self.current_level = level

    def close(self):
        self.closed = True


class FailingLoggingComponents(MockLoggingComponents):
    def close(self):
        raise RuntimeError("close failed")


@pytest.fixture
def mock_log_manager():
    return MockLoggingComponents()


def result(status: RunStatus, message: str = "") -> RunResult:
    error = (
        ErrorInfo(
            kind=ErrorKind.MACRO,
            code="NYX_MACRO_FAILED",
            message=message,
            component="test",
            exception_type="RuntimeError",
            recoverable=False,
        )
        if message
        else None
    )
    now = datetime.now()
    return RunResult(
        run_id="run-1",
        macro_id="Sample",
        macro_name="Sample",
        status=status,
        started_at=now,
        finished_at=now,
        error=error,
    )


def test_configure_logging_normal(monkeypatch, mock_log_manager):
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_default_logging", lambda **_kwargs: mock_log_manager
    )
    logging = configure_logging()
    assert logging is mock_log_manager
    assert mock_log_manager.current_level == "INFO"


def test_configure_logging_silent(monkeypatch, mock_log_manager):
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_default_logging", lambda **_kwargs: mock_log_manager
    )
    configure_logging(silence=True)
    assert mock_log_manager.current_level == "ERROR"


def test_configure_logging_verbose(monkeypatch, mock_log_manager):
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_default_logging", lambda **_kwargs: mock_log_manager
    )
    configure_logging(verbose=True)
    assert mock_log_manager.current_level == "DEBUG"


def test_create_protocol_valid():
    assert isinstance(create_protocol("CH552"), CH552SerialProtocol)


def test_create_protocol_3ds():
    assert isinstance(create_protocol("3DS"), ThreeDSSerialProtocol)


def test_create_protocol_empty():
    with pytest.raises(ValueError, match="Protocol name cannot be empty"):
        create_protocol("")


def test_create_protocol_unknown():
    with pytest.raises(ValueError, match="Unknown protocol: UNKNOWN"):
        create_protocol("UNKNOWN")


def test_create_runtime_builder_delegates_device_selection_to_builder(monkeypatch, tmp_path):
    mock_registry = MagicMock()
    registry = MagicMock()
    mock_registry.return_value = registry
    mock_builder = MagicMock()
    discovery = MagicMock()
    controller_factory = MagicMock()
    frame_factory = MagicMock()
    settings_store = MagicMock(snapshot=MagicMock(return_value={"runtime.allow_dummy": False}))
    secrets_snapshot = object()
    secrets_store = MagicMock(snapshot=MagicMock(return_value=secrets_snapshot))
    monkeypatch.setattr("nyxpy.cli.run_cli.MacroRegistry", mock_registry)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_notification_handler_from_settings",
        lambda settings, logger: "notifier",
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.create_device_runtime_builder", mock_builder)

    logger = MockLogger()
    create_runtime_builder(
        MagicMock(),
        logger=logger,
        project_root=tmp_path,
        settings_store=settings_store,
        secrets_store=secrets_store,
        device_discovery=discovery,
        controller_output_factory=controller_factory,
        frame_source_factory=frame_factory,
    )

    mock_registry.assert_called_once_with(project_root=tmp_path)
    registry.reload.assert_called_once()
    assert mock_builder.call_args.kwargs["device_discovery"] is discovery
    assert mock_builder.call_args.kwargs["controller_output_factory"] is controller_factory
    assert mock_builder.call_args.kwargs["frame_source_factory"] is frame_factory
    assert mock_builder.call_args.kwargs["settings"] == {"runtime.allow_dummy": False}
    assert "serial_device" not in mock_builder.call_args.kwargs
    assert "capture_device" not in mock_builder.call_args.kwargs


def test_create_runtime_builder_passes_project_config_dir_to_stores(monkeypatch, tmp_path):
    mock_registry = MagicMock()
    mock_registry.return_value = MagicMock(reload=lambda: None)
    mock_builder = MagicMock()
    settings_store = MagicMock(snapshot=MagicMock(return_value={}))
    secrets_snapshot = object()
    secrets_store = MagicMock(snapshot=MagicMock(return_value=secrets_snapshot))
    mock_settings_store = MagicMock(return_value=settings_store)
    mock_secrets_store = MagicMock(return_value=secrets_store)

    monkeypatch.setattr("nyxpy.cli.run_cli.MacroRegistry", mock_registry)
    monkeypatch.setattr("nyxpy.cli.run_cli.SettingsStore", mock_settings_store)
    monkeypatch.setattr("nyxpy.cli.run_cli.SecretsStore", mock_secrets_store)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_notification_handler_from_settings",
        lambda settings, logger: "notifier",
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.create_device_runtime_builder", mock_builder)

    create_runtime_builder(MagicMock(), logger=MockLogger(), project_root=tmp_path)

    mock_settings_store.assert_called_once_with(
        config_dir=tmp_path.resolve() / ".nyxpy",
        strict_load=False,
    )
    mock_secrets_store.assert_called_once_with(
        config_dir=tmp_path.resolve() / ".nyxpy",
        strict_load=False,
    )


def test_execute_macro_success(monkeypatch, mock_log_manager):
    builder = MagicMock(run=MagicMock(return_value=result(RunStatus.SUCCESS)))

    run_result = execute_macro(builder, "Sample", {"arg1": "value1"}, mock_log_manager.logger)

    assert run_result.status is RunStatus.SUCCESS
    request = builder.run.call_args.args[0]
    assert request.macro_id == "Sample"
    assert request.exec_args == {"arg1": "value1"}


def test_execute_macro_cancelled(monkeypatch, mock_log_manager):
    builder = MagicMock(run=MagicMock(return_value=result(RunStatus.CANCELLED)))

    run_result = execute_macro(builder, "Sample", {}, mock_log_manager.logger)

    assert run_result.status is RunStatus.CANCELLED
    assert any(log[1] == "WARNING" for log in mock_log_manager.logger.logs)


def test_execute_macro_failed(monkeypatch, mock_log_manager):
    builder = MagicMock(run=MagicMock(return_value=result(RunStatus.FAILED, "boom")))

    run_result = execute_macro(builder, "Sample", {}, mock_log_manager.logger)

    assert run_result.status is RunStatus.FAILED
    assert any(log[1] == "ERROR" for log in mock_log_manager.logger.logs)


def test_cli_presenter_exit_codes() -> None:
    presenter = CliPresenter()

    assert presenter.exit_code(result(RunStatus.SUCCESS)) == 0
    assert presenter.exit_code(result(RunStatus.CANCELLED)) == 130
    assert presenter.exit_code(result(RunStatus.FAILED, "boom")) == 2


def test_cli_does_not_accept_notification_secret_args() -> None:
    options = {action.dest for action in build_parser()._actions}

    assert "discord_webhook_url" not in options
    assert "bluesky_password" not in options


def make_args():
    args = MagicMock()
    args.serial = "COM1"
    args.capture = "Camera1"
    args.protocol = "CH552"
    args.baud = None
    args.macro_name = "Sample"
    args.silence = False
    args.verbose = False
    args.define = []
    return args


def patch_cli_workspace(monkeypatch, tmp_path):
    paths = SimpleNamespace(
        project_root=tmp_path,
        config_dir=tmp_path / ".nyxpy",
        logs_dir=tmp_path / "logs",
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.resolve_project_root", lambda **_kwargs: tmp_path)
    monkeypatch.setattr("nyxpy.cli.run_cli.ensure_workspace", MagicMock(return_value=paths))
    return paths


def test_cli_main_success(monkeypatch, tmp_path):
    args = make_args()
    paths = patch_cli_workspace(monkeypatch, tmp_path)
    mock_logging = MockLoggingComponents()
    mock_configure = MagicMock(return_value=mock_logging)
    mock_protocol = MagicMock()
    mock_builder = MagicMock()
    mock_create_builder = MagicMock(return_value=mock_builder)
    mock_execute = MagicMock(return_value=result(RunStatus.SUCCESS))

    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", mock_configure)
    monkeypatch.setattr("nyxpy.cli.run_cli.create_protocol", lambda name: mock_protocol)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_runtime_builder",
        mock_create_builder,
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr("nyxpy.cli.run_cli.execute_macro", mock_execute)

    assert cli_main(args) == 0
    mock_configure.assert_called_once_with(
        silence=False,
        verbose=False,
        base_dir=paths.logs_dir,
    )
    mock_create_builder.assert_called_once_with(
        protocol=mock_protocol,
        logger=mock_logging.logger,
        project_root=paths.project_root,
        serial_name="COM1",
        capture_name="Camera1",
        baudrate=9600,
    )
    mock_execute.assert_called_once_with(
        runtime_builder=mock_builder,
        macro_name="Sample",
        exec_args={},
        logger=mock_logging.logger,
    )


def test_cli_main_uses_3ds_default_baudrate(monkeypatch, tmp_path):
    args = make_args()
    args.protocol = "3DS"
    patch_cli_workspace(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "nyxpy.cli.run_cli.configure_logging",
        MagicMock(return_value=MockLoggingComponents()),
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_runtime_builder",
        MagicMock(return_value=MagicMock()),
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.execute_macro",
        MagicMock(return_value=result(RunStatus.SUCCESS)),
    )

    assert cli_main(args) == 0
    create_builder = __import__(
        "nyxpy.cli.run_cli", fromlist=["create_runtime_builder"]
    ).create_runtime_builder
    assert create_builder.call_args.kwargs["baudrate"] == 115200


def test_cli_main_baud_override(monkeypatch, tmp_path):
    args = make_args()
    args.protocol = "3DS"
    args.baud = 9600
    patch_cli_workspace(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "nyxpy.cli.run_cli.configure_logging",
        MagicMock(return_value=MockLoggingComponents()),
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_runtime_builder",
        MagicMock(return_value=MagicMock()),
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.execute_macro",
        MagicMock(return_value=result(RunStatus.SUCCESS)),
    )

    assert cli_main(args) == 0
    create_builder = __import__(
        "nyxpy.cli.run_cli", fromlist=["create_runtime_builder"]
    ).create_runtime_builder
    assert create_builder.call_args.kwargs["baudrate"] == 9600


def test_cli_main_value_error(monkeypatch, mock_log_manager, tmp_path):
    args = make_args()
    args.serial = "COM3"
    patch_cli_workspace(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "nyxpy.cli.run_cli.configure_logging", MagicMock(return_value=mock_log_manager)
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_protocol",
        lambda name: (_ for _ in ()).throw(ValueError("invalid protocol")),
    )

    assert cli_main(args) == 1
    assert any(log[1] == "ERROR" for log in mock_log_manager.logger.logs)


def test_cli_main_exception(monkeypatch, mock_log_manager, tmp_path):
    args = make_args()
    patch_cli_workspace(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.configure_logging", MagicMock(return_value=mock_log_manager)
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_protocol",
        lambda name: (_ for _ in ()).throw(Exception("Unexpected error")),
    )

    assert cli_main(args) == 2
    assert any(
        log[1] == "ERROR" and "Unhandled exception" in log[2]
        for log in mock_log_manager.logger.logs
    )


def test_cli_unhandled_exception_uses_fixed_user_message(
    monkeypatch, mock_log_manager, capsys, tmp_path
):
    args = make_args()
    patch_cli_workspace(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.configure_logging", MagicMock(return_value=mock_log_manager)
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_protocol",
        lambda name: (_ for _ in ()).throw(
            RuntimeError("secret value leaked from E:\\secret\\payload.txt")
        ),
    )

    assert cli_main(args) == 2

    captured = capsys.readouterr()
    assert captured.out.strip() == "Unexpected error. See logs for details."
    assert "secret value" not in captured.out
    assert "E:\\secret\\payload.txt" not in captured.out
    assert any(log[4] == "cli.unhandled" for log in mock_log_manager.logger.logs)


def test_cli_configuration_error_returns_1(monkeypatch, mock_log_manager, tmp_path):
    args = make_args()
    patch_cli_workspace(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.configure_logging", MagicMock(return_value=mock_log_manager)
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_protocol",
        lambda name: (_ for _ in ()).throw(ConfigurationError("invalid protocol settings")),
    )

    assert cli_main(args) == 1
    assert any(log[4] == "configuration.invalid" for log in mock_log_manager.logger.logs)


def test_cli_cleanup_failures_are_logged(monkeypatch, tmp_path):
    args = make_args()
    patch_cli_workspace(monkeypatch, tmp_path)
    logging = FailingLoggingComponents()
    builder = MagicMock()
    builder.shutdown = MagicMock(side_effect=RuntimeError("shutdown failed"))

    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", MagicMock(return_value=logging))
    monkeypatch.setattr("nyxpy.cli.run_cli.create_protocol", lambda name: MagicMock())
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_runtime_builder",
        MagicMock(return_value=builder),
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.execute_macro",
        MagicMock(return_value=result(RunStatus.SUCCESS)),
    )

    assert cli_main(args) == 0
    cleanup_events = [
        log
        for log in logging.logger.logs
        if log[0] == "technical" and log[4] == "resource.cleanup_failed"
    ]
    assert len(cleanup_events) == 2

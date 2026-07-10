"""NyX CLI のマクロ実行 entrypoint。"""

import argparse
import pathlib
import sys
from dataclasses import dataclass, replace
from typing import Any

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.swbt.config import (
    SwbtControllerConfig,
    supported_controller_models,
)
from nyxpy.framework.core.hardware.swbt.diagnostics import LoggerDiagnosticsWriter
from nyxpy.framework.core.hardware.swbt.discovery import SwbtAdapterDiscoveryService
from nyxpy.framework.core.hardware.swbt.factory import SwbtControllerOutputPortFactory
from nyxpy.framework.core.io.controller_config import (
    ControllerConfig,
    SerialControllerConfig,
    controller_config_from_overrides,
)
from nyxpy.framework.core.io.device_factories import (
    FrameSourcePortFactory,
    SerialControllerOutputPortFactory,
)
from nyxpy.framework.core.logger import LoggerPort, LoggingComponents, create_default_logging
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.notifications.notification_handler import (
    create_notification_handler_from_settings,
)
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder, create_device_runtime_builder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.exec_args import parse_define_args
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.settings.global_settings import SettingsStore
from nyxpy.framework.core.settings.secrets_settings import SecretsStore
from nyxpy.framework.core.settings.workspace import ensure_workspace, resolve_project_root

from .swbt_adapter import canonicalize_swbt_adapter


@dataclass(frozen=True)
class UserMessage:
    """CLI へ表示するユーザ向けメッセージ。"""

    level: str
    text: str
    code: str | None = None


class CliPresenter:
    """`RunResult` を終了コードとユーザ向け表示へ変換します。"""

    def render_result(self, result: RunResult) -> UserMessage:
        if result.status is RunStatus.SUCCESS:
            return UserMessage("INFO", "Macro execution completed")
        if result.status is RunStatus.CANCELLED:
            return UserMessage("WARNING", "Macro execution was interrupted")
        message = result.error.message if result.error is not None else "Macro execution failed"
        code = result.error.code if result.error is not None else None
        return UserMessage("ERROR", message, code=code)

    def exit_code(self, result: RunResult) -> int:
        if result.status is RunStatus.SUCCESS:
            return 0
        if result.status is RunStatus.CANCELLED:
            return 130
        return 2


def format_cli_error(message: str, *, code: str | None = None) -> str:
    """CLI の error message に framework code を付ける。"""
    if code:
        return f"エラー [{code}]: {message}"
    return f"エラー: {message}"


def configure_logging(
    silence: bool = False,
    verbose: bool = False,
    *,
    base_dir: pathlib.Path | None = None,
) -> LoggingComponents:
    """コマンドライン引数に基づいてログレベルを設定します。

    Args:
        silence: Trueの場合、ほとんどのログ出力を抑制します
        verbose: Trueの場合、デバッグレベルのログを有効にします
        base_dir: ログ出力ディレクトリ。未指定の場合は現在の作業ディレクトリ配下の logs

    """
    logging = create_default_logging(base_dir=base_dir or pathlib.Path.cwd() / "logs")
    if silence:
        print("Running in silent mode; logging is disabled.")
        logging.set_all_levels("ERROR")
    elif verbose:
        print("Verbose logging enabled.")
        logging.set_all_levels("DEBUG")
    else:
        logging.set_console_level("INFO")
    return logging


def create_protocol(protocol_name: str) -> SerialProtocolInterface:
    """プロトコル名に基づいてプロトコルインスタンスを作成して返します。

    Args:
        protocol_name: 作成するプロトコルの名前

    Returns:
        SerialProtocolInterfaceの実装

    Raises:
        ValueError: プロトコル名が不明な場合

    """
    return ProtocolFactory.create_protocol(protocol_name)


def create_runtime_builder(
    logger: LoggerPort,
    *,
    controller_config: ControllerConfig,
    project_root: pathlib.Path | None = None,
    capture_name: str | None = None,
    detection_timeout_sec: float = 2.0,
    settings_store: SettingsStore | None = None,
    secrets_store: SecretsStore | None = None,
    device_discovery: DeviceDiscoveryService | None = None,
    serial_controller_factory: SerialControllerOutputPortFactory | None = None,
    swbt_controller_factory: SwbtControllerOutputPortFactory | None = None,
    frame_source_factory: FrameSourcePortFactory | None = None,
) -> MacroRuntimeBuilder:
    """CLI で利用する Runtime builder を作成します。

    Args:
        logger: Runtime に注入する logger
        controller_config: 使用する controller backend 設定
        project_root: 使用する NyX workspace root
        capture_name: 使用するキャプチャデバイス名
        detection_timeout_sec: デバイス自動検出のタイムアウト秒数
        settings_store: 差し替え用の設定 store。未指定の場合は workspace から読み込みます
        secrets_store: 差し替え用の secrets store。未指定の場合は workspace から読み込みます
        device_discovery: 差し替え用のデバイス検出 service
        serial_controller_factory: 差し替え用の serial controller output factory
        swbt_controller_factory: 差し替え用の swbt controller output factory
        frame_source_factory: 差し替え用の frame source factory

    Returns:
        設定済みの Runtime builder

    """
    resolved_root = resolve_project_root(
        explicit_root=project_root,
        allow_current_as_new=False,
    )
    paths = ensure_workspace(resolved_root)
    registry = MacroRegistry(project_root=paths.project_root)
    registry.reload()
    settings = settings_store or SettingsStore(config_dir=paths.config_dir, strict_load=False)
    secrets = secrets_store or SecretsStore(config_dir=paths.config_dir, strict_load=False)
    discovery = device_discovery or DeviceDiscoveryService(logger=logger)
    frame_factory = frame_source_factory or FrameSourcePortFactory(
        discovery=discovery,
        logger=logger,
    )
    notification_handler = create_notification_handler_from_settings(
        secrets.snapshot(), logger=logger
    )
    resolved_swbt_factory = swbt_controller_factory
    if isinstance(controller_config, SwbtControllerConfig) and resolved_swbt_factory is None:
        resolved_swbt_factory = SwbtControllerOutputPortFactory(
            diagnostics_writer=LoggerDiagnosticsWriter(logger)
        )
    return create_device_runtime_builder(
        project_root=paths.project_root,
        registry=registry,
        device_discovery=discovery,
        controller_config=controller_config,
        serial_controller_factory=serial_controller_factory,
        swbt_controller_factory=resolved_swbt_factory,
        frame_source_factory=frame_factory,
        capture_name=capture_name,
        detection_timeout_sec=detection_timeout_sec,
        notification_handler=notification_handler,
        logger=logger,
        settings=settings.snapshot(),
    )


def execute_macro(
    runtime_builder: MacroRuntimeBuilder,
    macro_name: str,
    exec_args: dict[str, Any],
    logger: LoggerPort,
) -> RunResult:
    """CLI entrypoint の RuntimeBuildRequest を作成し、Runtime builder で実行します。

    Args:
        runtime_builder: 実行用 Runtime builder
        macro_name: 実行するマクロの名前
        exec_args: マクロに渡す引数
        logger: CLI 実行結果を出力する logger

    Returns:
        Runtime が返した RunResult

    """
    result = runtime_builder.run(
        RuntimeBuildRequest(macro_id=macro_name, entrypoint="cli", exec_args=exec_args)
    )
    if result.status is RunStatus.CANCELLED:
        logger.user(
            "WARNING",
            "Macro execution was interrupted",
            component="CLI",
            event="macro.cancelled",
        )
        return result
    if not result.ok:
        message = result.error.message if result.error is not None else "Macro execution failed"
        logger.user("ERROR", message, component="CLI", event="macro.failed")
        return result
    logger.user("INFO", "Macro execution completed", component="CLI", event="macro.finished")
    return result


def _record_cleanup_failure(
    logger: LoggerPort | None,
    action: str,
    exc: BaseException,
) -> None:
    message = f"Cleanup failed while trying to {action}"
    if logger is None:
        print(message, file=sys.stderr)
        return

    try:
        logger.technical(
            "WARNING",
            message,
            component="CLI",
            event="resource.cleanup_failed",
            extra={"action": action, "exception_type": type(exc).__name__},
            exc=exc,
        )
    except Exception as log_exc:
        print(message, file=sys.stderr)
        print(f"Cleanup failure logging failed: {type(log_exc).__name__}", file=sys.stderr)


def _run_cleanup(
    action: str,
    cleanup,
    logger: LoggerPort | None,
) -> None:
    try:
        cleanup()
    except Exception as exc:
        _record_cleanup_failure(logger, action, exc)


def cli_main(
    args: argparse.Namespace,
    *,
    swbt_adapter_discovery: SwbtAdapterDiscoveryService | None = None,
) -> int:
    """CLIアプリケーションのメインエントリーポイント。

    この関数は解析済み引数から Runtime 実行要求を組み立てます。

    Args:
        args: コマンドライン引数
        swbt_adapter_discovery: swbt adapter 名を正規化する discovery service

    Returns:
        終了コード（0:成功、0以外:エラー）

    """
    try:
        project_root = resolve_project_root(allow_current_as_new=False)
        paths = ensure_workspace(project_root)

        # ログの設定
        logging = configure_logging(
            silence=args.silence,
            verbose=args.verbose,
            base_dir=paths.logs_dir,
        )
        logger = logging.logger

        settings = SettingsStore(config_dir=paths.config_dir, strict_load=False)
        controller_config = _controller_config_from_args(
            args,
            settings_snapshot=settings.snapshot(),
            workspace_root=paths.project_root,
        )
        if isinstance(controller_config, SwbtControllerConfig):
            controller_config = canonicalize_swbt_adapter(
                controller_config,
                discovery_service=swbt_adapter_discovery,
            )
        runtime_builder = create_runtime_builder(
            logger=logger,
            controller_config=controller_config,
            project_root=paths.project_root,
            capture_name=args.capture,
            settings_store=settings,
        )

        # マクロ実行引数の解析
        exec_args = parse_define_args(args.define or [])

        # マクロの実行
        result = execute_macro(
            runtime_builder=runtime_builder,
            macro_name=args.macro_name,
            exec_args=exec_args,
            logger=logger,
        )

        presenter = CliPresenter()
        user_message = presenter.render_result(result)
        if user_message.level != "INFO":
            if user_message.level == "ERROR":
                print(format_cli_error(user_message.text, code=user_message.code))
            else:
                print(user_message.text)
        return presenter.exit_code(result)

    except (ConfigurationError, ValueError) as ve:
        error_code = ve.code if isinstance(ve, ConfigurationError) else None
        error_message = ve.message if isinstance(ve, ConfigurationError) else str(ve)
        if "logger" in locals():
            logger.user(
                "ERROR",
                error_message,
                component="CLI",
                event="configuration.invalid",
                code=error_code,
            )
            logger.technical(
                "ERROR",
                "Invalid CLI configuration",
                component="CLI",
                event="configuration.invalid",
                exc=ve,
            )
        print(format_cli_error(error_message, code=error_code))
        return 1  # エラー時の終了コード

    except Exception as e:
        if "logger" in locals():
            logger.technical(
                "ERROR",
                "Unhandled exception",
                component="CLI",
                event="cli.unhandled",
                exc=e,
            )
        print("Unexpected error. See logs for details.")
        return 2  # 重大なエラー時の終了コード

    finally:
        cleanup_logger = logger if "logger" in locals() else None
        if "runtime_builder" in locals():
            _run_cleanup("shutdown runtime builder", runtime_builder.shutdown, cleanup_logger)
        if "logging" in locals():
            _run_cleanup("close logging", logging.close, cleanup_logger)


def build_parser() -> argparse.ArgumentParser:
    """CLIの引数パーサーを構築します。"""
    parser = argparse.ArgumentParser(description="NyXPy-FW CLI - game automation tool")
    add_run_arguments(parser)
    return parser


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    """マクロ実行 command の共通引数を parser に追加します。"""
    parser.add_argument("macro_name", help="実行するマクロ名")
    parser.add_argument(
        "--controller",
        choices=("serial", "swbt"),
        default=None,
        help="controller backend override",
    )
    parser.add_argument("-s", "--serial", default=None, help="シリアルデバイス名")
    parser.add_argument("-c", "--capture", default=None, help="キャプチャデバイス名")
    parser.add_argument(
        "-p",
        "--protocol",
        default=None,
        help="通信プロトコル",
    )
    parser.add_argument("--baud", type=int, default=None, help="シリアルボーレート")
    parser.add_argument("--swbt-adapter", default=None, help="swbt adapter override")
    parser.add_argument(
        "--swbt-controller-type",
        choices=tuple(model.settings_value for model in supported_controller_models()),
        default=None,
        help="swbt controller type override",
    )
    parser.add_argument(
        "--swbt-key-store",
        type=pathlib.Path,
        default=None,
        help="swbt pairing key store path override",
    )
    parser.add_argument(
        "--swbt-timeout",
        type=float,
        default=None,
        help="swbt connect timeout seconds override",
    )
    parser.add_argument("--silence", action="store_true", help="ログ出力を最小限に抑制")
    parser.add_argument("--verbose", action="store_true", help="詳細なログ出力を有効化")
    parser.add_argument(
        "--define",
        action="append",
        help="マクロ実行時の変数定義 (key=value形式)",
        default=[],
    )


def _controller_config_from_args(
    args: argparse.Namespace,
    *,
    settings_snapshot,
    workspace_root: pathlib.Path,
) -> ControllerConfig:
    config = controller_config_from_overrides(
        settings_snapshot,
        workspace_root=workspace_root,
        backend=getattr(args, "controller", None),
        serial_device=getattr(args, "serial", None),
        serial_protocol=getattr(args, "protocol", None),
        serial_baudrate=getattr(args, "baud", None),
        swbt_adapter=getattr(args, "swbt_adapter", None),
        swbt_controller_type=getattr(args, "swbt_controller_type", None),
        swbt_key_store_path=getattr(args, "swbt_key_store", None),
        swbt_connect_timeout_sec=getattr(args, "swbt_timeout", None),
    )
    if isinstance(config, SerialControllerConfig):
        protocol_override = getattr(args, "protocol", None)
        baud_override = getattr(args, "baud", None)
        if protocol_override is not None and baud_override is None:
            return replace(
                config,
                baudrate=ProtocolFactory.resolve_baudrate(config.protocol, None),
            )
    return config


def main():
    """CLIのメインエントリーポイント

    コマンドライン引数を解析してcli_mainを呼び出します
    """
    parser = build_parser()

    args = parser.parse_args()
    exit_code = cli_main(args)
    exit(exit_code)

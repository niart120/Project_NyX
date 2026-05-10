import argparse
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

from nyxpy.framework.core.api.notification_handler import (
    create_notification_handler_from_settings,
)
from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.io.device_factories import (
    ControllerOutputPortFactory,
    FrameSourcePortFactory,
)
from nyxpy.framework.core.logger import LoggerPort, LoggingComponents, create_default_logging
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder, create_device_runtime_builder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.settings.global_settings import SettingsStore
from nyxpy.framework.core.settings.secrets_settings import SecretsStore
from nyxpy.framework.core.utils.helper import parse_define_args


@dataclass(frozen=True)
class UserMessage:
    level: str
    text: str
    code: str | None = None


class CliPresenter:
    def render_result(self, result: RunResult) -> UserMessage:
        if result.status is RunStatus.SUCCESS:
            return UserMessage("INFO", "Macro execution completed")
        if result.status is RunStatus.CANCELLED:
            return UserMessage("WARNING", "Macro execution was interrupted")
        message = result.error.message if result.error is not None else "Macro execution failed"
        return UserMessage("ERROR", message)

    def exit_code(self, result: RunResult) -> int:
        if result.status is RunStatus.SUCCESS:
            return 0
        if result.status is RunStatus.CANCELLED:
            return 130
        return 2


def configure_logging(silence: bool = False, verbose: bool = False) -> LoggingComponents:
    """
    コマンドライン引数に基づいてログレベルを設定します。

    Args:
        silence: Trueの場合、ほとんどのログ出力を抑制します
        verbose: Trueの場合、デバッグレベルのログを有効にします
    """
    logging = create_default_logging(base_dir=pathlib.Path.cwd() / "logs")
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
    """
    プロトコル名に基づいてプロトコルインスタンスを作成して返します。

    Args:
        protocol_name: 作成するプロトコルの名前

    Returns:
        SerialProtocolInterfaceの実装

    Raises:
        ValueError: プロトコル名が不明な場合
    """
    return ProtocolFactory.create_protocol(protocol_name)


def create_runtime_builder(
    protocol: SerialProtocolInterface,
    logger: LoggerPort,
    resources_dir: pathlib.Path | None = None,
    *,
    serial_name: str | None = None,
    capture_name: str | None = None,
    baudrate: int | None = None,
    detection_timeout_sec: float = 2.0,
    settings_store: SettingsStore | None = None,
    secrets_store: SecretsStore | None = None,
    device_discovery: DeviceDiscoveryService | None = None,
    controller_output_factory: ControllerOutputPortFactory | None = None,
    frame_source_factory: FrameSourcePortFactory | None = None,
) -> MacroRuntimeBuilder:
    """
    CLI で利用する Runtime builder を作成します。

    Args:
        protocol: 使用するプロトコル実装
        logger: Runtime に注入する logger
        resources_dir: 旧互換引数。指定時はプロジェクトルートとして扱います。
        serial_name: 使用するシリアルデバイス名
        capture_name: 使用するキャプチャデバイス名
        baudrate: シリアルボーレート

    Returns:
        設定済みの Runtime builder
    """
    project_root = pathlib.Path.cwd() if resources_dir is None else resources_dir
    registry = MacroRegistry(project_root=project_root)
    registry.reload()
    config_dir = project_root / ".nyxpy"
    settings = settings_store or SettingsStore(config_dir=config_dir, strict_load=False)
    secrets = secrets_store or SecretsStore(config_dir=config_dir, strict_load=False)
    discovery = device_discovery or DeviceDiscoveryService(logger=logger)
    controller_factory = controller_output_factory or ControllerOutputPortFactory(
        discovery=discovery,
        protocol=protocol,
    )
    frame_factory = frame_source_factory or FrameSourcePortFactory(
        discovery=discovery,
        logger=logger,
    )
    notification_handler = create_notification_handler_from_settings(
        secrets.snapshot(), logger=logger
    )
    return create_device_runtime_builder(
        project_root=project_root,
        registry=registry,
        device_discovery=discovery,
        controller_output_factory=controller_factory,
        frame_source_factory=frame_factory,
        serial_name=serial_name,
        capture_name=capture_name,
        baudrate=baudrate,
        detection_timeout_sec=detection_timeout_sec,
        protocol=protocol,
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
    """
    CLI entrypoint の RuntimeBuildRequest を作成し、Runtime builder で実行します。

    Args:
        runtime_builder: 実行用 Runtime builder
        macro_name: 実行するマクロの名前
        exec_args: マクロに渡す引数

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


def cli_main(args: argparse.Namespace) -> int:
    """
    CLIアプリケーションのメインエントリーポイント。
    この関数は解析済み引数から Runtime 実行要求を組み立てます。

    Args:
        args: コマンドライン引数

    Returns:
        終了コード（0:成功、0以外:エラー）
    """
    try:
        # ログの設定
        logging = configure_logging(silence=args.silence, verbose=args.verbose)
        logger = logging.logger

        baudrate = ProtocolFactory.resolve_baudrate(args.protocol, getattr(args, "baud", None))

        protocol = create_protocol(args.protocol)
        runtime_builder = create_runtime_builder(
            protocol=protocol,
            logger=logger,
            serial_name=args.serial,
            capture_name=args.capture,
            baudrate=baudrate,
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
            print(user_message.text)
        return presenter.exit_code(result)

    except (ConfigurationError, ValueError) as ve:
        if "logger" in locals():
            logger.user("ERROR", str(ve), component="CLI", event="configuration.invalid")
            logger.technical(
                "ERROR",
                "Invalid CLI configuration",
                component="CLI",
                event="configuration.invalid",
                exc=ve,
            )
        print(f"エラー: {ve}")
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
    """
    CLIの引数パーサーを構築します。
    """
    parser = argparse.ArgumentParser(description="NyX CLI - Nintendo Switch Automation Tool")
    parser.add_argument("macro_name", help="実行するマクロ名")
    parser.add_argument("--serial", required=True, help="シリアルデバイス名")
    parser.add_argument("--capture", required=True, help="キャプチャデバイス名")
    parser.add_argument("--protocol", default="ch552", help="通信プロトコル (default: ch552)")
    parser.add_argument("--baud", type=int, default=None, help="シリアルボーレート")
    parser.add_argument("--silence", action="store_true", help="ログ出力を最小限に抑制")
    parser.add_argument("--verbose", action="store_true", help="詳細なログ出力を有効化")
    parser.add_argument(
        "--define",
        action="append",
        help="マクロ実行時の変数定義 (key=value形式)",
    )
    return parser


def main():
    """
    CLIのメインエントリーポイント
    コマンドライン引数を解析してcli_mainを呼び出します
    """
    parser = build_parser()

    args = parser.parse_args()
    exit_code = cli_main(args)
    exit(exit_code)

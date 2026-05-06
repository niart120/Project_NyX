import argparse
import pathlib
import time
from dataclasses import dataclass
from typing import Any

from nyxpy.framework.core.api.notification_handler import (
    create_notification_handler_from_settings,
)
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.logger import LoggerPort, LoggingComponents, create_default_logging
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder, create_legacy_runtime_builder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.framework.core.singletons import capture_manager, serial_manager
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
) -> MacroRuntimeBuilder:
    """
    指定されたコンポーネントでCommandインスタンスを作成します。

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
    if serial_name is not None:
        _select_serial_device(serial_name, baudrate, detection_timeout_sec)
    if capture_name is not None:
        _select_capture_device(capture_name, detection_timeout_sec)
    serial_device = serial_manager.get_active_device()
    capture_device = capture_manager.get_active_device()
    secrets_settings = SecretsSettings()
    notification_handler = create_notification_handler_from_settings(
        secrets_settings, logger=logger
    )
    return create_legacy_runtime_builder(
        project_root=project_root,
        registry=registry,
        serial_device=serial_device,
        capture_device=capture_device,
        protocol=protocol,
        notification_handler=notification_handler,
        logger=logger,
    )


def _select_serial_device(name: str, baudrate: int | None, timeout_sec: float) -> None:
    serial_manager.auto_register_devices()
    available_devices = _wait_for_device(serial_manager, name, timeout_sec)
    if name not in available_devices:
        available_devices_str = ", ".join(available_devices)
        raise ValueError(
            f"Serial port '{name}' not found. Available devices: {available_devices_str}"
        )
    serial_manager.set_active(name, baudrate or 9600)


def _select_capture_device(name: str, timeout_sec: float) -> None:
    capture_manager.auto_register_devices()
    available_devices = _wait_for_device(capture_manager, name, timeout_sec)
    print(f"Available capture devices: {available_devices}")
    if name not in available_devices:
        available_devices_str = ", ".join(available_devices)
        raise ValueError(
            f"Capture device '{name}' not found. Available devices: {available_devices_str}"
        )
    capture_manager.set_active(name)


def _wait_for_device(manager, desired_name: str, timeout_sec: float) -> list[str]:
    deadline = time.monotonic() + timeout_sec
    while True:
        devices = list(manager.list_devices())
        if desired_name in devices:
            return devices
        if time.monotonic() >= deadline:
            return devices
        time.sleep(0.05)


def execute_macro(
    runtime_builder: MacroRuntimeBuilder,
    macro_name: str,
    exec_args: dict[str, Any],
    logger: LoggerPort,
) -> RunResult:
    """
    適切なエラー処理でマクロを実行します。

    Args:
        runtime_builder: 実行用 Runtime builder
        macro_name: 実行するマクロの名前
        exec_args: マクロに渡す引数

    Raises:
        RuntimeError: マクロ実行が失敗した場合
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


def cli_main(args: argparse.Namespace) -> int:
    """
    CLIアプリケーションのメインエントリーポイント。
    この関数はコマンドライン引数を解析し、適切なコマンドを実行します。

    Args:
        args: コマンドライン引数

    Returns:
        終了コード（0:成功、0以外:エラー）
    """
    try:
        # ログの設定
        logging = configure_logging(silence=args.silence, verbose=args.verbose)
        logger = logging.logger

        capture_manager.set_logger(logger)
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
        exec_args = parse_define_args(args.define)

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

    except ValueError as ve:
        if "logger" in locals():
            logger.user("ERROR", str(ve), component="CLI", event="configuration.invalid")
        print(f"エラー: {ve}")
        return 1  # エラー時の終了コード

    except Exception as e:
        if "logger" in locals():
            logger.technical(
                "ERROR",
                "Unhandled exception",
                component="CLI",
                event="macro.failed",
                exc=e,
            )
        print(f"Unexpected error: {e}")
        return 2  # 重大なエラー時の終了コード

    finally:
        if "logging" in locals():
            logging.close()
        # デバイスリソースを確実に解放（ゾンビプロセス防止）
        try:
            capture_manager.release_active()
        except Exception:
            pass
        try:
            serial_manager.close_active()
        except Exception:
            pass


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

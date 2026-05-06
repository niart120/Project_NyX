import argparse
import pathlib
from typing import Any

from nyxpy.framework.core.api.notification_handler import (
    create_notification_handler_from_settings,
)
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder, create_legacy_runtime_builder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.singletons import capture_manager, serial_manager
from nyxpy.framework.core.utils.helper import parse_define_args


def configure_logging(silence: bool = False, verbose: bool = False) -> None:
    """
    コマンドライン引数に基づいてログレベルを設定します。

    Args:
        silence: Trueの場合、ほとんどのログ出力を抑制します
        verbose: Trueの場合、デバッグレベルのログを有効にします
    """
    if silence:
        print("Running in silent mode; logging is disabled.")
        log_manager.set_level("ERROR")
    elif verbose:
        print("Verbose logging enabled.")
        log_manager.set_level("DEBUG")
    else:
        log_manager.set_level("INFO")


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
    resources_dir: pathlib.Path | None = None,
) -> MacroRuntimeBuilder:
    """
    指定されたコンポーネントでCommandインスタンスを作成します。

    Args:
        protocol: 使用するプロトコル実装
        resources_dir: リソースI/O用のディレクトリ（デフォルトは'./static'）

    Returns:
        設定済みの Runtime builder
    """
    if resources_dir is None:
        resources_dir = pathlib.Path.cwd() / "static"

    resource_io = StaticResourceIO(resources_dir)
    registry = MacroRegistry(project_root=pathlib.Path.cwd())
    registry.reload()
    serial_device = serial_manager.get_active_device()
    capture_device = capture_manager.get_active_device()
    global_settings = GlobalSettings()
    notification_handler = create_notification_handler_from_settings(global_settings)
    return create_legacy_runtime_builder(
        project_root=pathlib.Path.cwd(),
        registry=registry,
        serial_device=serial_device,
        capture_device=capture_device,
        resource_io=resource_io,
        protocol=protocol,
        notification_handler=notification_handler,
        log_manager=log_manager,
    )


def execute_macro(
    runtime_builder: MacroRuntimeBuilder, macro_name: str, exec_args: dict[str, Any]
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
        log_manager.log("WARNING", "Macro execution was interrupted", component="CLI")
        return result
    if not result.ok:
        message = result.error.message if result.error is not None else "Macro execution failed"
        log_manager.log("ERROR", message, component="CLI")
        raise RuntimeError(message)
    log_manager.log("INFO", "Macro execution completed", component="CLI")
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
        configure_logging(silence=args.silence, verbose=args.verbose)

        # シングルトンの初期化
        serial_manager.auto_register_devices()
        capture_manager.auto_register_devices()

        available_serial_devices = serial_manager.list_devices()
        if not available_serial_devices:
            raise ValueError("No serial devices detected")
        if args.serial not in available_serial_devices:
            available_devices_str = ", ".join(available_serial_devices)
            raise ValueError(
                f"Serial port '{args.serial}' not found. Available devices: {available_devices_str}"
            )
        baudrate = ProtocolFactory.resolve_baudrate(args.protocol, getattr(args, "baud", None))
        serial_manager.set_active(args.serial, baudrate)

        available_capture_devices = capture_manager.list_devices()
        print(f"Available capture devices: {available_capture_devices}")
        if not available_capture_devices:
            raise ValueError("No capture devices detected")
        if args.capture not in available_capture_devices:
            available_devices_str = ", ".join(available_capture_devices)
            raise ValueError(
                f"Capture device '{args.capture}' not found. "
                f"Available devices: {available_devices_str}"
            )
        capture_manager.set_active(args.capture)

        protocol = create_protocol(args.protocol)
        runtime_builder = create_runtime_builder(protocol=protocol)

        # マクロ実行引数の解析
        exec_args = parse_define_args(args.define)

        # マクロの実行
        execute_macro(
            runtime_builder=runtime_builder,
            macro_name=args.macro_name,
            exec_args=exec_args,
        )

        return 0  # 成功時の終了コード

    except ValueError as ve:
        log_manager.log("ERROR", str(ve), component="CLI")
        print(f"エラー: {ve}")
        return 1  # エラー時の終了コード

    except Exception as e:
        log_manager.log("ERROR", f"Unhandled exception: {e}", component="CLI")
        print(f"Unexpected error: {e}")
        return 2  # 重大なエラー時の終了コード

    finally:
        # デバイスリソースを確実に解放（ゾンビプロセス防止）
        try:
            capture_manager.release_active()
        except Exception:
            pass
        try:
            serial_manager.close_active()
        except Exception:
            pass


def main():
    """
    CLIのメインエントリーポイント
    コマンドライン引数を解析してcli_mainを呼び出します
    """
    import argparse

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

    args = parser.parse_args()
    exit_code = cli_main(args)
    exit(exit_code)

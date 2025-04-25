import pathlib
import argparse
from typing import Optional, Any

from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.facade import HardwareFacade
from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.framework.core.macro.command import DefaultCommand, Command
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.hardware.protocol import (
    CH552SerialProtocol,
    SerialProtocolInterface,
)
from nyxpy.framework.core.utils.helper import parse_define_args
from nyxpy.framework.core.utils.cancellation import CancellationToken


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
    if not protocol_name:
        raise ValueError("Protocol name cannot be empty")

    match protocol_name.upper():
        case "CH552SERIAL" | "CH552":
            return CH552SerialProtocol()
        case _:
            raise ValueError(f"Unknown protocol: {protocol_name}")


def create_hardware_components(serial_port: str, capture_device: str) -> HardwareFacade:
    """
    ハードウェアコンポーネントを作成して初期化します。

    Args:
        serial_port: 使用するシリアルポートの名前
        capture_device: 使用するキャプチャデバイスの名前

    Returns:
        設定済みのHardwareFacadeインスタンス

    Raises:
        ValueError: 必要なハードウェアが初期化できない場合
    """
    # シリアルマネージャーの初期化
    serial_manager = SerialManager()
    serial_manager.auto_register_devices()

    available_serial_devices = serial_manager.list_devices()
    if not available_serial_devices:
        raise ValueError("No serial devices detected")

    if serial_port not in available_serial_devices:
        available_devices_str = ", ".join(available_serial_devices)
        raise ValueError(
            f"Serial port '{serial_port}' not found. Available devices: {available_devices_str}"
        )

    serial_manager.set_active(serial_port)

    # キャプチャマネージャーの初期化
    capture_manager = CaptureManager()
    capture_manager.auto_register_devices()

    available_capture_devices = capture_manager.list_devices()
    print(f"Available capture devices: {available_capture_devices}")

    if not available_capture_devices:
        raise ValueError("No capture devices detected")

    if capture_device not in available_capture_devices:
        available_devices_str = ", ".join(available_capture_devices)
        raise ValueError(
            f"Capture device '{capture_device}' not found. Available devices: {available_devices_str}"
        )

    capture_manager.set_active(capture_device)

    # ハードウェアファサードの作成
    return HardwareFacade(serial_manager, capture_manager)


def create_command(
    hardware_facade: HardwareFacade,
    protocol: SerialProtocolInterface,
    resources_dir: Optional[pathlib.Path] = None,
) -> Command:
    """
    指定されたコンポーネントでCommandインスタンスを作成します。

    Args:
        hardware_facade: 使用するハードウェアファサード
        protocol: 使用するプロトコル実装
        resources_dir: リソースI/O用のディレクトリ（デフォルトは'./static'）

    Returns:
        設定済みのCommandインスタンス
    """
    if resources_dir is None:
        resources_dir = pathlib.Path.cwd() / "static"

    resource_io = StaticResourceIO(resources_dir)
    cancellation_token = CancellationToken()

    return DefaultCommand(
        hardware_facade=hardware_facade,
        resource_io=resource_io,
        protocol=protocol,
        ct=cancellation_token,
    )


def execute_macro(
    executor: MacroExecutor, cmd: Command, macro_name: str, exec_args: dict[str, Any]
) -> None:
    """
    適切なエラー処理でマクロを実行します。

    Args:
        executor: MacroExecutorインスタンス
        cmd: マクロに渡すCommandインスタンス
        macro_name: 実行するマクロの名前
        exec_args: マクロに渡す引数

    Raises:
        ValueError: マクロが見つからない場合
    """
    try:
        executor.select_macro(macro_name)
    except ValueError as ve:
        log_manager.log("ERROR", str(ve), component="MacroExecutor")
        raise

    try:
        executor.execute(cmd, exec_args)
    except MacroStopException as mse:
        cmd.log("Macro execution was interrupted:", mse, level="WARNING")
    except Exception as e:
        cmd.log(
            "An unexpected error occurred during macro execution:", e, level="ERROR"
        )
        raise
    finally:
        cmd.log("Macro execution completed.")


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

        # コンポーネントの作成と設定
        hardware_facade = create_hardware_components(
            serial_port=args.serial, capture_device=args.capture
        )

        protocol = create_protocol(args.protocol)

        cmd = create_command(hardware_facade=hardware_facade, protocol=protocol)

        # マクロ実行引数の解析
        exec_args = parse_define_args(args.define)

        # マクロの実行
        execute_macro(
            executor=MacroExecutor(),
            cmd=cmd,
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

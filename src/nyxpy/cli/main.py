import pathlib
import time
import sys
import argparse
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.utils.helper import parse_define_args

def cli_main(args: argparse.Namespace) -> None:
    """
    Main entry point for the CLI application.
    This function parses command-line arguments and executes the appropriate commands.
    """

    # Configure logging based on --silence or --verbose options.
    if args.silence:
        print("Running in silent mode; logging is disabled.")
        # In an actual implementation, disable logger output.
    elif args.verbose:
        print("Verbose logging enabled.")

    # オプション値に基づいてハードウェアコンポーネントを作成する

    # args.capture を使用して CaptureManager を初期化、args.protocol を設定
    serial_manager = SerialManager(args.serial)  
    # キャプチャデバイスの管理を行う CaptureManager を初期化
    capture_manager = CaptureManager()
    capture_manager.auto_register_devices()  # 自動登録を実行
    capture_manager.set_active_device(args.capture)  # アクティブデバイスを設定

    # args.protocol に基づいてプロトコルを選択
    protocol = None 
    match args.protocol.upper():
        case "CH552Serial" | "CH552":
            from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
            protocol = CH552SerialProtocol()  # CH552プロトコルのインスタンスを作成
            
        case _:
            print(f"Unknown protocol: {args.protocol}.")
            sys.exit(1) # プロトコルが不明な場合は終了

    # リソースの入出力を管理する StaticResourceIO を初期化
    resource_io = StaticResourceIO(pathlib.Path.cwd() / "static")  # 静的リソースの入出力を管理するクラス

    # DefaultCommand インスタンスを作成
    cmd = DefaultCommand(
        serial_manager,
        capture_manager,
        resource_io,
        protocol 
    )
    
    # Create and configure the MacroExecutor
    executor = MacroExecutor()
    try:
        executor.select_macro(args.macro_name)
    except ValueError as ve:
        print(ve)
        sys.exit(1)

    # Process the macro execution arguments provided via -D
    exec_args = parse_define_args(args.define)

    # Execute the macro lifecycle (initialize, run, finalize)
    try:
        executor.execute(cmd, exec_args)
    except MacroStopException as mse:
        cmd.log("Macro execution was interrupted:", mse)
    except Exception as e:
        cmd.log("An unexpected error occurred during macro execution:", e)
    finally:
        # Additional cleanup if necessary
        time.sleep(0.1)
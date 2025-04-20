import argparse
import sys
import os
from pathlib import Path

from nyxpy.cli.run_cli import cli_main
from nyxpy.gui.run_gui import main as gui_main
from nyxpy.framework.core.global_settings import GlobalSettings

def init_app() -> int:
    """
    Initialize the workspace for GUI/CLI: create macros, snapshots, static folders.
    """
    dirs = ["macros", "snapshots", "static"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
    # Ensure macros is a package
    init_file = Path("macros") / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")
    # Initialize global settings directory and default config
    GlobalSettings()
    print(f"Initialized directories: {', '.join(dirs)}, .nyxpy")
    return 0

def parse_arguments() -> argparse.Namespace:
    """
    NyXアプリケーションのコマンドライン引数を解析します。
    
    Returns:
        解析されたコマンドライン引数
    """
    parser = argparse.ArgumentParser(
        prog="nyxpy",
        description="NyX Macro Framework for Nintendo Switch automation"
    )
    subparsers = parser.add_subparsers(
        dest="command", 
        required=True,
        help="Command to execute"
    )

    # CLIサブコマンドパーサー
    cli_parser = subparsers.add_parser(
        "cli", 
        help="Run macro via command line interface"
    )
    
    cli_parser.add_argument(
        "-s", "--serial", 
        type=str, 
        required=True,
        help="Serial port name (e.g., COM3)"
    )
    
    cli_parser.add_argument(
        "-c", "--capture", 
        type=str,
        required=True,
        help="Capture device name (index or identifier)"
    )
    
    cli_parser.add_argument(
        "-p", "--protocol", 
        type=str,
        default="CH552",
        help="Protocol name (default: CH552)"
    )
    
    cli_parser.add_argument(
        "-D", "--define", 
        action="append", 
        help="Macro execution argument in key=value format", 
        default=[]
    )
    
    cli_parser.add_argument(
        "--silence", 
        action="store_true", 
        help="Disable log output"
    )
    
    cli_parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable debug logs"
    )
    
    cli_parser.add_argument(
        "macro_name",
        help="Name of macro to execute"
    )
    
    # GUI/CLI 初期化および GUI 起動コマンド
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize workspace (create macros, snapshots, static folders)"
    )
    
    # GUI 起動サブコマンド
    gui_parser = subparsers.add_parser(
        "gui",
        help="Launch the graphical user interface"
    )
    
    # 将来: ここに他のサブコマンドを追加（例: server）
    
    return parser.parse_args()


def main() -> int:
    """
    NyXアプリケーションのメインエントリーポイント。
    
    Returns:
        終了コード（0:成功、0以外:失敗）
    """
    try:
        args = parse_arguments()
        
        if args.command == "cli":
            return cli_main(args)
        elif args.command == "init":
            return init_app()
        elif args.command == "gui":
            # Launch GUI and start Qt event loop
            gui_main()
            return 0
        else:
            # subparsers required のためここは実行されない
            print(f"Unknown command: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        print(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    # これは、スクリプトが直接実行された場合のエントリーポイントです。
    # main関数から終了コードを返します
    sys.exit(main())
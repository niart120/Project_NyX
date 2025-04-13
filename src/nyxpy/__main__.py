import argparse
import sys

from nyxpy.cli.main import cli_main  # Import the CLI main function from the cli module

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nyxpy",
        description="NyX Macro Framework"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    cli_parser = subparsers.add_parser("cli", help="Run macro via CLI")
    cli_parser.add_argument("-s", "--serial", type=str, help="Serial port name")
    cli_parser.add_argument("-c", "--capture", type=str, help="Capture device name")
    cli_parser.add_argument("-p", "--protocol", type=str, help="Protocol name")
    cli_parser.add_argument("-D", "--define", action="append", help="Macro execution argument in key=value format", default=[])
    cli_parser.add_argument("--silence", action="store_true", help="Disable log output")
    cli_parser.add_argument("--verbose", action="store_true", help="Enable debug logs")
    cli_parser.add_argument("macro_name", help="Name of macro to execute")
    return parser.parse_args()

def main():
    args = parse_arguments()

    if args.command == "cli":
        cli_main(args)

    else:
        print("Unknown command.")
        sys.exit(1)

if __name__ == "__main__":
    # This is the entry point for the script when run directly.
    # It will parse command-line arguments and execute the main function. 
    main()
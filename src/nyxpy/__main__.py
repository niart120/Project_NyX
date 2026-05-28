"""NyX package entrypoint。"""

import argparse
import sys
from pathlib import Path

from nyxpy.cli.run_cli import add_run_arguments, cli_main
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.scaffold import (
    MacroScaffoldConflictError,
    ScaffoldConflictPolicy,
    create_macro_scaffold,
)
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.framework.core.settings.workspace import ensure_workspace

_DOC_URLS = (
    ("User guide", "https://niart120.github.io/Project_NyX/user-guide/"),
    ("Macro development docs", "https://niart120.github.io/Project_NyX/macro-development/"),
    ("Agent brief", "https://niart120.github.io/Project_NyX/macro-development/agent-brief/"),
    ("API reference", "https://niart120.github.io/Project_NyX/api/framework/"),
    ("Local API help", "python -m pydoc nyxpy.framework.core.macro.command"),
)


def init_app(
    *,
    blank: bool = False,
    force: bool = False,
    project_root: Path | None = None,
) -> int:
    """Initialize the workspace and optionally create the sample macro scaffold."""
    paths = ensure_workspace(project_root or Path.cwd())
    GlobalSettings(config_dir=paths.config_dir)
    SecretsSettings(config_dir=paths.config_dir)
    dirs = ["macros", "snapshots", "resources", "runs", "logs"]
    print(f"Initialized directories: {', '.join(dirs)}, .nyxpy")
    if not blank:
        result = create_macro_scaffold(
            macro_id="sample_macro",
            project_root=paths.project_root,
            conflict_policy=(
                ScaffoldConflictPolicy.OVERWRITE if force else ScaffoldConflictPolicy.SKIP
            ),
        )
        _print_scaffold_result(result)
    return 0


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """NyXアプリケーションのコマンドライン引数を解析します。

    Args:
        argv: 解析対象の引数列。未指定の場合は `sys.argv` を使います。

    Returns:
        解析されたコマンドライン引数

    """
    parser = argparse.ArgumentParser(
        prog="nyxpy", description="NyXPy-FW macro framework for game automation"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    run_parser = subparsers.add_parser("run", help="Run macro via command line interface")
    add_run_arguments(run_parser)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize workspace and create sample macro scaffold",
    )
    init_parser.add_argument("--blank", action="store_true", help="Skip sample macro scaffold")
    init_parser.add_argument("--force", action="store_true", help="Overwrite sample macro scaffold")

    create_parser = subparsers.add_parser("create", help="Create a macro scaffold")
    create_parser.add_argument("macro_id", help="Macro id in lower_snake_case")
    create_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    create_parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Workspace root. Defaults to nearest parent containing .nyxpy",
    )

    subparsers.add_parser("docs", help="Print documentation URLs")

    subparsers.add_parser("gui", help="Launch the graphical user interface")

    return parser.parse_args(argv)


def docs_app() -> int:
    """Print public documentation URLs."""
    for label, value in _DOC_URLS:
        print(f"{label}: {value}")
    return 0


def create_app(args: argparse.Namespace) -> int:
    """Create a macro scaffold from CLI arguments."""
    result = create_macro_scaffold(
        macro_id=args.macro_id,
        project_root=args.root,
        conflict_policy=(
            ScaffoldConflictPolicy.OVERWRITE if args.force else ScaffoldConflictPolicy.FAIL
        ),
    )
    _print_scaffold_result(result)
    return 0


def gui_app() -> int:
    """Launch the GUI lazily so non-GUI commands do not import Qt."""
    from nyxpy.gui.run_gui import main as gui_main

    gui_main()
    return 0


def run_alias_main(argv: list[str] | None = None) -> int:
    """Run macro execution CLI as the `nyx-cli` alias."""
    parser = argparse.ArgumentParser(description="NyXPy-FW CLI - game automation tool")
    add_run_arguments(parser)
    return cli_main(parser.parse_args(argv))


def _print_scaffold_result(result) -> None:
    print(f"Created macro scaffold: {result.macro_id}")
    _print_paths("created", result.created, result.project_root)
    _print_paths("overwritten", result.overwritten, result.project_root)
    _print_paths("skipped", result.skipped, result.project_root)


def _print_paths(label: str, paths: tuple[Path, ...], project_root: Path) -> None:
    for path in paths:
        print(f"  {label}: {path.relative_to(project_root)}")


def main(argv: list[str] | None = None) -> int:
    """NyXアプリケーションのメインエントリーポイント。

    Args:
        argv: 解析対象の引数列。未指定の場合は `sys.argv` を使います。

    Returns:
        終了コード（0:成功、0以外:失敗）

    """
    try:
        args = parse_arguments(argv)

        if args.command == "run":
            return cli_main(args)
        elif args.command == "init":
            return init_app(blank=args.blank, force=args.force)
        elif args.command == "create":
            return create_app(args)
        elif args.command == "docs":
            return docs_app()
        elif args.command == "gui":
            return gui_app()
        else:
            # subparsers required のためここは実行されない
            print(f"Unknown command: {args.command}")
            return 1

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 130  # Standard exit code for SIGINT
    except MacroScaffoldConflictError as exc:
        print(f"エラー: {exc.message}")
        print("Use --force to overwrite existing scaffold files.")
        return 1
    except ConfigurationError as exc:
        print(f"エラー: {exc.message}")
        return 1
    except Exception:
        print("Unexpected error. See logs for details.")
        return 1


if __name__ == "__main__":
    # これは、スクリプトが直接実行された場合のエントリーポイントです。
    # main関数から終了コードを返します
    sys.exit(main())

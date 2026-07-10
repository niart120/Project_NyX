"""`nyxpy swbt` CLI。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import TextIO

from nyxpy.framework.core.hardware.swbt.config import (
    SwbtControllerConfig,
    supported_controller_models,
)
from nyxpy.framework.core.hardware.swbt.diagnostics import LoggerDiagnosticsWriter
from nyxpy.framework.core.hardware.swbt.discovery import (
    SwbtAdapterDiscoveryService,
    SwbtAdapterView,
)
from nyxpy.framework.core.hardware.swbt.factory import SwbtControllerOutputPortFactory
from nyxpy.framework.core.io.controller_config import controller_config_from_overrides
from nyxpy.framework.core.logger import LoggingComponents, create_default_logging
from nyxpy.framework.core.settings.global_settings import SettingsStore
from nyxpy.framework.core.settings.workspace import ensure_workspace, resolve_project_root

from .swbt_adapter import canonicalize_swbt_adapter


def add_swbt_arguments(subparsers: argparse._SubParsersAction) -> None:
    """top-level parser に `swbt` subcommand を追加する。"""
    swbt_parser = subparsers.add_parser("swbt", help="Manage swbt controller backend")
    swbt_subparsers = swbt_parser.add_subparsers(
        dest="swbt_command",
        required=True,
        help="swbt command to execute",
    )
    adapters_parser = swbt_subparsers.add_parser(
        "adapters",
        help="List swbt USB Bluetooth adapters",
    )
    adapters_parser.add_argument("--json", action="store_true", help="Print full JSON output")
    for command in ("pair", "reconnect"):
        lifecycle_parser = swbt_subparsers.add_parser(
            command,
            help=f"{command} swbt controller",
        )
        _add_lifecycle_options(lifecycle_parser)


def cli_main(
    args: argparse.Namespace,
    *,
    discovery_service: SwbtAdapterDiscoveryService | None = None,
    controller_factory: SwbtControllerOutputPortFactory | None = None,
    settings_store: SettingsStore | None = None,
    project_root: Path | None = None,
    stdout: TextIO | None = None,
) -> int:
    """解析済み `nyxpy swbt` 引数を実行する。"""
    output = stdout or sys.stdout
    if args.swbt_command == "adapters":
        service = discovery_service or SwbtAdapterDiscoveryService()
        adapters = service.list_adapters()
        if bool(getattr(args, "json", False)):
            _print_json(adapters, output)
        else:
            _print_adapters(adapters, output)
        return 0
    if args.swbt_command in {"pair", "reconnect"}:
        factory = controller_factory
        logging: LoggingComponents | None = None
        try:
            config = _controller_config_from_args(
                args,
                settings_store=settings_store,
                project_root=project_root,
            )
            config = canonicalize_swbt_adapter(
                config,
                discovery_service=discovery_service,
            )
            if factory is None:
                resolved_root = resolve_project_root(
                    explicit_root=project_root,
                    allow_current_as_new=False,
                )
                paths = ensure_workspace(resolved_root)
                logging = create_default_logging(base_dir=paths.logs_dir)
                factory = SwbtControllerOutputPortFactory(
                    diagnostics_writer=LoggerDiagnosticsWriter(logging.logger)
                )
            if args.swbt_command == "pair":
                factory.pair(config, timeout_sec=config.connect_timeout_sec)
                print("swbt pair completed.", file=output)
            else:
                factory.reconnect(config, timeout_sec=config.connect_timeout_sec)
                print("swbt reconnect completed.", file=output)
            return 0
        finally:
            try:
                if factory is not None:
                    factory.close()
            finally:
                if logging is not None:
                    logging.close()
    raise ValueError(f"Unknown swbt command: {args.swbt_command}")


def _print_json(adapters: tuple[SwbtAdapterView, ...], output: TextIO) -> None:
    payload = [asdict(adapter) for adapter in adapters]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=output)


def _print_adapters(adapters: tuple[SwbtAdapterView, ...], output: TextIO) -> None:
    if not adapters:
        print("No swbt USB Bluetooth adapter found.", file=output)
        return
    for adapter in adapters:
        aliases = ", ".join(adapter.aliases) if adapter.aliases else "-"
        print(f"{adapter.name}\t{adapter.display_name}\taliases: {aliases}", file=output)


def _add_lifecycle_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--adapter", default=None, help="swbt adapter override")
    parser.add_argument(
        "--controller-type",
        choices=tuple(model.settings_value for model in supported_controller_models()),
        default=None,
        help="swbt controller type override",
    )
    parser.add_argument(
        "--key-store",
        type=Path,
        default=None,
        help="swbt pairing key store path override",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="swbt connect timeout seconds override",
    )


def _controller_config_from_args(
    args: argparse.Namespace,
    *,
    settings_store: SettingsStore | None,
    project_root: Path | None,
) -> SwbtControllerConfig:
    resolved_root = resolve_project_root(
        explicit_root=project_root,
        allow_current_as_new=False,
    )
    paths = ensure_workspace(resolved_root)
    settings = settings_store or SettingsStore(config_dir=paths.config_dir, strict_load=False)
    config = controller_config_from_overrides(
        settings.snapshot(),
        workspace_root=paths.project_root,
        backend="swbt",
        swbt_adapter=getattr(args, "adapter", None),
        swbt_controller_type=getattr(args, "controller_type", None),
        swbt_key_store_path=getattr(args, "key_store", None),
        swbt_connect_timeout_sec=getattr(args, "timeout", None),
    )
    if not isinstance(config, SwbtControllerConfig):
        raise TypeError(f"expected SwbtControllerConfig, got {type(config).__name__}")
    return config

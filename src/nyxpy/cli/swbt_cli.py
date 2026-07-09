"""`nyxpy swbt` CLI。"""

import argparse
import json
import sys
from dataclasses import asdict
from typing import TextIO

from nyxpy.framework.core.hardware.swbt.discovery import (
    SwbtAdapterDiscoveryService,
    SwbtAdapterView,
)


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


def cli_main(
    args: argparse.Namespace,
    *,
    discovery_service: SwbtAdapterDiscoveryService | None = None,
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

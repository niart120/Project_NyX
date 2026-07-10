import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """--realdevice フラグを追加する。"""
    parser.addoption(
        "--realdevice",
        action="store_true",
        default=False,
        help="run tests that require real hardware devices",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """--realdevice が指定されていない場合、realdevice マーク付きテストをスキップする。"""
    if config.getoption("--realdevice"):
        return
    swbt_env_enabled = os.environ.get("NYX_REALDEVICE") == "1" and os.environ.get("NYX_SWBT") == "1"
    skip_real = pytest.mark.skip(reason="need --realdevice option to run")
    for item in items:
        if "realdevice" in item.keywords:
            if "swbt" in item.keywords and swbt_env_enabled:
                continue
            item.add_marker(skip_real)

import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "src"))
sys.path.insert(0, str(_root / "macros"))


def pytest_addoption(parser: pytest.Parser) -> None:
    """--realdevice フラグを追加する。"""
    parser.addoption(
        "--realdevice",
        action="store_true",
        default=False,
        help="run tests that require real hardware devices",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """--realdevice が指定されていない場合、realdevice マーク付きテストをスキップする。"""
    if config.getoption("--realdevice"):
        return
    skip_real = pytest.mark.skip(reason="need --realdevice option to run")
    for item in items:
        if "realdevice" in item.keywords:
            item.add_marker(skip_real)

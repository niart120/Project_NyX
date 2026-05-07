import importlib.util


def test_legacy_static_resource_io_removed() -> None:
    assert importlib.util.find_spec("nyxpy.framework.core.hardware.resource") is None

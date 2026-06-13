"""GUI capture source availability helpers."""

from importlib.util import find_spec


def is_ponkan_capture_available() -> bool:
    """Return whether ponkan-python is installed without importing it."""
    return find_spec("ponkan") is not None

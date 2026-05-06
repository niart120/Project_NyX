import importlib
import inspect
import sys

import pytest


def _parameter_names(obj) -> list[str]:
    return list(inspect.signature(obj).parameters)


def test_macro_public_import_paths_are_stable() -> None:
    from nyxpy.framework.core.constants import Button, Hat, KeyType, LStick, RStick
    from nyxpy.framework.core.macro.base import MacroBase
    from nyxpy.framework.core.macro.command import Command, DefaultCommand
    from nyxpy.framework.core.macro.exceptions import MacroStopException

    assert MacroBase.__module__ == "nyxpy.framework.core.macro.base"
    assert Command.__module__ == "nyxpy.framework.core.macro.command"
    assert DefaultCommand.__module__ == "nyxpy.framework.core.macro.command"
    assert MacroStopException.__module__ == "nyxpy.framework.core.macro.exceptions"
    assert all(value is not None for value in (Button, Hat, LStick, RStick, KeyType))


def test_macrobase_lifecycle_signature_is_stable() -> None:
    from nyxpy.framework.core.macro.base import MacroBase

    assert _parameter_names(MacroBase.initialize) == ["self", "cmd", "args"]
    assert _parameter_names(MacroBase.run) == ["self", "cmd"]
    assert _parameter_names(MacroBase.finalize) == ["self", "cmd"]

    assert inspect.signature(MacroBase.initialize).return_annotation is None
    assert inspect.signature(MacroBase.run).return_annotation is None
    assert inspect.signature(MacroBase.finalize).return_annotation is None


def test_macro_metadata_defaults_are_stable() -> None:
    from nyxpy.framework.core.macro.base import MacroBase

    assert MacroBase.description == ""
    assert MacroBase.tags == []


def test_command_public_method_names_are_stable() -> None:
    from nyxpy.framework.core.macro.command import Command

    expected_methods = {
        "press",
        "hold",
        "release",
        "wait",
        "stop",
        "log",
        "capture",
        "save_img",
        "load_img",
        "keyboard",
        "type",
        "notify",
        "touch",
        "touch_down",
        "touch_up",
        "disable_sleep",
    }

    missing = {name for name in expected_methods if not hasattr(Command, name)}
    assert missing == set()


def test_command_core_signatures_are_stable() -> None:
    from nyxpy.framework.core.macro.command import Command

    press = inspect.signature(Command.press)
    assert _parameter_names(Command.press) == ["self", "keys", "dur", "wait"]
    assert press.parameters["keys"].kind is inspect.Parameter.VAR_POSITIONAL
    assert press.parameters["dur"].default == 0.1
    assert press.parameters["wait"].default == 0.1

    log = inspect.signature(Command.log)
    assert _parameter_names(Command.log) == ["self", "values", "sep", "end", "level"]
    assert log.parameters["values"].kind is inspect.Parameter.VAR_POSITIONAL
    assert log.parameters["sep"].default == " "
    assert log.parameters["end"].default == "\n"
    assert log.parameters["level"].default == "DEBUG"

    capture = inspect.signature(Command.capture)
    assert _parameter_names(Command.capture) == ["self", "crop_region", "grayscale"]
    assert capture.parameters["crop_region"].default is None
    assert capture.parameters["grayscale"].default is False

    save_img = inspect.signature(Command.save_img)
    assert _parameter_names(Command.save_img) == ["self", "filename", "image"]
    assert save_img.parameters["filename"].default is inspect.Parameter.empty
    assert save_img.parameters["image"].default is inspect.Parameter.empty

    load_img = inspect.signature(Command.load_img)
    assert _parameter_names(Command.load_img) == ["self", "filename", "grayscale"]
    assert load_img.parameters["filename"].default is inspect.Parameter.empty
    assert load_img.parameters["grayscale"].default is False


def test_command_optional_capability_signatures_are_stable() -> None:
    from nyxpy.framework.core.macro.command import Command

    touch = inspect.signature(Command.touch)
    assert _parameter_names(Command.touch) == ["self", "x", "y", "dur", "wait"]
    assert touch.parameters["dur"].default == 0.1
    assert touch.parameters["wait"].default == 0.1

    assert _parameter_names(Command.touch_down) == ["self", "x", "y"]
    assert _parameter_names(Command.touch_up) == ["self"]

    disable_sleep = inspect.signature(Command.disable_sleep)
    assert _parameter_names(Command.disable_sleep) == ["self", "enabled"]
    assert disable_sleep.parameters["enabled"].default is True


def test_macro_stop_exception_constructor_and_catch_are_stable() -> None:
    from nyxpy.framework.core.macro.exceptions import MacroStopException

    try:
        raise MacroStopException("stop requested")
    except MacroStopException as exc:
        assert str(exc) == "stop requested"


def test_macro_executor_removed() -> None:
    sys.modules.pop("nyxpy.framework.core.macro.executor", None)
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("nyxpy.framework.core.macro.executor")

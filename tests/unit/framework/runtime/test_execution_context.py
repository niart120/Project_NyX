from types import MappingProxyType

import pytest

from tests.support.fake_execution_context import make_fake_execution_context


def test_execution_context_shallow_copies_args_and_metadata(tmp_path) -> None:
    nested = {"value": 1}
    exec_args = {"nested": nested}
    metadata = {"source": "test"}

    context = make_fake_execution_context(tmp_path, exec_args=exec_args, metadata=metadata)
    exec_args["added"] = "ignored"
    metadata["added"] = "ignored"
    nested["value"] = 2

    assert isinstance(context.exec_args, MappingProxyType)
    assert "added" not in context.exec_args
    assert "added" not in context.metadata
    assert context.exec_args["nested"]["value"] == 2
    with pytest.raises(TypeError):
        context.exec_args["new"] = "blocked"


def test_execution_context_does_not_hold_command(tmp_path) -> None:
    context = make_fake_execution_context(tmp_path)

    assert not hasattr(context, "command")

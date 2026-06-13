import sys

from nyxpy.gui import capture_availability


def test_availability_check_does_not_import_ponkan(monkeypatch):
    sys.modules.pop("ponkan", None)

    def fake_find_spec(name: str):
        assert name == "ponkan"
        return object()

    monkeypatch.setattr(capture_availability, "find_spec", fake_find_spec)

    assert capture_availability.is_ponkan_capture_available()
    assert "ponkan" not in sys.modules

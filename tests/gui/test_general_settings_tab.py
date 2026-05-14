from nyxpy.gui.dialogs.settings.general_tab import GeneralSettingsTab


class FakeSettings:
    def __init__(self, preset: str = "full_hd") -> None:
        self.data = {"gui": {"window_size_preset": preset}}

    def get(self, key: str, default=None):
        value = self.data
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def set(self, key: str, value):
        current = self.data
        parts = key.split(".")
        for part in parts[:-1]:
            nested = current.get(part)
            if not isinstance(nested, dict):
                nested = {}
                current[part] = nested
            current = nested
        current[parts[-1]] = value


def test_settings_dialog_updates_window_size_preset(qtbot) -> None:
    settings = FakeSettings("hd")
    tab = GeneralSettingsTab(settings, None)
    qtbot.addWidget(tab)

    tab.window_size_preset.setCurrentIndex(tab.window_size_preset.findData("four_k"))
    tab.apply()

    assert settings.get("gui.window_size_preset") == "four_k"


def test_settings_dialog_falls_back_to_fullhd_for_unknown_preset(qtbot) -> None:
    tab = GeneralSettingsTab(FakeSettings("removed"), None)
    qtbot.addWidget(tab)

    assert tab.window_size_preset.currentData() == "full_hd"

from types import MappingProxyType

import pytest

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.settings.global_settings import SettingsStore
from nyxpy.framework.core.settings.schema import (
    SecretBoundaryError,
    SettingField,
    SettingsSchema,
)
from nyxpy.framework.core.settings.secrets_settings import SecretsStore


def test_settings_store_applies_defaults_and_returns_immutable_snapshot(tmp_path) -> None:
    store = SettingsStore(config_dir=tmp_path)

    snapshot = store.snapshot()

    assert snapshot["serial_baud"] == 9600
    assert snapshot["capture_source_type"] == "camera"
    assert snapshot["capture_aspect_box_enabled"] is False
    assert snapshot["capture_region"] == {}
    assert snapshot["runtime"]["allow_dummy"] is False
    assert snapshot["gui"]["window_size_preset"] == "full_hd"
    assert isinstance(snapshot, MappingProxyType)
    with pytest.raises(TypeError):
        snapshot["serial_baud"] = 115200
    with pytest.raises(TypeError):
        snapshot["runtime"]["allow_dummy"] = True


def test_settings_store_requires_config_dir() -> None:
    with pytest.raises(TypeError):
        SettingsStore()
    with pytest.raises(TypeError):
        SecretsStore()


def test_settings_store_writes_only_to_config_dir(tmp_path, monkeypatch) -> None:
    cwd = tmp_path / "cwd"
    config_dir = tmp_path / "workspace" / ".nyxpy"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    SettingsStore(config_dir=config_dir)
    SecretsStore(config_dir=config_dir)

    assert (config_dir / "global.toml").exists()
    assert (config_dir / "secrets.toml").exists()
    assert not (cwd / ".nyxpy").exists()


def test_settings_store_get_set_supports_dotted_keys(tmp_path) -> None:
    store = SettingsStore(config_dir=tmp_path)

    store.set("runtime.allow_dummy", True)
    store.set("serial_baud", 115200)

    assert store.get("runtime.allow_dummy") is True
    assert store.get("serial_baud") == 115200


def test_settings_store_rejects_invalid_schema_type(tmp_path) -> None:
    (tmp_path / "global.toml").write_text('serial_baud = "fast"\n', encoding="utf-8")

    with pytest.raises(ConfigurationError) as exc_info:
        SettingsStore(config_dir=tmp_path)

    assert exc_info.value.code == "NYX_SETTINGS_SCHEMA_INVALID"


def test_settings_store_rejects_broken_toml_without_overwriting(tmp_path) -> None:
    config_path = tmp_path / "global.toml"
    config_path.write_text('serial_device = "unterminated\n', encoding="utf-8")

    with pytest.raises(ConfigurationError) as exc_info:
        SettingsStore(config_dir=tmp_path)

    assert exc_info.value.code == "NYX_SETTINGS_PARSE_FAILED"
    assert config_path.read_text(encoding="utf-8") == 'serial_device = "unterminated\n'


def test_settings_store_schema_rejects_secret_fields(tmp_path) -> None:
    schema = SettingsSchema(
        fields={
            "token": SettingField("token", str, "", secret=True),
        }
    )

    with pytest.raises(SecretBoundaryError):
        SettingsStore(config_dir=tmp_path, schema=schema)


def test_secrets_store_snapshot_masks_secret_values(tmp_path) -> None:
    store = SecretsStore(config_dir=tmp_path)
    store.set("notification.discord.enabled", True)
    store.set("notification.discord.webhook_url", "https://discord/webhook")

    snapshot = store.snapshot()
    masked = snapshot.masked()

    assert snapshot.get("notification.discord.enabled") is True
    assert snapshot.get_secret("notification.discord.webhook_url") == "https://discord/webhook"
    assert masked["notification"]["discord"]["webhook_url"] == "***"
    with pytest.raises(TypeError):
        masked["notification"]["discord"]["webhook_url"] = "leak"


def test_secrets_snapshot_rejects_non_secret_plaintext_access(tmp_path) -> None:
    store = SecretsStore(config_dir=tmp_path)

    with pytest.raises(SecretBoundaryError):
        store.snapshot().get_secret("notification.discord.enabled")

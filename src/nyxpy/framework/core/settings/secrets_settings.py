from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from threading import RLock
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.settings.schema import (
    SecretsSnapshot,
    SettingField,
    SettingsSchema,
    SettingValue,
    dotted_get,
    dotted_set,
    freeze_mapping,
)

SECRETS_SETTINGS_SCHEMA = SettingsSchema(
    fields={
        "notification.discord.enabled": SettingField("notification.discord.enabled", bool, False),
        "notification.discord.webhook_url": SettingField(
            "notification.discord.webhook_url", str, "", secret=True
        ),
        "notification.bluesky.enabled": SettingField("notification.bluesky.enabled", bool, False),
        "notification.bluesky.identifier": SettingField(
            "notification.bluesky.identifier", str, "", secret=True
        ),
        "notification.bluesky.password": SettingField(
            "notification.bluesky.password", str, "", secret=True
        ),
    }
)


class SecretsStore:
    """Schema-validated store for notification secrets and secret-adjacent flags."""

    schema: SettingsSchema

    def __init__(
        self,
        config_dir: Path | None = None,
        *,
        schema: SettingsSchema = SECRETS_SETTINGS_SCHEMA,
        filename: str = "secrets.toml",
        strict_load: bool = True,
    ) -> None:
        self.config_dir = config_dir or Path.cwd() / ".nyxpy"
        self.config_dir.mkdir(exist_ok=True)
        self.config_path = self.config_dir / filename
        self.schema = schema
        self.strict_load = strict_load
        self._lock = RLock()
        self.data: dict[str, SettingValue] = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                if self.config_path.exists():
                    loaded = tomlkit.loads(self.config_path.read_text(encoding="utf-8"))
                    self.data = self.schema.validate(loaded)
                else:
                    self.data = self.schema.defaults()
                    self.save()
            except TOMLKitError as exc:
                if self.strict_load:
                    raise ConfigurationError(
                        "failed to parse secrets file",
                        code="NYX_SETTINGS_PARSE_FAILED",
                        component=type(self).__name__,
                        details={
                            "path": self.config_path.name,
                            "exception_type": type(exc).__name__,
                        },
                        cause=exc,
                    ) from exc
                self.data = self.schema.defaults()
            except ConfigurationError:
                if self.strict_load:
                    raise
                self.data = self.schema.defaults()

    def save(self) -> None:
        with self._lock:
            self.data = self.schema.validate(self.data)
            tmp_path = self.config_path.with_suffix(f"{self.config_path.suffix}.tmp")
            tmp_path.write_text(tomlkit.dumps(self.data), encoding="utf-8")
            tmp_path.replace(self.config_path)

    def snapshot(self) -> SecretsSnapshot:
        with self._lock:
            return SecretsSnapshot(freeze_mapping(self.data), self.schema)

    def snapshot_masked(self) -> Mapping[str, SettingValue]:
        with self._lock:
            return freeze_mapping(self.schema.mask(self.data))

    def get_secret(self, key: str) -> str:
        return self.snapshot().get_secret(key)

    def validate(self) -> None:
        with self._lock:
            self.data = self.schema.validate(self.data)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return dotted_get(self.data, key, default)

    def set(self, key: str, value: SettingValue) -> None:
        with self._lock:
            dotted_set(self.data, key, value)
            self.save()


class SecretsSettings(SecretsStore):
    """Compatibility shim for .nyxpy/secrets.toml under the working directory."""

    def __init__(self, config_dir: Path | None = None) -> None:
        super().__init__(config_dir=config_dir, strict_load=False)

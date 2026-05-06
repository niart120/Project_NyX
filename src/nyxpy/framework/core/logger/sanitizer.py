from __future__ import annotations

import json
import re
from collections.abc import Mapping

from nyxpy.framework.core.logger.events import LogExtraValue


class LogSanitizer:
    def __init__(self, mask_secret_keys: list[str] | None = None) -> None:
        self.secret_fragments = tuple(
            fragment.lower()
            for fragment in (
                "password",
                "passwd",
                "secret",
                "token",
                "webhook",
                "authorization",
                "auth",
                *(mask_secret_keys or []),
            )
        )

    def sanitize_extra_for_technical(
        self, extra: Mapping[str, object] | None
    ) -> dict[str, LogExtraValue]:
        return {
            str(key): self._sanitize_value(value, key_path=(str(key),), for_user=False)
            for key, value in dict(extra or {}).items()
        }

    def sanitize_extra_for_user(
        self, extra: Mapping[str, object] | None
    ) -> dict[str, LogExtraValue]:
        sanitized: dict[str, LogExtraValue] = {}
        for key, value in dict(extra or {}).items():
            key_text = str(key)
            if self._is_secret_key((key_text,)):
                continue
            sanitized[key_text] = self._sanitize_value(value, key_path=(key_text,), for_user=True)
        return sanitized

    def mask_text(self, text: str) -> str:
        sanitized = text.replace("\r", "\\r").replace("\n", "\\n")
        for fragment in self.secret_fragments:
            sanitized = re.sub(
                rf"({re.escape(fragment)}\s*[:=]\s*)[^\s,;]+",
                r"\1***",
                sanitized,
                flags=re.IGNORECASE,
            )
        return sanitized

    def _sanitize_value(
        self,
        value: object,
        *,
        key_path: tuple[str, ...],
        for_user: bool,
    ) -> LogExtraValue:
        if self._is_secret_key(key_path):
            return None if for_user else "***"
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Mapping):
            nested: dict[str, LogExtraValue] = {}
            for child_key, child_value in value.items():
                child_path = (*key_path, str(child_key))
                if for_user and self._is_secret_key(child_path):
                    continue
                nested[str(child_key)] = self._sanitize_value(
                    child_value,
                    key_path=child_path,
                    for_user=for_user,
                )
            return nested
        if isinstance(value, (list, tuple)):
            return [
                self._sanitize_value(item, key_path=key_path, for_user=for_user) for item in value
            ]
        return self._json_safe_repr(value)

    def _json_safe_repr(self, value: object) -> str:
        text = repr(value)
        json.dumps(text, ensure_ascii=False)
        return text

    def _is_secret_key(self, key_path: tuple[str, ...]) -> bool:
        key_text = ".".join(key_path).lower()
        return any(fragment in key_text for fragment in self.secret_fragments)

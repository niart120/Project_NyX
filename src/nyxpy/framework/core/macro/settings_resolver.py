"""マクロ設定ファイル path の解決と読み込み。"""

from pathlib import Path, PurePosixPath
from typing import Any

import tomlkit
from tomlkit.exceptions import ParseError

from nyxpy.framework.core.macro.registry import MacroDefinition, MacroSettingsSource
from nyxpy.framework.core.settings.exceptions import ConfigurationError


class MacroSettingsResolver:
    r"""マクロ定義の `settings_path` を実ファイルへ解決して読み込みます。

    文字列の path は環境に依存しない表記として扱い、`\\`、絶対パス、`..` を拒否します。
    `resource:` は `resources/<macro_id>`、`project:` はプロジェクトルート、
    接頭辞なしの相対 path はマクロ本体ディレクトリを基準にします。
    """

    def __init__(self, project_root: Path) -> None:
        """Project root を保持し、設定 path 解決の基準にします。"""
        self.project_root = Path(project_root).resolve()

    def resolve(self, definition: MacroDefinition) -> MacroSettingsSource | None:
        """設定ファイルの解決結果を返します。

        `settings_path` が未指定の場合は `None` を返します。許可された root から外れる
        path は `ConfigurationError` にします。
        """
        if definition.settings_path is None:
            return None

        path = definition.settings_path
        if isinstance(path, Path):
            candidate = path if path.is_absolute() else definition.macro_root / path
            return self._source(candidate, definition.macro_root, "path")

        path_text = str(path)
        self._validate_portable_path(path_text)
        if path_text.startswith("resource:"):
            relative_path = path_text.removeprefix("resource:")
            self._validate_portable_path(relative_path)
            resource_root = self._resource_root(definition)
            return self._source(resource_root / relative_path, resource_root, "resource")
        if path_text.startswith("project:"):
            relative_path = path_text.removeprefix("project:")
            self._validate_portable_path(relative_path)
            return self._source(self.project_root / relative_path, self.project_root, "manifest")

        return self._source(definition.macro_root / path_text, definition.macro_root, "manifest")

    def _resource_root(self, definition: MacroDefinition) -> Path:
        root = definition.resources_root
        if root is not None:
            return Path(root).resolve()
        return (self.project_root / "resources" / definition.id).resolve()

    def load(self, definition: MacroDefinition) -> dict[str, Any]:
        """TOML 設定ファイルを読み込み、辞書として返します。

        ファイル未存在、読み込み失敗、TOML 解析失敗は `ConfigurationError` として
        macro_id、指定 path、解決後 path を含めて通知します。
        """
        source = self.resolve(definition)
        if source is None:
            return {}
        details = self._error_details(definition, source)
        try:
            return dict(tomlkit.loads(source.path.read_text(encoding="utf-8")))
        except FileNotFoundError as exc:
            raise ConfigurationError(
                "Macro settings file not found: "
                f"macro_id={definition.id}, settings_path={definition.settings_path!r}, "
                f"resolved_path={source.path}",
                code="NYX_SETTINGS_NOT_FOUND",
                component="MacroSettingsResolver",
                details=details,
                cause=exc,
            ) from exc
        except OSError as exc:
            raise ConfigurationError(
                "Failed to read macro settings: "
                f"macro_id={definition.id}, settings_path={definition.settings_path!r}, "
                f"resolved_path={source.path}",
                code="NYX_SETTINGS_READ_FAILED",
                component="MacroSettingsResolver",
                details={**details, "exception_type": type(exc).__name__},
                cause=exc,
            ) from exc
        except ParseError as exc:
            raise ConfigurationError(
                "Failed to parse macro settings: "
                f"macro_id={definition.id}, settings_path={definition.settings_path!r}, "
                f"resolved_path={source.path}",
                code="NYX_SETTINGS_PARSE_FAILED",
                component="MacroSettingsResolver",
                details=details,
                cause=exc,
            ) from exc

    def _error_details(
        self, definition: MacroDefinition, source: MacroSettingsSource
    ) -> dict[str, str]:
        return {
            "macro_id": definition.id,
            "settings_path": str(definition.settings_path),
            "resolved_path": str(source.path),
            "source": source.source,
        }

    def _source(self, candidate: Path, root: Path, source: str) -> MacroSettingsSource:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve(strict=False)
        try:
            resolved_candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ConfigurationError(
                f"settings path escapes allowed root: {candidate}",
                code="NYX_SETTINGS_PATH_INVALID",
            ) from exc
        return MacroSettingsSource(path=resolved_candidate, source=source)

    def _validate_portable_path(self, path_text: str) -> None:
        if not path_text or "\\" in path_text:
            raise ConfigurationError(
                f"invalid portable settings path: {path_text!r}",
                code="NYX_SETTINGS_PATH_INVALID",
            )
        path = PurePosixPath(path_text)
        if path.is_absolute() or any(part == ".." or part.strip() == ".." for part in path.parts):
            raise ConfigurationError(
                f"invalid portable settings path: {path_text!r}",
                code="NYX_SETTINGS_PATH_INVALID",
            )

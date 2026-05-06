from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol

from nyxpy.framework.core.macro.base import MacroBase

if TYPE_CHECKING:
    from nyxpy.framework.core.macro.settings_resolver import MacroSettingsResolver


class MacroLoadError(Exception):
    """マクロロードに失敗したことを表す例外。"""

    def __init__(
        self,
        message: str,
        *,
        error_type: str = "module_import_error",
        macro_id: str | None = None,
        entrypoint: str | None = None,
        module_name: str = "",
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.macro_id = macro_id
        self.entrypoint = entrypoint
        self.module_name = module_name


class AmbiguousMacroError(ValueError):
    """互換名が複数マクロへ解決される場合に送出する。"""

    def __init__(self, requested_name: str, candidates: Sequence[str]) -> None:
        self.requested_name = requested_name
        self.candidates = tuple(candidates)
        candidate_text = ", ".join(self.candidates)
        super().__init__(f"Ambiguous class name '{requested_name}'. Use macro id: {candidate_text}")


class RegistryLockTimeoutError(TimeoutError):
    """registry reload lock の取得がタイムアウトしたことを表す例外。"""


@dataclass(frozen=True)
class MacroLoadDiagnostic:
    macro_id: str | None
    entrypoint: str | None
    source_path: Path
    module_name: str
    error_type: str
    exception_type: str
    message: str
    traceback_path: Path | None = None


@dataclass(frozen=True)
class MacroSettingsSource:
    path: Path
    source: str


class MacroFactory(Protocol):
    def create(self) -> MacroBase:
        """実行ごとに新しい MacroBase インスタンスを返す。"""


@dataclass(frozen=True)
class ClassMacroFactory:
    macro_cls: type[MacroBase]

    def create(self) -> MacroBase:
        return self.macro_cls()


@dataclass(frozen=True)
class MacroDefinition:
    id: str
    aliases: tuple[str, ...]
    display_name: str
    class_name: str
    module_name: str
    macro_root: Path
    source_path: Path
    settings_path: Path | str | None
    description: str
    tags: tuple[str, ...]
    factory: MacroFactory
    manifest_path: Path | None = None
    entrypoint_kind: str = "convention"


class MacroRegistry:
    def __init__(
        self,
        project_root: Path | None = None,
        macros_dir: Path | None = None,
        settings_resolver: MacroSettingsResolver | None = None,
    ) -> None:
        if project_root is None:
            raise ValueError("project_root is required")
        self.project_root = Path(project_root).resolve()
        self.macros_dir = (
            Path(macros_dir).resolve() if macros_dir is not None else self.project_root / "macros"
        )
        self.settings_resolver = settings_resolver or self._create_settings_resolver()
        self._lock = RLock()
        self._definitions: dict[str, MacroDefinition] = {}
        self._diagnostics: tuple[MacroLoadDiagnostic, ...] = ()
        self._alias_map: dict[str, str] = {}
        self._ambiguous_aliases: dict[str, tuple[str, ...]] = {}

    @property
    def definitions(self) -> Mapping[str, MacroDefinition]:
        with self._lock:
            return dict(self._definitions)

    @property
    def diagnostics(self) -> Sequence[MacroLoadDiagnostic]:
        with self._lock:
            return tuple(self._diagnostics)

    def reload(self) -> None:
        from nyxpy.framework.core.macro.entrypoint_loader import EntryPointLoader

        loader = EntryPointLoader(project_root=self.project_root, macros_dir=self.macros_dir)
        definitions: dict[str, MacroDefinition] = {}
        diagnostics: list[MacroLoadDiagnostic] = []

        if self.macros_dir.is_dir():
            manifest_stems = {
                path.stem for path in self.macros_dir.glob("*.toml") if path.name != "macro.toml"
            }
            for entry in sorted(self.macros_dir.iterdir(), key=lambda path: path.name):
                if entry.is_dir():
                    manifest_path = entry / "macro.toml"
                    self._load_entry(
                        loader=loader,
                        source_path=manifest_path if manifest_path.exists() else entry,
                        definitions=definitions,
                        diagnostics=diagnostics,
                        manifest=manifest_path.exists(),
                    )
                elif entry.is_file() and entry.suffix == ".toml" and entry.name != "macro.toml":
                    self._load_entry(
                        loader=loader,
                        source_path=entry,
                        definitions=definitions,
                        diagnostics=diagnostics,
                        manifest=True,
                    )
                elif (
                    entry.is_file()
                    and entry.suffix == ".py"
                    and entry.name != "__init__.py"
                    and entry.stem not in manifest_stems
                ):
                    self._load_entry(
                        loader=loader,
                        source_path=entry,
                        definitions=definitions,
                        diagnostics=diagnostics,
                        manifest=False,
                    )

        alias_map, ambiguous_aliases = self._build_alias_maps(definitions)
        with self._lock:
            self._definitions = dict(definitions)
            self._diagnostics = tuple(diagnostics)
            self._alias_map = alias_map
            self._ambiguous_aliases = ambiguous_aliases

    def resolve(self, name_or_id: str) -> MacroDefinition:
        with self._lock:
            if name_or_id in self._definitions:
                return self._definitions[name_or_id]
            if name_or_id in self._ambiguous_aliases:
                raise AmbiguousMacroError(name_or_id, self._ambiguous_aliases[name_or_id])
            definition_id = self._alias_map.get(name_or_id)
            if definition_id is not None:
                return self._definitions[definition_id]
            raise ValueError(
                f"Macro '{name_or_id}' not found. Available macros: {list(self._definitions.keys())}"
            )

    def create(self, name_or_id: str) -> MacroBase:
        return self.resolve(name_or_id).factory.create()

    def list(self, include_failed: bool = False) -> Sequence[MacroDefinition]:
        with self._lock:
            return tuple(self._definitions.values())

    def get_settings(self, definition: MacroDefinition) -> dict[str, Any]:
        return self.settings_resolver.load(definition)

    def _create_settings_resolver(self) -> MacroSettingsResolver:
        from nyxpy.framework.core.macro.settings_resolver import MacroSettingsResolver

        return MacroSettingsResolver(self.project_root)

    def _load_entry(
        self,
        *,
        loader,
        source_path: Path,
        definitions: dict[str, MacroDefinition],
        diagnostics: list[MacroLoadDiagnostic],
        manifest: bool,
    ) -> None:
        try:
            definition = (
                loader.load_definition(source_path)
                if manifest
                else loader.load_convention_definition(source_path)
            )
            if definition.id in definitions:
                diagnostics.append(
                    MacroLoadDiagnostic(
                        macro_id=definition.id,
                        entrypoint=None,
                        source_path=source_path,
                        module_name=definition.module_name,
                        error_type="ambiguous_entrypoint",
                        exception_type="MacroLoadError",
                        message=f"Duplicate macro id: {definition.id}",
                    )
                )
                return
            definitions[definition.id] = definition
        except Exception as exc:
            diagnostics.append(self._diagnostic_from_exception(source_path, exc))

    def _diagnostic_from_exception(self, source_path: Path, exc: Exception) -> MacroLoadDiagnostic:
        return MacroLoadDiagnostic(
            macro_id=getattr(exc, "macro_id", None),
            entrypoint=getattr(exc, "entrypoint", None),
            source_path=source_path,
            module_name=getattr(exc, "module_name", ""),
            error_type=getattr(exc, "error_type", "module_import_error"),
            exception_type=type(exc).__name__,
            message=str(exc),
        )

    def _build_alias_maps(
        self, definitions: Mapping[str, MacroDefinition]
    ) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
        alias_map: dict[str, str] = {}
        grouped_aliases: dict[str, list[str]] = defaultdict(list)

        for definition in definitions.values():
            for alias in definition.aliases:
                if alias != definition.id:
                    grouped_aliases[alias].append(definition.id)

        ambiguous_aliases = {
            alias: tuple(sorted(ids)) for alias, ids in grouped_aliases.items() if len(ids) > 1
        }
        for alias, ids in grouped_aliases.items():
            if alias not in ambiguous_aliases:
                alias_map[alias] = ids[0]

        return alias_map, ambiguous_aliases

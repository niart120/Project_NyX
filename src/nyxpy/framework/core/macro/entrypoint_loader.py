from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import tomlkit

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.registry import (
    ClassMacroFactory,
    MacroDefinition,
    MacroLoadError,
)


class EntryPointLoader:
    def __init__(self, project_root: Path, macros_dir: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.macros_dir = Path(macros_dir).resolve()
        self.import_root = self.macros_dir.parent
        self.module_prefix = self.macros_dir.name

    def load_definition(self, manifest_path: Path) -> MacroDefinition:
        manifest_path = manifest_path.resolve()
        try:
            manifest = tomlkit.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MacroLoadError(
                f"Failed to parse manifest: {exc}",
                error_type="manifest_parse_error",
                module_name="",
            ) from exc

        macro_table = manifest.get("macro")
        if not isinstance(macro_table, dict):
            raise MacroLoadError(
                "macro.toml must contain [macro]",
                error_type="manifest_parse_error",
                module_name="",
            )

        entrypoint = macro_table.get("entrypoint")
        macro_id = str(macro_table.get("id") or self._default_id_for_manifest(manifest_path))
        if not entrypoint:
            raise MacroLoadError(
                "macro.toml [macro].entrypoint is required",
                error_type="entrypoint_not_found",
                macro_id=macro_id,
                module_name="",
            )

        module_name, class_name = self._parse_entrypoint(str(entrypoint))
        module = self._import_module(module_name)
        macro_cls = self._get_macro_class(module, class_name, str(entrypoint), macro_id)
        return self._definition_from_class(
            macro_cls=macro_cls,
            macro_id=macro_id,
            module_name=module_name,
            macro_root=manifest_path.parent,
            source_path=Path(inspect.getfile(macro_cls)).resolve(),
            manifest_path=manifest_path,
            entrypoint_kind="manifest",
            settings_path=macro_table.get("settings"),
            display_name=macro_table.get("display_name"),
            description=macro_table.get("description"),
            tags=macro_table.get("tags"),
        )

    def load_convention_definition(self, source_path: Path) -> MacroDefinition:
        source_path = source_path.resolve()
        if source_path.is_file():
            module_name = f"{self.module_prefix}.{source_path.stem}"
            module = self._import_module(module_name)
            macro_cls = self._single_local_macro_class(module, source_path)
            macro_root = source_path.parent
            default_id = source_path.stem
        elif source_path.is_dir():
            macro_py = source_path / "macro.py"
            init_py = source_path / "__init__.py"
            macro_candidates = self._module_candidates(macro_py) if macro_py.exists() else []
            init_candidates = self._module_candidates(init_py) if init_py.exists() else []
            if macro_candidates and init_candidates:
                raise MacroLoadError(
                    "Convention discovery found MacroBase classes in both macro.py and __init__.py",
                    error_type="ambiguous_entrypoint",
                    module_name=f"{self.module_prefix}.{source_path.name}",
                )
            candidates = macro_candidates or init_candidates
            if len(candidates) != 1:
                raise MacroLoadError(
                    f"Convention discovery requires exactly one local MacroBase subclass, found {len(candidates)}",
                    error_type="ambiguous_entrypoint",
                    module_name=f"{self.module_prefix}.{source_path.name}",
                )
            macro_cls, module_name = candidates[0]
            macro_root = source_path
            default_id = source_path.name
        else:
            raise MacroLoadError(
                f"Macro source does not exist: {source_path}",
                error_type="entrypoint_not_found",
            )

        return self._definition_from_class(
            macro_cls=macro_cls,
            macro_id=str(getattr(macro_cls, "macro_id", default_id)),
            module_name=module_name,
            macro_root=macro_root,
            source_path=Path(inspect.getfile(macro_cls)).resolve(),
            manifest_path=None,
            entrypoint_kind="convention",
            settings_path=getattr(macro_cls, "settings_path", None),
            display_name=getattr(macro_cls, "display_name", None),
            description=getattr(macro_cls, "description", None),
            tags=getattr(macro_cls, "tags", None),
        )

    def _module_candidates(self, module_path: Path) -> list[tuple[type[MacroBase], str]]:
        module_name = self._module_name_for_file(module_path)
        module = self._import_module(module_name)
        return [(macro_cls, module_name) for macro_cls in self._local_macro_classes(module)]

    def _single_local_macro_class(self, module: ModuleType, source_path: Path) -> type[MacroBase]:
        candidates = self._local_macro_classes(module)
        if len(candidates) != 1:
            raise MacroLoadError(
                f"Convention discovery requires exactly one local MacroBase subclass, found {len(candidates)}",
                error_type="ambiguous_entrypoint",
                module_name=module.__name__,
            )
        return candidates[0]

    def _local_macro_classes(self, module: ModuleType) -> list[type[MacroBase]]:
        result: list[type[MacroBase]] = []
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if obj is MacroBase or obj.__module__ != module.__name__:
                continue
            if issubclass(obj, MacroBase):
                result.append(obj)
        return result

    def _import_module(self, module_name: str) -> ModuleType:
        with self._temporary_sys_path(self.import_root):
            self._clear_stale_module(module_name)
            importlib.invalidate_caches()
            try:
                return importlib.import_module(module_name)
            except Exception as exc:
                raise MacroLoadError(
                    f"Failed to import {module_name}: {exc}",
                    error_type="module_import_error",
                    module_name=module_name,
                ) from exc

    def _get_macro_class(
        self, module: ModuleType, class_name: str, entrypoint: str, macro_id: str
    ) -> type[MacroBase]:
        obj = getattr(module, class_name, None)
        if obj is None:
            raise MacroLoadError(
                f"Entrypoint class not found: {entrypoint}",
                error_type="entrypoint_not_found",
                macro_id=macro_id,
                entrypoint=entrypoint,
                module_name=module.__name__,
            )
        if not inspect.isclass(obj) or not issubclass(obj, MacroBase) or obj is MacroBase:
            raise MacroLoadError(
                f"Entrypoint is not a MacroBase subclass: {entrypoint}",
                error_type="invalid_macro_class",
                macro_id=macro_id,
                entrypoint=entrypoint,
                module_name=module.__name__,
            )
        return obj

    def _definition_from_class(
        self,
        *,
        macro_cls: type[MacroBase],
        macro_id: str,
        module_name: str,
        macro_root: Path,
        source_path: Path,
        manifest_path: Path | None,
        entrypoint_kind: str,
        settings_path,
        display_name,
        description,
        tags,
    ) -> MacroDefinition:
        class_name = macro_cls.__name__
        description_value = self._description(macro_cls, description)
        tags_value = tuple(
            str(tag) for tag in (tags if tags is not None else getattr(macro_cls, "tags", ()))
        )
        return MacroDefinition(
            id=macro_id,
            aliases=(class_name,),
            display_name=str(
                display_name or getattr(macro_cls, "display_name", None) or class_name
            ),
            class_name=class_name,
            module_name=module_name,
            macro_root=macro_root.resolve(),
            source_path=source_path.resolve(),
            settings_path=settings_path,
            description=description_value,
            tags=tags_value,
            factory=ClassMacroFactory(macro_cls),
            manifest_path=manifest_path.resolve() if manifest_path is not None else None,
            entrypoint_kind=entrypoint_kind,
        )

    def _description(self, macro_cls: type[MacroBase], explicit_description) -> str:
        if explicit_description is not None:
            return str(explicit_description)
        class_description = getattr(macro_cls, "description", None)
        if class_description:
            return str(class_description)
        return inspect.cleandoc(macro_cls.__doc__ or "")

    def _module_name_for_file(self, source_path: Path) -> str:
        relative_path = source_path.resolve().relative_to(self.import_root)
        return ".".join(relative_path.with_suffix("").parts)

    def _parse_entrypoint(self, entrypoint: str) -> tuple[str, str]:
        if ":" not in entrypoint:
            raise MacroLoadError(
                f"Entrypoint must be 'module:ClassName': {entrypoint}",
                error_type="entrypoint_not_found",
                entrypoint=entrypoint,
                module_name="",
            )
        module_name, class_name = entrypoint.split(":", 1)
        if not module_name or not class_name:
            raise MacroLoadError(
                f"Entrypoint must be 'module:ClassName': {entrypoint}",
                error_type="entrypoint_not_found",
                entrypoint=entrypoint,
                module_name=module_name,
            )
        return module_name, class_name

    def _default_id_for_manifest(self, manifest_path: Path) -> str:
        return (
            manifest_path.parent.name if manifest_path.name == "macro.toml" else manifest_path.stem
        )

    def _clear_stale_module(self, module_name: str) -> None:
        stale_keys = [
            key for key in sys.modules if key == module_name or key.startswith(module_name + ".")
        ]
        for key in stale_keys:
            del sys.modules[key]

    @contextmanager
    def _temporary_sys_path(self, path: Path) -> Iterator[None]:
        path_text = str(path)
        added = path_text not in sys.path
        if added:
            sys.path.insert(0, path_text)
        try:
            yield
        finally:
            if added:
                try:
                    sys.path.remove(path_text)
                except ValueError as exc:
                    raise MacroLoadError(
                        f"Failed to restore sys.path: {path_text}",
                        error_type="sys_path_restore_error",
                    ) from exc

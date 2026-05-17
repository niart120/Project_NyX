from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO, Protocol

import cv2

from nyxpy.framework.core.macro.exceptions import ResourceError


class ResourceKind(StrEnum):
    ASSET = "asset"
    OUTPUT = "output"


class ResourceSource(StrEnum):
    STANDARD_ASSETS = "standard_assets"
    MACRO_PACKAGE = "macro_package"
    PACKAGE_RESOURCE = "package_resource"
    RUN_OUTPUTS = "run_outputs"


class OverwritePolicy(StrEnum):
    ERROR = "error"
    REPLACE = "replace"
    UNIQUE = "unique"


class ResourcePathError(ResourceError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_PATH_INVALID")),
            component=str(kwargs.pop("component", "ResourcePathGuard")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceNotFoundError(ResourceError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_READ_FAILED")),
            component=str(kwargs.pop("component", "ResourceStorePort")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceReadError(ResourceError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_READ_FAILED")),
            component=str(kwargs.pop("component", "ResourceStorePort")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceWriteError(ResourceError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_WRITE_FAILED")),
            component=str(kwargs.pop("component", "RunArtifactStore")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceAlreadyExistsError(ResourceWriteError):
    pass


class ResourceConfigurationError(ResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="NYX_RESOURCE_PATH_INVALID",
            component="ResourceConfiguration",
        )


@dataclass(frozen=True)
class MacroResourceScope:
    project_root: Path
    macro_id: str
    macro_root: Path | None
    assets_roots: tuple[Path, ...]

    @classmethod
    def from_definition(cls, definition, project_root: Path) -> MacroResourceScope:
        project_root = Path(project_root).resolve()
        macro_id = str(definition.id)
        _validate_resource_identifier(macro_id)
        resources_root = getattr(definition, "resources_root", None)
        standard_root = (
            Path(resources_root).resolve()
            if resources_root is not None
            else project_root / "resources" / macro_id
        )
        assets_roots = [standard_root / "assets"]
        macro_root = (
            Path(definition.macro_root).resolve() if definition.macro_root is not None else None
        )
        if macro_root is not None:
            assets_roots.append(macro_root / "assets")
        return cls(
            project_root=project_root,
            macro_id=macro_id,
            macro_root=macro_root,
            assets_roots=tuple(assets_roots),
        )

    def candidate_asset_paths(
        self, name: str | Path, guard: ResourcePathGuard | None = None
    ) -> tuple[Path, ...]:
        path_guard = guard or DefaultResourcePathGuard()
        return tuple(path_guard.resolve_under_root(root, name) for root in self.assets_roots)


@dataclass(frozen=True)
class ResourceRef:
    kind: ResourceKind
    source: ResourceSource
    path: Path
    relative_path: Path
    macro_id: str
    run_id: str | None = None


class ResourcePathGuard(Protocol):
    def resolve_under_root(self, root: Path, name: str | Path) -> Path: ...


class DefaultResourcePathGuard:
    _RESERVED_WINDOWS_NAMES = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    def resolve_under_root(self, root: Path, name: str | Path) -> Path:
        if not isinstance(name, (str, PathLike)):
            raise ResourcePathError("resource path must be str or Path")
        root_path = Path(root)
        root_resolved = root_path.resolve(strict=root_path.exists())
        name_text = str(name)
        if not name_text or name_text in {".", ""}:
            raise ResourcePathError("resource path is empty")
        if name_text.startswith("\\\\") or name_text.startswith(("\\", "/")):
            raise ResourcePathError("resource path must be relative")
        if len(name_text) >= 2 and name_text[1] == ":":
            raise ResourcePathError("resource path must not contain a drive")

        raw_parts = tuple(name_text.replace("\\", "/").split("/"))
        if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
            raise ResourcePathError("resource path must not escape the resource root")
        if any(self._is_reserved_windows_name(part) for part in raw_parts):
            raise ResourcePathError("resource path contains a reserved name")

        relative_path = Path(*raw_parts)
        if relative_path.is_absolute():
            raise ResourcePathError("resource path must be relative")

        candidate = (root_resolved / relative_path).resolve(strict=False)
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise ResourcePathError("resource path escapes the resource root") from exc
        return candidate

    def _is_reserved_windows_name(self, part: str) -> bool:
        return part.split(".", maxsplit=1)[0].upper() in self._RESERVED_WINDOWS_NAMES


class ResourceStorePort(ABC):
    @abstractmethod
    def resolve_asset_path(self, name: str | Path) -> ResourceRef: ...

    @abstractmethod
    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...

    def close(self) -> None:
        pass


class RunArtifactStore(ABC):
    @abstractmethod
    def resolve_output_path(self, name: str | Path) -> ResourceRef: ...

    @abstractmethod
    def save_image(
        self,
        name: str | Path,
        image: cv2.typing.MatLike,
        *,
        overwrite: OverwritePolicy = OverwritePolicy.REPLACE,
        atomic: bool = True,
    ) -> ResourceRef: ...

    @abstractmethod
    def open_output(
        self,
        name: str | Path,
        mode: str = "xb",
        *,
        overwrite: OverwritePolicy = OverwritePolicy.ERROR,
        atomic: bool = True,
    ) -> BinaryIO: ...

    def close(self) -> None:
        pass


class LocalResourceStore(ResourceStorePort):
    def __init__(
        self,
        scope: MacroResourceScope,
        guard: ResourcePathGuard | None = None,
    ) -> None:
        self.scope = scope
        self.guard = guard or DefaultResourcePathGuard()

    def resolve_asset_path(self, name: str | Path) -> ResourceRef:
        for index, root in enumerate(self.scope.assets_roots):
            candidate = self.guard.resolve_under_root(root, name)
            if candidate.exists():
                return ResourceRef(
                    kind=ResourceKind.ASSET,
                    source=(
                        ResourceSource.STANDARD_ASSETS
                        if index == 0
                        else ResourceSource.MACRO_PACKAGE
                    ),
                    path=candidate,
                    relative_path=candidate.relative_to(
                        Path(root).resolve(strict=Path(root).exists())
                    ),
                    macro_id=self.scope.macro_id,
                )
        raise ResourceNotFoundError(f"resource not found: {name}")

    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike:
        ref = self.resolve_asset_path(name)
        flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
        image = cv2.imread(str(ref.path), flag)
        if image is None:
            raise ResourceReadError(f"failed to read image: {ref.relative_path}")
        return image


class LocalRunArtifactStore(RunArtifactStore):
    def __init__(
        self,
        output_root: Path,
        *,
        macro_id: str,
        run_id: str,
        overwrite: OverwritePolicy = OverwritePolicy.REPLACE,
        atomic: bool = True,
        guard: ResourcePathGuard | None = None,
    ) -> None:
        self.output_root = Path(output_root).resolve(strict=False)
        self.macro_id = macro_id
        self.run_id = run_id
        self.overwrite = overwrite
        self.atomic = atomic
        self.guard = guard or DefaultResourcePathGuard()

    def resolve_output_path(self, name: str | Path) -> ResourceRef:
        path = self.guard.resolve_under_root(self.output_root, name)
        return self._ref(path)

    def save_image(
        self,
        name: str | Path,
        image: cv2.typing.MatLike,
        *,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        final_ref = self._prepare_output(name, overwrite or self.overwrite)
        use_atomic = self.atomic if atomic is None else atomic
        if use_atomic:
            self._write_image_atomic(final_ref.path, image)
        else:
            self._write_image(final_ref.path, image)
        return final_ref

    def open_output(
        self,
        name: str | Path,
        mode: str = "xb",
        *,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> BinaryIO:
        if "b" not in mode:
            raise ResourceConfigurationError("open_output requires a binary mode")
        if not any(flag in mode for flag in ("w", "x", "a")):
            raise ResourceConfigurationError("open_output requires a writable mode")

        policy = overwrite or OverwritePolicy.ERROR
        final_ref = self._prepare_output(name, policy)
        use_atomic = self.atomic if atomic is None else atomic
        if not use_atomic:
            open_mode = mode
            if "x" in open_mode and policy is OverwritePolicy.REPLACE:
                open_mode = open_mode.replace("x", "w")
            if "x" in open_mode and final_ref.path.exists():
                raise ResourceAlreadyExistsError(
                    f"output already exists: {final_ref.relative_path}"
                )
            return final_ref.path.open(open_mode)

        if "a" in mode:
            raise ResourceConfigurationError("atomic append output is not supported")
        temp_path = self._create_temp_path(final_ref.path)
        temp_mode = "w+b" if "+" in mode else "wb"
        return _AtomicOutputFile(temp_path.open(temp_mode), temp_path, final_ref.path)

    def _prepare_output(self, name: str | Path, policy: OverwritePolicy) -> ResourceRef:
        ref = self.resolve_output_path(name)
        ref.path.parent.mkdir(parents=True, exist_ok=True)
        guarded_path = self.guard.resolve_under_root(self.output_root, ref.relative_path)
        if policy is OverwritePolicy.ERROR and guarded_path.exists():
            raise ResourceAlreadyExistsError(f"output already exists: {ref.relative_path}")
        if policy is OverwritePolicy.UNIQUE:
            guarded_path = self._unique_path(guarded_path)
        return self._ref(guarded_path)

    def _write_image_atomic(self, final_path: Path, image: cv2.typing.MatLike) -> None:
        temp_path = self._create_temp_path(final_path)
        try:
            self._write_image(temp_path, image)
            temp_path.replace(final_path)
            if not final_path.exists():
                raise ResourceWriteError(f"output was not created: {final_path.name}")
        except Exception as exc:
            self._cleanup_temp(temp_path)
            if isinstance(exc, ResourceWriteError):
                raise
            raise ResourceWriteError(
                f"failed to write output: {final_path.name}", cause=exc
            ) from exc

    def _write_image(self, path: Path, image: cv2.typing.MatLike) -> None:
        if not cv2.imwrite(str(path), image):
            raise ResourceWriteError(f"failed to write output: {path.name}")
        if not path.exists():
            raise ResourceWriteError(f"output was not created: {path.name}")

    def _create_temp_path(self, final_path: Path) -> Path:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            dir=final_path.parent,
            prefix=f".{final_path.stem}.",
            suffix=final_path.suffix,
            delete=False,
        ) as temp:
            return Path(temp.name)

    def _unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        for index in range(1, 10_000):
            candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
            if not candidate.exists():
                return candidate
        raise ResourceWriteError(f"failed to find unique output path: {path.name}")

    def _cleanup_temp(self, temp_path: Path) -> None:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass

    def _ref(self, path: Path) -> ResourceRef:
        output_root = self.output_root.resolve(strict=self.output_root.exists())
        return ResourceRef(
            kind=ResourceKind.OUTPUT,
            source=ResourceSource.RUN_OUTPUTS,
            path=path,
            relative_path=path.relative_to(output_root),
            macro_id=self.macro_id,
            run_id=self.run_id,
        )


class _AtomicOutputFile(AbstractContextManager):
    def __init__(self, file: BinaryIO, temp_path: Path, final_path: Path) -> None:
        self._file = file
        self._temp_path = temp_path
        self._final_path = final_path
        self._closed = False

    def __getattr__(self, name: str):
        return getattr(self._file, name)

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._file)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._file.close()
            self._temp_path.replace(self._final_path)
        except Exception:
            if self._temp_path.exists():
                self._temp_path.unlink()
            raise

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_type is not None:
            self._closed = True
            self._file.close()
            if self._temp_path.exists():
                self._temp_path.unlink()
            return False
        self.close()
        return False


def _validate_resource_identifier(value: str) -> None:
    if not value or any(separator in value for separator in ("\\", "/", ":")):
        raise ResourceConfigurationError(f"invalid macro resource id: {value!r}")

"""マクロ資材と実行成果物の local file store。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

import cv2

from nyxpy.framework.core.macro.exceptions import ResourceError


class ResourceKind(StrEnum):
    """資材参照の用途種別。"""

    ASSET = "asset"
    ARTIFACT = "artifact"


class ResourceSource(StrEnum):
    """資材または成果物が解決された元の場所。"""

    STANDARD_ASSETS = "standard_assets"
    MACRO_PACKAGE = "macro_package"
    PACKAGE_RESOURCE = "package_resource"
    ARTIFACT_RUN = "artifact_run"
    ARTIFACT_STABLE = "artifact_stable"


class OverwritePolicy(StrEnum):
    """成果物保存時の既存ファイル処理方針。"""

    ERROR = "error"
    REPLACE = "replace"
    UNIQUE = "unique"


class ArtifactScope(StrEnum):
    """Artifact の保存・読み戻し基準。"""

    RUN = "run"
    STABLE = "stable"


class ResourcePathError(ResourceError):
    """資材パスが root 外や不正名を指す場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """不正 path の詳細を `ResourceError` として初期化します。"""
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_PATH_INVALID")),
            component=str(kwargs.pop("component", "ResourcePathGuard")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceNotFoundError(ResourceError):
    """指定された資材が探索 root に存在しない場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """資材読み込み失敗 code を持つ `ResourceError` として初期化します。"""
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_READ_FAILED")),
            component=str(kwargs.pop("component", "ResourceStorePort")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceReadError(ResourceError):
    """資材ファイルの読み込みに失敗した場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """資材読み込み失敗の詳細を `ResourceError` として初期化します。"""
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_READ_FAILED")),
            component=str(kwargs.pop("component", "ResourceStorePort")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceWriteError(ResourceError):
    """実行成果物の書き込みに失敗した場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """成果物書き込み失敗の詳細を `ResourceError` として初期化します。"""
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_RESOURCE_WRITE_FAILED")),
            component=str(kwargs.pop("component", "RunArtifactStore")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceAlreadyExistsError(ResourceWriteError):
    """上書き禁止の出力先が既に存在する場合の例外。"""

    pass


class ResourceConfigurationError(ResourceError):
    """資材 store の設定や出力 mode が不正な場合の例外。"""

    def __init__(self, message: str) -> None:
        """資材設定不正の code を持つ `ResourceError` として初期化します。"""
        super().__init__(
            message,
            code="NYX_RESOURCE_PATH_INVALID",
            component="ResourceConfiguration",
        )


@dataclass(frozen=True)
class MacroResourceScope:
    """マクロごとの資材探索範囲を表します。

    標準資材は `resources/<macro_id>/assets` に置きます。マクロ本体パッケージ内の
    `assets` は、サンプルや配布形態で資材を同梱する場合の代替探索先です。
    """

    project_root: Path
    macro_id: str
    macro_root: Path | None
    assets_roots: tuple[Path, ...]

    @classmethod
    def from_definition(cls, definition, project_root: Path) -> MacroResourceScope:
        """マクロ定義から標準資材 root と代替資材 root を組み立てます。"""
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
        """資材名に対応する候補パスを探索順に返します。"""
        path_guard = guard or DefaultResourcePathGuard()
        return tuple(path_guard.resolve_under_root(root, name) for root in self.assets_roots)

    @property
    def artifacts_root(self) -> Path:
        """標準 resource root 配下の artifact 保存 root を返します。"""
        return self.assets_roots[0].parent / "artifacts"


@dataclass(frozen=True)
class ResourceRef:
    """解決済み資材または実行成果物の参照情報です。"""

    kind: ResourceKind
    source: ResourceSource
    path: Path
    relative_path: Path
    macro_id: str
    run_id: str | None = None


class ResourcePathGuard(Protocol):
    """資材パスが許可された root の内側に収まることを保証する protocol です。"""

    def resolve_under_root(self, root: Path, name: str | Path) -> Path: ...


class DefaultResourcePathGuard:
    """相対パスだけを許可し、root 外への脱出と Windows 予約名を拒否します。"""

    _RESERVED_WINDOWS_NAMES = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    def resolve_under_root(self, root: Path, name: str | Path) -> Path:
        """資材名を root 配下の安全な絶対パスへ解決します。"""
        root_path = Path(root)
        if not isinstance(name, (str, PathLike)):
            raise self._path_error(
                "resource path must be str or Path",
                root=root_path,
                name=name,
                reason="invalid_type",
            )
        root_resolved = root_path.resolve(strict=root_path.exists())
        name_text = str(name)
        if not name_text or name_text in {".", ""}:
            raise self._path_error(
                "resource path is empty",
                root=root_path,
                name=name,
                reason="empty",
            )
        if name_text.startswith("\\\\") or name_text.startswith(("\\", "/")):
            raise self._path_error(
                "resource path must be relative",
                root=root_path,
                name=name,
                reason="absolute",
            )
        if len(name_text) >= 2 and name_text[1] == ":":
            raise self._path_error(
                "resource path must not contain a drive",
                root=root_path,
                name=name,
                reason="drive",
            )

        raw_parts = tuple(name_text.replace("\\", "/").split("/"))
        if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
            raise self._path_error(
                "resource path must not escape the resource root",
                root=root_path,
                name=name,
                reason="path_traversal",
            )
        if any(self._is_reserved_windows_name(part) for part in raw_parts):
            raise self._path_error(
                "resource path contains a reserved name",
                root=root_path,
                name=name,
                reason="reserved_name",
            )

        relative_path = Path(*raw_parts)
        if relative_path.is_absolute():
            raise self._path_error(
                "resource path must be relative",
                root=root_path,
                name=name,
                reason="absolute",
            )

        candidate = (root_resolved / relative_path).resolve(strict=False)
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise self._path_error(
                "resource path escapes the resource root",
                root=root_path,
                name=name,
                reason="root_escape",
            ) from exc
        return candidate

    def _is_reserved_windows_name(self, part: str) -> bool:
        return part.split(".", maxsplit=1)[0].upper() in self._RESERVED_WINDOWS_NAMES

    def _path_error(
        self,
        message: str,
        *,
        root: Path,
        name: object,
        reason: str,
    ) -> ResourcePathError:
        return ResourcePathError(
            message,
            details={
                "root": str(root),
                "name": str(name),
                "reason": reason,
            },
        )


class ResourceStorePort(ABC):
    """読み取り専用のマクロ資材 store です。

    実装は資材名を安全なパスへ解決し、標準資材 root とマクロパッケージ内の
    `assets` を探索対象にできます。
    """

    @abstractmethod
    def resolve_asset_path(self, name: str | Path) -> ResourceRef: ...

    @abstractmethod
    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...

    @abstractmethod
    def load_blob(self, name: str | Path) -> bytes: ...

    def close(self) -> None:
        pass


class RunArtifactStore(ABC):
    """マクロ実行ごとの artifact store です。

    保存先は resources/<macro_id>/artifacts 配下に限定します。
    実装は scope 解決、親ディレクトリ作成、上書き方針、atomic write、
    path guard、保存済み参照の記録を扱います。
    """

    @property
    @abstractmethod
    def artifact_dir_name(self) -> str: ...

    @abstractmethod
    def resolve_artifact_path(
        self,
        name: str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> ResourceRef: ...

    @abstractmethod
    def save_image(
        self,
        name: str | Path,
        image: cv2.typing.MatLike,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef: ...

    @abstractmethod
    def save_blob(
        self,
        name: str | Path,
        data: bytes,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef: ...

    @abstractmethod
    def load_image(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike: ...

    @abstractmethod
    def load_blob(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes: ...

    @abstractmethod
    def snapshot(self) -> tuple[ResourceRef, ...]: ...

    @property
    @abstractmethod
    def artifacts_overflow_count(self) -> int: ...

    def close(self) -> None:
        pass


class LocalResourceStore(ResourceStorePort):
    """ローカルファイルシステム上のマクロ資材 store です。"""

    def __init__(
        self,
        scope: MacroResourceScope,
        guard: ResourcePathGuard | None = None,
    ) -> None:
        """資材探索範囲と path guard を保持します。"""
        self.scope = scope
        self.guard = guard or DefaultResourcePathGuard()

    def resolve_asset_path(self, name: str | Path) -> ResourceRef:
        """探索順に資材を解決し、見つからない場合は `ResourceNotFoundError` にします。"""
        candidate_paths: list[str] = []
        for index, root in enumerate(self.scope.assets_roots):
            candidate = self.guard.resolve_under_root(root, name)
            candidate_paths.append(str(candidate))
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
        raise ResourceNotFoundError(
            f"resource not found: {name}",
            details={
                "macro_id": self.scope.macro_id,
                "name": str(name),
                "candidate_paths": candidate_paths,
            },
        )

    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike:
        """画像資材を OpenCV 画像として読み込みます。"""
        ref = self.resolve_asset_path(name)
        flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
        image = cv2.imread(str(ref.path), flag)
        if image is None:
            raise ResourceReadError(
                f"failed to read image: {ref.relative_path}",
                details={
                    "macro_id": ref.macro_id,
                    "name": str(name),
                    "path": str(ref.path),
                    "relative_path": str(ref.relative_path),
                    "source": str(ref.source),
                },
            )
        return image

    def load_blob(self, name: str | Path) -> bytes:
        """任意 bytes 資材を読み込みます。"""
        ref = self.resolve_asset_path(name)
        try:
            return ref.path.read_bytes()
        except OSError as exc:
            raise ResourceReadError(
                f"failed to read blob: {ref.relative_path}",
                details={
                    "macro_id": ref.macro_id,
                    "name": str(name),
                    "path": str(ref.path),
                    "relative_path": str(ref.relative_path),
                    "source": str(ref.source),
                },
                cause=exc,
            ) from exc


class LocalRunArtifactStore(RunArtifactStore):
    """ローカルファイルシステム上の artifact store です。"""

    def __init__(
        self,
        artifacts_root: Path,
        *,
        macro_id: str,
        run_id: str,
        artifact_dir_name: str,
        overwrite: OverwritePolicy = OverwritePolicy.REPLACE,
        atomic: bool = True,
        tracked_limit: int = 65535,
        guard: ResourcePathGuard | None = None,
    ) -> None:
        """Artifact root、run 情報、上書き方針、path guard を保持します。"""
        if tracked_limit < 0:
            raise ResourceConfigurationError(
                "tracked artifact limit must be greater than or equal to 0"
            )
        _validate_artifact_dir_name(artifact_dir_name)
        self.artifacts_root = Path(artifacts_root).resolve(strict=False)
        self.macro_id = macro_id
        self.run_id = run_id
        self._artifact_dir_name = artifact_dir_name
        self.overwrite = overwrite
        self.atomic = atomic
        self.tracked_limit = tracked_limit
        self.guard = guard or DefaultResourcePathGuard()
        self._tracked_refs: list[ResourceRef] = []
        self._tracked_paths: dict[Path, ResourceRef] = {}
        self._artifacts_overflow_count = 0

    @property
    def artifact_dir_name(self) -> str:
        """実行ごとの artifact directory 名を返します。"""
        return self._artifact_dir_name

    @property
    def artifacts_overflow_count(self) -> int:
        """保持上限を超えて `RunResult.artifacts` から落とした件数を返します。"""
        return self._artifacts_overflow_count

    def snapshot(self) -> tuple[ResourceRef, ...]:
        """保存済み artifact 参照の現在の snapshot を返します。"""
        return tuple(self._tracked_refs)

    def resolve_artifact_path(
        self,
        name: str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> ResourceRef:
        """Artifact 名を scope 配下の安全なパスへ解決します。"""
        path = self.guard.resolve_under_root(self._scope_root(scope), name)
        return self._ref(path, scope)

    def resolve_output_path(self, name: str | Path) -> ResourceRef:
        """内部移行用に run-scoped artifact path を解決します。"""
        return self.resolve_artifact_path(name)

    def save_image(
        self,
        name: str | Path,
        image: cv2.typing.MatLike,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        """画像を artifact root 配下に保存し、保存後の参照情報を返します。"""
        final_ref = self._prepare_artifact(name, scope, overwrite or self.overwrite)
        use_atomic = self.atomic if atomic is None else atomic
        if use_atomic:
            self._write_image_atomic(final_ref.path, image)
        else:
            self._write_image(final_ref.path, image)
        self._record(final_ref)
        return final_ref

    def save_blob(
        self,
        name: str | Path,
        data: bytes,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        """任意 bytes を artifact root 配下に保存します。"""
        final_ref = self._prepare_artifact(name, scope, overwrite or self.overwrite)
        use_atomic = self.atomic if atomic is None else atomic
        if use_atomic:
            self._write_blob_atomic(final_ref.path, data)
        else:
            self._write_blob(final_ref.path, data)
        self._record(final_ref)
        return final_ref

    def load_image(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        """画像 artifact を OpenCV 画像として読み戻します。"""
        ref = self._resolve_artifact_for_read(artifact, scope)
        flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
        image = cv2.imread(str(ref.path), flag)
        if image is None:
            raise ResourceReadError(
                f"failed to read artifact image: {ref.relative_path}",
                details={
                    "macro_id": ref.macro_id,
                    "run_id": ref.run_id,
                    "path": str(ref.path),
                    "relative_path": str(ref.relative_path),
                    "source": str(ref.source),
                },
            )
        return image

    def load_blob(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes:
        """任意 bytes artifact を読み戻します。"""
        ref = self._resolve_artifact_for_read(artifact, scope)
        try:
            return ref.path.read_bytes()
        except OSError as exc:
            raise ResourceReadError(
                f"failed to read artifact blob: {ref.relative_path}",
                details={
                    "macro_id": ref.macro_id,
                    "run_id": ref.run_id,
                    "path": str(ref.path),
                    "relative_path": str(ref.relative_path),
                    "source": str(ref.source),
                },
                cause=exc,
            ) from exc

    def _resolve_artifact_for_read(
        self,
        artifact: ResourceRef | str | Path,
        scope: ArtifactScope,
    ) -> ResourceRef:
        if isinstance(artifact, ResourceRef):
            ref = self._guard_ref(artifact)
        else:
            ref = self.resolve_artifact_path(artifact, scope=scope)
        if not ref.path.exists():
            raise ResourceNotFoundError(
                f"artifact not found: {ref.relative_path}",
                details={
                    "macro_id": ref.macro_id,
                    "run_id": ref.run_id,
                    "path": str(ref.path),
                    "relative_path": str(ref.relative_path),
                    "source": str(ref.source),
                },
            )
        return ref

    def _prepare_artifact(
        self,
        name: str | Path,
        scope: ArtifactScope,
        policy: OverwritePolicy,
    ) -> ResourceRef:
        ref = self.resolve_artifact_path(name, scope=scope)
        ref.path.parent.mkdir(parents=True, exist_ok=True)
        scope_root = self._scope_root(scope)
        relative_to_scope = ref.path.relative_to(scope_root.resolve(strict=False))
        guarded_path = self.guard.resolve_under_root(scope_root, relative_to_scope)
        if policy is OverwritePolicy.ERROR and guarded_path.exists():
            raise ResourceAlreadyExistsError(
                f"artifact already exists: {ref.relative_path}",
                details={
                    "macro_id": ref.macro_id,
                    "run_id": ref.run_id,
                    "path": str(ref.path),
                    "relative_path": str(ref.relative_path),
                },
            )
        if policy is OverwritePolicy.UNIQUE:
            guarded_path = self._unique_path(guarded_path)
        return self._ref(guarded_path, scope)

    def _write_blob_atomic(self, final_path: Path, data: bytes) -> None:
        temp_path = self._create_temp_path(final_path)
        try:
            temp_path.write_bytes(data)
            temp_path.replace(final_path)
            if not final_path.exists():
                raise ResourceWriteError(
                    f"artifact was not created: {final_path.name}",
                    details={"path": str(final_path), "name": final_path.name},
                )
        except Exception as exc:
            self._cleanup_temp(temp_path)
            raise ResourceWriteError(
                f"failed to write artifact: {final_path.name}",
                details={"path": str(final_path), "name": final_path.name},
                cause=exc,
            ) from exc

    def _write_blob(self, path: Path, data: bytes) -> None:
        try:
            path.write_bytes(data)
        except OSError as exc:
            raise ResourceWriteError(
                f"failed to write artifact: {path.name}",
                details={"path": str(path), "name": path.name},
                cause=exc,
            ) from exc

    def _write_image_atomic(self, final_path: Path, image: cv2.typing.MatLike) -> None:
        temp_path = self._create_temp_path(final_path)
        try:
            self._write_image(temp_path, image)
            temp_path.replace(final_path)
            if not final_path.exists():
                raise ResourceWriteError(
                    f"artifact was not created: {final_path.name}",
                    details={"path": str(final_path), "name": final_path.name},
                )
        except Exception as exc:
            self._cleanup_temp(temp_path)
            raise ResourceWriteError(
                f"failed to write artifact: {final_path.name}",
                details={"path": str(final_path), "name": final_path.name},
                cause=exc,
            ) from exc

    def _write_image(self, path: Path, image: cv2.typing.MatLike) -> None:
        if not cv2.imwrite(str(path), image):
            raise ResourceWriteError(
                f"failed to write artifact: {path.name}",
                details={"path": str(path), "name": path.name},
            )
        if not path.exists():
            raise ResourceWriteError(
                f"artifact was not created: {path.name}",
                details={"path": str(path), "name": path.name},
            )

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
        raise ResourceWriteError(
            f"failed to find unique artifact path: {path.name}",
            details={"path": str(path), "name": path.name},
        )

    def _cleanup_temp(self, temp_path: Path) -> None:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass

    def _scope_root(self, scope: ArtifactScope) -> Path:
        if scope is ArtifactScope.RUN:
            return self.artifacts_root / self._artifact_dir_name
        if scope is ArtifactScope.STABLE:
            return self.artifacts_root / "stable"
        raise ResourceConfigurationError(f"unsupported artifact scope: {scope!r}")

    def _ref(self, path: Path, scope: ArtifactScope) -> ResourceRef:
        artifacts_root = self.artifacts_root.resolve(strict=self.artifacts_root.exists())
        source = (
            ResourceSource.ARTIFACT_RUN
            if scope is ArtifactScope.RUN
            else ResourceSource.ARTIFACT_STABLE
        )
        return ResourceRef(
            kind=ResourceKind.ARTIFACT,
            source=source,
            path=path,
            relative_path=path.relative_to(artifacts_root),
            macro_id=self.macro_id,
            run_id=self.run_id,
        )

    def _guard_ref(self, ref: ResourceRef) -> ResourceRef:
        artifacts_root = self.artifacts_root.resolve(strict=self.artifacts_root.exists())
        path = Path(ref.path).resolve(strict=False)
        try:
            path.relative_to(artifacts_root)
        except ValueError as exc:
            raise ResourcePathError(
                "artifact path escapes the artifacts root",
                details={
                    "macro_id": ref.macro_id,
                    "run_id": ref.run_id,
                    "path": str(ref.path),
                    "artifacts_root": str(artifacts_root),
                },
            ) from exc
        return ResourceRef(
            kind=ResourceKind.ARTIFACT,
            source=ref.source,
            path=path,
            relative_path=path.relative_to(artifacts_root),
            macro_id=ref.macro_id,
            run_id=ref.run_id,
        )

    def _record(self, ref: ResourceRef) -> None:
        path_key = ref.path.resolve(strict=False)
        if path_key in self._tracked_paths:
            self._tracked_refs = [
                existing
                for existing in self._tracked_refs
                if existing.path.resolve(strict=False) != path_key
            ]
        self._tracked_paths[path_key] = ref
        self._tracked_refs.append(ref)
        while len(self._tracked_refs) > self.tracked_limit:
            removed = self._tracked_refs.pop(0)
            self._tracked_paths.pop(removed.path.resolve(strict=False), None)
            self._artifacts_overflow_count += 1


def _validate_resource_identifier(value: str) -> None:
    if not value or any(separator in value for separator in ("\\", "/", ":")):
        raise ResourceConfigurationError(f"invalid macro resource id: {value!r}")


def _validate_artifact_dir_name(value: str) -> None:
    if not value or any(separator in value for separator in ("\\", "/", ":")):
        raise ResourceConfigurationError(f"invalid artifact directory name: {value!r}")
    try:
        DefaultResourcePathGuard().resolve_under_root(Path("."), value)
    except ResourcePathError as exc:
        raise ResourceConfigurationError(f"invalid artifact directory name: {value!r}") from exc

# Resource File I/O 再設計仕様書

> **対象モジュール**: `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\hardware\`, `src\nyxpy\framework\core\macro\`  
> **目的**: マクロが参照する read-only assets と実行中に生成する writable outputs の配置、解決、読み書きを Runtime Port と互換 Command API へ分離する。  
> **関連ドキュメント**: `CONFIGURATION_AND_RESOURCES.md`, `RUNTIME_AND_IO_PORTS.md`, `IMPLEMENTATION_PLAN.md`  
> **既存ソース**: `src\nyxpy\framework\core\hardware\resource.py`, `src\nyxpy\framework\core\utils\helper.py`, `src\nyxpy\framework\core\macro\command.py`  
> **破壊的変更**: なし。既存 `cmd.load_img()` / `cmd.save_img()` と `static\<macro_name>\...` 参照は互換層で維持する。

## 1. 概要

### 1.1 目的

Resource File I/O は、マクロが読む画像・テンプレート・補助ファイルと、実行中に保存する画像・CSV・通知添付候補を明確に分離するためのフレームワーク境界である。本仕様は settings lookup から独立し、`Command` 互換 API、`ResourceStorePort`、`MacroResourceScope`、`RunArtifactStore` の責務を定義する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作、キャプチャ、画像入出力、通知、ログを行うための高レベル API |
| Resource File I/O | マクロの assets 読み込みと run outputs 書き込みを扱うファイル I/O 境界。settings TOML 解決は含めない |
| ResourceStorePort | `Command.load_img()` 互換を支える Port。assets のパス検証、画像読み込み、失敗検出を担当する |
| MacroResourceScope | 1 つのマクロ ID に紐づく assets root、macro root、legacy static root を表す値オブジェクト |
| RunArtifactStore | 1 回の実行 ID に紐づく outputs root へ成果物を書き込む Port |
| Asset | マクロ実行前から存在するテンプレート画像、OCR 補助ファイル、固定データなどの read-only resource |
| Output | 実行中に生成するデバッグ画像、OCR 切り出し画像、CSV、通知添付候補などの writable artifact |
| Legacy static root | 現行互換の `project_root\static\<macro_name>` 配置 |
| MacroSettingsResolver | `static\<macro_name>\settings.toml` 互換と manifest settings path を解決する設定専用コンポーネント |
| Path traversal | `..`、絶対パス、シンボリックリンクなどで許可 root の外へアクセスする攻撃または誤設定 |
| Atomic write | 同一ディレクトリ内の一時ファイルへ書き込み、成功後に置換することで半端な成果物を見せない保存手順 |

### 1.3 背景・問題

現行 `StaticResourceIO` は `static` 配下の画像入出力を担当するが、`root / filename` 後の解決済みパス検証、`cv2.imwrite()` 戻り値検証、assets と outputs の分離が不足している。`load_macro_settings()` は `static\<macro_name>\settings.toml` を読むため、settings lookup と画像リソース I/O が同じ `static` 配置に見え、設計上の境界が曖昧である。

代表マクロでは `frlg_id_rng` が `cmd.save_img("frlg_id_rng/img/...png", cropped_img)` で static 配下へデバッグ画像を保存し、`sample_turbo_a_macro.py` が `cmd.save_img(capture_name, frame)` を使う。`frlg_initial_seed` は `output_dir = "static/frlg_initial_seed"` を設定値として持ち、CSV と画像を `Path` / `open()` で直接保存している。再設計では既存呼び出しを壊さず、assets 読み込みと run outputs 書き込みの新しい配置へ段階移行できるようにする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 既存 `cmd.save_img()` / `load_img()` のソース変更 | 変更不可 | 0 件 |
| settings lookup と画像 I/O の責務 | `static` 配置上で混同されやすい | `MacroSettingsResolver` と Resource File I/O を別コンポーネントに分離 |
| root 外アクセス防止 | `root / filename` 後の最終パス検証なし | `Path.resolve()` 後に許可 root 配下だけ許可 |
| 画像書き込み失敗検出 | `cv2.imwrite()` の戻り値未検証 | `False`、保存後未存在、atomic replace 失敗を例外化 |
| outputs の配置 | static 配下へ保存され assets と混在 | `runs\<run_id>\outputs` を標準保存先にする |
| read-only assets の保証 | 規約上の区別なし | `MacroResourceScope.assets_roots` は読み込み専用として扱う |

### 1.5 着手条件

- 既存 `Command.save_img(filename, image)` と `Command.load_img(filename, grayscale=False)` のシグネチャを維持する。
- `project_root\static\<macro_name>` 互換を legacy scope として維持する。
- settings TOML の探索は `MacroSettingsResolver` が担当し、本仕様の Resource Store へ戻さない。
- `MacroRuntime` / `ExecutionContext` は Resource Store を Port として注入できる。
- 実装前に `git diff --check` と関連単体テストのベースラインを確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\RESOURCE_FILE_IO.md` | 新規 | 本仕様書 |
| `spec\framework\rearchitecture\CONFIGURATION_AND_RESOURCES.md` | 変更 | settings 境界中心に整理し、ファイル I/O 詳細は本仕様参照へ寄せる |
| `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md` | 変更 | Runtime Port から Resource File I/O 詳細への参照を追加する |
| `spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md` | 変更 | Resource File I/O 再設計フェーズを追加する |
| `src\nyxpy\framework\core\io\resources.py` | 新規 | `ResourceStorePort`、`MacroResourceScope`、`RunArtifactStore`、path guard を実装 |
| `src\nyxpy\framework\core\hardware\resource.py` | 変更 | 既存 `StaticResourceIO` を互換 adapter とし、新 Resource Store へ委譲 |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `cmd.load_img()` / `cmd.save_img()` を Resource Store へ委譲 |
| `src\nyxpy\framework\core\runtime\context.py` | 変更 | `ExecutionContext` に macro resource scope と run artifact store を保持 |
| `tests\unit\framework\io\test_resource_file_io.py` | 新規 | path traversal、互換 API、atomic write、overwrite policy を検証 |
| `tests\integration\test_resource_file_io_compat.py` | 新規 | 代表マクロの `save_img()` と legacy static 互換を検証 |

## 3. 設計方針

### 3.1 リソース配置モデルの比較

| 案 | 配置 | 利点 | 欠点 | 採否 |
|----|------|------|------|------|
| A: 現行 static 固定 | `static\<macro_name>\...` | 既存マクロと設定ファイルに完全互換。移行コストが最小 | assets、settings、outputs が混在し、書き込み成果物を管理しにくい | legacy 互換として維持 |
| B: resources/runs 分離 | `resources\<macro_id>\assets`, `runs\<run_id>\outputs` | read-only assets と writable outputs が明確。実行単位の成果物管理と削除が容易 | 既存 `filename` の解釈を移行する adapter が必要 | 標準モデルとして採用 |
| C: project root 相対 | `project_root` からの相対パスを許可 | 既存の `static/...` や `references/...` を扱いやすい | 許可範囲が広く、誤保存の影響が大きい | manifest opt-in の限定用途のみ |
| D: macro root 相対 | `macros\<macro_id>\assets` など | マクロコードとリソースを近接配置できる | インストール後の書き込み不可領域と混同しやすい | read-only assets 候補として採用 |
| E: package resource | wheel 内 `importlib.resources` | 配布時に assets をパッケージへ同梱できる | OpenCV がパスを要求する場合は一時展開が必要。書き込み不可 | 将来拡張として許可 |

標準モデルは B とする。A は互換層として残し、D と E は read-only assets source として `MacroResourceScope` に接続する。outputs は常に `RunArtifactStore` が所有し、assets root へ直接保存しない。

### 3.2 read-only assets と writable outputs の分離

```text
project_root
  resources
    <macro_id>
      assets
        templates
        ocr
  runs
    <run_id>
      outputs
        images
        csv
        attachments
  static
    <macro_name>
      settings.toml      # MacroSettingsResolver が読む
      ...                # legacy assets / outputs 互換
```

- `MacroResourceScope.assets_roots` は読み込み専用である。`load_img()` の検索対象に含めるが、`save_img()` の保存先にしない。
- `RunArtifactStore.output_root` は書き込み専用の標準先である。`save_img()` の保存先は互換モードを除きここへ集約する。
- `LegacyStaticResourceStore` は既存 `static\<macro_name>` 互換を提供する。
- `MacroSettingsResolver` は settings TOML だけを扱う。Resource Store は settings ファイルを探索しない。

### 3.3 公開 API 方針

既存マクロ向けの `cmd.load_img()` と `cmd.save_img()` は互換 API として残す。新規フレームワーク API は Port と scope を明示し、ファイル I/O の意図を `load_asset()`、`save_output()`、`open_output()` のように分ける。

`cmd.save_img(filename, image)` の標準保存先は `RunArtifactStore` とする。ただし互換オプション `legacy_static_write=True` の実行では現行 static root へ保存する。既存 `StaticResourceIO` は新 Port へ委譲する adapter になり、`Path.cwd() / "static"` への直接依存を内部へ閉じ込める。

### 3.4 後方互換性

| 既存利用 | 移行後の扱い |
|----------|--------------|
| `cmd.load_img("template.png")` | `MacroResourceScope` の assets、legacy static root の順に検索 |
| `cmd.save_img("sample.png", frame)` | 既定では `runs\<run_id>\outputs\sample.png` へ保存。互換モードでは legacy static root へ保存 |
| `cmd.save_img("frlg_id_rng/img/a.png", frame)` | 先頭要素が実行中 macro ID と一致する場合は prefix を除去し、`outputs\img\a.png` へ保存。互換モードでは現行 static 形式も許可 |
| `StaticResourceIO(root).save_image()` | `LegacyStaticResourceStore` へ委譲し、root 配下検証を追加 |
| `static\<macro_name>\settings.toml` | `MacroSettingsResolver` が読み、Resource Store は関与しない |
| マクロ内の `Path(cfg.output_dir)` / `open()` | 段階移行対象。新 API `cmd.artifacts` または `RunArtifactStore` へ移すが、既存コードは即時変更しない |

### 3.5 レイヤー構成

| レイヤー | 責務 | 依存してよい先 |
|----------|------|----------------|
| macro | `Command` API を呼ぶ | `nyxpy.framework.*`, `macros.shared` |
| command facade | 既存 API と新 Port の橋渡し | runtime context, Resource Store, Frame Source |
| resource file io | assets 解決、outputs 保存、path guard、atomic write | 標準ライブラリ、OpenCV、フレームワーク例外 |
| settings resolver | settings TOML 解決と辞書化 | macro descriptor, TOML reader |
| runtime builder | macro ID と run ID から scope と store を構築 | registry, settings, resource file io |

フレームワーク層から `macros\<macro_id>` へ静的 import しない。macro root は `MacroDescriptor` の値として渡し、path 解決だけに使う。

### 3.6 性能要件

| 指標 | 目標値 |
|------|--------|
| path guard 解決 | 1 パスあたり 2 ms 未満 |
| `load_img()` の追加探索 overhead | OpenCV 読み込み時間を除き 5 ms 未満 |
| `save_img()` の atomic write overhead | OpenCV 書き込み時間を除き 10 ms 未満 |
| `RunArtifactStore` の run root 作成 | 1 実行あたり 20 ms 未満 |
| 10,000 個未満の成果物列挙 | 500 ms 未満 |

### 3.7 並行性・スレッド安全性

`MacroResourceScope` は immutable な値として扱う。`RunArtifactStore` は run ID ごとに 1 つの output root を持つため、異なる実行間で同じ root を共有しない。同一 run 内で同じ相対パスへ同時保存する場合は `overwrite` policy に従い、atomic replace 前後を per-path lock で保護する。

## 4. 実装仕様

### 公開インターフェース

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Protocol

import cv2


class ResourceKind(StrEnum):
    ASSET = "asset"
    OUTPUT = "output"
    LEGACY_STATIC = "legacy_static"


class OverwritePolicy(StrEnum):
    ERROR = "error"
    REPLACE = "replace"
    UNIQUE = "unique"


@dataclass(frozen=True)
class MacroResourceScope:
    project_root: Path
    macro_id: str
    macro_root: Path | None
    assets_roots: tuple[Path, ...]
    legacy_static_root: Path

    def candidate_asset_paths(self, name: str | Path) -> tuple[Path, ...]: ...


@dataclass(frozen=True)
class ResourceRef:
    kind: ResourceKind
    path: Path
    relative_path: Path
    macro_id: str
    run_id: str | None = None


class ResourceStorePort(ABC):
    @abstractmethod
    def resolve_asset_path(self, name: str | Path) -> ResourceRef: ...

    @abstractmethod
    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...

    def close(self) -> None: ...


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

    def close(self) -> None: ...


class ResourcePathGuard(Protocol):
    def resolve_under_root(self, root: Path, name: str | Path) -> Path: ...
```

```python
class CommandFacade(Command):
    def load_img(self, filename: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...
    def save_img(self, filename: str | Path, image: cv2.typing.MatLike) -> None: ...

    @property
    def artifacts(self) -> RunArtifactStore: ...
```

### 内部設計

#### Resource path 正規化

```text
resolve_under_root(root, name)
  -> name が str | Path であることを検証
  -> 空文字、空 Path、予約名を拒否
  -> 絶対パスを拒否
  -> path parts に ".." があれば拒否
  -> candidate = (root / name).resolve(strict=False)
  -> root_resolved = root.resolve(strict=True)
  -> candidate が root_resolved と同一または配下であることを検証
  -> candidate を返す
```

保存時は親ディレクトリを作成した後、親ディレクトリを `resolve(strict=True)` で再検証する。シンボリックリンク経由で root 外へ出る場合は `ResourcePathError` とする。

#### `cmd.load_img()` 解決順序

| 優先度 | 条件 | 解決先 |
|--------|------|--------|
| 1 | manifest / descriptor が assets root を持つ | `resources\<macro_id>\assets` または macro root assets |
| 2 | legacy static root に存在 | `static\<macro_name>` |
| 3 | package resource 対応が有効 | `importlib.resources` から読み取り、必要なら同一 run cache へ展開 |

複数候補に同名ファイルがある場合は優先度の高い候補を使い、`LoggerPort` に debug 診断を出す。存在しない場合は探索候補を secret なしの相対パスで例外に含める。

#### `cmd.save_img()` 解決順序

| 実行オプション | 保存先 |
|----------------|--------|
| 標準 | `runs\<run_id>\outputs\<filename>` |
| `legacy_static_write=True` | `static\<macro_name>\<filename>` |
| `filename` の先頭が実行中 macro ID | 標準では先頭要素を除去し `outputs` へ保存。互換モードでは現行 static 形式も許可 |

`cmd.save_img()` は戻り値を持たないため、保存先 `ResourceRef` は debug ログに記録する。新 API `RunArtifactStore.save_image()` は `ResourceRef` を返す。

#### Atomic write と overwrite policy

1. `OverwritePolicy.ERROR`: 既存ファイルがあれば `ResourceAlreadyExistsError`。
2. `OverwritePolicy.REPLACE`: 同一ディレクトリに一時ファイルを作り、成功後に `Path.replace()` する。
3. `OverwritePolicy.UNIQUE`: `name`, `name_1`, `name_2` の順に空きパスを選ぶ。

画像保存は OpenCV がファイルパスを要求するため、一時ファイル名を同じ拡張子で作る。`cv2.imwrite()` が `False` を返す、保存後に一時ファイルが存在しない、replace 後に最終ファイルが存在しない場合は `ResourceWriteError` とする。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `resource.assets_root` | `Path` | `project_root\resources` | 標準 assets root |
| `resource.runs_root` | `Path` | `project_root\runs` | 標準 outputs root |
| `resource.legacy_static_root` | `Path` | `project_root\static` | 現行互換 static root |
| `resource.write_mode` | `"runs" | "legacy_static"` | `"runs"` | `cmd.save_img()` の既定保存先 |
| `resource.overwrite_policy` | `OverwritePolicy` | `REPLACE` | 同名 output の扱い |
| `resource.atomic_write` | `bool` | `True` | output 保存で atomic write を使うか |
| `resource.allow_package_assets` | `bool` | `False` | package resource 読み込みを許可するか |
| `resource.max_output_bytes` | `int | None` | `None` | 1 ファイルの最大保存サイズ。`None` は制限なし |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ResourcePathError` | 空 path、絶対パス、`..`、root 外シンボリックリンク、予約名を検出した |
| `ResourceNotFoundError` | assets 検索対象のどこにもファイルが存在しない |
| `ResourceReadError` | `cv2.imread()` が `None`、または読み込み権限不足 |
| `ResourceWriteError` | `cv2.imwrite()` が `False`、atomic replace 失敗、保存後未存在、最大サイズ超過 |
| `ResourceAlreadyExistsError` | `OverwritePolicy.ERROR` で同名 output が存在する |
| `ResourceConfigurationError` | macro ID、run ID、root path、write mode の構成が不正 |

例外メッセージは project root 相対または scope root 相対の path を使う。ユーザ名を含む絶対パス、secret 値、通知 URL は含めない。

### シングルトン管理

Resource File I/O はシングルトンにしない。`MacroRuntimeBuilder` が実行ごとに `MacroResourceScope` と `RunArtifactStore` を生成し、`ExecutionContext` に注入する。`singletons.py` に追加が必要な場合でも root 設定の既定値だけに限定し、実体 Store は `reset_for_testing()` の対象にしない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_resource_path_guard_rejects_absolute_path` | 絶対パスを `ResourcePathError` にする |
| ユニット | `test_resource_path_guard_rejects_parent_escape` | `..` による root 外参照を拒否する |
| ユニット | `test_resource_path_guard_rejects_symlink_escape` | root 内シンボリックリンクから root 外へ出る path を拒否する |
| ユニット | `test_macro_resource_scope_asset_lookup_order` | assets root、legacy static root の順に `load_img()` 候補を解決する |
| ユニット | `test_command_load_img_uses_resource_store` | `CommandFacade.load_img()` が `ResourceStorePort.load_image()` へ委譲する |
| ユニット | `test_command_save_img_uses_run_artifact_store` | 標準モードの `save_img()` が `runs\<run_id>\outputs` へ保存する |
| ユニット | `test_command_save_img_legacy_static_write` | 互換モードで legacy static root へ保存できる |
| ユニット | `test_save_image_checks_imwrite_return` | `cv2.imwrite()` が `False` の場合に `ResourceWriteError` を送出する |
| ユニット | `test_save_image_atomic_replace` | 一時ファイルから最終 path へ replace され、半端な最終ファイルを残さない |
| ユニット | `test_overwrite_policy_error_rejects_existing_file` | `OverwritePolicy.ERROR` が既存 output を拒否する |
| ユニット | `test_overwrite_policy_unique_picks_new_name` | `OverwritePolicy.UNIQUE` が衝突しない path を返す |
| ユニット | `test_macro_settings_resolver_does_not_use_resource_store` | settings lookup が Resource Store に依存しない |
| 結合 | `test_existing_frlg_id_rng_save_img_compat` | `frlg_id_rng` の `cmd.save_img("frlg_id_rng/img/...png")` がマクロ修正なしで保存できる |
| 結合 | `test_sample_turbo_a_save_img_compat` | `sample_turbo_a_macro.py` の `cmd.save_img(capture_name, frame)` が保存できる |
| 結合 | `test_initial_seed_output_dir_migration_adapter` | `output_dir` を使う既存直接書き込みを移行警告付きで扱う方針を確認する |
| ハードウェア | `test_realdevice_run_artifact_save_image` | `@pytest.mark.realdevice`。実キャプチャ画像を run outputs へ保存できる |
| パフォーマンス | `test_resource_path_guard_perf` | 1,000 path 解決の平均が目標値内である |

テストでは fake `ResourceStorePort` とテスト作業ディレクトリ配下の project root を使う。外部一時ディレクトリには依存しない。

## 6. 実装チェックリスト

- [ ] `MacroResourceScope` のシグネチャ確定
- [ ] `ResourceStorePort` と `RunArtifactStore` の責務分離を実装
- [ ] `ResourcePathGuard` で path traversal を拒否
- [ ] `cmd.load_img()` 互換 adapter を実装
- [ ] `cmd.save_img()` 互換 adapter を実装
- [ ] `StaticResourceIO` を legacy adapter へ縮退
- [ ] `MacroSettingsResolver` から Resource Store 依存を排除
- [ ] `runs\<run_id>\outputs` の生成規則を Runtime builder に実装
- [ ] atomic write と overwrite policy を実装
- [ ] `cv2.imwrite()` と `cv2.imread()` の失敗を例外化
- [ ] 代表マクロの保存互換を結合テストで固定
- [ ] read-only assets と writable outputs の境界をドキュメントに反映
- [ ] `git diff --check` がパス
- [ ] 関連単体テストがパス

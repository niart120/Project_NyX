# Resource File I/O 再設計仕様書

> **対象モジュール**: `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\hardware\`, `src\nyxpy\framework\core\macro\`  
> **目的**: マクロが参照する read-only assets と実行中に生成する writable outputs の配置、解決、読み書きを Runtime Port と互換 Command API へ分離する。  
> **関連ドキュメント**: `CONFIGURATION_AND_RESOURCES.md`, `RUNTIME_AND_IO_PORTS.md`, `IMPLEMENTATION_PLAN.md`  
> **既存ソース**: `src\nyxpy\framework\core\hardware\resource.py`, `src\nyxpy\framework\core\utils\helper.py`, `src\nyxpy\framework\core\macro\command.py`  
> **破壊的変更**: Resource File I/O の破壊的変更と削除条件は `DEPRECATION_AND_MIGRATION.md` を正とする。本書は `cmd.load_img()` / `cmd.save_img()` の維持範囲、assets / outputs 配置、path guard、atomic write を定義する。

## 1. 概要

### 1.1 目的

Resource File I/O は、マクロが読む画像・テンプレート・補助ファイルと、実行中に保存する画像・CSV・通知添付候補を明確に分離するためのフレームワーク境界である。本仕様は settings lookup から独立し、`Command` 互換 API、`ResourceStorePort`、`MacroResourceScope`、`RunArtifactStore` の責務を定義する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作、キャプチャ、画像入出力、通知、ログを行うための高レベル API |
| Resource File I/O | マクロの assets 読み込みと run outputs 書き込みを扱うファイル I/O 境界。settings TOML 解決は含めない |
| ResourceStorePort | `Command.load_img()` 互換を支える Port。assets のパス検証、画像読み込み、失敗検出を担当する |
| MacroResourceScope | 1 つのマクロ ID に紐づく assets root と macro root を表す値オブジェクト |
| RunArtifactStore | 1 回の実行 ID に紐づく outputs root へ成果物を書き込む Port |
| Asset | マクロ実行前から存在するテンプレート画像、OCR 補助ファイル、固定データなどの read-only resource |
| Output | 実行中に生成するデバッグ画像、OCR 切り出し画像、CSV、通知添付候補などの writable artifact |
| ResourceSource | `ResourceRef` の由来。標準 assets、macro package assets、run outputs などを表す |
| MacroSettingsResolver | manifest または class metadata の settings source と project root 明示設定を解決する設定専用コンポーネント |
| Path traversal | `..`、絶対パス、シンボリックリンクなどで許可 root の外へアクセスする攻撃または誤設定 |
| Atomic write | 同一ディレクトリ内の一時ファイルへ書き込み、成功後に置換することで半端な成果物を見せない保存手順 |

### 1.3 背景・問題

現行 `StaticResourceIO` は `static` 配下の画像入出力を担当するが、`root / filename` 後の解決済みパス検証、`cv2.imwrite()` 戻り値検証、assets と outputs の分離が不足している。`load_macro_settings()` も同じ `static` 配置を使うため、settings lookup と画像リソース I/O が混同されている。再設計では旧 `static` 配置の自動互換を残さず、リソースは `resources` / `runs`、settings は manifest または class metadata の明示 settings source へ分離する。

代表マクロでは `frlg_id_rng` が `cmd.save_img("frlg_id_rng/img/...png", cropped_img)` で static 配下へデバッグ画像を保存し、`sample_turbo_a_macro.py` が `cmd.save_img(capture_name, frame)` を使う。`frlg_initial_seed` は `output_dir = "static/frlg_initial_seed"` を設定値として持ち、CSV と画像を `Path` / `open()` で直接保存している。再設計ではこれらのマクロ側修正を要求し、assets 読み込みと run outputs 書き込みを新しい配置へ移す。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 既存 `cmd.save_img()` / `load_img()` のパス指定変更 | 未整理 | 移行ガイドに従って全対象を新配置へ移行 |
| settings lookup と画像 I/O の責務 | `static` 配置上で混同されやすい | `MacroSettingsResolver` と Resource File I/O を別コンポーネントに分離 |
| root 外アクセス防止 | `root / filename` 後の最終パス検証なし | `Path.resolve()` 後に許可 root 配下だけ許可 |
| 画像書き込み失敗検出 | `cv2.imwrite()` の戻り値未検証 | `False`、保存後未存在、atomic replace 失敗を例外化 |
| outputs の配置 | static 配下へ保存され assets と混在 | `runs\<run_id>\outputs` を標準保存先にする |
| read-only assets の保証 | 規約上の区別なし | `MacroResourceScope.assets_roots` は読み込み専用として扱う |

### 1.5 着手条件

- 既存 `Command.save_img(filename, image)` と `Command.load_img(filename, grayscale=False)` のシグネチャを維持する。
- `project_root\static\<macro_name>` 互換は維持せず、必要な assets は `resources\<macro_id>\assets` または `macros\<macro_id>\assets` へ移動する。
- settings TOML の探索は `MacroSettingsResolver` が担当し、本仕様の Resource Store へ戻さない。
- `MacroRuntime` / `ExecutionContext` は Resource Store を Port として注入できる。
- `MacroRuntimeBuilder` は `RUNTIME_AND_IO_PORTS.md` の責務であり、本仕様は builder が呼び出す `MacroResourceScope` と Store だけを提供する。
- 実装前に `git diff --check` と関連単体テストのベースラインを確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/RESOURCE_FILE_IO.md` | 新規 | 本仕様書 |
| `spec/framework/rearchitecture/CONFIGURATION_AND_RESOURCES.md` | 変更 | settings 境界中心に整理し、ファイル I/O 詳細は本仕様参照へ寄せる |
| `spec/framework/rearchitecture/RUNTIME_AND_IO_PORTS.md` | 変更 | Runtime Port から Resource File I/O 詳細への参照を追加する |
| `spec/framework/rearchitecture/IMPLEMENTATION_PLAN.md` | 変更 | Resource File I/O 再設計フェーズを追加する |
| `src\nyxpy\framework\core\io\resources.py` | 新規 | `ResourceStorePort`、`MacroResourceScope`、`RunArtifactStore`、path guard を実装 |
| `src\nyxpy\framework\core\hardware\resource.py` | 変更 | 既存 `StaticResourceIO` 直接利用を削除または非公開化し、新 Resource Store へ置換 |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `cmd.load_img()` / `cmd.save_img()` を Resource Store へ委譲 |
| `src\nyxpy\framework\core\runtime\context.py` | 変更 | `ExecutionContext` に macro resource scope と run artifact store を保持 |
| `tests\unit\framework\io\test_resource_file_io.py` | 新規 | path traversal、新 Resource API、atomic write、overwrite policy を検証 |
| `tests\integration\test_resource_file_io_migration.py` | 新規 | 移行後マクロの `load_img()` / `save_img()` が新配置で動作することを検証 |

## 3. 設計方針

### 3.1 リソース配置モデルの比較

| 案 | 配置 | 利点 | 欠点 | 採否 |
|----|------|------|------|------|
| A: 現行 static 固定 | `static\<macro_name>\...` | 既存マクロと設定ファイルに完全互換。移行コストが最小 | assets、settings、outputs が混在し、書き込み成果物を管理しにくい | 不採用。移行ガイドで新配置へ移す |
| B: resources/runs 分離 | `resources\<macro_id>\assets`, `runs\<run_id>\outputs` | read-only assets と writable outputs が明確。実行単位の成果物管理と削除が容易 | 既存 `filename` の解釈を移行する adapter が必要 | 標準モデルとして採用 |
| C: project root 相対 | `project_root` からの相対パスを許可 | 既存の `static/...` や `references/...` を扱いやすい | 許可範囲が広く、誤保存の影響が大きい | manifest opt-in の限定用途のみ |
| D: macro root 相対 | `macros\<macro_id>\assets` など | マクロコードとリソースを近接配置できる | インストール後の書き込み不可領域と混同しやすい | read-only assets 候補として採用 |
| E: package resource | wheel 内 `importlib.resources` | 配布時に assets をパッケージへ同梱できる | OpenCV がパスを要求する場合は一時展開が必要。書き込み不可 | 将来拡張として許可 |

標準モデルは B とする。A は互換層として残さない。D と E は read-only assets source として `MacroResourceScope` に接続する。outputs は常に `RunArtifactStore` が所有し、assets root へ直接保存しない。

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
```

- `MacroResourceScope.assets_roots` は読み込み専用である。`load_img()` の検索対象に含めるが、`save_img()` の保存先にしない。
- `RunArtifactStore.output_root` は書き込み専用の標準先である。`save_img()` の保存先は常にここへ集約する。
- `MacroSettingsResolver` は settings TOML だけを扱う。Resource Store は settings ファイルを探索しない。

`Command.save_img()`、`RunArtifactStore.save_image()`、`RunArtifactStore.open_output()` は、読み込み元 assets root へ同名ファイルを書き戻さない。標準 assets と macro package 同梱 assets のどちらから読み込んだ場合でも、保存先は `runs\<run_id>\outputs` 配下だけである。assets を更新したい場合はマクロ実行の成果物として保存し、移行作業またはユーザー操作で assets へ反映する。

`MacroResourceScope.assets_roots` が複数 root を持つ理由は、標準 assets と macro package 同梱 assets を同時に検索するためである。例えば `frlg_id_rng` は次の順で検索する。

```text
resources/frlg_id_rng/assets
macros/frlg_id_rng/assets
```

複数 root は読み込み専用候補であり、保存先の分散には使わない。移行前の `static\<macro_name>` は自動検索せず、マクロ移行ガイドに従って新配置へ移動する。

### 3.3 公開 API 方針

既存マクロ向けの `cmd.load_img()` と `cmd.save_img()` はメソッド名と基本シグネチャだけを残す。パス解釈は新配置へ変更し、旧 static 互換は残さない。新規フレームワーク API は Port と scope を明示し、ファイル I/O の意図を `load_asset()`、`save_output()`、`open_output()` のように分ける。

`cmd.save_img(filename, image)` の保存先は常に `RunArtifactStore` とする。`legacy_static_write=True` や `resource.write_mode = "legacy_static"` は定義しない。既存 `StaticResourceIO` 直接利用は移行対象であり、互換 adapter は作らない。

### 3.4 後方互換性

| 既存利用 | 移行後の扱い |
|----------|--------------|
| `cmd.load_img("template.png")` | `resources\<macro_id>\assets`、`macros\<macro_id>\assets`、package resource の順に検索 |
| `cmd.save_img("sample.png", frame)` | `runs\<run_id>\outputs\sample.png` へ保存 |
| `cmd.save_img("frlg_id_rng/img/a.png", frame)` | prefix 除去は行わず、指定どおり `runs\<run_id>\outputs\frlg_id_rng\img\a.png` として扱う。不要な prefix はマクロ側で修正する |
| `StaticResourceIO(root).save_image()` | 互換 adapter を作らず、`RunArtifactStore.save_image()` へ移行する |
| `static\<macro_name>\settings.toml` | Resource Store は関与しない。settings 仕様側でも旧 static fallback は残さない |
| マクロ内の `Path(cfg.output_dir)` / `open()` | 段階移行対象。新 API `cmd.artifacts` または `RunArtifactStore` へ移すが、既存コードは即時変更しない |

### 3.5 レイヤー構成

| レイヤー | 責務 | 依存してよい先 |
|----------|------|----------------|
| macro | `Command` API を呼ぶ | `nyxpy.framework.*`, `macros.shared` |
| DefaultCommand 実装 | 既存 API と新 Port の橋渡し | runtime context, Resource Store, Frame Source |
| resource file io | assets 解決、outputs 保存、path guard、atomic write | 標準ライブラリ、OpenCV、フレームワーク例外 |
| settings resolver | settings TOML 解決と辞書化 | `MacroDefinition`, TOML reader |
| runtime builder | macro ID と run ID から scope と store を要求する。build 順序と API は `RUNTIME_AND_IO_PORTS.md` が正本 | registry, settings, resource file io |

フレームワーク層から `macros\<macro_id>` へ静的 import しない。macro root は `MacroDefinition` の値として渡し、path 解決だけに使う。

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


class ResourceSource(StrEnum):
    STANDARD_ASSETS = "standard_assets"
    MACRO_PACKAGE = "macro_package"
    PACKAGE_RESOURCE = "package_resource"
    RUN_OUTPUTS = "run_outputs"


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

    @classmethod
    def from_definition(cls, definition: MacroDefinition, project_root: Path) -> "MacroResourceScope": ...

    def candidate_asset_paths(self, name: str | Path) -> tuple[Path, ...]: ...


@dataclass(frozen=True)
class ResourceRef:
    kind: ResourceKind
    source: ResourceSource
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
class DefaultCommand(Command):
    def load_img(self, filename: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...
    def save_img(self, filename: str | Path, image: cv2.typing.MatLike) -> None: ...

    @property
    def artifacts(self) -> RunArtifactStore: ...
```

`DefaultCommand` から Resource File I/O への委譲は次の通りである。`ResourceStorePort` は読み込み専用、`RunArtifactStore` は書き込み専用であり、互いの責務を混ぜない。

| `Command` API | 委譲先 | 期待する root | 戻り値 |
|---------------|--------|---------------|--------|
| `load_img(filename, grayscale=False)` | `ResourceStorePort.load_image()` | `resources\<macro_id>\assets` または macro package assets | `cv2.typing.MatLike` |
| `save_img(filename, image)` | `RunArtifactStore.save_image()` | `runs\<run_id>\outputs` | 既存互換のため `None`。保存先 `ResourceRef` は debug ログへ記録 |
| `artifacts` property | `ExecutionContext.artifacts` | `runs\<run_id>\outputs` | `RunArtifactStore` |

### 内部設計

#### `MacroResourceScope.from_definition()` 変換規則

`MacroResourceScope.from_definition(definition, project_root)` は `MacroDefinition` の snapshot から読み込み候補だけを作る。settings path は `MacroSettingsResolver` の責務であり、本変換には含めない。

| 入力 | 変換先 | 規則 |
|------|--------|------|
| `definition.id` | `macro_id` | Resource path 用の安定 ID としてそのまま使う。`/`、`\`、drive、空文字は `ResourcePathError` |
| `project_root` | `project_root` | 呼び出し元が明示した root を保持し、標準 assets root と runs root の起点にする |
| `definition.macro_root` | `macro_root` | package / single-file macro の配置 root。`None` の場合は標準 assets root だけを候補にする |
| `project_root\resources\<macro_id>\assets` | `assets_roots[0]` | 標準 assets root。存在しない場合も候補として保持し、読み込み時に未存在を診断する |
| `definition.macro_root\assets` | `assets_roots[1]` | macro package 同梱 assets。`macro_root` が `None` の場合は追加しない |
| `definition.settings_path` | 変換対象外 | settings TOML は `MacroSettingsResolver` が解決する |
| `definition.manifest_path` | 変換対象外 | manifest の settings / entrypoint は Registry / SettingsResolver が解釈済みであり、Resource Store は参照しない |

`candidate_asset_paths(name)` は `assets_roots` の順序を保って `ResourcePathGuard.resolve_under_root(root, name)` を適用し、root 外参照が 1 件でもあれば `ResourcePathError` とする。root 配下だが未存在の候補は、探索候補として保持し、全候補が未存在の場合にまとめて `ResourceReadError` へ含める。

#### Resource path 正規化

```text
resolve_under_root(root, name)
  -> name が str | Path であることを検証
  -> 空文字、空 Path、予約名を拒否
  -> Windows drive、UNC、root 付き絶対パスを拒否
  -> Windows 区切り `\` と POSIX 区切り `/` は path separator として扱う
  -> path parts に ".."、空 segment、drive、anchor があれば拒否
  -> candidate = (root / name).resolve(strict=False)
  -> root_resolved = root.resolve(strict=True)
  -> candidate が root_resolved と同一または配下であることを検証
  -> candidate を返す
```

Resource File I/O の `name` は実行時 API の path 引数であるため、Windows path を許容する。`images\result.png` と `images/result.png` は同じ相対 path として扱う。一方、`C:foo.png`、`C:\foo.png`、`\\server\share\foo.png`、`\foo.png` は root 外へ出る可能性があるため拒否する。保存時は親ディレクトリを作成した後、親ディレクトリを `resolve(strict=True)` で再検証する。シンボリックリンク経由で root 外へ出る場合は `ResourcePathError` とする。

#### `cmd.load_img()` 解決順序

| 優先度 | 条件 | 解決先 |
|--------|------|--------|
| 1 | manifest / `MacroDefinition` が assets root を持つ | `resources\<macro_id>\assets` または macro root assets |
| 2 | package resource 対応が有効 | `importlib.resources` から読み取り、必要なら同一 run cache へ展開 |

複数候補に同名ファイルがある場合は優先度の高い候補を使い、`LoggerPort` に debug 診断を出す。存在しない場合は探索候補を secret なしの相対パスで例外に含める。

#### `cmd.save_img()` 解決順序

| 実行オプション | 保存先 |
|----------------|--------|
| 標準 | `runs\<run_id>\outputs\<filename>` |
| `filename` の先頭が実行中 macro ID | prefix 除去は行わず、指定どおり outputs 配下に保存 |

`cmd.save_img()` は戻り値を持たないため、保存先 `ResourceRef` は debug ログに記録する。新 API `RunArtifactStore.save_image()` は `ResourceRef` を返す。

#### Atomic write と overwrite policy

1. `OverwritePolicy.ERROR`: 既存ファイルがあれば `ResourceAlreadyExistsError`。
2. `OverwritePolicy.REPLACE`: 同一ディレクトリに一時ファイルを作り、成功後に `Path.replace()` する。
3. `OverwritePolicy.UNIQUE`: 拡張子を保持し、`sample.png`, `sample_1.png`, `sample_2.png` の順に空きパスを選ぶ。拡張子がない場合は `sample`, `sample_1`, `sample_2` とする。

画像保存は OpenCV がファイルパスを要求するため、`tempfile.NamedTemporaryFile(dir=output_root, delete=False, suffix=final_path.suffix)` 相当で同一ディレクトリに一時ファイルを作る。成功後は `Path.replace()` で最終ファイルへ置換する。同一ディレクトリ内の rename を前提に atomicity を確保するため、別ファイルシステムをまたぐ一時ディレクトリは使わない。`cv2.imwrite()` が `False` を返す、保存後に一時ファイルが存在しない、replace 後に最終ファイルが存在しない場合は `ResourceWriteError` とする。別ファイルシステム上の atomic write や NFS の rename semantics は後続課題とし、本仕様では保証しない。

atomic write の失敗時は一時ファイルを残さないことを原則とする。`cv2.imwrite()` が `False` を返した、一時ファイル作成に失敗した、`Path.replace()` が例外を送出した、最終ファイル検証に失敗した、または最大サイズ検証に失敗した場合は、存在する一時ファイルを削除してから `ResourceWriteError` を送出する。一時ファイル削除にも失敗した場合は、元の書き込み失敗を主エラーとし、削除失敗の例外型と mask 済み相対 path を `ResourceWriteError.details["cleanup_error"]` に保持する。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `resource.assets_root` | `Path` | `project_root\resources` | 標準 assets root |
| `resource.runs_root` | `Path` | `project_root\runs` | 標準 outputs root |
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
| ユニット | `test_resource_path_guard_accepts_windows_relative_path` | `images\result.png` を `images/result.png` と同じ相対 path として扱う |
| ユニット | `test_resource_path_guard_rejects_windows_drive_and_unc` | drive-relative、drive absolute、UNC、root 付き path を拒否する |
| ユニット | `test_resource_path_guard_rejects_parent_escape` | `..` による root 外参照を拒否する |
| ユニット | `test_resource_path_guard_rejects_symlink_escape` | root 内シンボリックリンクから root 外へ出る path を拒否する |
| ユニット | `test_macro_resource_scope_asset_lookup_order` | 標準 assets root、macro root assets、package resource の順に `load_img()` 候補を解決する |
| ユニット | `test_command_load_img_uses_resource_store` | `DefaultCommand.load_img()` が `ResourceStorePort.load_image()` へ委譲する |
| ユニット | `test_command_save_img_uses_run_artifact_store` | 標準モードの `save_img()` が `runs\<run_id>\outputs` へ保存する |
| ユニット | `test_command_save_img_does_not_strip_macro_id_prefix` | filename 先頭の macro ID を互換的に除去せず、指定どおり outputs 配下に保存する |
| ユニット | `test_save_image_checks_imwrite_return` | `cv2.imwrite()` が `False` の場合に `ResourceWriteError` を送出する |
| ユニット | `test_save_image_atomic_replace` | 一時ファイルから最終 path へ replace され、半端な最終ファイルを残さない |
| ユニット | `test_overwrite_policy_error_rejects_existing_file` | `OverwritePolicy.ERROR` が既存 output を拒否する |
| ユニット | `test_overwrite_policy_unique_keeps_extension` | `OverwritePolicy.UNIQUE` が `sample.png` 衝突時に `sample_1.png` を返す |
| ユニット | `test_macro_settings_resolver_does_not_use_resource_store` | settings lookup が Resource Store に依存しない |
| 結合 | `test_runtime_saves_command_images_to_run_outputs` | Runtime 経由の `cmd.save_img("sample/img/out.png")` が outputs 配下へ保存できる |
| 結合 | `test_sample_turbo_macro_saves_capture_to_run_outputs_without_prefix_stripping` | `sample_turbo_a_macro.py` の `cmd.save_img(capture_name, frame)` が macro ID prefix を除去せず outputs 配下へ保存できる |
| ハードウェア | `test_realdevice_run_artifact_save_image` | `@pytest.mark.realdevice`。実キャプチャ画像を run outputs へ保存できる |
| 性能 | `test_resource_path_guard_perf` | 1,000 path 解決の平均が目標値内である |

テストでは fake `ResourceStorePort` とテスト作業ディレクトリ配下の project root を使う。外部一時ディレクトリには依存しない。

## 6. 実装チェックリスト

- [x] `MacroResourceScope` のシグネチャ確定
- [x] `ResourceStorePort` と `RunArtifactStore` の責務分離を実装
- [x] `ResourcePathGuard` で path traversal を拒否
- [x] `cmd.load_img()` を新 assets lookup へ接続
- [x] `cmd.save_img()` を `RunArtifactStore` へ接続
- [x] `StaticResourceIO` 直接利用を削除し、互換 adapter を作らない
- [x] `MacroSettingsResolver` から Resource Store 依存を排除
- [x] `runs\<run_id>\outputs` の生成規則を Runtime builder に実装
- [x] atomic write と overwrite policy を実装
- [x] `cv2.imwrite()` と `cv2.imread()` の失敗を例外化
- [x] 代表マクロの保存互換を結合テストで固定
- [x] read-only assets と writable outputs の境界をドキュメントに反映
- [x] `git diff --check` がパス
- [x] 関連単体テストがパス

# マクロ互換性とレジストリ再設計 仕様書

> **文書種別**: 仕様書。既存マクロ互換契約、`MacroRegistry`、`MacroDefinition`、manifest ファイル形式、settings lookup の正本である。
> **対象モジュール**: `src/nyxpy/framework/core/macro/`  
> **目的**: 既存マクロ互換を最優先し、ロード・識別・実行基盤をレジストリ中心へ再設計する  
> **関連ドキュメント**: `.github/skills/framework-spec-writing/template.md`  
> **既存ソース**: `src/nyxpy/framework/core/macro/base.py`, `src/nyxpy/framework/core/macro/command.py`, `src/nyxpy/framework/core/macro/executor.py`, `src/nyxpy/framework/core/utils/helper.py`  
> **破壊的変更**: 既存ユーザーマクロの公開互換契約に対してはなし。`MacroExecutor` は互換契約に含めず、GUI/CLI/テストの参照解消後に削除する。

## 1. 概要

### 1.1 目的

現行マクロ資産を変更せずに動かし続けることを最優先し、マクロの発見・識別・生成・実行を `MacroRegistry` 中心の構成へ置き換える。既存の import path、ライフサイクル、Command API、定数 import、`static/<macro_name>/settings.toml` 参照は互換契約として固定し、内部実装と実行基盤は差し替え可能にする。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがボタン入力・待機・ログ・画像取得・画像保存・通知を行うための高レベル API |
| MacroBase | ユーザ定義マクロの抽象基底クラス。`initialize(cmd, args)` / `run(cmd)` / `finalize(cmd)` ライフサイクルを持つ |
| MacroExecutor | GUI / CLI から選択されたマクロを実行する既存の実行入口。再設計では公開互換契約、Runtime API、移行 adapter のいずれにも含めず削除する |
| MacroRuntime | マクロ発見・生成・実行・結果取得を統括する新しい実行中核 |
| MacroRegistry | 利用可能マクロを発見し、安定 ID とメタデータで管理する新しいレジストリ |
| MacroDefinition | 1 件のマクロを表す唯一の Python メタデータ型。ID、表示名、クラス、設定ファイル候補、ロード診断、factory を持つ |
| MacroFactory | 実行ごとに新しい `MacroBase` インスタンスを生成するファクトリ |
| MacroRunner | `initialize -> run -> finalize` を実行し、例外・中断・結果を `RunResult` に変換するコンポーネント |
| RunHandle | 非同期実行中のマクロに対する中断要求、完了待ち、結果取得を提供するハンドル |
| RunResult | 1 回のマクロ実行の成功・中断・失敗、例外、開始終了時刻を保持する結果値 |
| ExecutionContext | `run_id`、`macro_name`、Ports、中断トークン、options、`exec_args`、`metadata` を束ねる実行単位の値オブジェクト。`Command` は保持しない |
| Ports/Adapters | Runtime 中核がハードウェア・通知・ログ・GUI/CLI に直接依存しないための抽象境界と接続実装 |
| Legacy Compatibility Layer | 既存マクロが import する公開面を壊さない互換層。`MacroExecutor` は含めない |
| MacroManifest | `macro.toml` の永続化フォーマット名。Python クラスとしては定義せず、読み込み結果は `MacroDefinition` へ正規化する |
| MacroSettingsResolver | manifest settings path と `static/<macro_name>/settings.toml` 互換を解決する専用コンポーネント。画像リソース保存先は扱わない |
| LegacyMacroAdapter | 既存の `macros/<name>/macro.py`、`macros/<name>/__init__.py`、`macros/<name>.py` を変更なしで扱うアダプタ |
| Compatibility Contract | 既存マクロが依存している公開面を維持する契約。本仕様では破壊不可の要件として扱う |
| Qualified Macro ID | クラス名衝突を避けるための完全修飾 ID。例: `frlg_id_rng:FrlgIdRngMacro` |

### 1.3 背景・問題

現行 `MacroExecutor` は `Path.cwd() / "macros"` を探索し、見つけた `MacroBase` サブクラスを即時インスタンス化して `self.macros[obj.__name__]` に格納する。この方式には、同名クラスの衝突、`cwd` と `sys.path` への依存、ロード失敗時の診断不足、複数実行で同じインスタンス状態を再利用する問題がある。

既存マクロは `from nyxpy.framework.core.macro.base import MacroBase`、`from nyxpy.framework.core.macro.command import Command`、`from nyxpy.framework.core.constants import Button, LStick, Hat` などを直接 import している。これらの import path はマクロ資産の入口であり、内部再設計であっても壊してはならない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 既存マクロの変更必要数 | 0 件であるべきだが、実装変更時の契約が明文化されていない | 0 件を互換契約として固定 |
| import path 互換 | 暗黙維持 | `MacroBase` / `Command` / `constants` の path を絶対維持 |
| クラス名衝突 | 後勝ちで上書きされる | 衝突を診断し、`Qualified Macro ID` で両方選択可能 |
| ロード失敗診断 | ログ文字列のみ | `MacroLoadDiagnostic` と GUI / CLI 表示用メッセージを保持 |
| 実行ごとの状態分離 | reload 後に作ったインスタンスを再利用 | `MacroFactory.create()` で実行ごとに新規生成 |
| `cwd` 依存 | `Path.cwd()` 固定 | 明示 `project_root` を主経路にし、`cwd` は段階互換の fallback |

### 1.5 着手条件

- 既存テスト `uv run pytest tests/unit/executor/test_executor.py` が現状把握として確認されていること。
- GUI リロード挙動を検証する `tests/gui/test_macro_reload.py` が存在する場合は互換対象に含めること。
- 代表マクロ `macros/frlg_id_rng/macro.py`, `macros/frlg_initial_seed/macro.py`, `macros/frlg_gorgeous_resort/macro.py`, `macros/frlg_wild_rng/macro.py` の import、設定取得、ライフサイクルを維持対象として扱うこと。
- 本仕様の実装では、既存マクロのソース変更を要求しないこと。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/MACRO_COMPATIBILITY_AND_REGISTRY.md` | 新規 | 本仕様書 |
| `src/nyxpy/framework/core/macro/base.py` | 変更 | `MacroBase` の import path と lifecycle signature を維持。必要なら型注釈・docstring のみ補強 |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `Command` のメソッド名・引数互換を維持。実装差し替え時も既存メソッドを削除しない |
| `src/nyxpy/framework/core/macro/executor.py` | 削除 | GUI/CLI/テストの参照を `MacroRuntime` / `MacroRegistry` / `MacroFactory` へ移行した後に削除する |
| `src/nyxpy/framework/core/macro/registry.py` | 新規 | `MacroRegistry`, `MacroDefinition`, `MacroFactory`, `MacroLoadDiagnostic` を定義する正配置 |
| `src/nyxpy/framework/core/macro/settings_resolver.py` | 新規 | `MacroSettingsResolver` を定義し、settings TOML 解決を `ResourceStorePort` から分離 |
| `src/nyxpy/framework/core/macro/legacy_adapter.py` | 新規 | 旧方式マクロ探索・互換名生成を担当。settings 解決は `MacroSettingsResolver` へ委譲 |
| `src/nyxpy/framework/core/utils/helper.py` | 変更 | `load_macro_settings()` の既存挙動を維持し、新しい `MacroDefinition` ベース解決へ委譲可能にする |
| `tests/unit/executor/test_executor.py` | 変更 | 既存テストを維持し、衝突・失敗診断・実行ごとの新規インスタンス生成のテストを追加 |
| `tests/gui/test_macro_reload.py` | 変更 | 存在する場合、追加・削除リロード互換とロード失敗表示を検証 |
| `tests/unit/macro/test_registry.py` | 新規 | レジストリ、マニフェスト、Legacy adapter の純粋ロジックを検証 |
| `tests/integration/test_macro_registry_compat.py` | 新規 | 実際の `macros/` と `static/` 配置に近い構成で互換ロードを検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`MacroRegistry` はフレームワーク層のマクロ実行基盤に属する。GUI / CLI は `MacroRuntime` / `MacroRegistry` を呼び出す。`MacroExecutor` は再設計後の入口に使わず、フレームワーク層から GUI / CLI / 個別マクロへ逆依存しない。

依存方向は次の通りである。

```text
nyxpy.gui / nyxpy.cli
  -> nyxpy.framework.core.runtime
  -> nyxpy.framework.core.macro.registry
  -> nyxpy.framework.core.macro.legacy_adapter
  -> nyxpy.framework.core.macro.base / command / utils

macros/<name> -> nyxpy.framework.*       OK
nyxpy.framework.* -> macros/<name>       NG
```

レジストリは「マクロを import する」機能を持つが、個別マクロのシンボルに静的依存しない。探索対象のパスから動的ロードするだけに限定する。

### 公開 API 方針

`MacroExecutor` は Compatibility Contract の対象ではない。旧入口の例外再送出、成功時 `None` 戻り値、`macros` / `macro` 属性は保証しない。新 API は `MacroRegistry` と `MacroRuntime` へ追加し、既存 GUI / CLI はこれらへ直接移行する。

### 後方互換性

#### Compatibility Contract

次の項目は絶対維持する。内部実装の置換、モジュール分割、ロード方式変更があっても破壊してはならない。

| 項目 | 絶対維持する内容 | 互換判定 |
|------|------------------|----------|
| import path | `from nyxpy.framework.core.macro.base import MacroBase` | 既存マクロが import できる |
| import path | `from nyxpy.framework.core.macro.command import Command` | 既存マクロが import できる |
| constants import | `from nyxpy.framework.core.constants import Button, Hat, LStick, RStick, KeyType` | `__all__` 経由で import できる |
| lifecycle signature | `initialize(self, cmd: Command, args: dict) -> None` | 実行前に 1 回呼ばれる |
| lifecycle signature | `run(self, cmd: Command) -> None` | `initialize` 成功後に 1 回呼ばれる |
| lifecycle signature | `finalize(self, cmd: Command) -> None` | 例外・中断時も可能な限り呼ばれる |
| Command method names | `press`, `hold`, `release`, `wait`, `stop`, `log`, `capture`, `save_img`, `load_img`, `keyboard`, `type`, `notify`, `touch`, `touch_down`, `touch_up`, `disable_sleep` | 既存名を削除・改名しない |
| Command argument compatibility | `press(*keys, dur=0.1, wait=0.1)` など現行キーワード | 既存呼び出しが TypeError にならない |
| settings lookup | `static/<macro_name>/settings.toml` | 旧配置の TOML が読み込まれる |
| exec args merge | file settings より `exec_args` が優先 | 現行 `args = {**file_args, **exec_args}` と同じ |
| macro metadata | `description: str`, `tags: list[str]` | GUI 一覧・タグ抽出で利用できる |

`static settings lookup` は `MacroSettingsResolver` が担当する。画像保存・読み込み用の `ResourceStorePort` は settings TOML を探索しない。優先順は次の通りである。

1. `macro.toml [macro].settings` に明示されたパス。`static/...` のような通常パスは `project_root` 相対、`./settings.toml` のように `./` で始まるパスは manifest を置いた macro root 相対として解決する。絶対パスと `..` による root 外参照は拒否する。
2. legacy package 名から `project_root/static/<package_name>/settings.toml`。
3. legacy single-file 名から `project_root/static/<module_stem>/settings.toml`。
4. `cwd` 起点の legacy fallback。非推奨警告を出すが、非推奨期間中は読み込む。

旧方式は非推奨にするが、即削除しない。少なくとも 2 minor release または 6 か月の長い方を非推奨期間とし、その間は `warnings.warn(..., DeprecationWarning)` とログで移行先を案内する。既存マクロは変更不要である。新方式は `macro.toml` を置いたマクロだけが opt-in する。

#### 互換ポリシー表

| 区分 | 対象 | 方針 |
|------|------|------|
| 永久維持 | `MacroBase` / `Command` / `DefaultCommand` / constants import、`MacroBase` lifecycle、`Command` method names、`MacroStopException` constructor 互換、static settings lookup | 既存マクロ変更不要のため破壊不可。 |
| 削除対象 | `MacroExecutor` | 既存ユーザーマクロ互換契約には含めない。GUI/CLI/テストを新 API へ移行した後に削除し、シグネチャ保証、adapter 契約、import shim は提供しない。 |
| 一時互換 | legacy loader, `cwd` fallback | 既存マクロのロード互換に必要な範囲だけ警告付きで残す。 |
| 非推奨後削除候補 | 恒久的な `sys.path` 変更、曖昧な class 名選択、暗黙 dummy fallback、`cwd` のみに依存する探索 | 移行期間後、別仕様で削除可否を判断する。 |

### レイヤー構成

| レイヤー | 責務 | 主要クラス |
|----------|------|------------|
| 公開互換レイヤー | 既存ユーザーマクロが import する path と lifecycle / Command API を維持 | `MacroBase`, `Command`, `DefaultCommand`, constants, `MacroStopException` |
| 移行アダプタ | 必要な場合だけ旧 GUI/CLI/テスト入口を Runtime へ委譲 | `MacroExecutor` |
| レジストリレイヤー | マクロ一覧、ID、診断、ファクトリを管理 | `MacroRegistry`, `MacroDefinition` |
| 生成レイヤー | 実行ごとの新規インスタンス生成 | `MacroFactory` |
| 宣言レイヤー | 新方式の `macro.toml` 読み込み。読み込み結果は `MacroDefinition` へ正規化する | `macro.toml` |
| 旧方式アダプタ | 既存ファイル構造・表示名を解決 | `LegacyMacroAdapter` |
| 設定解決 | manifest settings と legacy static settings を解決 | `MacroSettingsResolver` |

### クラス名衝突方針

現行は `self.macros[obj.__name__] = instance` のため、同じクラス名が複数あると後勝ちで上書きされる。新方式では `MacroDefinition.id` を主キーにする。

- manifest あり: `id = manifest.id`。
- legacy package: `id = "<package_name>:<class_name>"`。
- legacy single-file: `id = "<module_stem>:<class_name>"`。
- `class_name` が一意な場合だけ、互換 alias として `class_name` でも選択可能。
- `class_name` が衝突した場合、`set_active_macro("ClassName")` は `AmbiguousMacroError` を送出し、候補 ID をメッセージに含める。
- GUI/CLI は `MacroRegistry.resolve()` の `AmbiguousMacroError` を表示用エラーへ変換する。`MacroExecutor.set_active_macro()` の旧互換は保証しない。

### cwd / sys.path 依存の扱い

`MacroRegistry(project_root: Path)` を主経路にする。`project_root` 未指定時だけ `Path.cwd()` を fallback とする。legacy import のために探索対象 root を一時的に `sys.path` へ追加する場合は context manager で囲み、ロード後に元へ戻す。恒久的な `sys.path.append(str(Path.cwd()))` は廃止する。

相対 import を使う package 型マクロは、現在と同じく `macros/<package>/__init__.py` または manifest entrypoint から import できる必要がある。`macros/shared/*` への依存は許可する。

### ロード失敗診断

ロード失敗は握りつぶさない。レジストリは成功したマクロと失敗診断を分けて保持する。

- GUI は成功マクロを一覧表示し、失敗診断を別ペインまたはログへ出す。
- CLI は `nyx-cli` の一覧表示時に失敗数と `module`, `path`, `exception_type`, `message` を出す。
- 1 件のマクロが失敗しても他のマクロのロードは継続する。

### 実行ごとのマクロインスタンス生成

`MacroDefinition` はクラス情報と `MacroFactory` を持つだけで、実行状態を持たない。`MacroRuntime` は毎回 `factory.create()` で新しいインスタンスを作る。これにより `initialize()` で設定された `_cfg`、カウンタ、OCR キャッシュなどが前回実行から漏れない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 100 マクロ探索時間 | 実機なしのローカル環境で 1 秒未満を目標 |
| 1 件ロード失敗時の影響 | 他マクロのロードを継続し、全体 reload を失敗させない |
| `set_active_macro()` | 登録済み ID / alias に対して O(1) |
| 実行時インスタンス生成 | `initialize()` 前に 1 回だけ |

### 並行性・スレッド安全性

マクロ実行自体は 1 `MacroRuntime` あたり単一実行を前提とする。`MacroRegistry.reload()` は内部ロックを持ち、GUI の reload ボタンと CLI 操作が同時に走っても `definitions` と `diagnostics` が中途半端な状態で参照されないようにする。

`CancellationToken` と `Command` の中断挙動は現行を維持する。`MacroRegistry` はハードウェアデバイスを保持せず、`Command` の生成や実機接続は既存の上位処理に任せる。

## 4. 実装仕様

### 公開インターフェース

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.runtime import MacroRuntime, RunResult


class MacroLoadError(Exception):
    """マクロロードに失敗したことを表す例外。"""


class AmbiguousMacroError(ValueError):
    """互換名が複数マクロへ解決される場合に送出する。"""

    def __init__(self, requested_name: str, candidates: Sequence[str]) -> None: ...


@dataclass(frozen=True)
class MacroLoadDiagnostic:
    macro_id: str | None
    source_path: Path
    module_name: str
    exception_type: str
    message: str
    traceback: str


class MacroFactory(Protocol):
    def create(self) -> MacroBase:
        """実行ごとに新しい MacroBase インスタンスを返す。"""


@dataclass(frozen=True)
class ClassMacroFactory:
    macro_cls: type[MacroBase]

    def create(self) -> MacroBase: ...


@dataclass(frozen=True)
class MacroDefinition:
    id: str
    aliases: tuple[str, ...]
    display_name: str
    class_name: str
    module_name: str
    source_path: Path
    settings_path: Path | None
    description: str
    tags: tuple[str, ...]
    factory: MacroFactory
    manifest_path: Path | None = None
    legacy: bool = False


class MacroSettingsResolver:
    def __init__(self, project_root: Path) -> None: ...

    def resolve(self, definition: "MacroDefinition") -> Path | None: ...

    def load(self, definition: "MacroDefinition") -> dict: ...


class MacroRegistry:
    def __init__(
        self,
        project_root: Path | None = None,
        macros_dir: Path | None = None,
        settings_resolver: MacroSettingsResolver | None = None,
    ) -> None: ...

    @property
    def definitions(self) -> Mapping[str, MacroDefinition]: ...

    @property
    def diagnostics(self) -> Sequence[MacroLoadDiagnostic]: ...

    def reload(self) -> None: ...

    def resolve(self, name_or_id: str) -> MacroDefinition: ...

    def create(self, name_or_id: str) -> MacroBase: ...

    def list(self, include_failed: bool = False) -> Sequence[MacroDefinition]: ...

    def get_settings(self, definition: MacroDefinition) -> dict: ...  # MacroSettingsResolver へ委譲


class LegacyMacroAdapter:
    def __init__(self, project_root: Path, macros_dir: Path) -> None: ...

    def discover(self) -> Sequence[Path]: ...

    def load_definition(self, path: Path) -> MacroDefinition: ...

    def resolve_settings_path(self, macro_cls: type[MacroBase]) -> Path | None: ...
```

`macro.toml` は入力ファイル形式であり、`MacroManifest` という Python クラスは定義しない。読み込み処理は TOML を検証して `MacroDefinition` を生成する。

既存 `Command` の公開メソッド名は維持する。

```python
class Command(ABC):
    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None: ...
    def hold(self, *keys: KeyType) -> None: ...
    def release(self, *keys: KeyType) -> None: ...
    def wait(self, wait: float) -> None: ...
    def stop(self) -> None: ...
    def log(self, *values, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None: ...
    def capture(self, crop_region: tuple[int, int, int, int] = None, grayscale: bool = False): ...
    def save_img(self, filename: str | Path, image) -> None: ...
    def load_img(self, filename: str | Path, grayscale: bool = False): ...
    def keyboard(self, text: str) -> None: ...
    def type(self, key: str | KeyCode | SpecialKeyCode) -> None: ...
    def notify(self, text: str, img=None) -> None: ...
    def touch(self, x: int, y: int, dur: float = 0.1, wait: float = 0.1) -> None: ...
    def touch_down(self, x: int, y: int) -> None: ...
    def touch_up(self) -> None: ...
    def disable_sleep(self, enabled: bool = True) -> None: ...
```

### 実行シーケンス

```text
GUI/CLI
  -> definition = registry.resolve(name_or_id)
  -> settings = settings_resolver.load(definition)
  -> context = runtime_builder.build(definition, settings, exec_args)
  -> result = runtime.run(context)
```

`MacroRuntime` が registry 解決結果、factory 呼び出し、Ports 準備、Port close を担当し、`MacroRunner` がライフサイクル実行、`MacroStopException` 正規化、`RunResult` 生成を担当する。

### Manifest 仕様

新方式は `macros/<macro_name>/macro.toml` を置いた場合のみ opt-in する。manifest が存在しないマクロは `LegacyMacroAdapter` で従来通り扱う。

```toml
[macro]
id = "frlg_id_rng"
entrypoint = "macros.frlg_id_rng.macro:FrlgIdRngMacro"
display_name = "FRLG TID乱数調整マクロ"
description = "FRLG TID乱数調整マクロ (Switch 720p)"
tags = ["pokemon", "frlg", "rng", "tid"]
version = "1.0.0"
settings = "static/frlg_id_rng/settings.toml"
```

manifest の `entrypoint` は `module:ClassName` 形式である。`class_name` は原則不要だが、将来の拡張で複数 entrypoint を扱う場合に備えて予約する。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `project_root` | `Path | None` | `None` | `MacroRegistry` の探索起点。`None` の場合は `Path.cwd()` を段階互換 fallback とする |
| `macros_dir` | `Path | None` | `None` | 探索対象ディレクトリ。`None` の場合は `<project_root>/macros` |
| `macro.toml [macro].id` | `str` | なし | 新方式の安定 ID。省略不可 |
| `macro.toml [macro].entrypoint` | `str` | なし | `module:ClassName` 形式の entrypoint。省略不可 |
| `macro.toml [macro].display_name` | `str | None` | class 名 | GUI / CLI 表示名 |
| `macro.toml [macro].description` | `str | None` | class 属性 `description` | マクロ説明文 |
| `macro.toml [macro].tags` | `list[str]` | `[]` | GUI タグフィルタ用 |
| `macro.toml [macro].settings` | `str | None` | legacy lookup | TOML 設定ファイルの相対パス。`static/...` は project-root 相対、`./...` は macro-root 相対 |

### Legacy loader 仕様

`LegacyMacroAdapter.discover()` は次を探索する。

| 形式 | 例 | module_name | legacy macro_name |
|------|----|-------------|-------------------|
| package `__init__.py` | `macros/frlg_id_rng/__init__.py` | `macros.frlg_id_rng` | `frlg_id_rng` |
| package `macro.py` | `macros/frlg_id_rng/macro.py` | `macros.frlg_id_rng.macro` | `frlg_id_rng` |
| single file | `macros/sample.py` | `macros.sample` | `sample` |

package に `macro.toml` がある場合は manifest を優先する。manifest がない場合、従来の `__init__.py` import と `macro.py` import の両方を許容する。ただし同一 package から同じ class が二重登録される場合は 1 件に統合し、診断に重複を記録する。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `MacroLoadError` | module import、manifest parse、entrypoint 解決、`MacroBase` 継承確認に失敗 |
| `AmbiguousMacroError` | 互換 alias が複数 `MacroDefinition` に一致 |
| `ValueError` | `set_active_macro()` で存在しない名前を指定。現行互換のため維持 |
| `FileNotFoundError` | 明示 manifest settings が存在必須と指定された将来拡張で未検出 |

ロード中の例外は `MacroRegistry.diagnostics` に蓄積し、reload 全体は継続する。実行中の例外は `MacroRunner` が `RunResult` へ正規化する。

### シングルトン管理

`MacroRegistry` はシングルトンにしない。GUI / CLI ごとに `MacroRuntime` または `MacroRegistry` を所有する。グローバル化が必要になった場合も `core/singletons.py` に集約し、`reset_for_testing()` でリセット可能にする。

### 移行計画

| 段階 | 方針 | 既存マクロへの影響 |
|------|------|--------------------|
| Phase 1 | `MacroRegistry` と `MacroDefinition` を導入し、GUI/CLI/テストが `MacroExecutor` を経由しない入口を用意する | 変更不要 |
| Phase 2 | GUI / CLI が definition ID と診断を表示 | 変更不要 |
| Phase 3 | `macro.toml` を任意導入。導入したマクロだけ新方式 | 変更不要 |
| Phase 4 | 旧方式に `DeprecationWarning` と移行ログを追加 | 実行継続 |
| Phase 5 | 非推奨期間後に削除可否を再判断 | 削除判断時は別仕様で扱う |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_registry_loads_legacy_package_macro` | `macros/pkg/macro.py` の `MacroBase` サブクラスを `MacroDefinition` として登録する |
| ユニット | `test_registry_loads_legacy_single_file_macro` | `macros/sample.py` を `sample:ClassName` で登録する |
| ユニット | `test_registry_loads_manifest_macro` | `macro.toml` の `entrypoint` と `settings` を優先する |
| ユニット | `test_class_name_alias_is_available_when_unique` | class 名が一意なら `set_active_macro("ClassName")` が通る |
| ユニット | `test_class_name_collision_requires_qualified_id` | 同名 class が複数ある場合に `AmbiguousMacroError` と候補 ID を返す |
| ユニット | `test_load_failure_is_reported_without_stopping_reload` | 1 件 import 失敗しても他マクロが登録され、diagnostics に失敗理由が残る |
| ユニット | `test_execute_creates_new_instance_each_time` | 2 回 execute して `MacroFactory.create()` が 2 回呼ばれ、状態が共有されない |
| ユニット | `test_settings_legacy_package_lookup` | `static/<package>/settings.toml` が読み込まれる |
| ユニット | `test_settings_legacy_single_file_lookup` | `static/<module_stem>/settings.toml` が読み込まれる |
| ユニット | `test_exec_args_override_file_settings` | file settings より `exec_args` が優先される |
| ユニット | `test_command_method_names_are_compatible` | `Command` が互換契約のメソッド名を持つ |
| ユニット | `test_command_type_accepts_str_keycode_special_keycode` | `Command.type(key: str | KeyCode | SpecialKeyCode)` の呼び出し互換を検証する |
| ユニット | `test_manifest_settings_path_resolution` | manifest settings が project-root 相対と macro-root 相対を区別して解決される |
| ユニット | `test_macro_executor_removed` | `MacroExecutor` を新 API、互換契約、移行 adapter として公開しない |
| ユニット | `test_constants_import_contract` | `from nyxpy.framework.core.constants import Button, Hat, LStick, RStick, KeyType` が成功する |
| 結合 | `test_existing_repository_macros_load_without_changes` | 代表マクロ 4 件が変更なしでロードされる |
| 結合 | `test_gui_cli_do_not_import_macro_executor` | GUI/CLI が `MacroExecutor` を import せず `MacroRuntime` / `MacroRegistry` を使う |
| GUI | `test_macro_reload_add_and_remove_real_env` | 既存 GUI リロードテストの追加・削除挙動を維持する |
| GUI | `test_macro_reload_shows_load_diagnostics` | 壊れたマクロを追加しても一覧は表示され、診断が確認できる |
| パフォーマンス | `test_registry_reload_100_macros_perf` | 100 件の dummy macro reload が 1 秒未満を目標に完了する |
| ハードウェア | `test_macro_execution_realdevice` | 必要に応じて `@pytest.mark.realdevice` で実機接続時の Command 送信を確認する |

既存 `tests/unit/executor/test_executor.py` は Runtime / Registry 入口のテストへ置き換える。`MacroExecutor.macros`、`MacroExecutor.macro`、`MacroExecutor.execute()` の戻り値互換は保証しない。新規テストは `tmp_path` と `monkeypatch.syspath_prepend()` を使い、実リポジトリの `macros/` を破壊しない。

実装後に最低限実行するコマンドは次である。

```powershell
uv run pytest tests/unit/executor/test_executor.py
uv run pytest tests/unit/macro/test_registry.py
uv run pytest tests/gui/test_macro_reload.py
uv run ruff check .
```

## 6. 実装チェックリスト

- [x] 既存 import path の互換契約を明記
- [x] lifecycle signature の互換契約を明記
- [x] Command method names の互換契約を明記
- [x] constants import の互換契約を明記
- [x] static settings lookup の段階互換を明記
- [x] `MacroRegistry`, `MacroDefinition`, `MacroFactory`, `macro.toml`, `LegacyMacroAdapter` の責務を定義
- [x] クラス名衝突時の ID / alias 方針を定義
- [x] `cwd` / `sys.path` 依存の解消方針を定義
- [x] ロード失敗診断の保持方針を定義
- [x] 実行ごとのマクロインスタンス生成を定義
- [x] 既存マクロ変更不要、新方式 opt-in、旧方式非推奨期間の方針を定義
- [x] 対象ファイル表を作成
- [x] 公開 API シグネチャを作成
- [x] 設定例 TOML を作成
- [x] テスト方針を作成

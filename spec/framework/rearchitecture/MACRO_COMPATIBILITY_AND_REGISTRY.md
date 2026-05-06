# マクロ互換性とレジストリ再設計 仕様書

> **文書種別**: 仕様書。既存マクロ import / lifecycle 互換契約、`MacroRegistry`、`MacroDefinition`、manifest 任意採用、settings lookup の正本である。
> **対象モジュール**: `src/nyxpy/framework/core/macro/`  
> **目的**: 既存マクロの import / lifecycle 互換を維持しつつ、ロード・識別・実行基盤をレジストリ中心へ再設計する
> **関連ドキュメント**: `.github/skills/framework-spec-writing/template.md`  
> **既存ソース**: `src/nyxpy/framework/core/macro/base.py`, `src/nyxpy/framework/core/macro/command.py`, `src/nyxpy/framework/core/macro/executor.py`, `src/nyxpy/framework/core/utils/helper.py`  
> **破壊的変更**: Resource I/O、settings lookup、旧 auto discovery、`DefaultCommand` 旧コンストラクタはマクロ側移行を前提に破壊的変更を許容する。`MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import と lifecycle は維持する。

## 1. 概要

### 1.1 目的

既存マクロの import path、ライフサイクル、Command API、定数 import を維持しつつ、マクロの発見・識別・生成・実行を `MacroRegistry` 中心の構成へ置き換える。`macro.toml` は必須にせず、複数 entrypoint、import 前 metadata、args schema などの高度機能で使う明示形式とする。`static/<macro_name>/settings.toml` 参照、旧 `cwd` fallback、クラス名だけに依存する旧 auto discovery は互換契約として固定せず、manifest / class metadata / convention の新方式へ移行する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがボタン入力・待機・ログ・画像取得・画像保存・通知を行うための高レベル API |
| MacroBase | ユーザ定義マクロの抽象基底クラス。`initialize(cmd, args)` / `run(cmd)` / `finalize(cmd)` ライフサイクルを持つ |
| MacroExecutor | GUI / CLI から選択されたマクロを実行する既存の実行入口。再設計では公開互換契約、Runtime API、移行 adapter のいずれにも含めず削除する |
| MacroRuntime | マクロ発見・生成・実行・結果取得を統括する新しい実行中核 |
| MacroRegistry | 利用可能マクロを発見し、安定 ID とメタデータで管理する新しいレジストリ |
| MacroDefinition | 1 件のマクロを表す唯一の Python メタデータ型。ID、表示名、クラス、設定ファイル候補、ロード診断、factory を持つ |
| MacroFactory | `MacroDefinition` が所有する生成責務。実行ごとに新しい `MacroBase` インスタンスを返す |
| MacroRunner | `initialize -> run -> finalize` を実行し、例外・中断・結果を `RunResult` に変換するコンポーネント |
| RunHandle | 非同期実行中のマクロに対する中断要求、完了待ち、結果取得を提供するハンドル |
| RunResult | 1 回のマクロ実行の成功・中断・失敗、例外、開始終了時刻を保持する結果値 |
| ExecutionContext | `run_id`、`macro_name`、Ports、中断トークン、options、`exec_args`、`metadata` を束ねる実行単位の値オブジェクト。`Command` は保持しない |
| Ports/Adapters | Runtime 中核がハードウェア・通知・ログ・GUI/CLI に直接依存しないための抽象境界と接続実装 |
| Compatibility Layer | 既存マクロが import する公開面を壊さない互換層。`MacroExecutor` は含めない |
| MacroManifest | 任意の `macro.toml` 永続化フォーマット名。Python クラスとしては定義せず、読み込み結果は `MacroDefinition` へ正規化する |
| Class metadata | `MacroBase` 派生クラスに置く `macro_id`、`display_name`、`description`、`tags`、`settings_path` などの任意属性 |
| Convention discovery | manifest がない軽量マクロを、`macros/<id>.py`、`macros/<id>/macro.py`、`macros/<id>/__init__.py` と 1 件の `MacroBase` 派生クラスから決定的に発見する規約 |
| MacroSettingsResolver | manifest または class metadata の settings source を解決する専用コンポーネント。画像リソース保存先は扱わない |
| Manifest entrypoint | `macro.toml [macro].entrypoint` で明示された `module:ClassName`。manifest を使う場合の最優先 entrypoint |
| Compatibility Contract | 既存マクロが依存している公開面を維持する契約。本仕様では破壊不可の要件として扱う |
| Qualified Macro ID | クラス名衝突を避けるための完全修飾 ID。例: `frlg_id_rng:FrlgIdRngMacro` |

### 1.3 背景・問題

現行 `MacroExecutor` は `Path.cwd() / "macros"` を探索し、見つけた `MacroBase` サブクラスを即時インスタンス化して `self.macros[obj.__name__]` に格納する。この方式には、同名クラスの衝突、`cwd` と `sys.path` への依存、ロード失敗時の診断不足、複数実行で同じインスタンス状態を再利用する問題がある。

既存マクロは `from nyxpy.framework.core.macro.base import MacroBase`、`from nyxpy.framework.core.macro.command import Command`、`from nyxpy.framework.core.constants import Button, LStick, Hat` などを直接 import している。これらの import path はマクロ資産の入口であり、内部再設計であっても壊してはならない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 既存マクロの変更必要数 | 0 件であるべきだが、実装変更時の契約が明文化されていない | Resource/settings は移行ガイドに従って変更。軽量マクロは manifest なしでもロード可能 |
| import path 互換 | 暗黙維持 | `MacroBase` / `Command` / `constants` の path を絶対維持 |
| クラス名衝突 | 後勝ちで上書きされる | 衝突を診断し、`Qualified Macro ID` で両方選択可能 |
| ロード失敗診断 | ログ文字列のみ | `MacroLoadDiagnostic` と GUI / CLI 表示用メッセージを保持 |
| 実行ごとの状態分離 | reload 後に作ったインスタンスを再利用 | `definition.factory.create()` で実行ごとに新規生成 |
| `cwd` 依存 | `Path.cwd()` 固定 | 明示 `project_root` を必須経路にし、`cwd` fallback を削除 |

### 1.5 着手条件

- 既存テスト `uv run pytest tests/unit/executor/test_executor.py` が現状把握として確認されていること。
- GUI リロード挙動を検証する `tests/gui/test_macro_reload.py` が存在する場合は互換対象に含めること。
- 代表マクロ `macros/frlg_id_rng/macro.py`, `macros/frlg_initial_seed/macro.py`, `macros/frlg_gorgeous_resort/macro.py`, `macros/frlg_wild_rng/macro.py` の import とライフサイクルを維持対象として扱うこと。
- Resource I/O、settings、entrypoint については既存マクロのソース変更を要求してよい。変更内容は `MACRO_MIGRATION_GUIDE.md` に集約すること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/MACRO_COMPATIBILITY_AND_REGISTRY.md` | 新規 | 本仕様書 |
| `src/nyxpy/framework/core/macro/base.py` | 変更 | `MacroBase` の import path と lifecycle signature を維持。必要なら型注釈・docstring のみ補強 |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `Command` のメソッド名・引数互換を維持。実装差し替え時も既存メソッドを削除しない |
| `src/nyxpy/framework/core/macro/executor.py` | 削除 | GUI/CLI/テストの参照を `MacroRuntime` / `MacroRegistry` / `MacroFactory` へ移行した後に削除する |
| `src/nyxpy/framework/core/macro/registry.py` | 新規 | `MacroRegistry`, `MacroDefinition`, `MacroFactory`, `MacroLoadDiagnostic` を定義する正配置 |
| `src/nyxpy/framework/core/macro/settings_resolver.py` | 新規 | `MacroSettingsResolver` を定義し、settings TOML 解決を `ResourceStorePort` から分離 |
| `src/nyxpy/framework/core/macro/entrypoint_loader.py` | 新規 | manifest / class metadata / convention から package / single-file macro を解決する |
| `src/nyxpy/framework/core/utils/helper.py` | 変更 | `load_macro_settings()` の旧 fallback を削除し、必要なら `MacroSettingsResolver` へ委譲 |
| `tests/unit/executor/test_executor.py` | 変更 | 既存テストを維持し、衝突・失敗診断・実行ごとの新規インスタンス生成のテストを追加 |
| `tests/gui/test_macro_reload.py` | 変更 | 存在する場合、追加・削除リロード互換とロード失敗表示を検証 |
| `tests/unit/framework/macro/test_registry.py` | 新規 | レジストリ、manifest 任意採用、class metadata、convention discovery の純粋ロジックを検証 |
| `tests/integration/test_macro_registry_migration.py` | 新規 | 移行後 `macros/` の manifest あり / なし構成でロードを検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`MacroRegistry` はフレームワーク層のマクロ実行基盤に属する。GUI / CLI は `MacroRuntime` / `MacroRegistry` を呼び出す。`MacroExecutor` は再設計後の入口に使わず、フレームワーク層から GUI / CLI / 個別マクロへ逆依存しない。

依存方向は次の通りである。

```text
nyxpy.gui / nyxpy.cli
  -> nyxpy.framework.core.runtime
  -> nyxpy.framework.core.macro.registry
  -> nyxpy.framework.core.macro.entrypoint_loader
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
| exec args merge | file settings より `exec_args` が優先 | 現行 `args = {**file_args, **exec_args}` と同じ |
| macro metadata | `description: str`, `tags: list[str]` | GUI 一覧・タグ抽出で利用できる |

`MacroSettingsResolver` は `MacroDefinition.settings_path` の解決だけを担当する。`settings_path` は manifest または class metadata から明示された場合だけ設定される。画像保存・読み込み用の `ResourceStorePort` は settings TOML を探索しない。解決順は次の通りである。

1. `macro.toml [macro].settings` に明示されたパス。`project:` prefix は `project_root` 相対、通常の相対パスは manifest を置いた macro root 相対として解決する。
2. class metadata `settings_path` に明示されたパス。`project:` prefix は `project_root` 相対、通常の相対パスは macro root 相対として解決する。
3. どちらも指定がない場合は settings file を読み込まず、`MacroSettingsResolver.resolve()` は `None` を返す。

`macro.toml` と class metadata に永続化する path 文字列は portable path として `/` のみを使う。Windows 実行環境でも `project:resources/frlg_id_rng/settings.toml` のように記述し、`\` は入力エラーとして診断する。実ファイルパスへの変換は resolver が行う。

`static/<macro_name>/settings.toml`、package / single-file 名からの settings 推測、`cwd` 起点 fallback は残さない。必要な settings は manifest または class metadata に明示し、マクロ移行ガイドで移動手順を示す。

#### 互換ポリシー表

| 区分 | 対象 | 方針 |
|------|------|------|
| 永久維持 | `MacroBase` / `Command` / `DefaultCommand` / constants import、`MacroBase` lifecycle、`Command` method names、`MacroStopException` constructor 互換 | Runtime 再設計後も破壊しない。 |
| 削除対象 | `MacroExecutor` | 既存ユーザーマクロ互換契約には含めない。GUI/CLI/テストを新 API へ移行した後に削除し、シグネチャ保証、adapter 契約、import shim は提供しない。 |
| 破壊的変更 | static settings lookup、旧 auto discovery、`cwd` fallback、`DefaultCommand` 旧コンストラクタ | マクロ移行ガイドに従って修正する。軽量マクロは convention discovery へ移行できる。 |
| 削除対象 | 恒久的な `sys.path` 変更、曖昧な class 名選択、暗黙 dummy fallback、`cwd` のみに依存する探索 | 新 Runtime 経路では残さない。 |

### レイヤー構成

| レイヤー | 責務 | 主要クラス |
|----------|------|------------|
| 公開互換レイヤー | 既存ユーザーマクロが import する path と lifecycle / Command API を維持 | `MacroBase`, `Command`, `DefaultCommand`, constants, `MacroStopException` |
| 旧入口移行対象 | 旧 GUI/CLI/テスト入口の参照を Runtime へ移行し、削除対象を明確にする | なし。`MacroExecutor` は adapter ではなく削除対象 |
| レジストリレイヤー | マクロ一覧、ID、診断、ファクトリを管理 | `MacroRegistry`, `MacroDefinition` |
| 生成レイヤー | 実行ごとの新規インスタンス生成 | `MacroFactory` |
| 宣言レイヤー | 任意の `macro.toml` と class metadata を読み込み、`MacroDefinition` へ正規化する | `macro.toml`, class metadata |
| entrypoint 解決 | manifest entrypoint、または convention discovery から package / single-file を解決 | `MacroDefinition.entrypoint_kind` |
| 設定解決 | manifest / class metadata settings を解決 | `MacroSettingsResolver` |

### クラス名衝突方針

現行は `self.macros[obj.__name__] = instance` のため、同じクラス名が複数あると後勝ちで上書きされる。新方式では `MacroDefinition.id` を主キーにする。

- manifest あり: `id = manifest.id`。
- manifest なし: class metadata `macro_id` があれば採用し、なければファイル名またはディレクトリ名を `id` にする。
- single-file macro は `macros/<id>.py` に `MacroBase` 派生クラスが 1 件だけある場合に convention discovery で扱う。複数候補がある場合は manifest を必須にする。
- `class_name` が一意な場合だけ、互換 alias として `class_name` でも選択可能。
- `class_name` が衝突した場合、`set_active_macro("ClassName")` は `AmbiguousMacroError` を送出し、候補 ID をメッセージに含める。
- GUI/CLI は `MacroRegistry.resolve()` の `AmbiguousMacroError` を表示用エラーへ変換する。`MacroExecutor.set_active_macro()` の旧互換は保証しない。

### cwd / sys.path 依存の扱い

`MacroRegistry(project_root: Path)` を主経路にし、`Path.cwd()` fallback は使わない。manifest entrypoint または convention discovery 対象を import する際に探索対象 root を一時的に `sys.path` へ追加する必要がある場合は context manager で囲み、ロード後に元へ戻す。恒久的な `sys.path.append(str(Path.cwd()))` は廃止する。

相対 import を使う package 型マクロは、manifest entrypoint または convention discovery で import できる必要がある。`macros/shared/*` への依存は許可する。

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

| lock 名 | 種別 | 保護対象 | 取得順 | timeout | timeout 時の例外 | 保持してはいけない処理 | テスト名 |
|---------|------|----------|--------|---------|------------------|------------------------|----------|
| `registry_reload_lock` | `threading.RLock` | `definitions`、`diagnostics`、alias map の snapshot 交換 | 全体 1 番目。`run_start_lock` より先 | 2 秒 | `RegistryLockTimeoutError` | module import、ユーザー macro class 生成、settings TOML parse、GUI 通知、ログ sink emit | `test_registry_reload_swaps_snapshot_atomically` |

`EntryPointLoader.load_definition()` は manifest entrypoint または convention discovery を解決し、ローカル変数へ候補を集める。`MacroRegistry.reload()` は最後に `registry_reload_lock` を取得して snapshot を一括交換する。`resolve()`、`list()`、`definitions`、`diagnostics` は lock 内で immutable snapshot への参照または浅い copy を取得し、呼び出し元へ返す前に lock を解放する。

`MacroRuntimeBuilder.build()` は `MacroRegistry.resolve()` で `MacroDefinition` の snapshot を取得した後、`registry_reload_lock` を保持しないまま settings 解決、resource scope 生成、Port 構築を行う。reload が実行中に完了しても、開始済みまたは開始準備済みの実行は取得済み `MacroDefinition` で完結する。

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


type SettingValue = str | int | float | bool | list[SettingValue] | dict[str, SettingValue] | None


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
    entrypoint_kind: str = "convention"


class MacroSettingsResolver:
    def __init__(self, project_root: Path) -> None: ...

    def resolve(self, definition: "MacroDefinition") -> MacroSettingsSource | None: ...

    def load(self, definition: "MacroDefinition") -> dict[str, SettingValue]: ...


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


class EntryPointLoader:
    def __init__(self, project_root: Path, macros_dir: Path) -> None: ...

    def load_definition(self, manifest_path: Path) -> MacroDefinition: ...

    def load_convention_definition(self, source_path: Path) -> MacroDefinition: ...
```

`macro.toml` は任意の入力ファイル形式であり、`MacroManifest` という Python クラスは定義しない。読み込み処理は TOML、class metadata、convention default を検証して `MacroDefinition` を生成する。

`MacroRegistry` は発見、ID 解決、診断、`MacroDefinition` の snapshot 管理だけを担当する。`MacroDefinition` は `factory` を所有し、Runtime は `definition.factory.create()` を呼ぶ。Runtime に別の `MacroFactory` facade は持たせず、生成ポリシーを二重化しない。

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
  -> request = RuntimeBuildRequest(macro_id=name_or_id, entrypoint=..., exec_args=...)
  -> context = runtime_builder.build(request)
     -> definition = registry.resolve(name_or_id)
     -> settings = settings_resolver.load(definition)
  -> result = runtime.run(context)
```

`MacroRuntime` が registry 解決結果、`definition.factory.create()`、Ports の利用、Port close を担当し、`MacroRunner` がライフサイクル実行、`MacroStopException` 正規化、`RunResult` 生成を担当する。Ports 準備と `ExecutionContext` 生成は `MacroRuntimeBuilder` の責務である。

### Manifest / class metadata / convention 仕様

`macros/<macro_name>/macro.toml` は必須ではない。manifest が存在する場合は最優先で読み、存在しない場合は class metadata と convention default から `MacroDefinition` を生成する。

manifest が必須になるのは、1 パッケージに複数 entrypoint を置く場合、GUI/CLI 一覧に import 前 metadata や args schema を出したい場合、配布・共有用に ID / metadata / resource roots を固定したい場合である。単一 `MacroBase` クラスだけの軽量マクロは manifest なしでよい。

```toml
[macro]
id = "frlg_id_rng"
entrypoint = "macros.frlg_id_rng.macro:FrlgIdRngMacro"
display_name = "FRLG TID乱数調整マクロ"
description = "FRLG TID乱数調整マクロ (Switch 720p)"
tags = ["pokemon", "frlg", "rng", "tid"]
version = "1.0.0"
settings = "settings.toml"
```

manifest の `entrypoint` は `module:ClassName` 形式である。`class_name` は原則不要だが、将来の拡張で複数 entrypoint を扱う場合に備えて予約する。

manifest なしの class metadata は次の任意属性を読む。

```python
class SampleMacro(MacroBase):
    macro_id = "sample"
    display_name = "Sample"
    description = "サンプルマクロ"
    tags = ("sample",)
    settings_path = "settings.toml"
```

class metadata もない場合の convention default は次の通りである。

| 項目 | default |
|------|---------|
| `id` | `macros/<id>.py` のファイル名、または `macros/<id>/` のディレクトリ名 |
| `display_name` | class metadata `display_name`、なければ class 名 |
| `description` | class metadata `description`、なければ class docstring、なければ空文字 |
| `tags` | class metadata `tags`、なければ空 tuple |
| `settings_path` | class metadata `settings_path`、なければ `None` |

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `project_root` | `Path` | なし | `MacroRegistry` の探索起点。省略不可 |
| `macros_dir` | `Path | None` | `None` | 探索対象ディレクトリ。`None` の場合は `<project_root>/macros` |
| `macro.toml [macro].id` | `str` | convention default | manifest を使う場合の安定 ID。省略時は convention default |
| `macro.toml [macro].entrypoint` | `str` | convention discovery | `module:ClassName` 形式の entrypoint。複数候補や import 前 metadata が必要な場合は必須 |
| `macro.toml [macro].display_name` | `str | None` | class 名 | GUI / CLI 表示名 |
| `macro.toml [macro].description` | `str | None` | class 属性 `description` | マクロ説明文 |
| `macro.toml [macro].tags` | `list[str]` | `[]` | GUI タグフィルタ用 |
| `macro.toml [macro].settings` | `str | None` | `None` | TOML 設定ファイルの相対パス。通常の相対パスは macro-root 相対、`project:` prefix は project-root 相対 |
### Entrypoint loader 仕様

`EntryPointLoader` は manifest がある場合は manifest entrypoint を優先し、manifest がない場合は convention discovery を使う。

| 形式 | 例 | entrypoint |
|------|----|------------|
| package `macro.py` | `macros/frlg_id_rng/macro.py` | `macros.frlg_id_rng.macro:FrlgIdRngMacro` |
| package `__init__.py` | `macros/frlg_id_rng/__init__.py` | `macros.frlg_id_rng:FrlgIdRngMacro` |
| single file | `macros/sample.py` | `macros.sample:SampleMacro` |

package に `macro.toml` がある場合は manifest を優先する。manifest がない場合は `macro.py` を優先し、なければ `__init__.py` を見る。両方に候補がある、または 1 ファイル内に複数の `MacroBase` 派生クラスがある場合は曖昧として診断し、manifest entrypoint を要求する。同一 package から同じ class が二重登録される場合は 1 件に統合し、診断に重複を記録する。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `MacroLoadError` | module import、manifest parse、entrypoint 解決、convention discovery、`MacroBase` 継承確認に失敗 |
| `AmbiguousMacroError` | 互換 alias が複数 `MacroDefinition` に一致 |
| `RegistryLockTimeoutError` | `registry_reload_lock` の取得が 2 秒以内に完了しない |
| `ValueError` | `set_active_macro()` で存在しない名前を指定。現行互換のため維持 |
| `FileNotFoundError` | 明示 settings が存在必須と指定された将来拡張で未検出 |

ロード中の例外は `MacroRegistry.diagnostics` に蓄積し、reload 全体は継続する。実行中の例外は `MacroRunner` が `RunResult` へ正規化する。

### シングルトン管理

`MacroRegistry` はシングルトンにしない。GUI / CLI ごとに `MacroRuntime` または `MacroRegistry` を所有する。グローバル化が必要になった場合も `core/singletons.py` に集約し、`reset_for_testing()` でリセット可能にする。

### 移行計画

| 段階 | 方針 | 既存マクロへの影響 |
|------|------|--------------------|
| Phase 1 | `MacroRegistry` と `MacroDefinition` を導入し、GUI/CLI/テストが `MacroExecutor` を経由しない入口を用意する | 変更不要 |
| Phase 2 | GUI / CLI が definition ID と診断を表示 | 変更不要 |
| Phase 3 | `macro.toml` 任意採用、class metadata、convention discovery を同じ `MacroDefinition` へ正規化する | 軽量マクロは変更不要。複数候補など曖昧な場合だけ manifest 追加 |
| Phase 4 | 旧 `static` settings lookup と `cwd` fallback を削除 | settings 利用マクロは manifest または class metadata へ移行 |
| Phase 5 | `MacroExecutor` 削除可否を再判断 | 削除判断時は別仕様で扱う |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_registry_loads_manifest_package_macro` | manifest entrypoint の package macro を `MacroDefinition` として登録する |
| ユニット | `test_registry_loads_manifest_single_file_macro` | manifest entrypoint の single-file macro を `MacroDefinition` として登録する |
| ユニット | `test_registry_loads_manifest_macro` | `macro.toml` の `entrypoint` と `settings` を優先する |
| ユニット | `test_registry_loads_convention_package_macro` | manifest なしの `macros/<id>/macro.py` を 1 件の `MacroDefinition` として登録する |
| ユニット | `test_registry_loads_convention_single_file_macro` | manifest なしの `macros/<id>.py` を 1 件の `MacroDefinition` として登録する |
| ユニット | `test_registry_uses_class_metadata_when_manifest_absent` | `macro_id`、`display_name`、`settings_path` などの class metadata を反映する |
| ユニット | `test_registry_requires_manifest_when_convention_is_ambiguous` | 複数 `MacroBase` 候補がある場合に診断し、manifest entrypoint を要求する |
| ユニット | `test_class_name_alias_is_available_when_unique` | class 名が一意なら `set_active_macro("ClassName")` が通る |
| ユニット | `test_class_name_collision_requires_qualified_id` | 同名 class が複数ある場合に `AmbiguousMacroError` と候補 ID を返す |
| ユニット | `test_load_failure_is_reported_without_stopping_reload` | 1 件 import 失敗しても他マクロが登録され、diagnostics に失敗理由が残る |
| ユニット | `test_registry_reload_swaps_snapshot_atomically` | reload 中に `definitions` と `diagnostics` の中途半端な snapshot が見えない |
| ユニット | `test_execute_creates_new_instance_each_time` | 2 回 execute して `definition.factory.create()` が 2 回呼ばれ、状態が共有されない |
| ユニット | `test_settings_without_explicit_source_returns_empty_dict` | manifest / class metadata の settings source がない場合は settings file を暗黙探索しない |
| ユニット | `test_settings_static_lookup_is_not_supported` | `static/<macro_name>/settings.toml` を互換 settings として読み込まない |
| ユニット | `test_exec_args_override_file_settings` | file settings より `exec_args` が優先される |
| ユニット | `test_command_method_names_are_compatible` | `Command` が互換契約のメソッド名を持つ |
| ユニット | `test_command_type_accepts_str_keycode_special_keycode` | `Command.type(key: str | KeyCode | SpecialKeyCode)` の呼び出し互換を検証する |
| ユニット | `test_explicit_settings_path_resolution` | manifest / class metadata settings が project-root 相対と macro-root 相対を区別して解決される |
| ユニット | `test_macro_executor_removed` | `MacroExecutor` を新 API、互換契約、移行 adapter として公開しない |
| ユニット | `test_constants_import_contract` | `from nyxpy.framework.core.constants import Button, Hat, LStick, RStick, KeyType` が成功する |
| 結合 | `test_migrated_repository_macros_load_with_optional_manifest` | 移行後の代表マクロが manifest あり / なしの両方でロードされる |
| 結合 | `test_gui_cli_do_not_import_macro_executor` | GUI/CLI が `MacroExecutor` を import せず `MacroRuntime` / `MacroRegistry` を使う |
| GUI | `test_macro_reload_add_and_remove_real_env` | 既存 GUI リロードテストの追加・削除挙動を維持する |
| GUI | `test_macro_reload_shows_load_diagnostics` | 壊れたマクロを追加しても一覧は表示され、診断が確認できる |
| 性能 | `test_registry_reload_100_macros_perf` | 100 件の dummy macro reload が 1 秒未満を目標に完了する |
| ハードウェア | `test_macro_execution_realdevice` | 必要に応じて `@pytest.mark.realdevice` で実機接続時の Command 送信を確認する |

既存 `tests/unit/executor/test_executor.py` は Runtime / Registry 入口のテストへ置き換える。`MacroExecutor.macros`、`MacroExecutor.macro`、`MacroExecutor.execute()` の戻り値互換は保証しない。新規テストは `tmp_path` と `monkeypatch.syspath_prepend()` を使い、実リポジトリの `macros/` を破壊しない。

実装後に最低限実行するコマンドは次である。

```powershell
uv run pytest tests/unit/executor/test_executor.py
uv run pytest tests/unit/framework/macro/test_registry.py
uv run pytest tests/gui/test_macro_reload.py
uv run ruff check .
```

## 6. 実装チェックリスト

本チェックリストは仕様確定項目である。実装タスクと検証タスクは `IMPLEMENTATION_PLAN.md` のフェーズ別チェックリストを正とする。

- [x] 既存 import path の互換契約を明記
- [x] lifecycle signature の互換契約を明記
- [x] Command method names の互換契約を明記
- [x] constants import の互換契約を明記
- [x] static settings lookup を互換対象から外す方針を明記
- [x] `MacroRegistry`, `MacroDefinition`, `MacroFactory`, `macro.toml`, `EntryPointLoader` の責務を定義
- [x] クラス名衝突時の ID / alias 方針を定義
- [x] `cwd` / `sys.path` 依存の解消方針を定義
- [x] ロード失敗診断の保持方針を定義
- [x] 実行ごとのマクロインスタンス生成を定義
- [x] Resource/settings/entrypoint のマクロ側移行を要求する方針を定義
- [x] 対象ファイル表を作成
- [x] 公開 API シグネチャを作成
- [x] 設定例 TOML を作成
- [x] テスト方針を作成

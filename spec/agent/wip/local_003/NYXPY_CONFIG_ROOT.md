# `.nyxpy` project root 配置仕様書

> **対象モジュール**: `src\nyxpy\framework\core\settings\`
> **目的**: `.nyxpy` の生成先と生成責務を project root に揃え、CLI / GUI / テストで同じ設定保存先を使う。
> **関連ドキュメント**: `spec\dev-journal.md`, `spec\gui\rearchitecture\PHASE_5_LEGACY_ROUTE_AND_FW_CLEANUP.md`
> **既存ソース**: `src\nyxpy\framework\core\settings\global_settings.py`, `src\nyxpy\framework\core\settings\secrets_settings.py`, `src\nyxpy\cli\run_cli.py`, `src\nyxpy\gui\app_services.py`
> **破壊的変更**: あり

## 1. 概要

### 1.1 目的

`.nyxpy` は NyX workspace の project root 配下に生成する。`SettingsStore` / `SecretsStore` は保存先を推測せず、CLI / GUI / init などの composition root が決定した `config_dir` を受け取る。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| project root | `macros`, `resources`, `runs`, `snapshots`, `.nyxpy` を保持する NyX workspace のルートディレクトリ |
| `.nyxpy` | `global.toml` と `secrets.toml` を置く project root 配下の設定ディレクトリ |
| config_dir | `SettingsStore` / `SecretsStore` が TOML ファイルを読み書きするディレクトリ。標準値は `project_root / ".nyxpy"` |
| composition root | CLI / GUI / init など、アプリケーション起動時に依存オブジェクトと lifetime を組み立てる入口 |
| SettingsStore | 非 secret のグローバル設定を schema 検証付きで永続化する store |
| SecretsStore | 通知 credential など secret を含む設定を schema 検証付きで永続化する store |
| workspace 初期化 | project root 配下に必要なディレクトリと `.nyxpy` の既定 TOML を生成する処理 |

### 1.3 背景・問題

現状では CLI の runtime builder は `project_root / ".nyxpy"` を明示する一方、GUI の `GuiAppServices` は `project_root` を保持しながら `GlobalSettings()` / `SecretsSettings()` を引数なしで生成する。store 内部は `config_dir` 未指定時に `Path.cwd() / ".nyxpy"` を使うため、`GuiAppServices(project_root=...)` と settings 保存先がずれる可能性がある。

`Path.cwd()` 依存は VS Code の実行構成、デスクトップショートカット、スケジューラ、サブディレクトリからの起動で意図しない `.nyxpy` を作る。設定と secrets はマクロ実行環境に影響するため、保存先は store 内部の暗黙値ではなく、起動入口が決定した project root によって固定する必要がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| settings 保存先の決定責務 | store と composition root に分散 | composition root に集約 |
| settings store 内の暗黙 `Path.cwd()` fallback | 2 箇所 | 0 箇所 |
| CLI / GUI の `.nyxpy` 配置 | CLI は project root、GUI は cwd 依存 | 全入口で `project_root / ".nyxpy"` |
| 意図しない cwd への `.nyxpy` 生成 | 起動方法により発生 | project root 確定後のみ生成 |
| テスト時の設定保存先 | fixture が明示する場合のみ安定 | store 生成時に常に明示 |

### 1.5 着手条件

- `spec\gui\rearchitecture\PHASE_5_LEGACY_ROUTE_AND_FW_CLEANUP.md` で `SettingsStore` / `SecretsStore` の `.nyxpy` 解決がマクロ resource fallback ではないことを確認済みであること。
- `MacroRegistry` が explicit `project_root` を要求する現行設計を前提にすること。
- 既存の `SettingsSchema` / secret boundary の責務を変更しないこと。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\agent\wip\local_003\NYXPY_CONFIG_ROOT.md` | 新規 | `.nyxpy` 配置と生成責務の仕様を定義する |
| `src\nyxpy\framework\core\settings\global_settings.py` | 変更 | `SettingsStore` / `GlobalSettings` の `config_dir` を必須化し、`Path.cwd()` fallback を削除する |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | `SecretsStore` / `SecretsSettings` の `config_dir` を必須化し、`Path.cwd()` fallback を削除する |
| `src\nyxpy\framework\core\settings\workspace.py` | 新規 | project root 解決と workspace 初期化の共通関数を定義する |
| `src\nyxpy\__main__.py` | 変更 | `nyxpy init` と GUI / CLI 起動時に workspace helper を使う |
| `src\nyxpy\cli\run_cli.py` | 変更 | CLI runtime builder が `WorkspacePaths.config_dir` を store に渡す |
| `src\nyxpy\gui\run_gui.py` | 変更 | GUI 起動時に project root を解決し `MainWindow` に渡す |
| `src\nyxpy\gui\main_window.py` | 変更 | `Path.cwd()` 直読みではなく注入された project root を使う |
| `src\nyxpy\gui\app_services.py` | 変更 | `project_root / ".nyxpy"` を `GlobalSettings` / `SecretsSettings` に渡す |
| `src\nyxpy\gui\dialogs\app_settings_dialog.py` | 変更 | fallback 生成時も親から渡された store を前提にし、引数なし store 生成を削除する |
| `tests\unit\framework\settings\test_settings_schema.py` | 変更 | `config_dir` 必須化と `.nyxpy` 生成先のテストを追加する |
| `tests\unit\test_workspace_initialization.py` | 変更 | init / GUI 起動が project root 配下に `.nyxpy` を生成することを検証する |
| `tests\unit\cli\test_main.py` | 変更 | CLI が resolved project root の config_dir を store に渡すことを検証する |
| `tests\gui\test_main_window.py` | 変更 | `MainWindow` が注入 project root を使い cwd に依存しないことを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`.nyxpy` は framework settings の永続化先であるが、保存先の決定は framework store の責務ではない。store は指定された `config_dir` の読み書きと schema 検証だけを担当し、project root の決定と初期化は composition root が行う。

### 公開 API 方針

`SettingsStore` / `SecretsStore` は `config_dir: Path` を必須引数にする。`GlobalSettings` / `SecretsSettings` は互換 shim ではなく schema 固定 store として残し、同じく `config_dir` を必須にする。

```python
class SettingsStore:
    def __init__(
        self,
        config_dir: Path,
        *,
        schema: SettingsSchema = GLOBAL_SETTINGS_SCHEMA,
        filename: str = "global.toml",
        strict_load: bool = True,
    ) -> None: ...


class GlobalSettings(SettingsStore):
    def __init__(self, config_dir: Path) -> None: ...


class SecretsStore:
    def __init__(
        self,
        config_dir: Path,
        *,
        schema: SettingsSchema = SECRETS_SETTINGS_SCHEMA,
        filename: str = "secrets.toml",
        strict_load: bool = True,
    ) -> None: ...


class SecretsSettings(SecretsStore):
    def __init__(self, config_dir: Path) -> None: ...
```

workspace helper は project root と config_dir を同時に返す。CLI / GUI はこの helper を使って保存先を明示する。

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    project_root: Path
    config_dir: Path
    macros_dir: Path
    resources_dir: Path
    snapshots_dir: Path
    runs_dir: Path
    logs_dir: Path


def resolve_project_root(
    *,
    explicit_root: Path | None = None,
    start: Path | None = None,
    allow_current_as_new: bool = False,
) -> Path: ...


def ensure_workspace(project_root: Path) -> WorkspacePaths: ...
```

### 後方互換性

破壊的変更あり。`GlobalSettings()` / `SecretsSettings()` / `SettingsStore()` / `SecretsStore()` の引数なし生成は削除する。Project NyX の framework はアルファ版であり、互換 shim や deprecation alias は追加しない。

### レイヤー構成

依存方向は次の通りである。

```text
CLI / GUI / tests
  -> nyxpy.framework.core.settings.workspace
  -> nyxpy.framework.core.settings.{global_settings,secrets_settings}
```

framework settings は GUI に依存しない。GUI は `WorkspacePaths` と store インスタンスを受け取り、settings dialog で新しい store を暗黙生成しない。

### `.nyxpy` の配置ルール

`.nyxpy` は常に `project_root / ".nyxpy"` に置く。`global.toml` と `secrets.toml` は同じ `config_dir` に置き、通知設定とデバイス設定が別 workspace に流出しないようにする。

| 対象 | 配置 |
|------|------|
| グローバル設定 | `project_root\.nyxpy\global.toml` |
| secrets 設定 | `project_root\.nyxpy\secrets.toml` |
| logs | `project_root\logs` |
| macro discovery | `project_root\macros` |
| snapshots | `project_root\snapshots` |
| resources | `project_root\resources` |
| runs | `project_root\runs` |

### project root の決定順

| 優先順位 | 入力 | 挙動 |
|----------|------|------|
| 1 | 明示 `project_root` | 正規化した path を project root として使う |
| 2 | cwd から親方向に見つかった `.nyxpy` | 既存 workspace として使う |
| 3 | `allow_current_as_new=True` の cwd | 新規 workspace root として `ensure_workspace()` で生成する |
| 4 | 上記なし | workspace 未決定として `ConfigurationError` を送出する |

`nyxpy init` は `allow_current_as_new=True` で cwd を初期化する。GUI の初回起動は root 選択 UI がない間だけ `allow_current_as_new=True` で cwd を使う。CLI の macro 実行は明示 root または既存 workspace を優先し、未初期化 cwd を新規 workspace として扱うかどうかを実装時に CLI UX と合わせて決定する。

### 生成タイミング

`.nyxpy` は project root が確定した後に生成する。store コンストラクタは指定された `config_dir` の存在を保証してよいが、保存先の推測はしない。

| シチュエーション | 生成可否 | 理由 |
|------------------|----------|------|
| `nyxpy init` | 生成する | ユーザが cwd を workspace root として初期化する意思を示している |
| GUI 初回起動 | 生成する | root 選択 UI がない現状では cwd を起動 root とする必要がある |
| CLI macro 実行 | 条件付きで生成する | macro discovery の project root と同一である場合のみ一貫性がある |
| `SettingsStore(config_dir=...)` | 生成する | config_dir は呼び出し元が既に決定済みである |
| `SettingsStore()` | 不可 | 保存先を推測しない |

### 採用理由とメリット・デメリット

| 方針 | メリット | デメリット | 判断 |
|------|----------|------------|------|
| project root 配下に固定 | CLI / GUI / tests の保存先が揃う。複数 workspace を分離できる。secrets が別 project に混入しにくい | root 決定処理が必要。引数なし store 生成を呼び出し元で修正する必要がある | 採用 |
| cwd を store 内部で使う | 実装が少なく現行 `nyxpy init` と近い | 起動 cwd に依存し、意図しない `.nyxpy` を作る。`project_root` 注入と矛盾する | 不採用 |
| ユーザ設定ディレクトリへ移す | 作業ディレクトリに依存しない | macro / resources / runs が project root 配下にある現行設計と分離する。workspace ごとのデバイス設定を持てない | 不採用 |
| 親方向探索のみ | サブディレクトリ起動に強い | 初回 workspace 作成の意思表示が別途必要 | 明示 root と併用 |

### ユースケース

| ユースケース | 必要な挙動 |
|--------------|------------|
| リポジトリ直下で `nyxpy init` を実行する | cwd に `.nyxpy`, `macros`, `resources`, `runs`, `snapshots` を生成する |
| GUI を project root から起動する | `project_root\.nyxpy` の設定を読み書きし、cwd 以外に生成しない |
| CLI で macro を実行する | macro discovery と settings が同じ project root を使う |
| `macros\foo` などサブディレクトリから起動する | 親方向の `.nyxpy` を見つけて project root を復元する |
| VS Code の実行構成やタスクから起動する | 実行構成で指定した root を使い、拡張機能の cwd に設定を作らない |
| 複数の macro workspace を使い分ける | workspace ごとに `global.toml` と `secrets.toml` が分離される |
| テストで一時ディレクトリを使う | fixture が `tmp_path / ".nyxpy"` を渡し、開発者の cwd を汚さない |
| パッケージ化 GUI から起動する | GUI が選択した workspace root 配下に `.nyxpy` を生成する |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| project root 探索 | cwd から root までの親ディレクトリ数に比例し、起動時 1 回だけ実行する |
| TOML 読み書き | 現行 `SettingsStore` / `SecretsStore` と同等 |

### 並行性・スレッド安全性

`SettingsStore` / `SecretsStore` の `RLock` による読み書き保護は維持する。workspace 初期化は起動時に単一スレッドで実行し、複数プロセスから同時に初期化された場合は `mkdir(exist_ok=True)` と既存ファイル保護により破壊しない。

## 4. 実装仕様

### workspace helper

`workspace.py` は project root の決定とディレクトリ生成を担当する。`resolve_project_root()` は path を返すだけで、ファイル生成は `ensure_workspace()` に分離する。

```python
def resolve_project_root(
    *,
    explicit_root: Path | None = None,
    start: Path | None = None,
    allow_current_as_new: bool = False,
) -> Path:
    """Resolve the NyX project root without creating settings files."""


def ensure_workspace(project_root: Path) -> WorkspacePaths:
    """Create workspace directories and return canonical paths."""
```

`ensure_workspace()` は次のディレクトリを生成する。

| ディレクトリ | 生成理由 |
|--------------|----------|
| `.nyxpy` | settings / secrets の保存先 |
| `macros` | macro discovery の対象 |
| `resources` | macro resource の保存先 |
| `snapshots` | GUI / preview snapshot の保存先 |
| `runs` | 実行成果物の保存先 |
| `logs` | `create_default_logging()` の保存先 |

`macros\__init__.py` の生成は既存 `init_app()` と同じく維持する。`static` は migration 後の旧ディレクトリであるため生成しない。

### settings store

`SettingsStore` / `SecretsStore` は `config_dir` を必須にし、次の責務だけを持つ。

| 責務 | 内容 |
|------|------|
| ディレクトリ存在保証 | 渡された `config_dir` を `mkdir(exist_ok=True)` で作る |
| TOML 生成 | ファイルがなければ schema default を保存する |
| schema 検証 | 読み込み値と保存値を `SettingsSchema` で検証する |
| エラー通知 | parse / schema error を `ConfigurationError` として送出する |

store は `Path.cwd()`、project root 探索、GUI 状態を参照しない。

### CLI / GUI wiring

CLI は runtime builder 作成前に `WorkspacePaths` を得て、`SettingsStore(config_dir=paths.config_dir)` と `SecretsStore(config_dir=paths.config_dir)` を生成する。GUI は `run_gui.main()` または `MainWindow` 生成前に project root を決め、`GuiAppServices(project_root=paths.project_root)` が `GlobalSettings(config_dir=paths.config_dir)` と `SecretsSettings(config_dir=paths.config_dir)` を生成する。

`AppSettingsDialog` は原則として `MainWindow` から渡された store を使う。引数省略時に新しい `GlobalSettings()` / `SecretsSettings()` を作る fallback は削除する。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `explicit_root` | `Path | None` | `None` | 呼び出し元が指定した project root |
| `start` | `Path | None` | `None` | `.nyxpy` を親方向に探索する開始ディレクトリ。未指定時は cwd |
| `allow_current_as_new` | `bool` | `False` | `.nyxpy` が見つからない場合に `start` を新規 project root として許可するか |
| `config_dir` | `Path` | なし | settings / secrets store の読み書き先 |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | project root が決定できない |
| `ConfigurationError` | settings / secrets TOML の parse に失敗した |
| `ConfigurationError` | settings / secrets TOML が schema に違反した |
| `SecretBoundaryError` | secret field を `SettingsStore` schema に含めた |

project root 未決定時の `ConfigurationError` は `code="NYX_WORKSPACE_NOT_FOUND"` を使う。エラー詳細には探索開始地点と明示 root の有無を含める。

### シングルトン管理

新規 singleton は追加しない。`WorkspacePaths`、settings store、secrets store は composition root が lifetime を所有し、GUI / CLI に注入する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_settings_store_requires_config_dir` | `SettingsStore()` / `SecretsStore()` の引数なし生成ができない |
| ユニット | `test_settings_store_writes_only_to_config_dir` | `config_dir` にだけ TOML を生成し、cwd に `.nyxpy` を作らない |
| ユニット | `test_resolve_project_root_prefers_explicit_root` | 明示 root が cwd や探索結果より優先される |
| ユニット | `test_resolve_project_root_finds_parent_marker` | サブディレクトリから親の `.nyxpy` を検出する |
| ユニット | `test_resolve_project_root_rejects_unknown_workspace` | marker なし、かつ新規 root 不許可の場合に `NYX_WORKSPACE_NOT_FOUND` を送出する |
| ユニット | `test_ensure_workspace_creates_expected_directories_without_static` | `.nyxpy`, `macros`, `resources`, `runs`, `snapshots`, `logs` を生成し、`static` は生成しない |
| ユニット | `test_init_app_uses_workspace_initializer` | `nyxpy init` が cwd を project root として初期化する |
| ユニット | `test_cli_runtime_builder_passes_project_config_dir` | CLI が `project_root\.nyxpy` を `SettingsStore` / `SecretsStore` に渡す |
| GUI | `test_gui_services_uses_project_root_config_dir` | `GuiAppServices(project_root=tmp_path)` が `tmp_path\.nyxpy` を使い、cwd に依存しない |
| GUI | `test_main_window_accepts_injected_project_root` | `MainWindow` が `Path.cwd()` ではなく注入 root を使う |
| 結合 | `test_cli_and_gui_share_workspace_settings_location` | 同じ project root で CLI と GUI が同じ `global.toml` を読む |

ハードウェアテストは不要である。`.nyxpy` の配置と store wiring は実機デバイスに依存しない。

## 6. 実装チェックリスト

- [ ] `WorkspacePaths`, `resolve_project_root()`, `ensure_workspace()` のシグネチャ確定
- [ ] `SettingsStore` / `SecretsStore` の `config_dir` 必須化
- [ ] `GlobalSettings` / `SecretsSettings` の `config_dir` 必須化
- [ ] CLI の workspace 解決と store wiring 更新
- [ ] GUI の workspace 解決と store wiring 更新
- [ ] `AppSettingsDialog` の引数なし store fallback 削除
- [ ] `nyxpy init` の workspace 初期化処理更新
- [ ] ユニットテスト作成・パス
- [ ] GUI テスト作成・パス
- [ ] 結合テスト作成・パス
- [ ] `uv run ruff check .` パス
- [ ] `uv run pytest tests\unit tests\gui tests\integration` パス

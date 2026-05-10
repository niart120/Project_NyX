# Framework Legacy Cleanup 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/runtime/`, `src/nyxpy/framework/core/macro/`, `src/nyxpy/framework/core/singletons.py`, `src/nyxpy/gui/`
> **目的**: Runtime / Ports 再設計後に残ったレガシー互換コードを、移行期間を設けず削除する。
> **関連ドキュメント**: `spec/framework/rearchitecture/ARCHITECTURE_DIAGRAMS.md`, `spec/framework/rearchitecture/DEPRECATION_AND_MIGRATION.md`, `spec/framework/rearchitecture/FOLLOWUP_FIXES.md`, `spec/gui/rearchitecture/IMPLEMENTATION_PLAN.md`, `spec/cli/rearchitecture/FOLLOWUP_FIXES.md`
> **既存ソース**: `src/nyxpy/framework/core/runtime/builder.py`, `src/nyxpy/framework/core/macro/command.py`, `src/nyxpy/framework/core/singletons.py`, `src/nyxpy/gui/main_window.py`, `src/nyxpy/gui/dialogs/settings/device_tab.py`
> **破壊的変更**: あり。Project NyX のフレームワークはアルファ版であり、レガシー API には非推奨期間、互換 shim、警告期間を設けない。

## 1. 概要

### 1.1 目的

フレームワーク再設計で導入した `MacroRuntimeBuilder` / Ports 経路を正とし、旧実装を残すためだけの alias、singleton、legacy 引数を削除する。GUI / CLI / テストは削除後の API に同時移行し、互換維持を理由に旧経路を残さない。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| レガシー互換コード | 旧 API 名、旧 singleton、旧コンストラクタ引数、旧 import path を動かすためだけに残っているコード |
| 破壊的変更 | 既存の import、関数名、引数、挙動を変更または削除する変更 |
| 互換 shim | 旧 API を受け付けて新 API へ委譲する薄い wrapper。今回の最終状態では残さない |
| 正 API | 再設計後の設計で採用する API。`create_device_runtime_builder()`、`MacroRuntimeBuilder`、`ExecutionContext`、Ports が該当する |
| composition root | GUI / CLI など、Runtime、Port、device manager、settings store を組み立てる上位層 |

### 1.3 背景・問題

framework followup と CLI followup では、段階作業を安全に進めるため `create_legacy_runtime_builder()` を `create_device_runtime_builder()` の alias として残した。GUI 側にも `nyxpy.framework.core.singletons` への直接依存が残っており、`singletons.py` は「compatibility singletons」として存在している。

この状態は、再設計後の境界を読みにくくする。旧名の alias や singleton module が残ると、後続実装が誤って旧経路へ依存し、Runtime / Ports の所有権や lifetime が二重化する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| legacy builder 名 | `create_legacy_runtime_builder()` が import 可能 | import 不能。呼び出し元は `create_device_runtime_builder()` のみ |
| singleton module 依存 | GUI とテストが `nyxpy.framework.core.singletons` を参照 | GUI / CLI / framework runtime / tests の参照数 0 |
| `DefaultCommand` legacy 引数 | `**legacy_kwargs` を受け取り、手動で TypeError を送出 | `DefaultCommand(context: ExecutionContext)` のみ |
| 互換 shim / 非推奨警告 | 一部仕様に shim や段階廃止の余地が残る | 本 cleanup 対象では shim / `DeprecationWarning` を追加しない |
| 削除ゲート | runtime / io / macro の一部だけを静的検査 | GUI / CLI / framework / tests の旧 import を静的検査 |

### 1.5 着手条件

- この仕様書のレビューで、削除対象と保持対象の境界が合意されていること。
- `master` が framework followup と CLI followup の merge 後であること。
- 実装前に `uv run pytest` と `uv run ruff check .` の現状を確認すること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/agent/wip/local_001/FRAMEWORK_LEGACY_CLEANUP.md` | 新規 | 本 cleanup の修正仕様を定義する |
| `.github/copilot-instructions.md` | 変更 | アルファ版フレームワークでは破壊的変更を許容し、移行期間を設けない方針を追記する |
| `.github/skills/framework-spec-writing/SKILL.md` | 変更 | フレームワーク仕様執筆時に旧 singleton や段階廃止を前提にしない方針へ更新する |
| `AGENTS.md` | 新規 | エージェント向けに後方互換性方針を明文化する |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | `create_legacy_runtime_builder()` を削除し、公開 builder 名を `create_device_runtime_builder()` に一本化する |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `DefaultCommand.__init__` から `**legacy_kwargs` を削除し、`context` 必須の署名にする |
| `src/nyxpy/framework/core/singletons.py` | 削除 | グローバル manager/settings singleton と `reset_for_testing()` を削除する |
| `src/nyxpy/gui/main_window.py` | 変更 | `create_legacy_runtime_builder()` と `singletons.py` 依存を削除し、GUI composition root で所有する store / manager / builder を使う |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | `singletons.py` 直接 import を削除し、呼び出し元から device source を注入する |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | legacy builder alias 前提を削除し、`create_device_runtime_builder()` を検証する |
| `tests/hardware/test_macro_runtime_realdevice.py` | 変更 | realdevice test の builder import を正 API へ更新する |
| `tests/unit/framework/runtime/test_removed_api_imports.py` | 変更 | `create_legacy_runtime_builder` と `nyxpy.framework.core.singletons` の import 不可を検証する |
| `tests/integration/test_cli_runtime_adapter.py` | 変更 | CLI 側の旧 import 禁止ゲートを維持し、削除後の API 名に合わせる |
| `tests/gui/` | 変更 | GUI の singleton 依存削除に合わせて fixture / monkeypatch を更新する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

Runtime / Ports 再設計後の正しい依存方向は、GUI / CLI が composition root として `MacroRuntimeBuilder` を組み立て、Runtime core は Ports だけを見る形である。`singletons.py` や legacy builder alias はこの依存方向を曖昧にするため削除する。

### 公開 API 方針

新 API は追加しない。既に導入済みの `create_device_runtime_builder()` を正 API とし、旧名の alias は削除する。

```python
def create_device_runtime_builder(
    *,
    project_root: Path,
    registry: MacroRegistry,
    protocol: SerialProtocolInterface,
    notification_handler,
    logger: LoggerPort,
    serial_manager=None,
    capture_manager=None,
    serial_device=None,
    capture_device=None,
    serial_name: str | None = None,
    capture_name: str | None = None,
    baudrate: int | None = None,
    detection_timeout_sec: float = 2.0,
    settings: SettingsSnapshot | None = None,
) -> MacroRuntimeBuilder: ...


class DefaultCommand(Command):
    def __init__(self, context: ExecutionContext) -> None: ...
```

`create_legacy_runtime_builder()` は削除する。`nyxpy.framework.core.singletons` も削除対象であり、import 互換 module は残さない。

### 後方互換性

破壊的変更を許容する。Project NyX のフレームワークはアルファ版であり、今回の cleanup では次を行わない。

- `warnings.warn(..., DeprecationWarning)` による段階廃止
- 旧 API 名から正 API へ委譲する alias
- import 互換用の空 module
- 「既存利用者の移行期間」を理由にした旧実装の温存

削除によって壊れる GUI / CLI / テスト / 既存マクロがある場合は、同じ変更内で正 API へ更新する。旧挙動を残すのではなく、呼び出し元を修正する。

### レイヤー構成

| レイヤー | cleanup 後の扱い |
|----------|------------------|
| GUI / CLI | `create_device_runtime_builder()` を直接使う。`singletons.py` は参照しない |
| Runtime builder | device manager または direct device を Port へ接続する正 API を提供する。legacy alias は持たない |
| Command | `ExecutionContext` を必須にする。旧コンストラクタ引数は受け付けない |
| Framework singleton | Runtime / GUI / CLI の共有状態として使わない。module ごと削除する |
| Tests | 旧 import を monkeypatch せず、fixture で manager / store / Port fake を生成する |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| GUI preview 更新 | cleanup 前後で preview perf gate の閾値を悪化させない |
| Runtime build | builder alias 削除により追加の wrapper 呼び出しを 0 にする |
| テスト分離 | singleton reset に依存しない fixture 生成へ移行する |

### 並行性・スレッド安全性

singleton 削除により、GUI preview、manual input、macro run が同じ global manager を暗黙共有する経路をなくす。GUI が所有する lifetime Port は `MacroRuntimeBuilder.shutdown()` で閉じ、run 単位の Port は `MacroRuntime` の実行 lifetime で閉じる方針を維持する。

## 4. 実装仕様

### 4.1 削除対象

| 対象 | 現状 | 修正後 |
|------|------|--------|
| `create_legacy_runtime_builder()` | `create_device_runtime_builder()` への alias | 関数削除。import は失敗する |
| `nyxpy.framework.core.singletons` | manager / settings singleton を生成 | ファイル削除。GUI / CLI / tests は import しない |
| `DefaultCommand.__init__(context=None, **legacy_kwargs)` | legacy 引数を受けて手動 TypeError | `DefaultCommand(context: ExecutionContext)` |
| GUI の global manager 利用 | `capture_manager`, `serial_manager`, `global_settings`, `secrets_settings` を import | `MainWindow` が store / manager を所有し、dialog へ注入 |
| GUI device settings tab の singleton import | dialog 内で global manager を参照 | constructor 引数または provider で device list を取得 |

### 4.2 保持してよい対象

| 対象 | 理由 | 制約 |
|------|------|------|
| `SerialManager` / `CaptureManager` クラス | 現時点では device の列挙、選択、active device 管理を行う具体 adapter として使われている | global singleton として公開しない。保持は互換目的ではなく composition root 所有の実体に限る |
| `create_device_runtime_builder()` の `serial_manager` / `capture_manager` 引数 | GUI / CLI が所有する manager を Port へ接続する正 API として使う | 旧 singleton module から渡さない。将来 DeviceDiscoveryService を導入する場合は別仕様で置換する |
| `Command` / `DefaultCommand` / `MacroBase` | Runtime 実行時の現行 API | 旧コンストラクタや旧 import shim は残さない |

### 4.3 呼び出し元移行

1. `tests/unit/framework/runtime/test_runtime_builder.py` と `tests/hardware/test_macro_runtime_realdevice.py` を `create_device_runtime_builder()` へ更新する。
2. GUI 起動時に `SerialManager`、`CaptureManager`、`SettingsStore`、`SecretsStore` を `MainWindow` の所有物として生成する。
3. `AppSettingsDialog` と `DeviceSettingsTab` に、global singleton ではなく呼び出し元所有の settings / secrets / device source を渡す。
4. `PreviewPane` には `MacroRuntimeBuilder.frame_source_for_preview()` を渡し、`capture_manager.get_active_device()` 直参照を削る。
5. GUI cleanup は `runtime_builder.shutdown()` と logging close に寄せ、`serial_manager.close_active()` / `capture_manager.release_active()` 直呼びを残さない。

### 4.4 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| 追加なし | - | - | 既存設定を変更せず、旧 API の削除と呼び出し元更新だけを行う |

### 4.5 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ImportError` / `ModuleNotFoundError` | 削除後の `create_legacy_runtime_builder` または `nyxpy.framework.core.singletons` を import した |
| `TypeError` | `DefaultCommand` を `context` なし、または旧 keyword 引数で生成した |
| `ConfigurationError` | device 未選択、dummy 不許可、direct device と manager の混在など、既存 builder validation に失敗した |

旧 API 呼び出し時に移行先を案内する専用例外や警告は追加しない。失敗は Python の通常の import / signature error として表面化させる。

### 4.6 シングルトン管理

`singletons.py` は削除する。テスト用の `reset_for_testing()` も削除し、テストは fixture で必要な object を生成する。Runtime、builder、Port、settings store、secrets store、device manager は呼び出し元が lifetime を所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_runtime_builder_public_factory_is_device_builder_only` | `create_device_runtime_builder()` が正 API として動作し、legacy alias を使わない |
| ユニット | `test_legacy_runtime_builder_removed` | `create_legacy_runtime_builder` が import できない |
| ユニット | `test_framework_singletons_module_removed` | `nyxpy.framework.core.singletons` が import できない |
| ユニット | `test_default_command_accepts_context_only` | `DefaultCommand(context)` は成功し、旧 keyword 引数は `TypeError` |
| 結合 | `test_cli_runtime_adapter_does_not_import_legacy_framework_apis` | CLI が legacy builder / singleton を参照しない |
| GUI | `test_main_window_uses_device_runtime_builder` | GUI が `create_device_runtime_builder()` と所有 manager から runtime builder を組み立てる |
| GUI | `test_device_settings_tab_uses_injected_device_source` | device settings tab が `singletons.py` を import しない |
| ハードウェア | `test_macro_runtime_runs_with_real_serial_and_capture` | realdevice test が正 API の builder で実機実行できる |
| 性能 | `test_preview_runtime_frame_source_contention` | preview と runtime の frame source 競合対策が cleanup 後も維持される |

実装後の検証コマンドは次を必須とする。

```powershell
uv run pytest
uv run ruff check .
git --no-pager diff --check
```

静的ゲートとして、次の文字列が実装コードとテストコードに残っていないことを確認する。

```powershell
rg "create_legacy_runtime_builder|nyxpy\.framework\.core\.singletons|from nyxpy\.framework\.core import singletons" src tests
rg "DeprecationWarning|warnings\.warn|Backward-compatible alias|compatibility singletons" src tests
```

## 6. 実装チェックリスト

- [ ] 仕様レビューで削除対象と保持対象の境界を確定
- [ ] `create_legacy_runtime_builder()` を削除
- [ ] `DefaultCommand.__init__` を `context` 必須署名へ変更
- [ ] `singletons.py` を削除
- [ ] GUI の singleton 依存を composition root 所有の object へ移行
- [ ] GUI device settings tab の singleton import を削除
- [ ] CLI / GUI / framework / tests の legacy import 静的ゲートを追加
- [ ] ユニットテストを更新
- [ ] GUI テストを更新
- [ ] ハードウェアテストの import を正 API へ更新
- [ ] `uv run pytest` をパス
- [ ] `uv run ruff check .` をパス
- [ ] `git --no-pager diff --check` をパス

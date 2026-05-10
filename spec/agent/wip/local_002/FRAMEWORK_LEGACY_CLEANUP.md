# Framework Legacy Cleanup 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/runtime/`, `src/nyxpy/framework/core/macro/`, `src/nyxpy/framework/core/hardware/`, `src/nyxpy/framework/core/io/`, `src/nyxpy/framework/core/singletons.py`, `src/nyxpy/gui/`, `src/nyxpy/cli/`
> **目的**: Runtime / Ports 再設計後に残ったレガシー互換コードを、移行期間を設けず削除する。
> **関連ドキュメント**: `spec/framework/rearchitecture/ARCHITECTURE_DIAGRAMS.md`, `spec/framework/rearchitecture/DEPRECATION_AND_MIGRATION.md`, `spec/framework/rearchitecture/FOLLOWUP_FIXES.md`, `spec/gui/rearchitecture/IMPLEMENTATION_PLAN.md`, `spec/cli/rearchitecture/FOLLOWUP_FIXES.md`
> **既存ソース**: `src/nyxpy/framework/core/runtime/builder.py`, `src/nyxpy/framework/core/macro/command.py`, `src/nyxpy/framework/core/singletons.py`, `src/nyxpy/gui/main_window.py`, `src/nyxpy/gui/dialogs/settings/device_tab.py`, `src/nyxpy/cli/run_cli.py`
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
| composition root | GUI / CLI など、Runtime、Port、device discovery、Port factory、settings store を組み立てる上位層 |

### 1.3 背景・問題

framework followup と CLI followup では、段階作業を安全に進めるため `create_legacy_runtime_builder()` を `create_device_runtime_builder()` の alias として残した。GUI 側にも `nyxpy.framework.core.singletons` への直接依存が残っており、`singletons.py` は「compatibility singletons」として存在している。

この状態は、再設計後の境界を読みにくくする。旧名の alias や singleton module が残ると、後続実装が誤って旧経路へ依存し、Runtime / Ports の所有権や lifetime が二重化する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| legacy builder 名 | `create_legacy_runtime_builder()` が import 可能 | import 不能。呼び出し元は `create_device_runtime_builder()` のみ |
| singleton module 依存 | GUI とテストが `nyxpy.framework.core.singletons` を参照 | GUI / CLI / framework runtime / tests の参照数 0 |
| `DefaultCommand` legacy 引数 | `**legacy_kwargs` を受け取り、手動で TypeError を送出 | `DefaultCommand(context: ExecutionContext)` のみ |
| manager 層 | `SerialManager` / `CaptureManager` と active device 状態が Runtime builder 入力に残る | `DeviceDiscoveryService` と Port factory に置換し、manager API は GUI / CLI / builder から見えない |
| 互換 shim / 非推奨警告 | 一部仕様に shim や段階廃止の余地が残る | 本 cleanup 対象では shim / `DeprecationWarning` を追加しない |
| 削除ゲート | runtime / io / macro の一部だけを静的検査 | GUI / CLI / framework の旧 import を AST で静的検査し、テストは旧 API を利用せず検査文字列だけを保持する |
| 依存方向ゲート | 新 FW の依存方向を明示的に検査するテストなし | framework から GUI / CLI / macros への逆依存、および macro 間直接依存を AST で検査 |

### 1.5 着手条件

- この仕様書のレビューで、削除対象と保持対象の境界が合意されていること。
- `master` が framework followup と CLI followup の merge 後であること。
- 実装前に `uv run pytest` と `uv run ruff check .` の現状を確認すること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/agent/wip/local_002/FRAMEWORK_LEGACY_CLEANUP.md` | 新規 | 本 cleanup の修正仕様を定義する |
| `.github/copilot-instructions.md` | 変更 | アルファ版フレームワークでは破壊的変更を許容し、移行期間を設けない方針を追記する |
| `.github/skills/framework-spec-writing/SKILL.md` | 変更 | 仕様執筆時に参照すべき rearchitecture ドキュメントを明示する。cleanup の経緯や旧実装固有の説明は追加しない |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | `create_legacy_runtime_builder()` を削除し、公開 builder 名を `create_device_runtime_builder()` に一本化する |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `DefaultCommand.__init__` から `**legacy_kwargs` を削除し、`context` 必須の署名にする |
| `src/nyxpy/framework/core/singletons.py` | 削除 | グローバル manager/settings singleton と `reset_for_testing()` を削除する |
| `src/nyxpy/framework/core/hardware/device_discovery.py` | 新規 | `DeviceDiscoveryService`、検出結果、timeout / failure 表現を実装し、manager の検出責務を置換する |
| `src/nyxpy/framework/core/io/device_factories.py` | 新規 | `ControllerOutputPortFactory` / `FrameSourcePortFactory` を実装し、active device 管理を Port 生成へ移す |
| `src/nyxpy/framework/core/io/adapters.py` | 変更 | `NotificationHandlerPort` 互換 alias を削除し、`NotificationHandlerAdapter` に一本化する |
| `src/nyxpy/framework/core/io/__init__.py` | 変更 | `NotificationHandlerPort` の re-export を削除する |
| `src/nyxpy/framework/core/utils/cancellation.py` | 変更 | `request_stop()` が記録する source から legacy 表現を除く。メソッド削除は別仕様で扱う |
| `src/nyxpy/framework/core/hardware/serial_comm.py` | 変更 | `SerialManager` を削除し、`SerialComm` / `DummySerialComm` など device 実体だけを残す |
| `src/nyxpy/framework/core/hardware/capture.py` | 変更 | `CaptureManager` を削除し、`AsyncCaptureDevice` / `DummyCaptureDevice` など device 実体だけを残す |
| `src/nyxpy/gui/main_window.py` | 変更 | `create_legacy_runtime_builder()` と `singletons.py` 依存を削除し、GUI composition root で discovery / Port factory / builder を使う |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | `singletons.py` 直接 import を削除し、呼び出し元から device source を注入する |
| `src/nyxpy/cli/run_cli.py` | 変更 | CLI composition root で discovery / Port factory を生成し、manager を生成・注入しない |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | legacy builder alias 前提を削除し、`create_device_runtime_builder()` を検証する |
| `tests/unit/framework/hardware/test_device_discovery.py` | 新規 | 明示検出、timeout、dummy 除外、検出結果を検証する |
| `tests/unit/framework/io/test_device_factories.py` | 新規 | device 名から Port を生成し、active device 状態を持たないことを検証する |
| `tests/hardware/test_macro_runtime_realdevice.py` | 変更 | realdevice test の builder import を正 API へ更新する |
| `tests/unit/framework/test_dependency_boundaries.py` | 新規 | 新 FW の依存方向と macro 間直接依存禁止を AST で検証する |
| `tests/unit/framework/runtime/test_removed_api_imports.py` | 変更 | `create_legacy_runtime_builder`、`nyxpy.framework.core.singletons`、互換 alias の import 不可と参照残りを検証する |
| `tests/unit/framework/io/test_adapters.py` | 変更 | `NotificationHandlerPort` 前提を削除し、`NotificationHandlerAdapter` のみを検証する |
| `tests/unit/framework/runtime/test_macro_runner.py` | 変更 | `CancellationToken.request_stop()` の source 表現変更に合わせる |
| `tests/integration/test_cli_runtime_adapter.py` | 変更 | CLI 側の旧 import 禁止ゲートを維持し、削除後の API 名に合わせる |
| `tests/gui/` | 変更 | GUI の singleton 依存削除に合わせて fixture / monkeypatch を更新する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

Runtime / Ports 再設計後の正しい依存方向は、GUI / CLI が composition root として `MacroRuntimeBuilder` を組み立て、Runtime core は Ports だけを見る形である。`singletons.py` や legacy builder alias はこの依存方向を曖昧にするため削除する。

### 公開 API 方針

`RUNTIME_AND_IO_PORTS.md` で定義済みの `DeviceDiscoveryService` と Port factory を実装へ昇格し、manager を builder の公開入力から外す。`create_device_runtime_builder()` は正 API として残すが、`serial_manager` / `capture_manager` / direct device 引数は削除する。

```python
def create_device_runtime_builder(
    *,
    project_root: Path,
    registry: MacroRegistry,
    device_discovery: DeviceDiscoveryService | None = None,
    controller_output_factory: ControllerOutputPortFactory | None = None,
    frame_source_factory: FrameSourcePortFactory | None = None,
    notification_handler,
    logger: LoggerPort,
    serial_name: str | None = None,
    capture_name: str | None = None,
    baudrate: int | None = None,
    detection_timeout_sec: float = 2.0,
    settings: SettingsSnapshot | None = None,
    lifetime_allow_dummy: bool | None = None,
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
| Runtime builder | `DeviceDiscoveryService` と Port factory から Port を組み立てる。manager / direct device 引数と legacy alias は持たない |
| Command | `ExecutionContext` を必須にする。旧コンストラクタ引数は受け付けない |
| Framework singleton | Runtime / GUI / CLI の共有状態として使わない。module ごと削除する |
| Tests | 旧 import を monkeypatch せず、fixture で discovery / Port factory / store fake を生成する |

### Manager 置換方針

`SerialManager` / `CaptureManager` は再設計後の正規レイヤーではない。device 列挙、active device 切り替え、暗黙 dummy 選択、非同期検出開始を 1 クラスに持つため、旧 singleton を削除しても manager 中心の lifetime と状態共有が残る。

今回の cleanup で manager を `DeviceDiscoveryService` と Port factory へ置換する。manager を暫定具象実装として温存しない。

| 旧 manager 責務 | 置換先 |
|----------------|--------|
| device 列挙 | `DeviceDiscoveryService.detect(timeout_sec)` |
| active device 選択 | `ControllerOutputPortFactory.create(name, baudrate, allow_dummy)` / `FrameSourcePortFactory.create(name, allow_dummy)` |
| 暗黙 dummy fallback | `RuntimeBuildRequest.allow_dummy` と `RuntimeOptions.allow_dummy` による明示許可 |
| 非同期検出開始だけして完了を待たない挙動 | `DeviceDiscoveryResult` の success / timeout / failure |
| manager close / release | Port factory の `close()` と `MacroRuntimeBuilder.shutdown()` |

GUI / CLI は device 一覧表示と実行要求のために `DeviceDiscoveryService` を使ってよいが、active device 実体を保持しない。Runtime core と `ExecutionContext` は Port だけを扱い、device discovery や factory の具象状態へ依存しない。

Port factory は device 名ごとに device 実体を共有する。GUI preview、manual input、macro run が同じ物理デバイスを参照しても、同一 COM ポートや同一 capture device を二重 open しない。run 単位の Port は軽量 wrapper とし、実体の close / release は factory と builder shutdown が担う。

### 削除ゲートと依存方向ゲート

削除ゲートは「削除対象 API を import できないこと」だけでなく、「削除対象 API への参照が実装コード・テストコードに残っていないこと」を検証する。文字列検索だけでは import 形態の揺れを拾いにくいため、`ast.Import` / `ast.ImportFrom` を走査するユニットテストを追加する。

依存方向ゲートは次を検証する。

| 検査対象 | 禁止する依存 |
|----------|--------------|
| `src/nyxpy/framework/**/*.py` | `nyxpy.gui`、`nyxpy.cli`、`macros` への import |
| `src/nyxpy/gui/**/*.py` / `src/nyxpy/cli/**/*.py` | `nyxpy.framework.core.singletons` と legacy builder への import |
| `macros/{macro}/**/*.py` | `macros.shared` 以外の `macros.{other_macro}` への import |
| `tests/**/*.py` | 削除対象 API を monkeypatch / import する依存。ただし削除ゲート自身の検査文字列は除外 |

マクロはフレームワークへ依存してよい。フレームワークは GUI / CLI / macros へ依存しない。GUI / CLI は composition root として framework の正 API を組み立てる。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| GUI preview 更新 | cleanup 前後で preview perf gate の閾値を悪化させない |
| Runtime build | builder alias 削除により追加の wrapper 呼び出しを 0 にする |
| テスト分離 | singleton reset に依存しない fixture 生成へ移行する |

### 並行性・スレッド安全性

singleton 削除により、GUI preview、manual input、macro run が同じ global manager を暗黙共有する経路をなくす。GUI が所有する lifetime Port は `MacroRuntimeBuilder.shutdown()` で閉じ、run 単位の Port は `MacroRuntime` の実行 lifetime で閉じる方針を維持する。

GUI の preview / manual input 用 lifetime Port は初回起動時に設定が空でも作成できるよう、`lifetime_allow_dummy=True` を明示して dummy を許可する。マクロ実行時の dummy 許可は `RuntimeBuildRequest.allow_dummy` と `runtime.allow_dummy` に従い、preview 用の許可を run に流用しない。設定変更時は builder を再生成し、旧 builder を shutdown して lifetime Port と factory cache を差し替える。

## 4. 実装仕様

### 4.1 削除対象

| 対象 | 現状 | 修正後 |
|------|------|--------|
| `create_legacy_runtime_builder()` | `create_device_runtime_builder()` への alias | 関数削除。import は失敗する |
| `nyxpy.framework.core.singletons` | manager / settings singleton を生成 | ファイル削除。GUI / CLI / tests は import しない |
| `DefaultCommand.__init__(context=None, **legacy_kwargs)` | legacy 引数を受けて手動 TypeError | `DefaultCommand(context: ExecutionContext)` |
| `create_device_runtime_builder(serial_manager=..., capture_manager=...)` | manager を Port へ接続する暫定入力 | 引数削除。discovery / Port factory 入力だけを受け付ける |
| `SerialManager` / `CaptureManager` | device 列挙、active device、暗黙 dummy fallback を保持 | public class として削除。device 実体と検出 helper は discovery / factory へ移す |
| `NotificationHandlerPort` | `NotificationHandlerAdapter` の互換 alias | class / re-export を削除し、呼び出し元は `NotificationHandlerAdapter` を使う |
| `CancellationToken.request_stop()` の source 値 | `source="legacy"` を記録 | `source="request_stop"` など、呼び出し元を表す値にする |
| GUI の global manager 利用 | `capture_manager`, `serial_manager`, `global_settings`, `secrets_settings` を import | `MainWindow` は manager を所有せず、GUI composition root が discovery / Port factory / settings を所有する |
| GUI device settings tab の singleton import | dialog 内で global manager を参照 | constructor 引数または provider で device list を取得 |

### 4.2 保持してよい対象

| 対象 | 理由 | 制約 |
|------|------|------|
| `SerialComm` / `DummySerialComm` | controller Port factory が接続する device 実体 | manager を経由せず、factory が生成・close する |
| `AsyncCaptureDevice` / `DummyCaptureDevice` | frame source Port factory が接続する device 実体 | manager を経由せず、factory が生成・release する |
| `create_device_runtime_builder()` | GUI / CLI composition root が Runtime を組み立てる正 API | manager / direct device 引数を受け付けない |
| `Command` / `DefaultCommand` / `MacroBase` | Runtime 実行時の現行 API | 旧コンストラクタや旧 import shim は残さない |
| `CancellationToken.request_stop()` メソッド | 現行の中断要求 API として残す | legacy 由来のメタデータを残さない。メソッド自体の統廃合は Cancellation API 仕様で扱う |
| `MacroStopException` | Runtime が捕捉する現行の中断例外として使われている | 今回は削除しない。例外体系の統廃合は別仕様で扱う |

### 4.3 呼び出し元移行

1. `DeviceDiscoveryService` と Port factory を実装し、`create_device_runtime_builder()` の manager / direct device 引数を削除する。
2. `tests/unit/framework/runtime/test_runtime_builder.py` と `tests/hardware/test_macro_runtime_realdevice.py` を discovery / Port factory 入力へ更新する。
3. GUI 起動時に `GlobalSettings`、`SecretsSettings`、`DeviceDiscoveryService`、Port factory を `MainWindow` の composition root で生成する。
4. `AppSettingsDialog` と `DeviceSettingsTab` に、global singleton ではなく discovery service 由来の device list を渡す。
5. `PreviewPane` には `MacroRuntimeBuilder.frame_source_for_preview()` を渡し、`capture_manager.get_active_device()` 直参照を削る。
6. CLI 起動時に `DeviceDiscoveryService` と Port factory を生成し、`create_device_runtime_builder()` へ渡す。
7. GUI / CLI cleanup は `runtime_builder.shutdown()` と logging close に寄せ、manager close / release 直呼びを残さない。
8. `SerialManager` / `CaptureManager` public class を削除し、必要な列挙 helper と device 生成は discovery / factory へ移す。
9. `NotificationHandlerPort` を参照するテストを `NotificationHandlerAdapter` へ移行し、alias を削除する。
10. `CancellationToken.request_stop()` の source 値を `request_stop` へ変更し、legacy 表現をテスト期待値に残さない。

### 4.4 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| 追加なし | - | - | `runtime.allow_dummy`、`runtime.device_detection_timeout_sec` など既存 rearchitecture 方針の設定だけを使う |

### 4.5 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ImportError` / `ModuleNotFoundError` | 削除後の `create_legacy_runtime_builder` または `nyxpy.framework.core.singletons` を import した |
| `TypeError` | `DefaultCommand` を `context` なし、または旧 keyword 引数で生成した |
| `ConfigurationError` | device 未選択、dummy 不許可、factory / discovery の構成不正など、builder validation に失敗した |
| `DeviceDiscoveryResult.timed_out` | device discovery が timeout 内に完了しない |
| `DeviceDiscoveryResult.errors` | serial / capture の列挙処理が例外を返した。例外内容は logger にも出力し、空の成功結果として扱わない |

旧 API 呼び出し時に移行先を案内する専用例外や警告は追加しない。失敗は Python の通常の import / signature error として表面化させる。

### 4.6 シングルトン管理

`singletons.py` は削除する。テスト用の `reset_for_testing()` も削除し、テストは fixture で必要な object を生成する。Runtime、builder、Port、settings store、secrets store、device discovery、Port factory は呼び出し元が lifetime を所有する。

### 4.7 skills / agent 向け文書の扱い

`.github/skills/framework-spec-writing/SKILL.md` には、仕様書執筆時に参照すべき現行ドキュメントを追記するにとどめる。cleanup の経緯、旧実装の詳細、なぜ削除したかの説明は仕様書側に置き、skills 側には持たせない。

参照先として追加する候補は次に限定する。

| 参照先 | 用途 |
|--------|------|
| `spec/framework/rearchitecture/ARCHITECTURE_DIAGRAMS.md` | Runtime / Ports 再設計後の依存方向を確認する |
| `spec/framework/rearchitecture/DEPRECATION_AND_MIGRATION.md` | cleanup 時の互換性方針を確認する |
| `spec/framework/rearchitecture/FOLLOWUP_FIXES.md` | followup で残った実装課題を確認する |

### 4.8 追加 cleanup の扱い

今回の主対象は Runtime builder、Command、framework singleton、GUI composition root である。調査で見つかった互換 alias や legacy 表現のうち、呼び出し元が限定的で同時修正できるものは同じ変更に含める。

| 対象 | 扱い |
|------|------|
| `SerialManager` / `CaptureManager` | 旧 manager 層を温存しない。DeviceDiscoveryService / Port factory へ置換し、public class を削除する |
| `NotificationHandlerPort` | `NotificationHandlerAdapter` の別名であり、現状の参照は framework io テストに限定されるため同時削除する |
| `CancellationToken.request_stop()` の `source="legacy"` | API 削除ではなくメタデータ表現の cleanup として同時修正する |
| `MacroStopException` | Runtime と import contract に関わるため今回の同時削除対象外。例外 API cleanup として別仕様で扱う |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_runtime_builder_public_factory_is_device_builder_only` | `create_device_runtime_builder()` が正 API として動作し、legacy alias を使わない |
| ユニット | `test_legacy_runtime_builder_removed` | `create_legacy_runtime_builder` が import できない |
| ユニット | `test_framework_singletons_module_removed` | `nyxpy.framework.core.singletons` が import できない |
| ユニット | `test_default_command_accepts_context_only` | `DefaultCommand(context)` は成功し、旧 keyword 引数は `TypeError` |
| ユニット | `test_framework_does_not_depend_on_upper_layers` | framework から GUI / CLI / macros への import がない |
| ユニット | `test_macros_only_depend_on_framework_and_shared_macros` | `macros.shared` 以外の macro 間直接依存がない |
| ユニット | `test_application_code_does_not_import_removed_apis` | 実装コードが削除対象 API を import しない |
| ユニット | `test_device_discovery_returns_detected_names_without_dummy` | manager を使わず device 検出結果を取得し、dummy を検出結果へ混ぜない |
| ユニット | `test_device_discovery_reports_timeout` | 検出 timeout を例外ではなく結果として扱う |
| ユニット | `test_device_discovery_reports_detection_errors` | 検出例外を結果とログに表面化し、成功扱いで握りつぶさない |
| ユニット | `test_device_factories_reject_implicit_dummy_when_dummy_is_not_allowed` | Port factory の dummy 生成が Runtime validation をすり抜けない |
| ユニット | `test_frame_source_factory_reuses_device_and_initializes_once` | Port factory が同一 device 実体を共有し、二重 initialize を避ける |
| ユニット | `test_notification_handler_port_alias_removed` | `NotificationHandlerPort` が import できず、`NotificationHandlerAdapter` のみを使う |
| ユニット | `test_request_stop_records_non_legacy_source` | `CancellationToken.request_stop()` が legacy 表現を source に残さない |
| 結合 | `test_cli_runtime_adapter_does_not_import_legacy_framework_apis` | CLI が legacy builder / singleton を参照しない |
| GUI | `test_main_window_uses_device_runtime_builder` | GUI が discovery / Port factory から runtime builder を組み立て、manager を所有しない |
| GUI | `test_device_settings_tab_uses_injected_device_source` | device settings tab が `singletons.py` を import しない |
| ハードウェア | `test_macro_runtime_runs_with_real_serial_and_capture` | realdevice test が正 API の builder で実機実行できる |
| 性能 | `test_preview_runtime_frame_source_contention` | preview と runtime の frame source 競合対策が cleanup 後も維持される |

実装後の検証コマンドは次を必須とする。

```powershell
uv run pytest
uv run ruff check .
git --no-pager diff --check
```

静的ゲートは文字列検索だけに頼らず、AST ベースのテストで import を検査する。補助確認として次を実行する。

```powershell
uv run pytest tests\unit\framework\runtime\test_removed_api_imports.py tests\unit\framework\test_dependency_boundaries.py
rg "create_legacy_runtime_builder|nyxpy\.framework\.core\.singletons|NotificationHandlerPort|SerialManager|CaptureManager|serial_manager|capture_manager" src
rg "DeprecationWarning|warnings\.warn|Backward-compatible alias|compatibility singletons|source=\"legacy\"" src tests
```

## 6. 実装チェックリスト

- [x] 仕様レビューで削除対象と保持対象の境界を確定
- [x] `create_legacy_runtime_builder()` を削除
- [x] `DefaultCommand.__init__` を `context` 必須署名へ変更
- [x] `singletons.py` を削除
- [x] `SerialManager` / `CaptureManager` を DeviceDiscoveryService / Port factory へ置換
- [x] `create_device_runtime_builder()` の manager / direct device 引数を削除
- [x] `NotificationHandlerPort` alias を削除
- [x] `CancellationToken.request_stop()` の legacy source 表現を削除
- [x] GUI の singleton 依存を composition root 所有の discovery / Port factory / store へ移行
- [x] GUI device settings tab の singleton import を削除
- [x] manager の active device、dummy fallback、終了処理が実装コードに残っていないことを確認
- [x] framework / GUI / CLI / macros の依存方向ゲートを追加
- [x] CLI / GUI / framework / tests の legacy import 静的ゲートを追加
- [x] ユニットテストを更新
- [x] GUI テストを更新
- [x] ハードウェアテストの import を正 API へ更新
- [x] `uv run pytest` をパス
- [x] `uv run ruff check .` をパス
- [x] `git --no-pager diff --check` をパス

# swbt runtime / CLI 連携仕様書

## 1. 概要

### 1.1 目的

Runtime builder の構成起点で `serial` / `swbt` controller backend を選択し、`swbt` backend では serial protocol 生成を通らずに `SwbtControllerOutputPortFactory` を注入する。CLI には `nyxpy run --controller swbt` と `nyxpy swbt pair/reconnect` を追加する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `ControllerConfig` | `SerialControllerConfig | SwbtControllerConfig` |
| `make_controller_port_factory` | `ControllerConfig` から runtime 用 `PortFactory[ControllerOutputPort]` を作る構成関数 |
| `nyxpy swbt pair` | settings + CLI override から swbt config を作り、明示 pairing する CLI |
| `nyxpy swbt reconnect` | settings + CLI override から swbt config を作り、保存済み key store で明示 reconnect する CLI |
| runtime reconnect | macro run 開始時に保存済み pairing key で接続する処理。pairing はしない |
| CLI override | settings より優先する CLI 指定値。当該実行だけに効き、settings を書き換えない |

### 1.3 背景・問題

現行 `nyxpy run` は serial protocol を先に作ってから runtime builder を構成する。これでは `--controller swbt` を選んでも serial device / protocol 生成を避けられない。swbt backend は `SerialProtocolInterface` ではなく `ControllerOutputPort` backend なので、controller backend の解決を protocol 生成より前へ移す必要がある。

Pairing は利用者の明示操作である。macro run が key store 不足を見て暗黙 pairing すると、実行時に Switch 側状態を要求し、再現性の低い副作用になる。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt run | 未導入 | `nyxpy run sample --controller swbt ...` で runtime port を注入できる |
| serial protocol 生成 | CLI が常に実行 | swbt backend では 0 回 |
| pair/reconnect CLI | 未導入 | `nyxpy swbt pair` / `reconnect` で明示 lifecycle |
| CLI choices | 手書きになり得る | `supported_controller_models()` から導出 |
| parser 必須 | `--serial` / `--capture` が必須 | settings fallback と validation に寄せる |

### 1.5 着手条件

- `local_022` の config、IMU、adapter discovery、`nyxpy swbt adapters` が完了している。
- `local_023` の session、mapper、port、factory が完了している。
- CLI に clipboard / command copy / GUI 連携用 preview は追加しない。
- `nyxpy swbt status` は初期範囲外とする。

### 1.6 完了結果

- `create_device_runtime_builder()` は `ControllerConfig` を受け取り、`SerialControllerConfig` では `SerialControllerOutputPortFactory`、`SwbtControllerConfig` では `SwbtControllerOutputPortFactory` を選ぶ構成にした。
- `nyxpy run` は settings と CLI override から controller config を作る。`--controller swbt` では serial protocol を生成しない。
- `nyxpy swbt pair` / `reconnect` を追加し、CLI override が settings を保存しないことをテストで確認した。fresh factory では前回 process の cached session を閉じられないため、CLI `disconnect` は監査で削除した。
- CLI は同期 facade として factory / session を呼び、swbt-python 0.2.0 の async API は session の event loop thread で完了待ちする。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | `ControllerConfig` ベースの factory 選択と `make_controller_port_factory()` を追加する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | 既存 serial factory を `SerialControllerOutputPortFactory` として扱い、旧名 alias を残さない |
| `src/nyxpy/cli/run_cli.py` | 変更 | `--controller`、`--swbt-adapter`、`--swbt-controller-type`、`--swbt-key-store`、`--swbt-timeout` を追加し、`--serial` / `--capture` の parser 必須を外す |
| `src/nyxpy/cli/swbt_cli.py` | 変更 | `pair`、`reconnect` subcommand の処理を実装する |
| `src/nyxpy/__main__.py` | 変更 | `swbt pair/reconnect` subparser を追加し、`swbt_cli.py` へ委譲する |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | backend 別 factory 選択を検証する |
| `tests/unit/cli/test_run_cli_parser.py` | 変更 | `nyxpy run` の swbt option、`--serial` / `--capture` 任意化、backend validation を検証する |
| `tests/unit/cli/test_swbt_cli.py` | 変更 | `pair`、`reconnect`、adapter 正規化を fake factory で検証する |
| `tests/integration/test_swbt_runtime_cli_integration.py` | 新規 | dummy session で `Command.press()` / `Command.imu()` が runtime から届くことを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

backend 選択は runtime builder を作る構成処理で完了させる。`MacroRuntimeBuilder.build()`、`ExecutionContext`、`Command` は backend 種別を判定しない。controller backend と capture source は独立して解決する。

### 公開 API 方針

`nyxpy run` の `--controller` は `serial|swbt` を受ける。未指定時は settings の `controller.backend` に従う。`nyxpy swbt` は developer / operator 向け CLI であり、GUI 連携用の clipboard 出力は持たない。

### 後方互換性

旧 serial flat settings key は廃止する。`--serial`、`--protocol`、`--baud` は serial backend 用 override として残すが、parser 必須にはしない。swbt backend では `--serial`、`--protocol`、`--baud` を controller factory へ渡さない。

### レイヤー構成

`run_cli.py` と `swbt_cli.py` は `hardware/swbt` の service / factory を使うが、`swbt-python` の controller class を直接 import しない。`__main__.py` は subparser と委譲だけを担当する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `--controller swbt` の serial protocol 生成 | 0 回 |
| `nyxpy swbt adapters` | `local_022` で実装済み。adapter open なし |
| dummy runtime integration | 実機なしで短時間に完了 |
| runtime shutdown | swbt factory close callback が 1 回実行される |

### 並行性・スレッド安全性

CLI は同期処理として session / factory を呼ぶ。async controller API の完了待ちは session が所有する。CLI 終了時は `finally` で runtime builder または factory を close する。

## 4. 実装仕様

### runtime factory 選択

```python
def make_controller_port_factory(
    *,
    config: ControllerConfig,
    serial_factory: SerialControllerOutputPortFactory | None,
    swbt_factory: SwbtControllerOutputPortFactory | None,
    allow_dummy: Callable[[RuntimeBuildRequest], bool],
    detection_timeout_sec: float,
) -> PortFactory[ControllerOutputPort]: ...
```

`SerialControllerConfig` では serial factory を使う。`SwbtControllerConfig` では swbt factory を使い、`factory.create(config=config, allow_dummy=..., timeout_sec=config.connect_timeout_sec)` を呼ぶ。swbt branch では `ProtocolFactory.resolve_baudrate()` と `ProtocolFactory.create_protocol()` を呼ばない。

### `nyxpy run` option

| option | 型 | backend | 説明 |
|--------|----|---------|------|
| `--controller serial|swbt` | `str | None` | 共通 | controller backend override |
| `--serial` | `str | None` | serial | serial device override |
| `--protocol` | `str | None` | serial | protocol override |
| `--baud` | `int | None` | serial | baudrate override |
| `--capture` | `str | None` | capture | capture source override |
| `--swbt-adapter` | `str | None` | swbt | adapter override |
| `--swbt-controller-type` | `str | None` | swbt | controller type override |
| `--swbt-key-store` | `Path | None` | swbt | key store override |
| `--swbt-timeout` | `float | None` | swbt | connect timeout override |

`--serial` と `--capture` は parser 必須にしない。未指定時は settings から解決する。serial backend で serial device が解決できない場合、または capture source が解決できない場合は validation error とする。

### `nyxpy swbt pair` / `reconnect`

```console
nyxpy swbt pair --adapter usb:0 --controller-type pro-controller
nyxpy swbt reconnect --adapter usb:0 --controller-type pro-controller
```

各 command は workspace settings を読み、CLI option で override して `SwbtControllerConfig` を作る。`--controller-type` を省略した場合は `controller.swbt.controller_type` を使う。`--key-store` を省略した場合は、解決済み controller type から workspace root 基準の `.nyxpy/swbt/<controller>-bond.json` を使う。`--adapter` を省略した場合は settings の `controller.swbt.adapter` を使う。settings と CLI の両方で adapter が空なら `NYX_SWBT_ADAPTER_NOT_SELECTED` とする。指定値は discovery 結果の `name` / `aliases` から代表 `name` へ正規化し、不一致と曖昧 alias を明示 error にする。

CLI override は settings を書き換えない。

CLI は command ごとに別 process で fresh factory を作る。同一 process の cached session が存在しないため、`disconnect` subcommand は提供しない。GUI は同じ factory lifetime を維持するため `Disconnect` を提供する。

### エラーハンドリング

| 条件 | 動作 |
|------|------|
| serial backend で serial device 未指定 | `ConfigurationError` を表示し終了 code 1 |
| capture source 未選択 | `ConfigurationError` を表示し終了 code 1 |
| adapter 未選択 / 不一致 / alias 曖昧 | 説明本文と `NYX_SWBT_ADAPTER_*` code を表示 |
| key store 不正 | `NYX_SWBT_KEY_STORE_INVALID` を表示 |
| pairing / reconnect timeout | `NYX_SWBT_CONNECTION_TIMED_OUT` を表示 |
| `runtime_builder.shutdown()` 失敗 | technical log に残し、既存 cleanup 方針に従う |

### シングルトン管理

新規グローバル singleton は追加しない。CLI 実行ごとに factory を生成し、`finally` で close する。runtime builder が factory lifetime を所有する場合は shutdown callback に登録する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_run_parser_accepts_swbt_without_serial` | `--controller swbt` で `--serial` なし parse が通る |
| ユニット | `test_run_parser_accepts_settings_capture_without_capture_option` | `--capture` なし parse が通る |
| ユニット | `test_run_serial_requires_serial_at_validation` | serial backend だけ serial device を要求する |
| ユニット | `test_run_capture_requires_source_at_validation` | capture source 未解決を失敗にする |
| ユニット | `test_run_swbt_does_not_resolve_serial_protocol` | swbt backend で serial protocol factory が呼ばれない |
| ユニット | `test_run_swbt_cli_overrides_settings` | adapter、controller type、key store、timeout を config へ反映 |
| ユニット | `test_make_controller_port_factory_selects_swbt` | swbt config で swbt factory を選ぶ |
| ユニット | `test_swbt_pair_cli_calls_factory_pair` | pair CLI が明示 pairing だけを呼ぶ |
| ユニット | `test_swbt_reconnect_cli_calls_factory_reconnect` | reconnect CLI が明示 reconnect だけを呼ぶ |
| ユニット | `test_swbt_cli_canonicalizes_adapter_alias` | alias を discovery 結果の代表名へ正規化する |
| ユニット | `test_swbt_cli_overrides_do_not_mutate_settings` | CLI override が settings を保存しない |
| 結合 | `test_swbt_runtime_runs_press_and_imu_with_dummy_session` | dummy session に Button と IMU state が届く |
| 結合 | `test_command_runtime_context_do_not_import_swbt` | `Command` / `MacroRuntime` / `ExecutionContext` が swbt を import しない |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/cli/test_run_cli_parser.py tests/unit/cli/test_swbt_cli.py tests/unit/framework/runtime/test_runtime_builder.py tests/integration/test_swbt_runtime_cli_integration.py -m "not realdevice and not swbt"
uv run pytest tests/unit -m "not realdevice and not swbt"
uv run pytest tests/integration -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [x] `SerialControllerOutputPortFactory` を正名として扱い、旧名 alias を残さない。
- [x] `make_controller_port_factory()` を追加し、backend 分岐を構成処理に閉じる。
- [x] `create_device_runtime_builder()` と `create_runtime_builder()` を `ControllerConfig` ベースへ更新する。
- [x] swbt backend で serial protocol 生成を呼ばないことをテストする。
- [x] `nyxpy run` に swbt option を追加する。
- [x] `--serial` と `--capture` の parser 必須を外し、validation へ移す。
- [x] `nyxpy swbt pair` と `nyxpy swbt reconnect` を追加する。
- [x] fresh factory で意味を持たない CLI `disconnect` を削除する。
- [x] `supported_controller_models()` から CLI choices を作る。
- [x] CLI override が settings を書き換えないことを確認する。
- [x] runtime shutdown で swbt factory close が呼ばれることを確認する。
- [x] dummy session を使った runtime integration test を追加する。

## 7. 2026-07-10 監査追補

本仕様の当初完了後、CLI `disconnect` が毎回生成される fresh factory に対する no-op であることを確認した。アルファ版の後方互換性方針に従い subcommand を削除し、pair / reconnect 時の adapter alias 正規化と error code 表示を追加した。

`MacroRuntimeBuilder.build()` の途中で factory が失敗した場合は、生成済み `artifacts -> resources -> frame_source -> controller` を取得と逆順で close する。元の build 例外を失わず、cleanup 例外も `ExceptionGroup` に保持する。`notifications` と `logger` は runtime close contract の対象外である。

# swbt runtime / CLI 連携仕様書

## 1. 概要

### 1.1 目的

Runtime builder の構成起点で `serial` / `swbt` controller backend を選択し、`swbt` backend では serial protocol 生成を通らずに `SwbtControllerOutputPortFactory` を注入する。CLI には `nyxpy run --controller swbt` と `nyxpy swbt adapters/pair/reconnect` を追加する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `ControllerConfig` | `SerialControllerConfig | SwbtControllerConfig` |
| `make_controller_port_factory` | `ControllerConfig` から runtime 用 `PortFactory[ControllerOutputPort]` を作る構成関数 |
| `nyxpy swbt adapters` | adapter 候補を列挙する CLI。pairing / reconnect は開始しない |
| `nyxpy swbt pair` | controller type、adapter、key store を指定して明示 pairing する CLI |
| `nyxpy swbt reconnect` | 保存済み key store で明示 reconnect する CLI |
| runtime reconnect | macro run 開始時に保存済み pairing key で接続する処理。pairing はしない |
| CLI override | settings より優先する CLI 指定値 |

### 1.3 背景・問題

現行 `nyxpy run` は serial protocol を先に作ってから runtime builder を構成する。これでは `--controller swbt` を選んでも serial device / protocol 生成を避けられない。swbt backend は `SerialProtocolInterface` ではなく `ControllerOutputPort` backend なので、controller backend の解決を protocol 生成より前へ移す必要がある。

Pairing は利用者の明示操作である。macro run が key store 不足を見て暗黙 pairing すると、実行時に Switch 側状態を要求し、再現性の低い副作用になる。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt run | 未導入 | `nyxpy run sample --controller swbt ...` で runtime port を注入できる |
| serial protocol 生成 | CLI が常に実行 | swbt backend では 0 回 |
| adapter CLI | 未導入 | `nyxpy swbt adapters [--json]` で no-open discovery |
| pair/reconnect CLI | 未導入 | `nyxpy swbt pair` と `nyxpy swbt reconnect` で明示 lifecycle |
| CLI choices | 手書きになり得る | `supported_controller_models()` から導出 |

### 1.5 着手条件

- `local_022` の config、IMU、adapter discovery が完了している。
- `local_023` の session、mapper、port、factory が完了している。
- `swbt-python` 未導入環境では、`--controller swbt` または `nyxpy swbt ...` 実行時にだけ dependency missing を表示する。
- CLI に clipboard / command copy / GUI 連携用 preview は追加しない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | `ControllerConfig` ベースの factory 選択と `make_controller_port_factory()` を追加する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | 既存 serial factory を `SerialControllerOutputPortFactory` として扱い、旧名 alias を残さない |
| `src/nyxpy/cli/run_cli.py` | 変更 | `--controller`、`--swbt-adapter`、`--swbt-controller-type`、`--swbt-key-store`、`--swbt-timeout` を追加する |
| `src/nyxpy/cli/swbt_cli.py` | 新規 | `adapters`、`pair`、`reconnect` subcommand の処理を実装する |
| `src/nyxpy/__main__.py` | 変更 | `swbt` subparser を追加し、`swbt_cli.py` へ委譲する |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | backend 別 factory 選択を検証する |
| `tests/unit/cli/test_run_cli_parser.py` | 変更 | `nyxpy run` の swbt option と serial validation を検証する |
| `tests/unit/cli/test_swbt_cli.py` | 新規 | `adapters`、`pair`、`reconnect` CLI を fake service で検証する |
| `tests/integration/test_swbt_runtime_cli_integration.py` | 新規 | dummy session で `Command.press()` / `Command.imu()` が runtime から届くことを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

backend 選択は runtime builder を作る構成処理で完了させる。`MacroRuntimeBuilder.build()`、`ExecutionContext`、`Command` は backend 種別を判定しない。

### 公開 API 方針

`nyxpy run` の `--controller` は `serial|swbt` を受ける。未指定時は settings の `controller.backend` に従う。`nyxpy swbt` は developer / operator 向け CLI であり、GUI 連携用の clipboard 出力は持たない。

### 後方互換性

`nyxpy run sample --serial COM3 --capture Camera1` は維持する。`--serial` は parser 必須ではなく backend validation で必須にする。swbt backend では `--serial`、`--protocol`、`--baud` を controller factory へ渡さない。

### レイヤー構成

`run_cli.py` と `swbt_cli.py` は `hardware/swbt` の service / factory を使うが、`swbt-python` の controller class を直接 import しない。`__main__.py` は subparser と委譲だけを担当する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `--controller swbt` の serial protocol 生成 | 0 回 |
| `nyxpy swbt adapters` | adapter open なし |
| dummy runtime integration | 実機なしで短時間に完了 |
| runtime shutdown | factory close callback が 1 回実行される |

### 並行性・スレッド安全性

CLI は同期処理として session / factory を呼ぶ。event loop thread は `SwbtControllerSession` が所有する。CLI 終了時は `finally` で runtime builder または factory を close する。

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
| `--swbt-adapter` | `str | None` | swbt | adapter override |
| `--swbt-controller-type` | `str | None` | swbt | controller type override |
| `--swbt-key-store` | `Path | None` | swbt | key store override |
| `--swbt-timeout` | `float | None` | swbt | connect timeout override |
| `--swbt-diagnostics` | `Path | None` | swbt | diagnostics trace path |

`--swbt-controller-type` の choices は `supported_controller_models()` から作る。dependency missing で choices を作れない場合は swbt backend 実行時に `NYX_SWBT_DEPENDENCY_MISSING` として失敗する。

### `nyxpy swbt adapters`

```console
nyxpy swbt adapters
nyxpy swbt adapters --json
```

標準出力には adapter `name`、display name、aliases、VID/PID を出す。`--json` は `SwbtAdapterView` の machine-readable 表現を出す。列挙だけを行い、pairing / reconnect / report loop を開始しない。

### `nyxpy swbt pair` / `reconnect`

```console
nyxpy swbt pair --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
nyxpy swbt reconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
```

`pair` は `SwbtControllerOutputPortFactory.pair(config)` を呼ぶ。`reconnect` は `factory.reconnect(config)` を呼ぶ。どちらも最後に factory を close し、close 時に neutral を試みる。

### エラーハンドリング

| 条件 | 動作 |
|------|------|
| serial backend で serial device 未指定 | `ConfigurationError` を表示し終了 code 1 |
| swbt extra 未導入 | `NYX_SWBT_DEPENDENCY_MISSING` を表示 |
| adapter 未選択 / 不一致 | `NYX_SWBT_ADAPTER_*` を表示 |
| key store 不正 | `NYX_SWBT_KEY_STORE_INVALID` を表示 |
| pairing / reconnect timeout | `NYX_SWBT_CONNECTION_TIMED_OUT` を表示 |
| `runtime_builder.shutdown()` 失敗 | technical log に残し、既存 cleanup 方針に従う |

### シングルトン管理

新規グローバル singleton は追加しない。CLI 実行ごとに factory を生成し、`finally` で close する。runtime builder が factory lifetime を所有する場合は shutdown callback に登録する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_run_parser_accepts_swbt_without_serial` | `--controller swbt` で `--serial` なし parse が通る |
| ユニット | `test_run_serial_requires_serial_at_validation` | serial backend だけ serial device を要求する |
| ユニット | `test_run_swbt_does_not_resolve_serial_protocol` | swbt backend で serial protocol factory が呼ばれない |
| ユニット | `test_run_swbt_cli_overrides_settings` | adapter、controller type、key store、timeout を config へ反映 |
| ユニット | `test_make_controller_port_factory_selects_swbt` | swbt config で swbt factory を選ぶ |
| ユニット | `test_swbt_adapters_cli_prints_json` | fake discovery の JSON 出力 |
| ユニット | `test_swbt_pair_cli_calls_factory_pair` | pair CLI が明示 pairing だけを呼ぶ |
| ユニット | `test_swbt_reconnect_cli_calls_factory_reconnect` | reconnect CLI が明示 reconnect だけを呼ぶ |
| 結合 | `test_swbt_runtime_runs_press_and_imu_with_dummy_session` | dummy session に Button と IMU state が届く |
| 結合 | `test_command_runtime_context_do_not_import_swbt` | `Command` / `MacroRuntime` / `ExecutionContext` が swbt を import しない |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/cli/test_run_cli_parser.py tests/unit/cli/test_swbt_cli.py tests/unit/framework/runtime/test_runtime_builder.py tests/integration/test_swbt_runtime_cli_integration.py -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [ ] `SerialControllerOutputPortFactory` を正名として扱い、旧名 alias を残さない。
- [ ] `make_controller_port_factory()` を追加し、backend 分岐を構成処理に閉じる。
- [ ] `create_device_runtime_builder()` と `create_runtime_builder()` を `ControllerConfig` ベースへ更新する。
- [ ] swbt backend で serial protocol 生成を呼ばないことをテストする。
- [ ] `nyxpy run` に swbt option を追加する。
- [ ] `nyxpy swbt adapters` を追加し、adapter refresh が接続を開始しないことをテストする。
- [ ] `nyxpy swbt pair` と `nyxpy swbt reconnect` を追加する。
- [ ] `supported_controller_models()` から CLI choices を作る。
- [ ] runtime shutdown で swbt factory close が呼ばれることを確認する。
- [ ] dummy session を使った runtime integration test を追加する。

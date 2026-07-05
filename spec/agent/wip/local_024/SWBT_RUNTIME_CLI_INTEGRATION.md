# swbt runtime / CLI 連携仕様書

> **対象モジュール**: `src/nyxpy/framework/core/runtime/`, `src/nyxpy/cli/`
> **目的**: `controller.backend` と `--controller` で選ばれた controller backend を runtime builder に接続し、`swbt` backend では serial protocol 生成を通らずに `ControllerOutputPort` を注入する。
> **関連ドキュメント**: `spec/agent/wip/local_021/SWBT_CONTROLLER_BACKEND.md`, `docs/architecture/swbt-integration/runtime-composition.md`, `docs/architecture/swbt-integration/configuration-cli-gui.md`, `docs/architecture/swbt-integration/testing-rollout.md`
> **破壊的変更**: あり。`create_runtime_builder()` と `create_device_runtime_builder()` の controller 引数を config ベースへ寄せ、旧 `ControllerOutputPortFactory` 名の互換 alias は使わない。

## 1. 概要

### 1.1 目的

Runtime と CLI の構成起点で `serial` / `swbt` backend を一度だけ選択し、`MacroRuntimeBuilder` へ `PortFactory[ControllerOutputPort]` として注入する。`swbt` backend では `--serial` を不要にし、`ProtocolFactory.resolve_baudrate()` と `ProtocolFactory.create_protocol()` を呼ばない経路をテストで固定する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| MacroRuntimeBuilder | Registry と各種 port factory から `ExecutionContext` と `MacroRuntime` 実行単位を組み立てる composition root |
| ControllerConfig | `SerialControllerConfig` または `SwbtControllerConfig` の union。local_022 で追加される controller backend 設定 |
| SerialControllerConfig | serial backend の device、protocol、baudrate を保持する設定値 object |
| SwbtControllerConfig | swbt backend の adapter、key store、pairing 許可、timeout、diagnostics などを保持する設定値 object |
| SerialControllerOutputPortFactory | serial device と `SerialProtocolInterface` から `ControllerOutputPort` を生成する factory。local_022 の改名後名 |
| SwbtControllerOutputPortFactory | `SwbtGamepadService` を所有し、swbt 用 `ControllerOutputPort` を生成する factory。local_023 で追加される |
| CLI override | `nyxpy run` の option によって settings snapshot より優先される実行時設定 |
| dummy swbt service | 実 Bluetooth 接続を行わず、`ControllerOutputPort` から送られた state を記録するテスト用 service |

### 1.3 背景・問題

現行 `src/nyxpy/cli/run_cli.py` は `cli_main()` で `ProtocolFactory.resolve_baudrate()` と `create_protocol()` を先に呼び、その後 `create_runtime_builder()` に protocol を渡す。現行 `create_device_runtime_builder()` も `SerialProtocolInterface` と `ControllerOutputPortFactory.create(name=..., baudrate=...)` を必須前提にしている。

この順序では `--controller swbt` を選んでも serial protocol 生成を避けられない。swbt は `SerialProtocolInterface` ではなく `ControllerOutputPort` backend なので、backend 選択を protocol 生成より前へ移し、runtime builder には backend 選択済みの controller factory を渡す必要がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt CLI 実行時の serial protocol 生成 | `cli_main()` が常に `resolve_baudrate()` と `create_protocol()` を呼ぶ | `--controller swbt` では両方とも呼ばない |
| `--serial` の必須性 | parser が常に `required=True` とする | `serial` backend の実行時 validation だけで必須とし、`swbt` backend では不要 |
| runtime builder の controller 構成 | serial 名、baudrate、protocol を直接受ける | `ControllerConfig` から `PortFactory[ControllerOutputPort]` を構成する |
| 実機なし swbt runtime test | 未整備 | dummy swbt service で `Command.press()` から state 反映まで検証する |
| `Command` / `MacroRuntime` の swbt 依存 | swbt 未導入 | 引き続き swbt を import しない |

### 1.5 着手条件

- local_022 で `SerialControllerConfig`、`SwbtControllerConfig`、`ControllerConfig`、settings 正規化、`SerialControllerOutputPortFactory` 改名が実装済みであること。
- local_023 で `SwbtControllerOutputPortFactory`、`SwbtControllerOutputPort`、`DummySwbtGamepadService` 相当のテスト用 service が実装済みであること。
- `docs/architecture/swbt-integration/` の判断どおり、旧 factory 名の alias、互換 import、`DeprecationWarning` を追加しないこと。
- 既存 serial backend の CLI / runtime テストが、local_022 と local_023 の変更後も実行可能であること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | `create_device_runtime_builder()` を `ControllerConfig` ベースの controller factory 選択へ更新し、`make_controller_port_factory()` を追加する |
| `src/nyxpy/cli/run_cli.py` | 変更 | `--controller` と `--bt-*` option を追加し、backend 解決後に runtime builder を作成する |
| `src/nyxpy/__main__.py` | 変更 | `add_run_arguments()` 由来の `nyxpy run` parser で新 option を利用できることを維持する |
| `tests/unit/cli/test_run_cli_parser.py` | 変更 | CLI parser と `cli_main()` の backend 別挙動を検証する |
| `tests/unit/cli/test_main.py` | 変更 | `create_runtime_builder()` の新 signature と serial baudrate 解決を検証する |
| `tests/integration/test_cli_runtime_adapter.py` | 変更 | CLI adapter が secrets / settings / controller config を runtime builder へ正しく渡すことを検証する |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | `create_device_runtime_builder()` が `ControllerConfig` から serial / swbt factory を選ぶことを検証する |
| `tests/integration/test_swbt_runtime_cli_integration.py` | 新規 | dummy swbt service を使い、CLI 相当設定から runtime 実行までを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`MacroRuntimeBuilder` 本体は現行どおり `PortFactory[ControllerOutputPort]` を受ける。backend 選択は `MacroRuntimeBuilder.build()` 内では行わず、`create_device_runtime_builder()` の構成処理で完了させる。

`run_cli.py` は CLI option と settings snapshot を統合して `ControllerConfig` を作る。`serial` の場合だけ `ProtocolFactory.resolve_baudrate()` と `ProtocolFactory.create_protocol()` を呼び、`swbt` の場合は `SwbtControllerOutputPortFactory` へ必要な設定を渡す。

### 公開 API 方針

`nyxpy run` には次の option を追加する。

| option | 用途 | backend |
|--------|------|---------|
| `--controller serial|swbt` | controller backend の実行時選択 | 共通 |
| `--bt-adapter TEXT` | swbt adapter 名 | swbt |
| `--bt-pair` | pairing を一度許可する | swbt |
| `--bt-key-store PATH` | swbt bond 情報の保存先 | swbt |
| `--bt-timeout FLOAT` | swbt 接続 timeout 秒 | swbt |
| `--bt-diagnostics PATH` | swbt diagnostics trace 出力先 | swbt |

`--controller` の parser default は `None` とし、未指定時は settings 正規化に委ねる。settings にも backend がなければ local_022 の既定値として `serial` になる。これにより、設定ファイルで `controller.backend = "swbt"` を選んだ workspace を CLI の暗黙 default が上書きしない。

### 後方互換性

破壊的変更あり。`create_runtime_builder()` と `create_device_runtime_builder()` の controller 引数は `ControllerConfig` を中心に再設計する。Project NyX のフレームワーク本体はアルファ版として扱うため、旧 signature の shim は追加しない。呼び出し元とテストを同じ変更で正 API へ更新する。

CLI の利用者向け挙動では、既存の serial 実行形を維持する。

```console
nyxpy run sample_macro --serial COM3 --capture Camera1
nyxpy run sample_macro --controller serial --serial COM3 --capture Camera1
```

`--serial` は parser では必須にしない。`serial` backend の構成時に未指定なら `ConfigurationError` とし、`swbt` backend では未指定でも実行可能にする。`swbt` backend で明示された `--serial`、`--protocol`、`--baud` は serial factory へ渡さず、protocol 生成も行わない。

### レイヤー構成

`swbt-python` の import は local_023 の `hardware` / `io` 層に閉じる。`run_cli.py` は `SwbtControllerConfig` と `SwbtControllerOutputPortFactory` までを扱い、`swbt.SwitchGamepad` を直接 import しない。

`Command`、`MacroRuntime`、`ExecutionContext` は swbt を知らない。CLI の backend 分岐は composition root の責務であり、マクロ API や runtime 実行中の分岐には持ち込まない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| serial backend の device discovery | 現行どおり builder 作成時に一度実行する |
| swbt backend の serial discovery | controller 用には実行しない。capture discovery は既存 frame source 用に維持する |
| swbt backend の protocol factory 呼び出し | 0 回 |
| dummy swbt runtime integration | 実機なしで 1 秒以内に完了する短い smoke test とする |

### 並行性・スレッド安全性

本仕様の runtime / CLI 実装は、`SwbtGamepadService` の event loop thread や lock を直接実装しない。local_023 の factory と service が thread safety を担う。`create_device_runtime_builder()` は factory の lifetime を `shutdown_callbacks` に登録し、CLI の `finally` で `runtime_builder.shutdown()` を呼ぶ現行構造を維持する。

## 4. 実装仕様

### 公開インターフェース

```python
def make_controller_port_factory(
    *,
    config: ControllerConfig,
    serial_factory: SerialControllerOutputPortFactory | None,
    swbt_factory: SwbtControllerOutputPortFactory | None,
    allow_dummy: Callable[[RuntimeBuildRequest], bool],
    timeout_sec: float,
) -> PortFactory[ControllerOutputPort]:
    """ControllerConfig から runtime 用 controller port factory を作る。"""


def create_device_runtime_builder(
    *,
    project_root: Path,
    registry: MacroRegistry,
    notification_handler,
    logger: LoggerPort,
    controller_config: ControllerConfig | None = None,
    device_discovery: DeviceDiscoveryService | None = None,
    serial_controller_factory: SerialControllerOutputPortFactory | None = None,
    swbt_controller_factory: SwbtControllerOutputPortFactory | None = None,
    frame_source_factory: FrameSourcePortFactory | None = None,
    capture_name: str | None = None,
    detection_timeout_sec: float = 2.0,
    settings: SettingsSnapshot | None = None,
    lifetime_allow_dummy: bool | None = None,
) -> MacroRuntimeBuilder:
    """Device discovery と controller config を Runtime builder へ接続する。"""


def create_runtime_builder(
    logger: LoggerPort,
    *,
    project_root: pathlib.Path | None = None,
    controller_config: ControllerConfig | None = None,
    capture_name: str | None = None,
    detection_timeout_sec: float = 2.0,
    settings_store: SettingsStore | None = None,
    secrets_store: SecretsStore | None = None,
    device_discovery: DeviceDiscoveryService | None = None,
    serial_controller_factory: SerialControllerOutputPortFactory | None = None,
    swbt_controller_factory: SwbtControllerOutputPortFactory | None = None,
    frame_source_factory: FrameSourcePortFactory | None = None,
) -> MacroRuntimeBuilder:
    """CLI で利用する Runtime builder を作成する。"""
```

`create_runtime_builder()` から `protocol` の必須引数を外す。serial backend では `controller_config.protocol` から protocol を作り、`SerialControllerOutputPortFactory` を構成する。swbt backend では protocol を作らず、local_023 の `SwbtControllerOutputPortFactory` を使う。

### controller factory 選択

`make_controller_port_factory()` は `ControllerConfig` の型で分岐する。分岐後に返す callable は `MacroRuntimeBuilder` へ渡される通常の `PortFactory[ControllerOutputPort]` である。

```python
match config:
    case SerialControllerConfig():
        return lambda request, _definition: serial_factory.create(
            name=config.device,
            baudrate=config.baudrate,
            allow_dummy=allow_dummy(request),
            timeout_sec=timeout_sec,
        )
    case SwbtControllerConfig():
        return lambda request, _definition: swbt_factory.create(
            allow_dummy=allow_dummy(request),
            timeout_sec=config.connect_timeout_sec,
        )
```

`serial_factory` が `None` のまま `SerialControllerConfig` を受けた場合、`create_device_runtime_builder()` は `ProtocolFactory.create_protocol(config.protocol)` を使って `SerialControllerOutputPortFactory` を作る。`swbt_factory` が `None` のまま `SwbtControllerConfig` を受けた場合、local_023 の factory constructor へ `SwbtControllerConfig` を渡して作る。

### CLI option と settings 統合

`add_run_arguments()` は `--serial` の `required=True` を外し、`--controller` と `--bt-*` を追加する。CLI option の default は、settings を上書きしない値にする。

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `args.controller` | `str | None` | `None` | CLI 指定時だけ `controller.backend` を上書きする |
| `args.serial` | `str | None` | `None` | serial backend の device override。swbt では使わない |
| `args.protocol` | `str | None` | `None` | serial backend の protocol override。swbt では使わない |
| `args.baud` | `int | None` | `None` | serial backend の baudrate override。swbt では使わない |
| `args.capture` | `str` | 必須 | frame source 用 capture 名。controller backend に関係なく必須 |
| `args.bt_adapter` | `str | None` | `None` | swbt adapter override |
| `args.bt_pair` | `bool` | `False` | swbt pairing 許可 override。指定時のみ `True` |
| `args.bt_key_store` | `pathlib.Path | None` | `None` | swbt key store override |
| `args.bt_timeout` | `float | None` | `None` | swbt 接続 timeout override |
| `args.bt_diagnostics` | `pathlib.Path | None` | `None` | swbt diagnostics path override |

settings snapshot から local_022 の `controller_config_from_settings()` で基準 config を作り、CLI override を重ねる。`--bt-pair` は flag なので、未指定なら settings の `controller.swbt.allow_pairing` を維持し、指定時だけ `True` にする。

### CLI 実行順序

`cli_main()` は次の順序で処理する。

1. workspace と logging を初期化する。
2. settings store と secrets store を開く。
3. settings snapshot から `ControllerConfig` を作る。
4. CLI option を `ControllerConfig` へ重ねる。
5. `serial` backend の場合だけ baudrate と protocol を解決する。
6. `swbt` backend の場合は protocol factory を呼ばずに runtime builder を作る。
7. `RuntimeBuildRequest(entrypoint="cli")` で macro を実行する。
8. `finally` で `runtime_builder.shutdown()` と logging close を行う。

この順序により、`--controller swbt` の smoke test で `ProtocolFactory.resolve_baudrate()` と `create_protocol()` を例外化しても実行が成功する。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | `--controller` が未対応値、serial backend で device 未指定、swbt factory 作成失敗、swbt extra 未導入 |
| `ConfigurationError` | `--bt-timeout` が `0` 以下、または local_022 の settings validation に反する値 |
| `ValueError` | `--baud` が整数として parse できないなど argparse で捕捉される CLI 入力 |
| `ExceptionGroup` | `runtime_builder.shutdown()` で複数 port / factory close が失敗した場合。現行 cleanup logging に任せる |

serial backend で device 未指定の場合は、parser error ではなく `ConfigurationError` として扱う。これにより parser は `swbt` 実行にも同じ形で使える。

### シングルトン管理

新規グローバル singleton は追加しない。CLI 実行ごとに `create_runtime_builder()` が factory を構成し、`cli_main()` の `finally` で `runtime_builder.shutdown()` を呼ぶ。settings store と secrets store は既存の workspace lifetime に従い、swbt service lifetime は local_023 の `SwbtControllerOutputPortFactory` が所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_cli_parser_accepts_swbt_without_serial` | `--controller swbt --capture Camera1` を parse でき、`args.serial is None` になる |
| ユニット | `test_cli_parser_keeps_serial_options_optional_at_parse_time` | parser 段階では `--serial` なしでも失敗せず、backend validation へ進められる |
| ユニット | `test_cli_main_serial_resolves_protocol_and_baudrate` | `serial` backend では `ProtocolFactory.resolve_baudrate()` と `create_protocol()` が呼ばれる |
| ユニット | `test_cli_main_swbt_does_not_resolve_serial_protocol` | `swbt` backend では `resolve_baudrate()` と `create_protocol()` が呼ばれない |
| ユニット | `test_cli_main_swbt_passes_bt_options_to_controller_config` | `--bt-adapter`、`--bt-pair`、`--bt-key-store`、`--bt-timeout`、`--bt-diagnostics` が `SwbtControllerConfig` に反映される |
| ユニット | `test_create_runtime_builder_builds_serial_factory_from_config` | `SerialControllerConfig` では serial factory が使われる |
| ユニット | `test_create_runtime_builder_builds_swbt_factory_from_config` | `SwbtControllerConfig` では swbt factory が使われ、serial factory を要求しない |
| ユニット | `test_make_controller_port_factory_selects_serial` | `SerialControllerConfig` から serial `PortFactory` が作られる |
| ユニット | `test_make_controller_port_factory_selects_swbt` | `SwbtControllerConfig` から swbt `PortFactory` が作られる |
| 結合 | `test_runtime_builder_uses_swbt_factory_without_protocol_factory` | swbt config の runtime build で serial protocol factory が呼ばれない |
| 結合 | `test_cli_swbt_runtime_runs_press_a_with_dummy_service` | dummy swbt service で `Command.press(Button.A)` の state と neutral が記録される |
| 結合 | `test_command_runtime_context_do_not_import_swbt` | `Command`、`MacroRuntime`、`ExecutionContext` が swbt module を import しない |

実装後の通常検証は次を使う。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/cli tests/unit/framework/runtime tests/integration/test_cli_runtime_adapter.py tests/integration/test_swbt_runtime_cli_integration.py -m "not realdevice and not swbt"
```

本仕様では実機検証を実施しない。実機 pairing、reconnect、button / stick 反映は local_021 の M6 へ渡す。

## 6. 実装チェックリスト

- [ ] `create_device_runtime_builder()` の controller 引数を `ControllerConfig` ベースへ更新する。
- [ ] `make_controller_port_factory()` を追加し、serial / swbt の factory 選択を runtime builder 構成時に閉じる。
- [ ] `create_runtime_builder()` から必須 `protocol` 引数を外し、settings snapshot と CLI override から `ControllerConfig` を渡す形へ更新する。
- [ ] `add_run_arguments()` に `--controller` と `--bt-*` option を追加する。
- [ ] `--serial` の parser 必須指定を外し、serial backend の validation で必須にする。
- [ ] `swbt` backend で `ProtocolFactory.resolve_baudrate()` と `create_protocol()` を呼ばない実装にする。
- [ ] `swbt` backend で `--bt-adapter`、`--bt-pair`、`--bt-key-store`、`--bt-timeout`、`--bt-diagnostics` が `SwbtControllerConfig` に反映されるようにする。
- [ ] `nyxpy run` と `nyxpy.__main__` 経由の parser が同じ option を使うことを確認する。
- [ ] 既存 serial backend の CLI unit test を新 signature に更新する。
- [ ] dummy swbt service を使った runtime integration test を追加する。
- [ ] `Command`、`MacroRuntime`、`ExecutionContext` が swbt を import しないことを確認する。
- [ ] `uv run ruff format .` を実行する。
- [ ] `uv run ruff check .` を実行する。
- [ ] `uv run ty check src/nyxpy --output-format concise --no-progress` を実行する。
- [ ] 対象 unit / integration test を実行する。

## 7. 親計画との依存関係

この仕様は `spec/agent/wip/local_021/SWBT_CONTROLLER_BACKEND.md` の M4 に対応する。local_022 の controller config と settings 正規化、local_023 の swbt port / service / factory が完了していることを前提にする。

local_022 から受け取るもの:

| 成果 | 利用箇所 |
|------|----------|
| `SerialControllerConfig` | serial backend の device / protocol / baudrate 解決 |
| `SwbtControllerConfig` | swbt backend の adapter / pairing / timeout / diagnostics 解決 |
| `controller_config_from_settings()` | settings snapshot からの基準 config 作成 |
| `SerialControllerOutputPortFactory` | serial runtime port factory |

local_023 から受け取るもの:

| 成果 | 利用箇所 |
|------|----------|
| `SwbtControllerOutputPortFactory` | swbt runtime port factory |
| `DummySwbtGamepadService` または同等の fake | runtime integration test |
| `SwbtControllerOutputPort` | `ControllerOutputPort` として runtime に注入される具象 port |
| swbt 例外変換 | CLI で `ConfigurationError` としてユーザ向けに表示する |

## 8. 完了後に次へ渡す成果

local_025 以降の GUI 仕様へ次を渡す。

| 成果 | 受け渡し先での用途 |
|------|--------------------|
| `create_device_runtime_builder(controller_config=...)` | GUI backend 選択から runtime builder を再生成する入口 |
| `create_runtime_builder(..., controller_config=...)` の CLI 実装例 | GUI service layer の構成処理の参考 |
| swbt factory lifetime の `shutdown_callbacks` 登録 | GUI backend 切り替え時の古い connection close |
| dummy swbt runtime integration test | GUI なしで runtime injection が成立している証跡 |
| `--controller swbt` が serial protocol を通らないテスト | GUI 実装でも `ProtocolFactory` へ swbt を入れないための回帰防止 |

実機検証仕様へ次を渡す。

| 成果 | 受け渡し先での用途 |
|------|--------------------|
| CLI の `--bt-adapter` / `--bt-key-store` / `--bt-pair` | pairing と reconnect の手動確認コマンド |
| `--bt-diagnostics` | 実機検証時の trace 保存 |
| dummy integration の期待 state | 実機入力反映と比較する最小操作列 |

## 9. 未解決事項

本仕様の実装に入る前に追加の意思決定が必要な項目はない。stick Y 軸の既定値、短押し時の flush 要否、GUI diagnostics の既定保存先は local_021 の M6 または GUI 仕様の判断対象であり、runtime / CLI の構成順序には影響しない。

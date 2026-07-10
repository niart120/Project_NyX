# swbt session / mapper / port / factory 仕様書

## 1. 概要

### 1.1 目的

`swbt-python` の async controller API を NyX の同期 `ControllerOutputPort` として扱う core 部品を追加する。対象は `SwbtControllerSession`、diagnostics writer adapter、`NyxSwbtInputMapper`、`SwbtControllerOutputPort`、`SwbtControllerOutputPortFactory`、`DummySwbtControllerSession` である。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `SwbtControllerSession` | swbt controller instance、pair/reconnect、apply、neutral、close を所有する backend 内部部品 |
| diagnostics writer adapter | swbt 側 diagnostics writer を NyX の `LoggerPort` と実機 evidence writer へ接続する adapter |
| `DummySwbtControllerSession` | 実機なしテストで `InputState` を記録する session double |
| `NyxSwbtState` | port が持つ現在入力状態。button、left stick、right stick、IMU frames を含む |
| `NyxSwbtInputMapper` | `NyxSwbtState` と NyX 入力を swbt `InputState` へ変換する mapper |
| `SwbtControllerOutputPort` | `ControllerOutputPort` を実装し、完全な `InputState` を session へ渡す port |
| `SwbtControllerOutputPortFactory` | config ごとの session cache を持ち、runtime / GUI lifetime port を生成する factory |
| session key | controller type、adapter、key store、report period を含む cache key |

### 1.3 背景・問題

serial backend は同期 `send()` で入力を送れる。swbt-python 0.2.0 は `open()`、`pair()`、`reconnect()`、`apply()`、`neutral()`、`close()` が async、`status()` が同期 API である。NyX 側では session が event loop thread と controller lifecycle の直列化を所有し、port は入力状態と mapper に集中する。

GUI manual input と macro runtime は同じ adapter を同時に開けない。factory は同じ session key の session を cache し、serial factory と同じく接続資源の lifetime を所有する。ただし同じ port object は共有しない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt 接続 lifecycle | 未導入 | session が open/pair/reconnect/apply/neutral/close を所有する |
| 入力変換 | 未導入 | mapper が button、D-pad、stick、IMU を完全 state へ変換する |
| unsupported input | 未導入 | Joy-Con capability、touch、keyboard、sleep control を明確に失敗させる |
| macro runtime pairing | 未導入 | `create()` は reconnect のみ行い、暗黙 pairing しない |
| diagnostics | 未導入 | swbt diagnostics writer を `LoggerPort` と evidence writer へ接続できる |
| close | 未導入 | port close は neutral、factory close / disconnect は session close を行う |

### 1.5 着手条件

- `local_022` で `SwbtControllerConfig`、`SwbtControllerModel`、`IMUFrame`、adapter discovery、error mapping が実装済みである。
- `swbt-python>=0.2.0,<0.3.0` の root module public API だけを使う。
- `hardware/swbt/manual.py`、`SwbtManualInputSession`、`swbt_*.py` module は追加しない。
- CLI、GUI、runtime builder の接続は `local_024` と `local_025` に残す。

### 1.6 完了結果

- `SwbtControllerSession` は `swbt-python 0.2.0` の async 公開 API を専用 event loop thread で完了待ちし、`RLock` で lifecycle と入力適用を直列化する形へ監査修正した。
- `SwbtControllerOutputPortFactory` は同一 session key の session を再利用し、`create()` では `open()` と `reconnect()` だけを行う。`pair()` は GUI / CLI からの明示操作用として分離した。
- `SwbtControllerOutputPort` は現在入力状態を保持し、`press` / `hold` / `release` / `imu` ごとに完全な `InputState` を session へ渡す。port close は neutral だけを送り、session close は factory が担う。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/hardware/swbt/session.py` | 新規 | `SwbtControllerSession`、`DummySwbtControllerSession`、connection lifecycle を実装する |
| `src/nyxpy/framework/core/hardware/swbt/diagnostics.py` | 新規 | swbt diagnostics writer を `LoggerPort` と JSONL evidence writer へ接続する adapter を実装する |
| `src/nyxpy/framework/core/hardware/swbt/mapper.py` | 新規 | `NyxSwbtState`、`NyxSwbtInputMapper`、button / D-pad / stick / IMU mapping を実装する |
| `src/nyxpy/framework/core/hardware/swbt/controller.py` | 新規 | `SwbtControllerOutputPort` を実装する |
| `src/nyxpy/framework/core/hardware/swbt/factory.py` | 新規 | `SwbtControllerOutputPortFactory`、session cache、pair/reconnect/disconnect/status を実装する |
| `src/nyxpy/framework/core/hardware/swbt/errors.py` | 変更 | session / mapper / port のエラー code を追加する |
| `src/nyxpy/framework/core/hardware/swbt/__init__.py` | 変更 | core 部品を re-export する |
| `tests/unit/framework/hardware/swbt/test_session.py` | 新規 | fake swbt controller で session lifecycle を検証する |
| `tests/unit/framework/hardware/swbt/test_diagnostics.py` | 新規 | diagnostics writer adapter と tee writer を検証する |
| `tests/unit/framework/hardware/swbt/test_mapper.py` | 新規 | button、D-pad、stick、IMU、capability validation を検証する |
| `tests/unit/framework/hardware/swbt/test_controller.py` | 新規 | port の press/hold/release/imu/close を検証する |
| `tests/unit/framework/hardware/swbt/test_factory.py` | 新規 | session key、cache、dummy fallback、pair/reconnect/disconnect/status を検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`hardware/swbt` は swbt backend の具象実装を所有する。`SwbtControllerOutputPort` は `ControllerOutputPort` を実装するが、GUI 専用 adapter ではない。`SwbtControllerSession` は serial backend における `SerialComm` と `SerialProtocolInterface` の組み合わせに近い内部部品である。

### 公開 API 方針

外部へ見せる surface は `ControllerOutputPort` と factory の high-level lifecycle method に限定する。swbt の `InputState`、`Button`、`Stick`、`IMUFrame` は mapper 内に閉じる。`SwbtControllerSession` は framework 内部 API として扱う。

### 後方互換性

新規 backend 追加であり、serial backend の既存動作を変えない。`ControllerOutputPort` に追加済みの `imu()` は serial backend で既定 unsupported のままでよい。

### レイヤー構成

`controller.py` は port contract、`mapper.py` は入力変換、`session.py` は controller lifecycle、`factory.py` は session cache と pair/reconnect/disconnect/status 操作を担当する。factory 以外が GUI state や runtime builder を知らない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `press` / `release` | port 内で完全 `InputState` を作り 1 回 `session.apply()` |
| session connect | `open()` 後に reconnect のみ行う |
| dummy session | Bluetooth transport を開かない |
| port close | neutral を試み、session は閉じない |
| factory close | cached session を close する |

### 並行性・スレッド安全性

session は `RLock` と専用 event loop thread を持ち、async connection operation と input apply を直列化する。同期 `status()` は同じ lock 内で取得する。port は自身の `NyxSwbtState` を `RLock` で守る。

## 4. 実装仕様

### session

```python
class SwbtControllerSession:
    def open(self) -> None: ...
    def pair(self, *, timeout_sec: float) -> None: ...
    def reconnect(self, *, timeout_sec: float) -> None: ...
    def apply(self, state: object) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> object: ...
    def close(self) -> None: ...
```

`open()` は transport と report loop の準備だけを行い、pairing / reconnect を開始しない。`start()` は作らない。`factory.create()` は `open()` と `reconnect()` を呼ぶ。key store がない場合に pairing へ fallback しない。`pair()` / `reconnect()` の戻り値は `None` であり、session は操作後の同期 `status().connection_state` で接続を確認する。

### diagnostics writer adapter

swbt diagnostics は path 設定ではなく、swbt 側 diagnostics writer を NyX の logging / evidence へ接続する内部 adapter として扱う。

| 用途 | 出力 |
|------|------|
| 通常運用 | `LoggerPort.technical(...)` |
| 実機テスト | `LoggerPort.technical(...)` と `tmp/hardware/swbt/<timestamp>/swbt-trace.jsonl` |

通常 settings に `controller.swbt.diagnostics_path` は置かない。GUI diagnostics path UI と CLI `--diagnostics` も初期範囲外である。

### mapper

現行 NyX constants を正として扱う。button mapping は次である。

| NyX | swbt |
|-----|------|
| `Button.A` / `B` / `X` / `Y` | 同名 button |
| `Button.L` / `R` / `ZL` / `ZR` | 同名 button |
| `Button.PLUS` / `MINUS` / `HOME` | 同名 button |
| `Button.CAP` | `Button.CAPTURE` |
| `Button.LS` | `Button.LEFT_STICK` |
| `Button.RS` | `Button.RIGHT_STICK` |

`Button.CAPTURE`、`Button.LCLICK`、`Button.RCLICK` の alias は追加しない。

`Hat` は D-pad button set に変換する。`Hat.CENTER` は D-pad 全解除である。`LStick` / `RStick` は `0..255`、中心 `128`、Y-down である。`value < 128` は `(value - 128) / 128`、それ以外は `(value - 128) / 127` で正規化し、Y を反転して `Stick.normalized(...)` へ渡す。Joy-Con L は right stick、Joy-Con R は left stick を拒否する。

IMU は `IMUFrame` 1 個または 3 個だけを受ける。1 個は 3 frame に複製し、3 個は順に使う。0、2、4 個以上は `DeviceError(code="NYX_IMU_FRAME_COUNT_INVALID")` とする。

### port

```python
class SwbtControllerOutputPort(ControllerOutputPort):
    @property
    def supports_imu(self) -> bool: ...
    @property
    def supports_touch(self) -> bool: ...
    def press(self, keys: tuple[KeyType, ...]) -> None: ...
    def hold(self, keys: tuple[KeyType, ...]) -> None: ...
    def release(self, keys: tuple[KeyType, ...] = ()) -> None: ...
    def imu(self, *frames: IMUFrame) -> None: ...
    def keyboard(self, text: str) -> None: ...
    def type_key(self, key: KeyCode | SpecialKeyCode) -> None: ...
    def close(self) -> None: ...
```

`press()` は state に追加し、`hold()` は state を破棄して keys だけにし、`release(keys)` は state から除去する。`release()` と `close()` は button、stick、IMU を neutral に戻し、`session.neutral()` を呼ぶ。close 後の入力操作は `DeviceError(code="NYX_SWBT_PORT_CLOSED")` とする。port `close()` は transport/session を閉じない。

port 作成時は常に neutral を試みる。`reset_on_port_create` は settings に出さない。

touch、keyboard、sleep control は `NotImplementedError` とする。silent no-op にしない。

### factory

```python
class SwbtControllerOutputPortFactory:
    def create(self, *, config: SwbtControllerConfig, allow_dummy: bool, timeout_sec: float) -> ControllerOutputPort: ...
    def pair(self, config: SwbtControllerConfig, *, timeout_sec: float | None = None) -> None: ...
    def reconnect(self, config: SwbtControllerConfig, *, timeout_sec: float | None = None) -> None: ...
    def disconnect(self, config: SwbtControllerConfig) -> None: ...
    def status(self, config: SwbtControllerConfig) -> object | None: ...
    def close(self) -> None: ...
```

`create()` は session key から session を取得し、未接続なら `open()` + `reconnect()` する。`allow_dummy=True` の場合だけ、transport open / reconnect 失敗時に `DummySwbtControllerSession` へ fallback できる。production GUI は swbt の dummy fallback を許可しない。`pair()` と `reconnect()` は GUI / CLI の明示操作であり、dummy fallback しない。

同一物理 adapter は controller model や key store が違っても同時に開かない。別 session key で同じ adapter を使う場合は、既存 active port と session を先に閉じる。

`disconnect(config)` は同一 factory が管理する cached session だけを対象にする。対象 session があれば neutral を試みて close し、cache から削除する。対象 session がなければ no-op とする。別 process、OS 側状態、Switch 側状態までは保証しない。

`status(config)` は factory が管理する cached session の状態を返す。外部 adapter の live inquiry ではない。cached session がなければ `None` とする。

session key に含める値:

```text
model.controller_type
adapter
key_store_path
report_period_us
```

session key に含めない値:

```text
connect_timeout_sec
operation_timeout_sec
allow_dummy
diagnostics writer
reset_on_port_create
```

### エラーハンドリング

| 条件 | NyX 例外 |
|------|----------|
| transport open 失敗 | `ConfigurationError(code="NYX_SWBT_TRANSPORT_OPEN_FAILED")` |
| connection timeout | `ConfigurationError(code="NYX_SWBT_CONNECTION_TIMED_OUT")` |
| connection failed | `ConfigurationError(code="NYX_SWBT_CONNECTION_FAILED")` |
| invalid key store | `ConfigurationError(code="NYX_SWBT_KEY_STORE_INVALID")` |
| unsupported input | `DeviceError(code="NYX_SWBT_INPUT_UNSUPPORTED")` |
| invalid input | `DeviceError(code="NYX_SWBT_INPUT_INVALID")` |
| close 後の port 操作 | `DeviceError(code="NYX_SWBT_PORT_CLOSED")` |
| close 後の session apply | `DeviceError(code="NYX_SWBT_NOT_CONNECTED")` |

`NotImplementedError` は backend として存在しない API に使う。`DeviceError(code="NYX_SWBT_INPUT_UNSUPPORTED")` は controller type と入力の組み合わせが非対応の場合に使う。

### シングルトン管理

新規グローバル singleton は追加しない。factory instance が session cache を所有し、runtime builder または GUI app service が factory lifetime を所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_session_open_does_not_pair_or_reconnect` | `open()` が接続操作を開始しない |
| ユニット | `test_factory_create_reconnects_without_pairing` | `create()` が reconnect のみ行う |
| ユニット | `test_session_pair_reconnect_apply_status_and_close` | pair / reconnect / apply / status / close の同期 lifecycle |
| ユニット | `test_session_requires_adapter_before_open` | adapter 未選択時の session open 失敗 |
| ユニット | `test_dummy_session_records_state_without_bluetooth_transport` | dummy session が Bluetooth transport を開かず state を記録する |
| ユニット | `test_diagnostics_writer_logs_to_logger_port` | swbt diagnostics が technical log へ流れる |
| ユニット | `test_diagnostics_writer_can_tee_to_jsonl` | 実機 evidence 用 tee writer |
| ユニット | `test_mapper_maps_buttons_with_current_nyx_names` | `CAP` / `LS` / `RS` を swbt 名へ変換する |
| ユニット | `test_mapper_replaces_dpad_direction` | D-pad 方向切替が古い方向を解除する |
| ユニット | `test_mapper_converts_stick_xy_and_rejects_joycon_missing_stick` | stick 変換と Joy-Con capability |
| ユニット | `test_mapper_normalizes_imu_one_or_three_frames` | IMU frame 数の規則 |
| ユニット | `test_port_press_hold_release_apply_complete_state` | port 操作が完全 state を apply する |
| ユニット | `test_port_imu_and_release_all_use_neutral` | IMU と release all が neutral state を使う |
| ユニット | `test_port_close_sends_neutral_without_session_close` | port close は transport を閉じない |
| ユニット | `test_port_rejects_backend_unsupported_apis` | touch / keyboard / sleep control を silent no-op にしない |
| ユニット | `test_factory_reuses_session_for_same_key_and_ports_are_new` | 同じ key で session を共有し port は新規 |
| ユニット | `test_factory_allows_dummy_fallback_only_for_create` | dummy fallback が create だけに限定される |
| ユニット | `test_factory_pair_reconnect_disconnect_and_status_are_explicit_operations` | pair / reconnect / disconnect / status が明示操作として session へ渡る |
| ユニット | `test_factory_close_closes_cached_sessions` | factory close が cached session を閉じる |
| ユニット | `test_factory_preserves_primary_and_cleanup_errors` | primary 接続例外を先頭にして cleanup leaf を実行順で保持する |
| ユニット | `test_factory_create_recovers_active_port_then_preserves_reconnect_failure` | active port neutral 失敗後の session close 回復と次の primary error |
| ユニット | `test_session_close_preserves_controller_and_loop_stop_errors` | controller close、loop stop の順で error を保持する |
| ユニット | `test_factory_does_not_create_manual_session_type` | `SwbtManualInputSession` が存在しない |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/framework/hardware/swbt/test_session.py tests/unit/framework/hardware/swbt/test_diagnostics.py tests/unit/framework/hardware/swbt/test_mapper.py tests/unit/framework/hardware/swbt/test_controller.py tests/unit/framework/hardware/swbt/test_factory.py
uv run pytest tests/unit/framework/hardware/swbt tests/unit/framework/io/test_controller_config.py tests/unit/framework/io/test_ports.py tests/unit/framework/runtime/test_default_command_ports.py tests/unit/cli/test_swbt_cli.py tests/unit/cli/test_run_cli_parser.py tests/unit/framework/settings/test_settings_schema.py
uv run pytest tests/unit -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [x] `SwbtControllerSession` を実装し、open と pair/reconnect を分離する。
- [x] `start()` を追加せず、factory `create()` から `open()` + `reconnect()` を呼ぶ。
- [x] `swbt-python 0.2.0` の async 公開 API を event loop thread で完了待ちし、session の直列化と close retry を実装する。
- [x] swbt diagnostics writer を `LoggerPort` と JSONL evidence writer へ接続する adapter を実装する。
- [x] `DummySwbtControllerSession` を実装し、Bluetooth transport を開かず state を記録する。
- [x] `NyxSwbtState` と `NyxSwbtInputMapper` を実装する。
- [x] button、D-pad、stick、IMU、Joy-Con capability の mapper test を追加する。
- [x] `SwbtControllerOutputPort` を実装し、非対応入力を silent no-op にしない。
- [x] port close と release all で IMU を含め neutral に戻す。
- [x] port close が session を閉じないことを確認する。
- [x] `SwbtControllerOutputPortFactory` を実装し、session key と session cache を管理する。
- [x] `create()` が暗黙 pairing せず reconnect のみ行うことを確認する。
- [x] `pair()` / `reconnect()` / `disconnect()` / `status()` を明示 lifecycle 操作として実装する。
- [x] `pair()` / `reconnect()` が dummy fallback しないことを確認する。
- [x] `hardware/swbt/manual.py`、`SwbtManualInputSession`、`swbt_*.py` module がないことを静的に確認する。

## 7. 2026-07-10 監査追補

complete 移動後の統合監査で次を修正した。

- `GamepadStatus.connection_state` を接続状態の正本とし、remote disconnect 後に cached boolean を返さない。
- port の入力 state は `session.apply()` 成功後だけ確定し、送信失敗時は変更前 state を維持する。
- `InvalidInputError` を `NYX_SWBT_INPUT_INVALID` へ変換する。
- active port neutral が失敗しても session の `close(neutral=True)` を必ず試す。session close 成功時は終端 neutral 済みとして旧 port を無効化し、cache を削除する。
- session close または loop stop も失敗した場合だけ参照を残し、close を再試行可能にする。
- primary 接続例外と cleanup 例外は primary を先頭に、controller close と loop stop は実行順に `ExceptionGroup` へ格納し、元の error code を保持する。
- production composition root から `LoggerDiagnosticsWriter` を注入し、swbt diagnostics を technical log へ流す。

stick の座標変換は単体テストで確定したが、Switch 画面上の方向は実機未検証である。

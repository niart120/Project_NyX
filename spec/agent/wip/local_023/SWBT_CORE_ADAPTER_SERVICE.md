# swbt session / mapper / port / factory 仕様書

## 1. 概要

### 1.1 目的

`swbt-python` の async controller API を NyX の同期 `ControllerOutputPort` として扱う core 部品を追加する。対象は `SwbtControllerSession`、`NyxSwbtInputMapper`、`SwbtControllerOutputPort`、`SwbtControllerOutputPortFactory`、`DummySwbtControllerSession` である。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `SwbtControllerSession` | swbt controller instance、event loop thread、pair/reconnect、apply、neutral、close を所有する backend 内部部品 |
| `DummySwbtControllerSession` | 実機なしテストで `InputState` を記録する session double |
| `NyxSwbtState` | port が持つ現在入力状態。button、left stick、right stick、IMU frames を含む |
| `NyxSwbtInputMapper` | `NyxSwbtState` と NyX 入力を swbt `InputState` へ変換する mapper |
| `SwbtControllerOutputPort` | `ControllerOutputPort` を実装し、完全な `InputState` を session へ渡す port |
| `SwbtControllerOutputPortFactory` | config ごとの session cache を持ち、runtime / GUI lifetime port を生成する factory |
| session key | controller model、adapter、key store、report period、diagnostics path、operation timeout を含む cache key |

### 1.3 背景・問題

serial backend は同期 `send()` で入力を送れる。一方、swbt backend は async resource と report loop を持つため、`ControllerOutputPort` から直接 `swbt-python` の coroutine を呼べない。session が event loop thread と lifecycle を所有し、port は入力状態と mapper に集中する必要がある。

GUI manual input と macro runtime は同じ adapter を同時に開けない。factory は同じ session key の session を cache し、GUI と runtime が同じ接続を再利用できるようにする。ただし同じ port object は共有しない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt 接続 lifecycle | 未導入 | session が open/pair/reconnect/start/apply/neutral/close を所有する |
| 入力変換 | 未導入 | mapper が button、D-pad、stick、IMU を完全 state へ変換する |
| unsupported input | 未導入 | Joy-Con capability、touch、keyboard、sleep control を明確に失敗させる |
| macro runtime pairing | 未導入 | `create()` は reconnect のみ行い、暗黙 pairing しない |
| close | 未導入 | port close と session/factory close の両方で neutral を試みる |

### 1.5 着手条件

- `local_022` で `SwbtControllerConfig`、`SwbtControllerModel`、`IMUFrame`、adapter discovery、error mapping が実装済みである。
- `swbt-python>=0.2.0,<0.3.0` の root module public API だけを使う。
- `hardware/swbt/manual.py`、`SwbtManualInputSession`、`swbt_*.py` module は追加しない。
- CLI、GUI、runtime builder の接続は `local_024` と `local_025` に残す。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/hardware/swbt/session.py` | 新規 | `SwbtControllerSession`、`DummySwbtControllerSession`、event loop bridge、connection lifecycle を実装する |
| `src/nyxpy/framework/core/hardware/swbt/mapper.py` | 新規 | `NyxSwbtState`、`NyxSwbtInputMapper`、button / D-pad / stick / IMU mapping を実装する |
| `src/nyxpy/framework/core/hardware/swbt/controller.py` | 新規 | `SwbtControllerOutputPort` を実装する |
| `src/nyxpy/framework/core/hardware/swbt/factory.py` | 新規 | `SwbtControllerOutputPortFactory`、session cache、pair/reconnect/disconnect/status を実装する |
| `src/nyxpy/framework/core/hardware/swbt/errors.py` | 変更 | session / mapper / port のエラー code を追加する |
| `src/nyxpy/framework/core/hardware/swbt/__init__.py` | 変更 | core 部品を re-export する |
| `tests/unit/framework/hardware/swbt/test_session.py` | 新規 | fake swbt controller で session lifecycle を検証する |
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

`controller.py` は port contract、`mapper.py` は入力変換、`session.py` は async lifecycle、`factory.py` は session cache と pair/reconnect 操作を担当する。factory 以外が GUI state や runtime builder を知らない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `press` / `release` | port 内で完全 `InputState` を作り 1 回 `session.apply()` |
| session start | `open()` 後に reconnect のみ行う |
| dummy session | Bluetooth transport を開かない |
| close | port close は neutral、factory close は session close |

### 並行性・スレッド安全性

session は event loop thread と `RLock` を持ち、connection operation と input apply を直列化する。`Future.result()` を待つ間に不要な lock を保持し続けない。port は自身の `NyxSwbtState` を `RLock` で守る。

## 4. 実装仕様

### session

```python
class SwbtControllerSession:
    def open(self) -> None: ...
    def start(self, *, timeout_sec: float) -> None: ...
    def pair(self, *, timeout_sec: float) -> object: ...
    def reconnect(self, *, timeout_sec: float) -> object: ...
    def apply(self, state: object) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> object: ...
    def close(self) -> None: ...
```

`open()` は transport と report loop の準備だけを行い、pairing / reconnect を開始しない。`start()` は macro / GUI lifetime port 用であり、保存済み key store に基づく reconnect だけを行う。key store がない場合に pairing へ fallback しない。

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

`Hat` は D-pad button set に変換する。`Hat.CENTER` は D-pad 全解除である。`LStick` / `RStick` は現行の `x` / `y` `0..255` を swbt `Stick` の範囲へ変換する。Joy-Con L は right stick、Joy-Con R は left stick を拒否する。

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

`press()` は state に追加し、`hold()` は state を破棄して keys だけにし、`release(keys)` は state から除去する。`release()` と `close()` は button、stick、IMU を neutral に戻し、`session.neutral()` を呼ぶ。close 後の入力操作は `DeviceError(code="NYX_SWBT_PORT_CLOSED")` とする。

touch、keyboard、sleep control は `NotImplementedError` とする。silent no-op にしない。

### factory

```python
class SwbtControllerOutputPortFactory:
    def create(self, *, config: SwbtControllerConfig, allow_dummy: bool, timeout_sec: float) -> ControllerOutputPort: ...
    def pair(self, config: SwbtControllerConfig, *, timeout_sec: float | None = None) -> object: ...
    def reconnect(self, config: SwbtControllerConfig, *, timeout_sec: float | None = None) -> object: ...
    def disconnect(self, config: SwbtControllerConfig) -> None: ...
    def status(self, config: SwbtControllerConfig) -> object | None: ...
    def close(self) -> None: ...
```

`create()` は session key から session を取得し、未接続なら `session.start()` で reconnect する。`allow_dummy=True` の場合だけ、transport 失敗時に `DummySwbtControllerSession` を返せる。`pair()` と `reconnect()` は GUI / CLI の明示操作であり、macro run からは呼ばない。

session key に含める値:

```text
model.controller_type
adapter
key_store_path
report_period_us
diagnostics_path
operation_timeout_sec
```

接続試行ごとの `connect_timeout_sec` と `allow_dummy` は session key に含めない。

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

### シングルトン管理

新規グローバル singleton は追加しない。factory instance が session cache を所有し、runtime builder または GUI app service が factory lifetime を所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_session_open_does_not_pair_or_reconnect` | `open()` が接続操作を開始しない |
| ユニット | `test_session_start_reconnects_without_pairing` | `start()` が reconnect のみ行う |
| ユニット | `test_session_close_trails_neutral_and_stops_loop` | close 時に neutral と loop stop を行う |
| ユニット | `test_mapper_maps_buttons_with_current_nyx_names` | `CAP` / `LS` / `RS` を swbt 名へ変換する |
| ユニット | `test_mapper_replaces_dpad_direction` | D-pad 方向切替が古い方向を解除する |
| ユニット | `test_mapper_converts_stick_xy_and_rejects_joycon_missing_stick` | stick 変換と Joy-Con capability |
| ユニット | `test_mapper_normalizes_imu_one_or_three_frames` | IMU frame 数の規則 |
| ユニット | `test_port_press_hold_release_apply_complete_state` | port 操作が完全 state を apply する |
| ユニット | `test_port_close_sends_neutral_without_session_close` | port close は transport を閉じない |
| ユニット | `test_factory_reuses_session_for_same_key` | 同じ key で session を共有し port は新規 |
| ユニット | `test_factory_pair_reconnect_are_explicit_operations` | pair/reconnect が明示操作として session へ渡る |
| ユニット | `test_factory_does_not_create_manual_session_type` | `SwbtManualInputSession` が存在しない |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/framework/hardware/swbt/test_session.py tests/unit/framework/hardware/swbt/test_mapper.py tests/unit/framework/hardware/swbt/test_controller.py tests/unit/framework/hardware/swbt/test_factory.py
```

## 6. 実装チェックリスト

- [ ] `SwbtControllerSession` を実装し、open と pair/reconnect を分離する。
- [ ] session の event loop thread、operation timeout、close idempotency を実装する。
- [ ] `DummySwbtControllerSession` を実装し、Bluetooth transport を開かず state を記録する。
- [ ] `NyxSwbtState` と `NyxSwbtInputMapper` を実装する。
- [ ] button、D-pad、stick、IMU、Joy-Con capability の mapper test を追加する。
- [ ] `SwbtControllerOutputPort` を実装し、非対応入力を silent no-op にしない。
- [ ] port close と release all で IMU を含め neutral に戻す。
- [ ] `SwbtControllerOutputPortFactory` を実装し、session key と session cache を管理する。
- [ ] `create()` が暗黙 pairing せず reconnect のみ行うことを確認する。
- [ ] `pair()` / `reconnect()` / `disconnect()` / `status()` を明示 lifecycle 操作として実装する。
- [ ] `hardware/swbt/manual.py`、`SwbtManualInputSession`、`swbt_*.py` module がないことを静的に確認する。

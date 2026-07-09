# swbt GUI / shared service 仕様書

## 1. 概要

### 1.1 目的

GUI から `serial` / `swbt` controller backend を選択し、adapter refresh、controller type 選択、pair、reconnect、disconnect、status を操作できるようにする。manual input は既存 `VirtualControllerModel -> ControllerOutputPort` 経路を使い、macro runtime と同じ adapter を同時に開かないように制御する。capture backend / capture source と controller backend は独立して扱う。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| GUI lifetime port | GUI manual input 用に runtime builder から取得する `ControllerOutputPort` |
| manual input | GUI の仮想 controller から送る button、D-pad、stick、release all |
| adapter refresh | `SwbtAdapterDiscoveryService.list_adapters()` を呼び、候補を表示する操作 |
| pair | `SwbtControllerOutputPortFactory.pair(config)` による明示 pairing |
| reconnect | 保存済み key store による明示 reconnect |
| disconnect | factory が管理する cached session を閉じ、controller を `None` に戻す操作 |
| status | factory-managed cached session の状態を GUI 表示用 DTO に変換したもの |
| deferred settings apply | macro 実行中の capture / controller 設定変更を実行終了後へ遅延する処理 |

### 1.3 背景・問題

現行 GUI は serial controller を前提に runtime builder を作り、`VirtualControllerModel` へ controller port を差し込む。swbt backend でもこの経路を使えるが、pairing、reconnect、adapter refresh は入力送信とは別の lifecycle 操作である。GUI 専用の `SwbtManualInputSession` を作ると、既存 model と責務が二重化する。

swbt の GUI lifetime port と macro runtime port が同時に同じ adapter を使うと、USB transport と入力状態が競合する。macro start 前に manual port を解放し、runtime 終了後に自動 reconnect しない方針を明示する必要がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| backend 選択 | serial 固定 | GUI で `serial` / `swbt` を選択できる |
| adapter refresh | 未導入 | adapter 候補を列挙し、pair/reconnect を開始しない |
| manual input | serial port 前提 | `VirtualControllerModel` に swbt port を差し込む |
| macro 実行中 | manual input と runtime の排他なし | manual input、pair、reconnect、disconnect を無効化する |
| capture/controller settings | builder 一括更新になり得る | capture と controller の変更を独立して反映する |
| GUI scope | 未定義 | diagnostics editor、controller color editor、IMU editor、CLI copy は置かない |

### 1.5 着手条件

- `local_024` で backend-aware runtime builder と swbt CLI が実装済みである。
- `local_023` で `SwbtControllerOutputPortFactory` が pair/reconnect/disconnect/status を提供している。
- GUI は `swbt-python` を直接 import しない。
- 実機検証は `local_026` に残し、本仕様では fake factory / dummy session で検証する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/gui/app_services.py` | 変更 | controller backend 設定を runtime builder 更新対象に含め、swbt discovery / pair / reconnect / disconnect / status を提供する |
| `src/nyxpy/gui/main_window.py` | 変更 | 接続メニュー、状態表示、macro start 前の manual port release/close、capture/controller 独立 deferred apply を制御する |
| `src/nyxpy/gui/models/virtual_controller_model.py` | 変更 | manual input enabled 状態と `set_controller(None)` 時の no-op 挙動を整理する |
| `src/nyxpy/gui/panes/virtual_controller_pane.py` | 変更 | manual input disabled 状態を widget 有効状態へ反映する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | backend selector、controller type、adapter combo、refresh、key store path、pair/reconnect/disconnect/status を追加する |
| `tests/gui/test_app_services.py` | 変更 | swbt discovery / lifecycle service API と capture/controller 独立反映を検証する |
| `tests/gui/test_device_settings_tab.py` | 変更 | swbt settings UI の表示、有効/無効、保存を検証する |
| `tests/gui/test_main_window.py` | 変更 | pair/reconnect/disconnect、macro start 前 close、runtime 終了後の非 reconnect を検証する |
| `tests/gui/test_virtual_controller_model.py` | 変更 | controller `None`、manual disabled、release all の挙動を検証する |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | GUI lifetime port を builder 間で移す時に旧 factory shutdown callback が走らないことを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

GUI は `nyxpy.framework.*` を利用する上位層である。`GuiAppServices` が settings を `ControllerConfig` へ正規化し、runtime builder と `SwbtControllerOutputPortFactory` へ委譲する。Widget 層は swbt の `InputState`、`GamepadStatus`、controller class を扱わない。

### 公開 API 方針

マクロ API は変更しない。GUI 内部 API として `GuiAppServices.refresh_swbt_adapters()`、`pair_swbt()`、`reconnect_swbt()`、`disconnect_swbt()`、`swbt_status()` を追加する。

### 後方互換性

既存 serial 設定の旧 flat key は維持しない。GUI 保存時は `controller.*` schema へ寄せる。serial backend 選択時だけ serial device / protocol / baudrate UI を有効にする。

### レイヤー構成

adapter refresh は `SwbtAdapterDiscoveryService.list_adapters()` を呼ぶ。GUI から `swbt-probe` subprocess を呼ばない。pair/reconnect/disconnect/status は factory の lifecycle method へ委譲する。manual input は `VirtualControllerModel` の既存 method から `ControllerOutputPort` を呼ぶ。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| adapter refresh | GUI main thread を 100ms 以上止めない |
| pair/reconnect/disconnect | swbt 0.2.0 の public API は同期 API。local_025 では GUI service 経由で同期呼び出しし、実機時の応答性評価は `local_026` に残す |
| macro start 前 close | manual port release/close を 1 回行い、失敗時は runtime start を止める |
| runtime 終了後 | 自動 reconnect しない |
| controller backend 変更 | preview frame source を不要に再作成しない |
| capture settings 変更 | manual controller port を不要に再作成しない |

### 並行性・スレッド安全性

Qt widget 更新は main thread で行う。swbt lifecycle 操作は `GuiAppServices` の同期 API へ委譲する。macro 実行中は manual input、pair、reconnect、disconnect、backend 切替を無効化する。内部的に設定反映が入った場合は deferred として扱う。

## 4. 実装仕様

### GUI service API

```python
@dataclass(frozen=True, slots=True)
class SwbtControllerStatusView:
    connected: bool
    controller_type: str
    adapter: str
    message: str


class GuiAppServices:
    def refresh_swbt_adapters(self) -> tuple[SwbtAdapterView, ...]: ...
    def pair_swbt(self) -> SwbtControllerStatusView: ...
    def reconnect_swbt(self) -> SwbtControllerStatusView: ...
    def disconnect_swbt(self) -> None: ...
    def swbt_status(self) -> SwbtControllerStatusView | None: ...
```

`SwbtControllerStatusView` は GUI 表示用 DTO である。`swbt.GamepadStatus` を widget 層へ返さない。`swbt_status()` は factory-managed cached session の状態だけを表示する。外部 process や Switch 側状態の live inquiry ではない。

### GUI 項目

| 項目 | 必須 | 内容 |
|------|------|------|
| backend selector | yes | `serial` / `swbt` |
| controller type | yes | Pro Controller / Joy-Con L / Joy-Con R |
| adapter combo | yes | discovery 結果。表示は `display_name`、保存値は `name` |
| refresh adapters | yes | adapter 列挙のみ |
| key store path | yes | pairing key JSON |
| pair button | yes | 明示 pairing |
| reconnect button | yes | 保存済み key reconnect |
| disconnect button | yes | factory-managed cached session を close |
| connection status | yes | disconnected / pairing / connected / error |

GUI に置かない項目:

- CLI command preview
- clipboard copy
- diagnostics editor
- diagnostics folder open button
- controller color editor
- auto pairing suggestion
- IMU preset / pose / raw editor
- IMU recorder / replay

### 操作仕様

| 操作 | 入力条件 | 成功時 | 失敗時 |
|------|----------|--------|--------|
| Refresh adapters | macro 未実行中 | combo を更新。settings は変更しない | status bar と technical log に表示 |
| Pair | backend `swbt`、adapter、controller type、key store が有効 | status connected、manual port を注入 | controller `None`、error 表示 |
| Reconnect | backend `swbt`、key store が存在 | status connected、manual port を注入 | controller `None`、error 表示 |
| Disconnect | connected | factory-managed session close 後、controller `None` | error log、controller `None` |
| Macro run start | pair/reconnect 中でない | manual port を閉じて runtime start | close 失敗なら実行を止める |

### manual input

`VirtualControllerModel.set_controller(...)` は controller 参照の差し替えだけを行う。release / close は行わない。controller が `None` のとき manual input は no-op にする。接続済み port が error を返した場合は silent no-op にせず technical log と user-visible error を出し、必要に応じて controller を `None` に戻す。

macro start 前の処理:

```text
previous = virtual_controller.model.controller
virtual_controller.model.set_controller(None)
previous.release()
previous.close()
runtime start
```

`release()` / `close()` に失敗した場合は runtime start を止める。runtime 終了後は自動 reconnect しない。利用者が reconnect を押したときだけ GUI lifetime port を再作成する。

### settings 反映

controller backend、controller type、adapter、key store、report period、connect timeout が変わった場合、controller factory / manual controller port を更新する。capture source / backend が変わった場合、preview frame source を更新する。両者は独立して扱う。

macro 実行中は controller change と capture change を別々に deferred とし、実行完了後に必要な port だけ反映する。

### エラーハンドリング

| 条件 | 表示 |
|------|------|
| adapter discovery 失敗 | adapter refresh failed |
| adapter 未選択 | adapter を選択させる |
| key store 不正 | key store path を確認させる |
| pair/reconnect timeout | Switch 側の pairing / reconnect 操作を確認させる |
| unsupported input | 選択 controller type では入力不可と表示 |
| macro 実行中の操作 | UI disabled。内部呼び出しは deferred または明示エラー |

### シングルトン管理

新規グローバル singleton は追加しない。`GuiAppServices` が runtime builder と swbt factory lifetime を所有し、アプリ終了時に close する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI | `test_device_tab_switches_serial_and_swbt_fields` | backend に応じて設定欄が切り替わる |
| GUI | `test_device_tab_uses_supported_controller_models_for_choices` | controller type choices が model registry 由来 |
| GUI | `test_refresh_adapters_does_not_pair_or_reconnect` | fake discovery だけが呼ばれ、settings を変更しない |
| GUI | `test_app_services_refresh_swbt_adapters_uses_discovery_only` | service API が adapter discovery だけを呼ぶ |
| GUI | `test_app_services_pair_swbt_returns_gui_status_view` | factory status を GUI DTO に変換する |
| GUI | `test_pair_success_sets_manual_controller` | pair 成功後に `VirtualControllerModel.set_controller(port)` |
| GUI | `test_reconnect_success_sets_manual_controller` | reconnect 成功後に manual port を注入 |
| GUI | `test_disconnect_releases_and_clears_manual_controller` | disconnect で `release()` / `close()` / `None` |
| GUI | `test_macro_start_closes_manual_port_before_runtime` | macro start 前に GUI lifetime port を閉じる |
| GUI | `test_swbt_lifecycle_rejected_while_macro_running` | macro 実行中に swbt lifecycle 操作を止める |
| GUI | `test_runtime_finish_does_not_auto_reconnect` | 実行後に自動 reconnect しない |
| GUI | `test_apply_settings_updates_ports_without_pause_when_capture_unchanged` | controller 変更だけでは preview を再設定しない |
| GUI | `test_apply_settings_pauses_only_for_active_capture_change` | capture 変更だけでは manual controller を再設定しない |
| GUI | `test_deferred_apply_tracks_capture_and_controller_separately` | macro 実行中の deferred apply 粒度 |
| Unit | `test_runtime_builder_can_transfer_manual_controller_without_closing_factory` | manual controller 維持時に旧 controller factory callback が走らない |
| Unit | `test_runtime_builder_can_transfer_preview_source_without_closing_factory` | preview 維持時に旧 frame factory callback が走らない |
| 静的 | `test_gui_does_not_import_swbt_python` | GUI module が `swbt` を direct import しない |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/gui/ -m "not realdevice and not swbt"
uv run pytest tests/unit/framework/runtime/test_runtime_builder.py -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [x] GUI settings に backend selector、controller type、adapter、key store、pair/reconnect/disconnect/status を追加する。
- [x] adapter refresh が `SwbtAdapterDiscoveryService` だけを呼び、settings を変更しないようにする。
- [x] GUI に diagnostics editor、controller color editor、IMU editor、CLI copy を追加しない。
- [x] `GuiAppServices` が swbt factory lifecycle を所有する。
- [x] Pair / Reconnect 成功後に GUI lifetime port を `VirtualControllerModel` へ注入する。
- [x] Disconnect で manual port と factory-managed session を閉じ、controller を `None` に戻す。
- [x] `VirtualControllerModel.set_controller(...)` が release / close しないことを確認する。
- [x] macro start 前に manual port を退避してから model から外し、`release()` / `close()` する。
- [x] macro 実行中は manual input と swbt lifecycle 操作を無効化する。
- [x] runtime 終了後に自動 reconnect しない。
- [x] capture backend / capture source と controller backend の変更を独立して反映する。
- [x] GUI module が `swbt-python` を直接 import しないことを確認する。

## 7. 実装結果

- GUI settings に controller backend selector、swbt controller type、adapter combo、refresh、key store path、pair/reconnect/disconnect/status を追加した。保存先は `controller.*` schema に統一し、旧 flat serial key は使わない。
- `GuiAppServices` が `SwbtAdapterDiscoveryService` と `SwbtControllerOutputPortFactory` を所有し、GUI DTO `SwbtControllerStatusView` を返す API を提供する。
- `MainWindow` は pair/reconnect 成功後に runtime builder から GUI lifetime port を取得して `VirtualControllerModel` へ注入する。disconnect と macro start では既存 manual port を model から外してから `release()` / `close()` する。
- macro 実行中は manual input を無効化し、runtime 終了後も自動 reconnect しない。
- capture 変更と controller 変更の反映粒度を分け、変更していない lifetime port は builder 入れ替え時に新 builder へ移す。

検証:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src\nyxpy --output-format concise --no-progress
uv run pytest tests\unit\framework\runtime\test_runtime_builder.py tests\gui\test_app_services.py tests\gui\test_main_window.py -m "not realdevice and not swbt"
uv run pytest tests\gui -m "not realdevice and not swbt"
```

結果:

- `ruff format`: 実行済み
- `ruff check`: All checks passed
- `ty check`: All checks passed
- `pytest tests\unit\framework\runtime\test_runtime_builder.py tests\gui\test_app_services.py tests\gui\test_main_window.py -m "not realdevice and not swbt"`: 110 passed
- `pytest tests\gui -m "not realdevice and not swbt"`: 193 passed

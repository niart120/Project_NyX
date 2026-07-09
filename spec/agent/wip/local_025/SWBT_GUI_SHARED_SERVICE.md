# swbt GUI / shared service 仕様書

## 1. 概要

### 1.1 目的

GUI から `serial` / `swbt` controller backend を選択し、adapter refresh、controller type 選択、pair、reconnect、disconnect を操作できるようにする。manual input は既存 `VirtualControllerModel -> ControllerOutputPort` 経路を使い、macro runtime と同じ adapter を同時に開かないように制御する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| GUI lifetime port | GUI manual input 用に runtime builder から取得する `ControllerOutputPort` |
| manual input | GUI の仮想 controller から送る button、D-pad、stick、release all |
| adapter refresh | `SwbtAdapterDiscoveryService.list_adapters()` を呼び、候補を表示する操作 |
| pair | `SwbtControllerOutputPortFactory.pair(config)` による明示 pairing |
| reconnect | 保存済み key store による明示 reconnect |
| disconnect | GUI lifetime port と swbt session を閉じ、controller を `None` に戻す操作 |
| deferred settings apply | macro 実行中の backend / adapter 変更を実行終了後へ遅延する処理 |

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
| `src/nyxpy/gui/main_window.py` | 変更 | 接続メニュー、状態表示、macro start 前の manual port release/close、deferred apply を制御する |
| `src/nyxpy/gui/models/virtual_controller_model.py` | 変更 | manual input enabled 状態と `set_controller(None)` 時の neutral 処理を整理する |
| `src/nyxpy/gui/panes/virtual_controller_pane.py` | 変更 | manual input disabled 状態を widget 有効状態へ反映する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | backend selector、controller type、adapter combo、refresh、key store path、pair/reconnect/disconnect/status を追加する |
| `tests/gui/test_swbt_gui_shared_service.py` | 新規 | app service、main window、virtual controller の swbt 経路を検証する |
| `tests/gui/test_settings_tabs.py` | 変更 | swbt settings UI の表示、有効/無効、保存を検証する |
| `tests/gui/test_virtual_controller_model.py` | 変更 | controller `None`、manual disabled、release all の挙動を検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

GUI は `nyxpy.framework.*` を利用する上位層である。`GuiAppServices` が settings を `ControllerConfig` へ正規化し、runtime builder と `SwbtControllerOutputPortFactory` へ委譲する。Widget 層は swbt の `InputState`、`GamepadStatus`、controller class を扱わない。

### 公開 API 方針

マクロ API は変更しない。GUI 内部 API として `GuiAppServices.refresh_swbt_adapters()`、`pair_swbt()`、`reconnect_swbt()`、`disconnect_swbt()`、`swbt_status()` を追加する。

### 後方互換性

既存 serial 設定は読み続ける。GUI 保存時は `controller.*` schema へ寄せるが、旧名 alias API は追加しない。serial backend 選択時だけ serial device / protocol / baudrate UI を有効にする。

### レイヤー構成

adapter refresh は `SwbtAdapterDiscoveryService.list_adapters()` を呼ぶ。GUI から `swbt-probe` subprocess を呼ばない。pair/reconnect/disconnect は factory の lifecycle method へ委譲する。manual input は `VirtualControllerModel` の既存 method から `ControllerOutputPort` を呼ぶ。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| adapter refresh | GUI main thread を 100ms 以上止めない |
| pair/reconnect/disconnect | worker thread または既存非同期実行基盤で UI を固めない |
| macro start 前 close | manual port release/close を 1 回行い、失敗時は runtime start を止める |
| runtime 終了後 | 自動 reconnect しない |

### 並行性・スレッド安全性

Qt widget 更新は main thread で行う。swbt lifecycle 操作は worker に逃がし、完了後に signal / callback で UI へ戻す。macro 実行中は manual input、pair、reconnect、disconnect、backend 切替を無効化する。内部的に設定反映が入った場合は deferred として扱う。

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

`SwbtControllerStatusView` は GUI 表示用 DTO である。`swbt.GamepadStatus` を widget 層へ返さない。

### GUI 項目

| 項目 | 必須 | 内容 |
|------|------|------|
| backend selector | yes | `serial` / `swbt` |
| controller type | yes | Pro Controller / Joy-Con L / Joy-Con R |
| adapter combo | yes | discovery 結果 |
| refresh adapters | yes | adapter 列挙のみ |
| key store path | yes | pairing key JSON |
| pair button | yes | 明示 pairing |
| reconnect button | yes | 保存済み key reconnect |
| disconnect button | yes | GUI lifetime port と session を close |
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
| Refresh adapters | macro 未実行中 | combo を更新 | status bar と technical log に表示 |
| Pair | backend `swbt`、adapter、controller type、key store が有効 | status connected、manual port を注入 | controller `None`、error 表示 |
| Reconnect | backend `swbt`、key store が存在 | status connected、manual port を注入 | controller `None`、error 表示 |
| Disconnect | connected | `release()` / `close()` 後、controller `None` | error log、controller `None` |
| Macro run start | pair/reconnect 中でない | manual port を閉じて runtime start | close 失敗なら実行を止める |

### manual input

`VirtualControllerModel` は controller が `None` のとき no-op にする。接続済み port が error を返した場合は silent no-op にせず technical log と user-visible error を出し、必要に応じて controller を `None` に戻す。

macro start 前の処理:

```text
virtual_controller.model.set_controller(None)
previous_manual_port.release()
previous_manual_port.close()
runtime start
```

runtime 終了後は自動 reconnect しない。利用者が reconnect を押したときだけ GUI lifetime port を再作成する。

### settings 反映

controller backend、controller type、adapter、key store、report period、diagnostics path、operation timeout が変わった場合、旧 runtime builder を shutdown し、新しい builder を作る。macro 実行中は変更を deferred とし、実行完了後に反映する。

### エラーハンドリング

| 条件 | 表示 |
|------|------|
| swbt extra 未導入 | swbt extra の導入手順を促す |
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
| GUI | `test_refresh_adapters_does_not_pair_or_reconnect` | fake discovery だけが呼ばれる |
| GUI | `test_pair_success_sets_manual_controller` | pair 成功後に `VirtualControllerModel.set_controller(port)` |
| GUI | `test_reconnect_success_sets_manual_controller` | reconnect 成功後に manual port を注入 |
| GUI | `test_disconnect_releases_and_clears_manual_controller` | disconnect で `release()` / `close()` / `None` |
| GUI | `test_macro_start_closes_manual_port_before_runtime` | macro start 前に GUI lifetime port を閉じる |
| GUI | `test_macro_running_disables_swbt_actions` | macro 実行中に manual input と lifecycle 操作を止める |
| GUI | `test_runtime_finish_does_not_auto_reconnect` | 実行後に自動 reconnect しない |
| 静的 | `test_gui_does_not_import_swbt_python` | GUI module が `swbt` を direct import しない |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/gui/ -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [ ] GUI settings に backend selector、controller type、adapter、key store、pair/reconnect/disconnect/status を追加する。
- [ ] adapter refresh が `SwbtAdapterDiscoveryService` だけを呼ぶようにする。
- [ ] GUI に diagnostics editor、controller color editor、IMU editor、CLI copy を追加しない。
- [ ] `GuiAppServices` が swbt factory lifecycle を所有する。
- [ ] Pair / Reconnect 成功後に GUI lifetime port を `VirtualControllerModel` へ注入する。
- [ ] Disconnect で manual port と session を閉じ、controller を `None` に戻す。
- [ ] macro start 前に manual port を `release()` / `close()` する。
- [ ] macro 実行中は manual input と swbt lifecycle 操作を無効化する。
- [ ] runtime 終了後に自動 reconnect しない。
- [ ] GUI module が `swbt-python` を直接 import しないことを確認する。

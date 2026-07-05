# swbt GUI / shared service 仕様書

> **対象モジュール**: `src/nyxpy/gui/`, `src/nyxpy/framework/core/runtime/`, `src/nyxpy/framework/core/io/`
> **目的**: GUI から `serial` / `swbt` controller backend を選択し、GUI manual input と macro runtime が同じ `SwbtGamepadService` 接続を共有する。
> **親計画**: `spec/agent/wip/local_021/SWBT_CONTROLLER_BACKEND.md`
> **関連ドキュメント**: `docs/architecture/swbt-integration/runtime-composition.md`, `docs/architecture/swbt-integration/configuration-cli-gui.md`, `docs/architecture/swbt-integration/controller-port-contract.md`, `docs/architecture/swbt-integration/testing-rollout.md`
> **破壊的変更**: GUI 内部の controller 設定構成を backend 選択式へ変える。既存 serial 設定は `controller.serial.*` へ正規化して読み続ける。

## 1. 概要

### 1.1 目的

GUI の controller 出力を serial 固定から backend 選択式へ変更する。swbt backend では、設定画面、接続メニュー、manual input、macro runtime が同じ `SwbtControllerOutputPortFactory` と `SwbtGamepadService` を使い、runtime 開始のたびに Bluetooth 接続を作り直さない。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| controller backend | GUI と runtime が使う controller 出力方式。`serial` または `swbt` |
| `SwbtGamepadService` | `swbt-python` の `SwitchGamepad` lifecycle と非同期処理を NyX の同期 GUI/runtime へ接続する service |
| `SwbtControllerOutputPortFactory` | `SwbtGamepadService` を所有し、manual input 用 port と runtime 用 port を生成する factory |
| manual input | GUI の仮想 controller から直接 `ControllerOutputPort` へ送る入力 |
| runtime input | `MacroRuntime` が `ExecutionContext.controller` 経由で送る入力 |
| adapter refresh | GUI が `swbt-probe adapters --json` を subprocess として実行し、候補 adapter を表示する操作 |
| pair once | GUI 操作 1 回に限って `allow_pairing=True` で接続を試みる操作 |
| reconnect | 保存済み key store を使い、`allow_pairing=False` で接続を試みる操作 |
| disconnect | GUI が共有 service の transport を明示的に閉じる操作 |
| diagnostics path | `swbt-python` diagnostics trace の出力先。service lifetime に紐づく |

### 1.3 背景・問題

現行 GUI の `GuiAppServices._replace_runtime_builder()` は `ProtocolFactory.create_protocol()` と `ControllerOutputPortFactory` を常に作成し、serial controller を前提に `create_device_runtime_builder()` へ渡している。`VirtualControllerModel` は macro 実行状態を知らないため、manual input と runtime が同時に controller port を更新できる。

swbt backend では Bluetooth 接続、pairing、reconnect、diagnostics trace が service lifetime を持つ。GUI と runtime で別 service を作ると、manual input で接続済みでも macro 開始時に再接続が走り、backend 切り替え時の close 責務も曖昧になる。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| GUI controller backend | serial 固定 | `serial` / `swbt` を設定と接続メニューから選択できる |
| macro 開始時の swbt 接続 | backend 未導入 | 既存 service が接続済みなら再接続しない |
| manual input と runtime の同時更新 | GUI 側に明示制御なし | macro 実行中は manual input を無効化する |
| adapter 確認 | GUI から確認不可 | `swbt-probe adapters --json` の結果を 5 秒以内に表示する |
| backend 切り替え時の旧接続 | serial 前提の builder shutdown | runtime builder 再生成時に旧 factory を close し、transport を閉じる |
| diagnostics trace | GUI 方針未定 | 初期値は無効。path 設定時だけ service に渡す |

### 1.5 着手条件

- `local_022` foundation により `controller.*` settings schema と既存 serial 設定の正規化が実装済みである。
- `local_023` core により `SwbtGamepadService`、`SwbtControllerOutputPortFactory`、`SwbtControllerConfig`、swbt 例外変換が実装済みである。
- `local_024` runtime/CLI により backend-aware な runtime builder 構成と factory lifetime が利用できる。
- swbt backend で `SerialProtocolInterface` と `ProtocolFactory` を使わない構成が既存テストで確認済みである。
- GUI 着手前に `uv run pytest tests/unit/ tests/integration/ -m "not realdevice and not swbt"` が通る状態である。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/gui/app_services.py` | 変更 | controller backend 設定を runtime builder 更新対象に含め、backend-aware factory を保持し、swbt の pair once / reconnect / disconnect / status 操作を提供する |
| `src/nyxpy/gui/main_window.py` | 変更 | 接続メニューと状態表示を controller backend 対応にし、macro 実行中の manual input 無効化と backend 切り替え後の builder 再生成を制御する |
| `src/nyxpy/gui/models/virtual_controller_model.py` | 変更 | manual input の有効/無効状態を持ち、無効化時に controller を neutral へ戻す |
| `src/nyxpy/gui/panes/virtual_controller_pane.py` | 変更 | 仮想 controller widget 群の有効状態を `VirtualControllerModel` と同期する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | controller backend 選択、serial 設定、swbt 設定、adapter refresh、diagnostics path 入力を追加する |
| `src/nyxpy/gui/swbt_probe.py` | 新規 | `swbt-probe adapters --json` の subprocess 実行、JSON parse、GUI 表示用 result 変換を行う |
| `tests/gui/test_swbt_gui_shared_service.py` | 新規 | GUI service lifetime、manual input guard、settings dialog、adapter refresh の GUI 側仕様を検証する |
| `tests/gui/test_swbt_probe.py` | 新規 | `swbt_probe.py` の subprocess result parse と error handling を検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

GUI は controller backend の composition root として動作する。`GuiAppServices` が `GlobalSettings` / `SecretsSettings` を読み、`SwbtControllerConfig` または `SerialControllerConfig` へ正規化された結果を runtime builder へ渡す。

`SwbtGamepadService` の lifetime は `SwbtControllerOutputPortFactory` が所有する。GUI は service を直接生成せず、factory または factory が公開する high-level operation へ pair once / reconnect / disconnect を委譲する。

### 公開 API 方針

マクロ向け `Command` API は変更しない。GUI 内部 API として、`GuiAppServices` に swbt 操作用メソッドを追加する。これらは GUI から呼ぶための application service API であり、framework core の公開 API にはしない。

`VirtualControllerModel` には `set_manual_input_enabled()` を追加する。manual input 無効時は UI 操作を無視し、既存 controller port がある場合は `release()` または `close()` 相当ではなく `release(())` で neutral を試みる。

### 後方互換性

GUI の既存 serial 利用者は `serial_device` / `serial_baud` / `serial_protocol` を読み続けられる。設定保存時は新 schema へ寄せるが、旧設定名の alias API や互換 import は追加しない。

接続メニューの「シリアルデバイス」と「プロトコル」は controller backend が serial のときだけ有効にする。swbt 選択時に serial 設定を消さず、再度 serial へ戻したときに前回値を使えるようにする。

### レイヤー構成

`src/nyxpy/gui/` は `nyxpy.framework.*` を利用する。`src/nyxpy/framework/` は GUI を import しない。`swbt-python` の直接 import は `local_023` core の `hardware/swbt_service.py` と `io/swbt_adapter.py` 周辺に閉じる。

adapter refresh は `swbt-probe` subprocess 呼び出しから始める。GUI helper は `swbt` Python package を import せず、command not found、非ゼロ終了、JSON parse 失敗を GUI 表示用 error に変換する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| adapter refresh timeout | 既定 5.0 秒 |
| GUI 操作の main thread blocking | adapter refresh、pair once、reconnect、disconnect は UI を 100 ms 以上固めない |
| macro 実行中の manual input | 実行開始から終了まで入力 command を送らない |
| backend 切り替え時の close | 旧 builder shutdown を 1 回実行し、旧 factory close を取りこぼさない |
| diagnostics path 変更 | service key 変更として扱い、builder を再生成する |

### 並行性・スレッド安全性

Qt の UI 更新は main thread で行う。`swbt-probe` subprocess、pair once、reconnect、disconnect は worker thread または非同期 task に逃がし、完了後に signal で UI へ戻す。

manual input と runtime input は同じ service を共有するが、同時操作は許可しない。`MainWindow._start_macro()` が成功した時点で `VirtualControllerModel.set_manual_input_enabled(False)` を呼び、`_poll_run_handle()` または start failure の後に有効へ戻す。runtime 用 port は `SwbtControllerOutputPortFactory.create()` の責務として neutral から始める。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SwbtAdapterInfo:
    identifier: str
    label: str


@dataclass(frozen=True)
class SwbtAdapterRefreshResult:
    adapters: tuple[SwbtAdapterInfo, ...]
    bumble_version: str
    platform: str
    python_version: str
    opens_adapter: bool


@dataclass(frozen=True)
class SwbtControllerStatus:
    connected: bool
    adapter: str
    message: str


@dataclass(frozen=True)
class SwbtConnectionActionResult:
    backend: str
    status: SwbtControllerStatus | None
    message: str


class GuiAppServices:
    def refresh_swbt_adapters(self, *, timeout_sec: float = 5.0) -> SwbtAdapterRefreshResult: ...
    def pair_swbt_once(self) -> SwbtConnectionActionResult: ...
    def reconnect_swbt(self) -> SwbtConnectionActionResult: ...
    def disconnect_swbt(self) -> SwbtConnectionActionResult: ...
    def swbt_status(self) -> SwbtControllerStatus | None: ...


class VirtualControllerModel(QObject):
    def set_manual_input_enabled(self, enabled: bool) -> None: ...
    def manual_input_enabled(self) -> bool: ...
```

`swbt_probe.py` は `swbt-probe adapters --json` の出力を次の payload として扱う。

```json
{
  "bumble_version": "0.0.230",
  "candidate_adapters": ["usb:0"],
  "opens_adapter": false,
  "platform": "Windows-...",
  "python_version": "3.12.0",
  "status": "adapter listing does not open hardware"
}
```

`candidate_adapters` の各要素を `SwbtAdapterInfo(identifier=value, label=value)` に変換する。`opens_adapter` が `false` でない場合は、GUI からの adapter refresh としては失敗扱いにする。

GUI は `swbt-python` の `GamepadStatus` を直接 import しない。`SwbtGamepadService` または factory が返す `GamepadStatus` 相当の object は `GuiAppServices` 内で GUI 表示用の `SwbtControllerStatus` へ変換し、widget 層は `connected`、`adapter`、`message` だけを扱う。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `controller.backend` | `str` | `"serial"` | GUI と runtime の controller backend。`serial` または `swbt` |
| `controller.serial.device` | `str | None` | `None` | serial backend の device identifier |
| `controller.serial.protocol` | `str` | `"CH552"` | serial backend の protocol |
| `controller.serial.baudrate` | `int` | `9600` | serial backend の baudrate |
| `controller.swbt.adapter` | `str` | `"usb:0"` | `swbt-probe adapters --json` で表示する candidate adapter |
| `controller.swbt.key_store_path` | `str | None` | `".nyxpy/swbt/switch-bond.json"` | swbt bond 情報の保存先 |
| `controller.swbt.connect_timeout_sec` | `float` | `30.0` | pair once / reconnect の timeout 秒 |
| `controller.swbt.allow_pairing` | `bool` | `False` | 通常 runtime 起動時の pairing 許可。GUI の pair once 操作後も設定値は `False` に戻す |
| `controller.swbt.diagnostics_path` | `str | None` | `None` | GUI 初期実装では未指定なら diagnostics trace を出さない |
| `controller.swbt.invert_stick_y` | `bool` | `False` | stick Y 軸反転。実機検証で既定変更が必要なら `local_026` で判断する |

### GUI 操作仕様

| 操作 | 入力条件 | 処理 | 失敗時の表示 |
|------|----------|------|--------------|
| backend 選択 | macro 未実行中 | `controller.backend` を保存し、runtime builder を再生成する | builder 再生成失敗を status bar と technical log に出す |
| adapter refresh | swbt extra が導入済み | `swbt-probe adapters --json` を subprocess 実行し、候補を combo box へ反映する | command not found、非ゼロ終了、JSON 不正を設定画面内に表示する |
| pair once | backend が `swbt`、macro 未実行中 | 現在 config で `allow_pairing=True` の接続試行を 1 回だけ行う | pairing timeout、adapter open 失敗、key store 不正を表示する |
| reconnect | backend が `swbt`、macro 未実行中 | 現在 config で `allow_pairing=False` の接続試行を行う | bond 不足、timeout、adapter open 失敗を表示する |
| disconnect | backend が `swbt`、macro 未実行中 | shared service を close し、manual controller を外す | close error を表示し、builder 状態は再生成対象にする |
| manual input | macro 未実行中、manual controller 接続済み | `VirtualControllerModel` から current controller port へ送信する | port error を existing technical log へ出す |

### builder / service lifetime

`GuiAppServices` は現在の runtime builder と、そこへ渡した controller factory への参照を保持する。backend 設定、swbt adapter、key store、report period、device name、diagnostics path、`connect_on_open` が変わった場合は builder を再生成し、旧 builder の `shutdown()` で旧 factory を close する。

runtime builder から取得する manual controller と、macro runtime 用に build される controller は別 port でよい。どちらも同じ factory が所有する service を使う。manual controller を close しても transport は閉じず、backend 切り替え、disconnect、アプリ終了で factory close が走ったときだけ transport を閉じる。

### manual input guard

`VirtualControllerModel` は `manual_input_enabled=False` の間、button、D-pad、stick、touch の送信を行わない。無効化時に押下済み状態があれば `release(())` を 1 回試み、GUI 内部状態を neutral へ戻して `stateChanged` を emit する。

`MainWindow` は macro 開始成功後に manual input を無効化する。macro start が失敗した場合は無効化しない。macro 完了、cancel 完了、result 取得失敗、retry dialog の前で manual input を有効へ戻す。

通常の UI 操作では、macro 実行中に backend 選択、pair once、reconnect、disconnect を押せないようにする。テストや内部呼び出しで実行中に設定反映が入った場合は、現行 `GuiAppServices.apply_settings(is_run_active=True)` と同じく deferred として扱い、実行完了後に builder を再生成する。

### diagnostics path の GUI 初期扱い

GUI の初期値は `controller.swbt.diagnostics_path=None` とする。固定 path を自動生成しない。理由は、`SwbtGamepadService` が runtime artifact store に依存せず、diagnostics path が service key に含まれるためである。

ユーザが diagnostics path を設定した場合だけ service config へ渡す。path 変更時は既存 service を再利用せず builder を再生成する。run artifact directory ごとに trace を分ける設計は、この仕様では扱わない。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | swbt extra 未導入、backend 名不正、adapter open 失敗、key store 不正、connect timeout |
| `DeviceError` | 接続済み service の送信失敗、disconnect 中の lifecycle 不整合 |
| `SwbtAdapterProbeError` | `swbt-probe` が見つからない、非ゼロ終了、JSON parse 失敗、`opens_adapter=true` |
| `RuntimeError` | GUI が serial backend のまま pair once / reconnect / disconnect を呼んだ場合 |

GUI はこれらを握りつぶさない。status bar には短い利用者向け文言を出し、technical log には例外型、設定値、subprocess exit code を残す。

### シングルトン管理

新規グローバル singleton は追加しない。`GuiAppServices` が runtime builder lifetime を所有し、runtime builder または controller factory が `SwbtGamepadService` lifetime を所有する。アプリ終了時は `MainWindow.closeEvent()` から `GuiAppServices.close()` を呼び、builder shutdown と logging close を実行する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_swbt_probe_parses_adapter_payload` | `candidate_adapters=["usb:0"]` を GUI 表示用 result へ変換する |
| ユニット | `test_swbt_probe_rejects_adapter_opening_payload` | `opens_adapter=true` を adapter refresh 失敗として扱う |
| ユニット | `test_swbt_probe_reports_missing_command` | `swbt-probe` が見つからない場合に `SwbtAdapterProbeError` を返す |
| GUI | `test_device_settings_tab_switches_controller_backend_fields` | backend 選択に応じて serial / swbt 設定欄の有効状態が切り替わる |
| GUI | `test_device_settings_tab_refreshes_swbt_adapters` | adapter refresh 結果を combo box へ反映し、選択値を settings へ保存する |
| GUI | `test_virtual_controller_model_disables_manual_input_during_run` | 無効化中に button / stick 操作が controller port へ送られない |
| GUI | `test_virtual_controller_model_releases_on_disable` | 無効化時に `release(())` を 1 回試み、内部状態を neutral へ戻す |
| GUI | `test_gui_app_services_rebuilds_builder_on_swbt_service_key_change` | adapter、key store、diagnostics path 変更で旧 builder shutdown と新 builder 作成が走る |
| GUI | `test_gui_app_services_keeps_swbt_service_for_manual_and_runtime` | manual controller と runtime controller が同じ factory-owned service を使う |
| GUI | `test_main_window_defers_backend_change_during_run` | macro 実行中の backend 変更を deferred とし、完了後に builder を再生成する |
| 結合 | `test_main_window_pair_reconnect_disconnect_actions` | fake swbt factory を使い、pair once / reconnect / disconnect が UI 操作から呼ばれる |
| ハードウェア | `test_swbt_gui_pair_and_reconnect_device` | 実施しない。実機検証は次工程で `@pytest.mark.realdevice` / `@pytest.mark.swbt` として扱う |
| パフォーマンス | `test_swbt_adapter_refresh_timeout` | fake subprocess で timeout 経路を検証し、実機や Bluetooth adapter は開かない |

通常検証は次を使う。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/gui/ -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [ ] `GuiAppServices` が controller backend 設定を builder 更新対象に含める。
- [ ] `GuiAppServices` が swbt factory/service 操作用の pair once / reconnect / disconnect / status method を提供する。
- [ ] backend 切り替え、swbt service key 変更、diagnostics path 変更で旧 builder を shutdown する。
- [ ] `DeviceSettingsTab` に controller backend、serial 設定、swbt 設定、adapter refresh、diagnostics path を追加する。
- [ ] `swbt_probe.py` で `swbt-probe adapters --json` の subprocess 実行と parse error 変換を実装する。
- [ ] `MainWindow` の接続メニューと接続状態表示を controller backend 対応にする。
- [ ] macro 実行中に manual input を無効化し、実行後に有効へ戻す。
- [ ] `VirtualControllerModel` が無効化時に neutral を試み、無効中の操作を送信しない。
- [ ] GUI と runtime が同じ `SwbtGamepadService` を共有することを fake service で検証する。
- [ ] diagnostics path 未指定では trace を出さず、path 変更時は builder を再生成する。
- [ ] GUI / unit / integration test を追加して通す。
- [ ] `uv run ruff format .` を実行する。
- [ ] `uv run ruff check .` を実行する。
- [ ] `uv run ty check src/nyxpy --output-format concise --no-progress` を実行する。

## 7. 親計画との依存関係

この仕様は `local_021` の M5 に対応する。`local_022` は settings schema と config 正規化、`local_023` は swbt service / port / factory、`local_024` は runtime builder と CLI からの factory lifetime を提供する前提である。

この仕様では CLI option 実装、`SwbtControllerOutputPort` の内部状態遷移、`SwbtGamepadService` の非同期 event loop 実装、実機検証は扱わない。GUI が必要とする pair once / reconnect / disconnect / status 操作は `local_023` の `SwbtControllerOutputPortFactory` が提供する前提である。

## 8. 完了後に次へ渡す成果

- GUI から `serial` / `swbt` controller backend を選択できる。
- `swbt-probe adapters --json` の結果を GUI へ表示し、`controller.swbt.adapter` へ保存できる。
- GUI の pair once / reconnect / disconnect 操作が fake swbt factory で検証済みである。
- manual input と runtime が同じ service を共有し、macro 実行中に manual input が無効化される。
- diagnostics path の初期値は無効であり、path 変更時に builder を再生成する挙動が記録されている。

次工程の実機検証では、GUI からの pair once、reconnect、disconnect、button、D-pad、stick、neutral、diagnostics trace を確認する。stick Y 軸既定と短押し flush 要否は、この仕様では決めず実機結果に基づいて判断する。

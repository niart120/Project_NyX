# Device connection settings 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`, `src/nyxpy/framework/core/io/`, `src/nyxpy/framework/core/runtime/`, `src/nyxpy/gui/`
> **目的**: 保存済み接続設定と現在接続可能なデバイスの差分を安全に扱い、GUI から接続先を切り替えられるようにする
> **関連ドキュメント**: `spec/framework/archive/hardware_design.md`, `spec/framework/archive/protocol_design.md`
> **既存ソース**: `src/nyxpy/framework/core/hardware/device_discovery.py`, `src/nyxpy/framework/core/io/device_factories.py`, `src/nyxpy/gui/main_window.py`, `src/nyxpy/gui/dialogs/settings/device_tab.py`
> **破壊的変更**: あり。GUI のデバイス一覧は現在検出できる実デバイスだけを表示し、切断済みの保存値を候補へ再追加しない。

## 1. 概要

### 1.1 目的

設定ファイルに残った接続先が現在存在しない場合、GUI の preview と手動入力はダミーデバイスへ明示的にフォールバックする。デバイス列挙、接続解決、メニュー表示を requested / resolved の二層で扱い、保存済み設定と実効接続の混同をなくす。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| DeviceDiscoveryService | シリアルデバイス、カメラデバイス、ウィンドウキャプチャ候補を検出する service。 |
| DeviceDiscoveryResult | 検出時点で利用可能な実デバイス一覧と検出エラーを保持する値 object。 |
| DeviceInfo | GUI/CLI へ提示する検出済み device の情報。`kind`, `name`, `identifier`, `api_pref` を持つ。 |
| Dummy device | 実デバイスがない場合に使う `DummySerialComm` または `DummyCaptureDevice`。Discovery 結果には混ぜない。 |
| Requested target | 設定ファイルまたはユーザー操作で要求された接続先。実デバイスとして存在するとは限らない。 |
| Resolved target | 現在の検出結果と allow_dummy policy に基づいて実際に使う接続先。実デバイスまたは Dummy device のいずれかである。 |
| Connection menu | メニューバーの「接続」タブ。キャプチャ入力、コントローラー、設定ダイアログへの導線を持つ。 |
| CaptureDeviceInterface | フレーム取得デバイスが満たす同期 interface。 |
| SerialCommInterface | シリアル通信デバイスが満たす interface。 |
| SerialProtocolInterface | コントローラー入力をシリアル送信用 bytes へ変換する protocol interface。 |
| MacroRuntimeBuilder | `MacroDefinition` から実行 context と runtime handle を構築する builder。 |

### 1.3 背景・問題

現状の GUI は、`global.toml` に残った `serial_device` が現在検出できない場合でも設定ダイアログの候補へ再追加する。`FrameSourcePortFactory` には数字文字列の capture index を検出結果なしで接続試行する経路もあるため、設定ファイル上の古い接続先を「現在接続可能な候補」として扱う余地が残っている。結果として、切断済みデバイスを探し続ける、一覧にないデバイスへ接続を試みる、実効接続が UI から分からない、という状態が発生する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| GUI のデバイス候補 | 検出済み実デバイスに加え、保存済みの切断済み serial/window 値が再追加される | 現在検出できる実デバイスと明示的な Dummy だけを表示する |
| Missing device 時の GUI lifetime port | 接続失敗を warning として保持し、preview/manual が使えない | Dummy へフォールバックし、UI で実効接続と理由を確認できる |
| Requested と resolved の区別 | 設定値を現在接続中として扱いやすい | 設定値、検出結果、実効接続、fallback reason を別々に扱う |
| メニューからの接続切替 | File > Settings 経由で設定ダイアログを開く必要がある | 接続メニューからデバイス、protocol、FPS、baudrate を直接切り替えられる |

### 1.5 着手条件

- `DeviceDiscoveryResult` は実デバイスのみを表し、Dummy device を検出結果へ混ぜない方針を維持する。
- `runtime.allow_dummy` と `RuntimeBuildRequest.allow_dummy` の既存意味を確認する。
- GUI 起動時、明示的な再読み込み時、設定変更時の device discovery 実行タイミングを確定する。
- `uv run pytest tests\unit\framework\hardware tests\unit\framework\io tests\unit\framework\runtime` が着手前に通ること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/hardware/device_discovery.py` | 変更 | 検出結果は現在利用可能な実デバイスのみであることを contract 化し、同一性判定 helper を追加する。 |
| `src/nyxpy/framework/core/hardware/device_resolver.py` | 新規 | requested target と discovery result から resolved target を決定する純粋ロジックを追加する。 |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | missing / open failed / not selected 時の Dummy fallback を resolver 経由へ統一し、数字 capture index の裏口を廃止または明示的 legacy path として隔離する。 |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | GUI lifetime port と macro execution port の fallback policy を明確に分離する。 |
| `src/nyxpy/gui/app_services.py` | 変更 | device discovery の再読み込み、resolved target の保持、builder 再作成トリガを管理する。 |
| `src/nyxpy/gui/main_window.py` | 変更 | File menu を廃止し、接続 menu を構築する。Settings は接続 > 設定... へ移動する。 |
| `src/nyxpy/gui/connection_menu.py` | 新規 | 接続 menu の構築、チェック状態、再読み込み action、設定反映 action を分離する。 |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | 切断済みの保存値を候補へ再追加しない。missing 状態は警告表示または status text で示す。 |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | 必要に応じて device fallback policy や menu 表示用の設定を追加する。 |
| `tests/unit/framework/hardware/test_device_discovery.py` | 変更 | Discovery が Dummy と切断済み保存値を返さないことを確認する。 |
| `tests/unit/framework/hardware/test_device_resolver.py` | 新規 | requested / resolved / fallback reason の純粋ロジックを確認する。 |
| `tests/unit/framework/io/test_device_factories.py` | 変更 | missing / open failed 時の Dummy fallback と `allow_dummy=False` の例外を確認する。 |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | GUI lifetime と macro execution の fallback policy が分離されることを確認する。 |
| `tests/gui/test_connection_menu.py` | 新規 | 接続 menu のチェック状態、候補更新、実行中の操作制御を確認する。 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

接続解決は framework 層の device resolver が担う。GUI は resolver の結果を表示し、設定更新と再読み込みを要求するだけにする。`nyxpy.framework.*` から `nyxpy.gui.*` への依存は追加しない。

### 公開 API 方針

`DeviceDiscoveryService.detect()` は現在検出できる実デバイスだけを返す。保存済み設定値が検出結果にない場合でも、Discovery は候補を補完しない。Dummy device は Discovery の結果ではなく resolver の resolved target として扱う。

接続先の同一性は device kind ごとに定義する。

| 種別 | 永続化する値 | 表示ラベル | 同一性判定キー | 備考 |
|------|--------------|------------|----------------|------|
| シリアル | `DeviceInfo.identifier` の文字列 | `DeviceInfo.display_name` | `identifier` | 例: `COM3`, `/dev/ttyUSB0`。抜き差しで identifier が変われば missing 扱いである。 |
| カメラ | `DeviceInfo.name` | `DeviceInfo.display_name` | 原則 `name`、同名衝突時は `identifier` を補助 | 現状は `0: Device Name` のように index を含む name を保存する。 |
| ウィンドウ | `capture_window_identifier` と `capture_window_title` | `WindowInfo.display_name` | `identifier` 優先、なければ title | 検出できない保存済み window は候補へ再追加しない。 |
| Dummy | `DUMMY_DEVICE_NAME` | `ダミーデバイス` | sentinel | ユーザーが明示選択した場合だけ設定へ保存する。自動 fallback では保存値を書き換えない。 |

### 後方互換性

破壊的変更あり。GUI の device list は現在接続可能な実デバイスのみを列挙し、切断済みの保存値を候補へ戻さない。`capture_device` が数字文字列の場合に検出結果なしで index 接続を試す現行経路は、現在接続可能なデバイスのみを扱う方針と矛盾するため廃止候補とする。維持する場合は CLI 用の明示 index 指定として扱い、GUI メニューの候補やチェック判定には使わない。

### レイヤー構成

`device_resolver.py` は I/O を持たない純粋ロジックとして実装する。`device_factories.py` は resolver の結果に従って実デバイスまたは Dummy を生成する。`app_services.py` は discovery cache、resolved target、runtime builder の lifetime を所有する。`connection_menu.py` は Qt action と settings 反映だけを扱う。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| メニュー表示時の同期 device discovery | 0 回 |
| 明示再読み込みの UI ブロック | 0.1 秒未満。検出は worker 経由にする |
| device resolver の追加 I/O | 0 |
| メニュー action 生成数 | 検出デバイス数 + protocol 数 + FPS/baudrate 候補数に比例 |

### 並行性・スレッド安全性

Device discovery は GUI thread をブロックしない。メニュー表示は `DeviceDiscoveryService.last_result` と `GuiAppServices` が保持する resolved target snapshot だけを読む。再読み込み action は worker で `detect()` を実行し、完了後に GUI thread で menu action と runtime builder を再評価する。実行中マクロがある場合、接続切替は即時反映せず既存の `apply_settings(is_run_active=True)` と同じ deferred policy に従う。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

DeviceKind = Literal["serial", "capture", "window"]


class ConnectionResolveStatus(StrEnum):
    CONNECTED = "connected"
    FALLBACK_DUMMY = "fallback_dummy"
    ERROR = "error"


class ConnectionFallbackReason(StrEnum):
    NOT_SELECTED = "not_selected"
    NOT_FOUND = "not_found"
    OPEN_FAILED = "open_failed"
    TIMED_OUT = "timed_out"
    USER_SELECTED_DUMMY = "user_selected_dummy"


@dataclass(frozen=True)
class ConnectionRequest:
    kind: DeviceKind
    requested: str | None
    allow_dummy: bool


@dataclass(frozen=True)
class ResolvedConnection:
    kind: DeviceKind
    status: ConnectionResolveStatus
    requested: str | None
    resolved: DeviceInfo | None
    uses_dummy: bool
    reason: ConnectionFallbackReason | None = None
    message: str = ""


class DeviceResolver:
    def resolve_serial(
        self,
        request: ConnectionRequest,
        result: DeviceDiscoveryResult,
    ) -> ResolvedConnection:
        ...

    def resolve_capture(
        self,
        request: ConnectionRequest,
        result: DeviceDiscoveryResult,
    ) -> ResolvedConnection:
        ...

    def resolve_window(
        self,
        request: ConnectionRequest,
        windows: tuple[WindowInfo, ...],
    ) -> ResolvedConnection:
        ...
```

`ControllerOutputPortFactory.create()` と `FrameSourcePortFactory.create()` は、resolver が `FALLBACK_DUMMY` を返した場合に Dummy port を返す。resolver が `ERROR` を返した場合は `ConfigurationError` を送出し、`details` に `device_type`, `requested`, `available_devices`, `fallback_reason` を含める。実デバイスが見つかった後に `open()` または `initialize()` で失敗した場合、`allow_dummy=True` では Dummy に切り替え、`allow_dummy=False` では原因例外を `cause` に持つ `ConfigurationError` を送出する。

### 状態モデル

| 状態 | requested | resolved | 設定ファイル更新 | UI チェック |
|------|-----------|----------|------------------|-------------|
| 実デバイス接続中 | 実デバイス識別子 | 同じ実デバイス | ユーザー選択時に保存 | 実デバイスにチェック |
| 自動 Dummy fallback | 切断済みまたは未選択 | Dummy | 書き換えない | Dummy にチェックし、fallback reason を表示 |
| 明示 Dummy 選択 | `DUMMY_DEVICE_NAME` | Dummy | Dummy を保存 | Dummy にチェック |
| 再読み込みで実デバイス復帰 | 古い requested が再び検出可能 | 実デバイスへ再解決 | 書き換えない | 実デバイスにチェック |
| 明示 Dummy 中に実デバイス復帰 | `DUMMY_DEVICE_NAME` | Dummy | 書き換えない | Dummy にチェック |

再読み込み action は requested を再評価する。自動 Dummy fallback 中に同じ requested が再検出された場合は実デバイスへ自動復帰する。ユーザーが明示的に Dummy を選んだ場合は、自動復帰しない。

### 実行経路別 fallback policy

| 経路 | `allow_dummy` の決定 | Missing / not selected | Open failed | 目的 |
|------|----------------------|------------------------|-------------|------|
| GUI preview | `lifetime_allow_dummy=True` | Dummy fallback | Dummy fallback | GUI を起動可能に保つ |
| GUI 手動入力 | `lifetime_allow_dummy=True` | Dummy fallback | Dummy fallback | 仮想コントローラー操作で GUI が落ちないようにする |
| GUI マクロ実行 | `RuntimeBuildRequest.allow_dummy` または `runtime.allow_dummy` | `False` なら `ConfigurationError`、`True` なら Dummy fallback | 同左 | 実機なし実行を明示 opt-in にする |
| CLI マクロ実行 | `RuntimeBuildRequest.allow_dummy` または `runtime.allow_dummy` | `False` なら `ConfigurationError`、`True` なら Dummy fallback | 同左 | 予期しない空実行を避ける |

### Connection menu tree

推奨するメニュー構造は次のとおりである。FPS は capture device の子ではなく入力ソース全体の設定、baudrate は serial device の子ではなく protocol と同じ controller group の設定として扱う。

```text
接続
├─ キャプチャ入力
│  ├─ 入力ソース
│  │  ├─ カメラ
│  │  └─ ウィンドウ
│  ├─ カメラデバイス
│  │  ├─ ダミーデバイス
│  │  └─ <現在検出できるカメラ...>
│  ├─ ウィンドウ
│  │  └─ <現在検出できるウィンドウ...>
│  ├─ FPS
│  │  ├─ source default
│  │  ├─ 15
│  │  ├─ 30
│  │  └─ 60
│  └─ 再読み込み
├─ コントローラー
│  ├─ シリアルデバイス
│  │  ├─ ダミーデバイス
│  │  └─ <現在検出できるシリアル...>
│  ├─ プロトコル
│  │  ├─ CH552
│  │  ├─ PokeCon
│  │  └─ 3DS
│  ├─ ボーレート
│  │  └─ <現在の protocol が対応する baudrate...>
│  └─ 再読み込み
└─ 設定...
```

`File` menu は廃止する。既存の Settings action は `接続 > 設定...` へ移動する。`表示` menu は window size preset の責務を維持する。

### メニュー更新ルール

| 操作 | 検出実行 | 設定保存 | Builder 再作成 | 備考 |
|------|----------|----------|----------------|------|
| メニューを開く | しない | しない | しない | `last_result` と resolved snapshot だけで表示する。 |
| 再読み込み | worker で実行 | しない | 実行中でなければ再評価して必要時に再作成 | タイムアウト時は既存 resolved を維持し、status を表示する。 |
| 実デバイス選択 | しない | requested を保存 | 実行中でなければ即時再作成 | 選択肢は検出済み device のみ。 |
| Dummy 選択 | しない | `DUMMY_DEVICE_NAME` を保存 | 実行中でなければ即時再作成 | 明示 Dummy として自動復帰しない。 |
| Protocol 選択 | しない | protocol を保存 | 実行中でなければ即時再作成 | baudrate が非対応なら protocol 既定値へ補正する。 |
| Baudrate 選択 | しない | baudrate を保存 | 実行中でなければ即時再作成 | 候補は protocol の `supported_baudrates` のみ。 |
| FPS 選択 | しない | capture_fps を保存 | 実行中でなければ即時再作成 | preview の一時停止は許容する。hot apply は別仕様に分離する。 |

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | `camera` または `window`。接続 menu の入力ソースで切り替える。 |
| `capture_device` | `str` | `""` | カメラ入力の requested target。検出されない場合、GUI lifetime では Dummy fallback する。 |
| `capture_window_title` | `str` | `""` | window 入力の requested title。候補にない場合は GUI lifetime で Dummy fallback 対象にする。 |
| `capture_window_identifier` | `str` | `""` | window 入力の requested identifier。title より優先して同一性判定に使う。 |
| `capture_fps` | `float | None` | `None` | カメラ取得 FPS。`None` は source default。 |
| `serial_device` | `str` | `""` | シリアル入力の requested identifier。検出されない場合、GUI lifetime では Dummy fallback する。 |
| `serial_protocol` | `str` | `"CH552"` | `ProtocolFactory` が解決する protocol 名。 |
| `serial_baud` | `int` | `9600` | 現在の protocol が対応する baudrate。protocol 切替時に非対応なら既定値へ補正する。 |
| `runtime.allow_dummy` | `bool` | `False` | マクロ実行で Dummy fallback を許可するか。GUI lifetime fallback とは別に扱う。 |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | `allow_dummy=False` で requested target が未選択、検出不能、または open/initialize に失敗した場合。 |
| `ValueError` | `DeviceResolver` に未知の device kind や負の timeout など不正な引数を渡した場合。 |
| `ExceptionGroup` | runtime builder shutdown 時に複数 port の close が失敗した場合。現行仕様を維持する。 |

Dummy fallback は失敗を隠す成功扱いにしない。`ResolvedConnection.reason` と log event に fallback reason を残し、GUI は status text または tool log で表示する。

### シングルトン管理

新規 singleton は追加しない。`DeviceResolver` は `GuiAppServices`、runtime builder、テスト fixture が所有する通常 object とする。既存 `singletons.py` への依存は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_discovery_result_excludes_dummy_and_stale_settings` | Discovery 結果に Dummy と保存済み切断デバイスが含まれない。 |
| ユニット | `test_resolver_falls_back_to_dummy_when_requested_serial_missing` | `allow_dummy=True` で missing serial が Dummy fallback になる。 |
| ユニット | `test_resolver_returns_error_when_dummy_not_allowed` | `allow_dummy=False` で missing device が error になる。 |
| ユニット | `test_resolver_distinguishes_auto_dummy_from_user_selected_dummy` | 自動 fallback と明示 Dummy 選択の reason が分かれる。 |
| ユニット | `test_resolver_reconnects_requested_device_after_reload` | 自動 Dummy fallback 中に requested device が復帰した場合、実デバイスへ再解決する。 |
| ユニット | `test_controller_factory_falls_back_to_dummy_on_open_failure_when_allowed` | serial open failure が `allow_dummy=True` で Dummy port になる。 |
| ユニット | `test_frame_factory_falls_back_to_dummy_when_camera_missing` | camera missing が `allow_dummy=True` で Dummy frame source になる。 |
| ユニット | `test_window_source_missing_uses_dummy_for_gui_lifetime` | window source missing が GUI lifetime policy で Dummy frame source になる。 |
| ユニット | `test_macro_execution_still_rejects_missing_device_without_allow_dummy` | macro execution の `allow_dummy=False` では missing device が `ConfigurationError` のままである。 |
| GUI | `test_connection_menu_uses_cached_discovery_without_blocking` | menu 表示で同期 `detect()` を呼ばない。 |
| GUI | `test_connection_menu_checks_resolved_dummy_when_requested_missing` | requested が missing の時、Dummy action にチェックが付く。 |
| GUI | `test_connection_menu_protocol_change_clamps_baudrate` | protocol 変更時、非対応 baudrate が既定値へ補正される。 |
| GUI | `test_connection_menu_defers_change_while_macro_running` | マクロ実行中の接続変更が deferred または disabled として一貫して扱われる。 |
| ハードウェア | `test_device_reload_detects_reconnected_capture_device` | `@pytest.mark.realdevice`。切断後に Dummy、再接続後に実デバイスへ復帰する。 |
| パフォーマンス | `test_connection_menu_open_does_not_run_discovery` | menu open が device discovery timeout に依存しない。 |

## 6. 実装チェックリスト

- [ ] `DeviceResolver` の公開シグネチャを確定する。
- [ ] requested / resolved / fallback reason の状態モデルを実装する。
- [ ] Discovery 結果へ切断済み保存値を混ぜない contract をテストで固定する。
- [ ] GUI lifetime port の missing / open failed を Dummy fallback へ統一する。
- [ ] Macro execution の `allow_dummy=False` 既定を維持する。
- [ ] Window capture source の missing fallback policy を実装する。
- [ ] 数字 capture index fallback を廃止するか、GUI 対象外の明示 legacy path として隔離する。
- [ ] `File` menu を廃止し、`接続 > 設定...` へ Settings action を移動する。
- [ ] `connection_menu.py` を追加し、menu 表示で同期 discovery を呼ばない。
- [ ] Protocol 変更時に baudrate を対応範囲へ補正する。
- [ ] 設定ダイアログで切断済み保存値を候補へ再追加しない。
- [ ] ユニットテスト作成・パス。
- [ ] GUI テスト作成・パス。
- [ ] 実機必要テストに `@pytest.mark.realdevice` を付ける。
- [ ] `uv run ruff check src\nyxpy tests\unit tests\gui` を実行する。

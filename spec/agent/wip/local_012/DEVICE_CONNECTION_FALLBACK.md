# Device connection fallback 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`, `src/nyxpy/framework/core/io/`, `src/nyxpy/framework/core/runtime/`, `src/nyxpy/gui/`
> **目的**: 保存済み接続先が現在存在しない場合の解決規則を統一し、GUI lifetime port を Dummy device へ安全にフォールバックさせる
> **関連ドキュメント**: `spec/framework/archive/hardware_design.md`, `spec/framework/archive/protocol_design.md`, `spec/agent/wip/local_013/CONNECTION_MENU.md`
> **既存ソース**: `src/nyxpy/framework/core/hardware/device_discovery.py`, `src/nyxpy/framework/core/io/device_factories.py`, `src/nyxpy/framework/core/runtime/builder.py`, `src/nyxpy/gui/app_services.py`
> **破壊的変更**: あり。GUI と設定ダイアログは切断済みの保存値を現在接続可能な候補として扱わない。

## 1. 概要

### 1.1 目的

`global.toml` に残った接続先が現在検出できない場合、接続要求と実効接続を分離して扱う。GUI preview と手動入力は Dummy device へフォールバックし、マクロ実行は `allow_dummy` が明示的に有効な場合だけ Dummy device を使う。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| DeviceDiscoveryService | シリアルデバイス、カメラデバイス、ウィンドウキャプチャ候補を検出する service。 |
| DeviceDiscoveryResult | 検出時点で利用可能な実デバイス一覧と検出エラーを保持する値 object。 |
| DeviceInfo | GUI/CLI へ提示する検出済み device の情報。`kind`, `name`, `identifier`, `api_pref` を持つ。 |
| Dummy device | 実デバイスがない場合に使う `DummySerialComm` または `DummyCaptureDevice`。Discovery 結果には混ぜない。 |
| Requested target | 設定ファイルまたはユーザー操作で要求された接続先。実デバイスとして存在するとは限らない。 |
| Resolved target | 現在の検出結果と `allow_dummy` policy に基づいて実際に使う接続先。実デバイスまたは Dummy device のいずれかである。 |
| GUI lifetime port | GUI preview と手動入力が window lifetime 中に共有する `FrameSourcePort` / `ControllerOutputPort`。 |
| CaptureDeviceInterface | フレーム取得デバイスが満たす同期 interface。 |
| SerialCommInterface | シリアル通信デバイスが満たす interface。 |
| MacroRuntimeBuilder | `MacroDefinition` から実行 context と runtime handle を構築する builder。 |

### 1.3 背景・問題

現状の設定ダイアログは、`serial_device` や window source の保存値が現在検出できない場合でも候補へ再追加する。`FrameSourcePortFactory` には数字文字列の capture index を検出結果なしで接続試行する経路もある。これにより、切断済みデバイスを現在接続可能な候補として表示する、存在しない接続先を探し続ける、実効接続が Dummy なのか失敗なのか UI から判別できない、という状態が発生する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| Discovery 結果 | 実デバイスだけを返す設計だが、上位 UI が保存値を候補へ補完する | 実デバイスのみを唯一の列挙 source として扱う |
| Missing device 時の GUI lifetime port | 接続失敗を warning として保持し、preview/manual が使えない | Dummy device へフォールバックし、理由を log/UI に残す |
| Requested と resolved の区別 | 保存値を現在接続中として扱いやすい | 保存値、検出結果、実効接続、fallback reason を別々に扱う |
| マクロ実行時の Dummy 利用 | `runtime.allow_dummy` に依存するが GUI lifetime と区別しにくい | GUI lifetime と macro execution の policy を明確に分離する |

### 1.5 着手条件

- `DeviceDiscoveryResult` は実デバイスのみを表し、Dummy device を検出結果へ混ぜない方針を維持する。
- `runtime.allow_dummy` と `RuntimeBuildRequest.allow_dummy` の既存意味を維持する。
- GUI 接続メニューの構造は `spec/agent/wip/local_013/CONNECTION_MENU.md` で扱う。
- `uv run pytest tests\unit\framework\hardware tests\unit\framework\io tests\unit\framework\runtime` が着手前に通ること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/hardware/device_discovery.py` | 変更 | 現在利用可能な実デバイスの列挙だけを contract 化し、`find_serial()` / `find_capture()` の接続解決責務を移管または削除する。 |
| `src/nyxpy/framework/core/runtime/device_selection.py` | 新規候補 | requested target と discovery snapshot から selected target を決定する純粋関数と値 object を置く候補。採用可否は「責務再整理と採用判断」で決める。 |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | Port adapter の生成と open/initialize 失敗時の処理へ責務を絞り、requested target 探索ロジックを削減する。 |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | GUI lifetime port と macro execution port の fallback policy を明確に分離する。 |
| `src/nyxpy/gui/app_services.py` | 変更 | device discovery の再読み込み、resolved target の保持、runtime builder 再評価を管理する。 |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | 切断済みの保存値を候補へ再追加しない。missing 状態は警告表示または status text で示す。 |
| `tests/unit/framework/hardware/test_device_discovery.py` | 変更 | Discovery が Dummy と切断済み保存値を返さないことを確認する。 |
| `tests/unit/framework/runtime/test_device_selection.py` | 新規 | requested / selected / fallback reason の純粋ロジックを確認する。 |
| `tests/unit/framework/io/test_device_factories.py` | 変更 | missing / open failed 時の Dummy fallback と `allow_dummy=False` の例外を確認する。 |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | GUI lifetime と macro execution の fallback policy が分離されることを確認する。 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

接続先の選択方針は framework の Runtime assembly 境界で扱う。GUI は選択結果を表示し、設定更新と再読み込みを要求するだけにする。`nyxpy.framework.*` から `nyxpy.gui.*` への依存は追加しない。

### 公開 API 方針

`DeviceDiscoveryService.detect()` は現在検出できる実デバイスだけを返す。保存済み設定値が検出結果にない場合でも、Discovery は候補を補完しない。Dummy device は Discovery の結果ではなく device selection policy の selected target として扱う。

接続先の同一性は device kind ごとに定義する。

| 種別 | 永続化する値 | 表示ラベル | 同一性判定キー | 備考 |
|------|--------------|------------|----------------|------|
| シリアル | `DeviceInfo.identifier` の文字列 | `DeviceInfo.display_name` | `identifier` | 例: `COM3`, `/dev/ttyUSB0`。抜き差しで identifier が変われば missing 扱いである。 |
| カメラ | `DeviceInfo.name` | `DeviceInfo.display_name` | 原則 `name`、同名衝突時は `identifier` を補助 | 現状は `0: Device Name` のように index を含む name を保存する。 |
| ウィンドウ | `capture_window_identifier` と `capture_window_title` | `WindowInfo.display_name` | `identifier` 優先、なければ title | 検出できない保存済み window は候補へ再追加しない。 |
| Dummy | `DUMMY_DEVICE_NAME` | `ダミーデバイス` | sentinel | ユーザーが明示選択した場合だけ設定へ保存する。自動 fallback では保存値を書き換えない。 |

### 責務再整理と採用判断

フレームワーク再設計では、GUI/CLI は `MacroRuntimeBuilder` を呼ぶ entry adapter、Runtime は実行単位と Ports の組み立て、Ports は I/O 境界、Adapters は現行 Serial/Capture 実装への接続と定義されている。この構成に照らすと、接続関連の責務は次の 3 つに分ける。

| 責務 | 属する層 | やること | やらないこと |
|------|----------|----------|--------------|
| Device discovery | Hardware support | OS / OpenCV / pyserial から現在接続可能な device inventory を作る | 保存済み設定、Dummy fallback、GUI lifetime policy を判断しない |
| Device selection policy | Runtime assembly | requested target、discovery snapshot、`allow_dummy`、GUI lifetime policy から selected target と reason を決める | 実デバイスを open しない。Qt や GUI 表示へ依存しない |
| Port factory / adapter construction | I/O adapter | selected target から `ControllerOutputPort` / `FrameSourcePort` を生成し、open/initialize と cache/close を扱う | stale 設定値を候補として補完しない。Discovery を UI 表示目的で同期実行しない |

既存コードには selection policy に近い責務が分散している。

| 既存箇所 | 現在の責務 | 見直し後 |
|----------|------------|----------|
| `DeviceDiscoveryService.find_serial()` / `find_capture()` | `last_result` を検索し、見つからなければ同期 `detect()` を再実行する。 | Discovery は列挙と snapshot 保持に限定する。requested target の解決と再検出判断は device selection policy または呼び出し元 policy に移す。 |
| `ControllerOutputPortFactory.create()` | 未選択、Dummy、not found、実デバイス生成、cache を同じ method で扱う。 | requested target の選択は device selection policy、port 生成と cache は factory に分離する。 |
| `FrameSourcePortFactory._create_camera_source()` | 未選択、Dummy、not found、数字 index fallback、実デバイス生成、cache を同じ method で扱う。 | requested target の選択は device selection policy、capture device 生成と cache は factory に分離する。数字 index fallback は廃止または GUI 対象外に隔離する。 |
| `_device_not_selected()` / `_device_not_found()` / `_dummy_not_allowed()` | factory 内で条件ごとに例外 details を組み立てる。 | `ResolvedConnection` の status / reason をもとに共通の error details を生成する。 |

この責務をどこへ置くかは次の選択肢がある。

| 案 | 内容 | Pros | Cons | 評価 |
|----|------|------|------|------|
| A. DiscoveryService に寄せる | `DeviceDiscoveryService.find_*` を拡張し、selected target と Dummy fallback まで返す | 既存 API を活かせる。inventory に近い | Discovery が settings と runtime policy を持ち、hardware support 層が上位方針を知る。メニュー表示時の同期再検出も誘発しやすい | 不採用 |
| B. device_factories.py に寄せる | Factory 内で requested target、Dummy fallback、Port 生成を完結させる | open/initialize 失敗時の fallback を扱いやすい。変更ファイルが少ない | Factory が selection policy と adapter construction を兼務し続ける。GUI menu が「実効接続だけ知りたい」場合に factory/open へ依存する | 部分採用 |
| C. RuntimeBuilder に private helper として置く | `MacroRuntimeBuilder` 内で requested target を selected target に変換する | Runtime assembly の責務に近い。新規公開面が少ない | GUI lifetime / connection menu でも同じ判定を使うため、private helper では共有しにくい | 不採用 |
| D. Runtime assembly の小さな pure module に置く | `core/runtime/device_selection.py` に値 object と `select_*_target()` を置く。状態を持つ service class は作らない | 再設計の Runtime/Ports 境界に合う。GUI/CLI/Factory が同じ selection policy を共有できる。Discovery と Factory の肥大化を避けられる | 新規 module は増える。open/initialize 失敗後の fallback は factory と連携が必要 | 採用候補 |
| E. GUI AppServices に置く | GUI lifetime と menu 表示だけ `GuiAppServices` で解決する | GUI 要件には最短で届く | CLI / macro execution と policy が分岐する。framework core の挙動として固定できない | 不採用 |

採用方針は D 案を基本とする。ただし、`ConnectionResolver` のような状態を持つ新 service class は作らない。まずは `ResolvedConnection` 相当の値 object と `select_serial_target()` / `select_capture_target()` / `select_window_target()` の純粋関数を `src/nyxpy/framework/core/runtime/device_selection.py` へ置く。`ControllerOutputPortFactory` / `FrameSourcePortFactory` は selected target をもとに Port を生成する責務へ寄せ、実デバイスの open/initialize 失敗だけ factory 側で `OPEN_FAILED` fallback として扱う。

この判断により、既存コンポーネントは次のように削減する。

- `DeviceDiscoveryService.find_serial()` / `find_capture()` は public API から外す候補にし、Discovery は `detect()` と `last_result` に集中する。
- `_numeric_capture_info()` は GUI での「現在接続可能なデバイスのみ列挙」と矛盾するため削除候補にする。CLI の明示 index 指定を残す場合は device selection policy の入力として別扱いにする。
- `_device_not_selected()` / `_device_not_found()` / `_dummy_not_allowed()` は selected target の status / reason から共通 details を作る helper へ統合する。

### 後方互換性

破壊的変更あり。GUI の device list は現在接続可能な実デバイスのみを列挙し、切断済みの保存値を候補へ戻さない。`capture_device` が数字文字列の場合に検出結果なしで index 接続を試す現行経路は、現在接続可能なデバイスのみを扱う方針と矛盾するため廃止候補とする。維持する場合は CLI 用の明示 index 指定として扱い、GUI の候補やチェック判定には使わない。

### レイヤー構成

`device_selection.py` は I/O を持たない純粋ロジックとして実装する。`device_factories.py` は selected target に従って実デバイスまたは Dummy を生成する。`app_services.py` は discovery cache、selected target snapshot、runtime builder の lifetime を所有する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| device selection policy の追加 I/O | 0 |
| missing 判定に必要な同期 discovery | 既存の明示 discovery 1 回以内 |
| GUI lifetime fallback の追加待ち時間 | 実デバイス open/initialize 失敗後、Dummy 生成だけで完了する |

### 並行性・スレッド安全性

Device selection policy は immutable な request と discovery snapshot を受け取る純粋ロジックとし、lock を持たない。`DeviceDiscoveryService.last_result` の読み書きは既存の lock に従う。`GuiAppServices` は runtime builder の差し替え時に旧 builder を shutdown してから新しい selected target を公開する。

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


def select_serial_target(
    request: ConnectionRequest,
    result: DeviceDiscoveryResult,
) -> ResolvedConnection:
    ...


def select_capture_target(
    request: ConnectionRequest,
    result: DeviceDiscoveryResult,
) -> ResolvedConnection:
    ...


def select_window_target(
    request: ConnectionRequest,
    windows: tuple[WindowInfo, ...],
) -> ResolvedConnection:
    ...
```

`ControllerOutputPortFactory.create()` と `FrameSourcePortFactory.create()` は、selection policy が `FALLBACK_DUMMY` を返した場合に Dummy port を返す。selection policy が `ERROR` を返した場合は `ConfigurationError` を送出し、`details` に `device_type`, `requested`, `available_devices`, `fallback_reason` を含める。実デバイスが見つかった後に `open()` または `initialize()` で失敗した場合、`allow_dummy=True` では Dummy に切り替え、`allow_dummy=False` では原因例外を `cause` に持つ `ConfigurationError` を送出する。

### 状態モデル

| 状態 | requested | resolved | 設定ファイル更新 | UI 表示 |
|------|-----------|----------|------------------|---------|
| 実デバイス接続中 | 実デバイス識別子 | 同じ実デバイス | ユーザー選択時に保存 | 実デバイスを現在接続中として表示 |
| 自動 Dummy fallback | 切断済みまたは未選択 | Dummy | 書き換えない | Dummy と fallback reason を表示 |
| 明示 Dummy 選択 | `DUMMY_DEVICE_NAME` | Dummy | Dummy を保存 | Dummy を現在接続中として表示 |
| 再読み込みで実デバイス復帰 | 古い requested が再び検出可能 | 実デバイスへ再解決 | 書き換えない | 実デバイスを現在接続中として表示 |
| 明示 Dummy 中に実デバイス復帰 | `DUMMY_DEVICE_NAME` | Dummy | 書き換えない | Dummy を維持 |

自動 Dummy fallback 中に同じ requested target が再検出された場合は、再読み込み後に実デバイスへ自動復帰する。ユーザーが明示的に Dummy を選んだ場合は、自動復帰しない。

### 実行経路別 fallback policy

| 経路 | `allow_dummy` の決定 | Missing / not selected | Open failed | 目的 |
|------|----------------------|------------------------|-------------|------|
| GUI preview | `lifetime_allow_dummy=True` | Dummy fallback | Dummy fallback | GUI を起動可能に保つ |
| GUI 手動入力 | `lifetime_allow_dummy=True` | Dummy fallback | Dummy fallback | 仮想コントローラー操作で GUI が落ちないようにする |
| GUI マクロ実行 | `RuntimeBuildRequest.allow_dummy` または `runtime.allow_dummy` | `False` なら `ConfigurationError`、`True` なら Dummy fallback | 同左 | 実機なし実行を明示 opt-in にする |
| CLI マクロ実行 | `RuntimeBuildRequest.allow_dummy` または `runtime.allow_dummy` | `False` なら `ConfigurationError`、`True` なら Dummy fallback | 同左 | 予期しない空実行を避ける |

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_device` | `str` | `""` | カメラ入力の requested target。検出されない場合、GUI lifetime では Dummy fallback する。 |
| `capture_window_title` | `str` | `""` | window 入力の requested title。候補にない場合は GUI lifetime で Dummy fallback 対象にする。 |
| `capture_window_identifier` | `str` | `""` | window 入力の requested identifier。title より優先して同一性判定に使う。 |
| `serial_device` | `str` | `""` | シリアル入力の requested identifier。検出されない場合、GUI lifetime では Dummy fallback する。 |
| `runtime.allow_dummy` | `bool` | `False` | マクロ実行で Dummy fallback を許可するか。GUI lifetime fallback とは別に扱う。 |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | `allow_dummy=False` で requested target が未選択、検出不能、または open/initialize に失敗した場合。 |
| `ValueError` | device selection policy に未知の device kind など不正な引数を渡した場合。 |
| `ExceptionGroup` | runtime builder shutdown 時に複数 port の close が失敗した場合。現行仕様を維持する。 |

Dummy fallback は失敗を隠す成功扱いにしない。`ResolvedConnection.reason` と log event に fallback reason を残し、GUI は status text または tool log で表示する。

### シングルトン管理

新規 singleton は追加しない。device selection policy は状態を持たない関数として実装し、既存 `singletons.py` への依存は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_discovery_result_excludes_dummy_and_stale_settings` | Discovery 結果に Dummy と保存済み切断デバイスが含まれない。 |
| ユニット | `test_select_serial_target_falls_back_to_dummy_when_requested_missing` | `allow_dummy=True` で missing serial が Dummy fallback になる。 |
| ユニット | `test_select_target_returns_error_when_dummy_not_allowed` | `allow_dummy=False` で missing device が error になる。 |
| ユニット | `test_select_target_distinguishes_auto_dummy_from_user_selected_dummy` | 自動 fallback と明示 Dummy 選択の reason が分かれる。 |
| ユニット | `test_select_target_reconnects_requested_device_after_reload` | 自動 Dummy fallback 中に requested device が復帰した場合、実デバイスへ再選択する。 |
| ユニット | `test_controller_factory_falls_back_to_dummy_on_open_failure_when_allowed` | serial open failure が `allow_dummy=True` で Dummy port になる。 |
| ユニット | `test_frame_factory_falls_back_to_dummy_when_camera_missing` | camera missing が `allow_dummy=True` で Dummy frame source になる。 |
| ユニット | `test_window_source_missing_uses_dummy_for_gui_lifetime` | window source missing が GUI lifetime policy で Dummy frame source になる。 |
| ユニット | `test_macro_execution_still_rejects_missing_device_without_allow_dummy` | macro execution の `allow_dummy=False` では missing device が `ConfigurationError` のままである。 |
| ハードウェア | `test_device_reload_detects_reconnected_capture_device` | `@pytest.mark.realdevice`。切断後に Dummy、再接続後に実デバイスへ復帰する。 |

## 6. 実装チェックリスト

- [ ] `device_selection.py` の値 object と純粋関数のシグネチャを確定する。
- [ ] requested / resolved / fallback reason の状態モデルを実装する。
- [ ] Discovery 結果へ切断済み保存値を混ぜない contract をテストで固定する。
- [ ] GUI lifetime port の missing / open failed を Dummy fallback へ統一する。
- [ ] Macro execution の `allow_dummy=False` 既定を維持する。
- [ ] Window capture source の missing fallback policy を実装する。
- [ ] 数字 capture index fallback を廃止するか、GUI 対象外の明示 legacy path として隔離する。
- [ ] `DeviceDiscoveryService.find_serial()` / `find_capture()` を削除または private 化できるか確認する。
- [ ] `device_factories.py` から requested target 探索分岐を削減し、Port 生成と open/initialize failure handling へ寄せる。
- [ ] 設定ダイアログで切断済み保存値を候補へ再追加しない。
- [ ] ユニットテスト作成・パス。
- [ ] 実機必要テストに `@pytest.mark.realdevice` を付ける。
- [ ] `uv run ruff check src\nyxpy tests\unit` を実行する。

# Connection menu 仕様書

> **対象モジュール**: `src/nyxpy/gui/`, `src/nyxpy/framework/core/settings/`, `src/nyxpy/framework/core/hardware/`
> **目的**: メニューバーに「接続」を追加し、キャプチャ入力、シリアルデバイス、プロトコル、FPS、ボーレートを現在の検出結果から切り替えられるようにする
> **関連ドキュメント**: `spec/agent/complete/local_012/DEVICE_CONNECTION_FALLBACK.md`, `spec/agent/complete/local_006/WINDOW_SIZE_AND_PANEL_LAYOUT.md`
> **既存ソース**: `src/nyxpy/gui/main_window.py`, `src/nyxpy/gui/app_services.py`, `src/nyxpy/gui/dialogs/settings/device_tab.py`, `src/nyxpy/framework/core/hardware/protocol_factory.py`
> **破壊的変更**: あり。`File` menu を廃止する。Settings action はメニューバーへ置かない。

## 1. 概要

### 1.1 目的

GUI のメニューバーに「接続」を追加し、現在の実効接続をチェック付きで表示する。接続先、入力ソース、protocol、FPS、baudrate を設定ダイアログを開かずに切り替えられる経路を増やす。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Connection menu | メニューバーの「接続」タブ。キャプチャ入力、シリアルデバイス、プロトコルを直接の子に持つ。 |
| DeviceDiscoveryService | シリアルデバイス、カメラデバイス、ウィンドウキャプチャ候補を検出する service。 |
| Resolved target | `DEVICE_CONNECTION_FALLBACK.md` の resolver が決定した実効接続先。実デバイスまたは Dummy device である。 |
| QActionGroup | Qt の排他的 action group。入力ソース、デバイス、protocol、FPS、baudrate のチェック制御に使う。 |
| Capture source | `camera` または `window`。`capture_source_type` に保存する。 |
| Serial protocol | `ProtocolFactory` が生成する `SerialProtocolInterface` の種別。 |
| Baudrate | シリアル通信速度。現在選択中の protocol が対応する値だけを候補にする。 |
| Capture FPS | カメラ取得 FPS。`None` は source default として扱う。 |

### 1.3 背景・問題

現状のメニューバーは `File` menu に Settings action、`表示` menu に window size preset を持つ。接続先を切り替えるには設定ダイアログを開く必要があり、現在接続中のデバイスや protocol をメニューバーから確認できない。接続設定を GUI の主要操作として扱うには、File ではなく接続専用 menu に集約する必要がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 接続設定への到達 | File > Settings > 一般 tab | 接続 menu から主要項目を直接切替 |
| 現在接続中の確認 | preview/manual の状態や設定値から推測 | menu action のチェックで確認 |
| 切断済み保存値の表示 | 設定ダイアログで候補に戻る場合がある | 接続 menu には現在検出できる実デバイスと Dummy だけを表示 |
| Protocol と baudrate の整合 | ダイアログ UI 内でのみ既定 baudrate を補正 | menu 操作でも protocol 対応 baudrate へ補正 |

### 1.5 着手条件

- `spec/agent/complete/local_012/DEVICE_CONNECTION_FALLBACK.md` の requested / resolved model を採用する。
- 初期描画時は同期 `detect()` を実行せず、接続 menu を開く時だけ現在候補を更新する方針を採用する。
- `ProtocolFactory.get_descriptor()` の `supported_baudrates` を baudrate menu の正とする。
- 既存の設定ダイアログと各項目は廃止しない。本仕様は設定ダイアログを開かずに変更できる経路を追加する。
- `uv run pytest tests\gui` が着手前に通ること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/gui/main_window.py` | 変更 | `File` menu を廃止し、`接続` menu、チェック状態、設定反映 action を構築する。Settings action はメニューバーへ追加しない。 |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | 接続 menu と同じ列挙方針に合わせ、切断済み保存値を候補へ再追加しない。 |
| `src/nyxpy/framework/core/hardware/protocol_factory.py` | 変更 | menu が protocol 名、既定 baudrate、対応 baudrate を表示できる contract を固定する。 |
| `tests/gui/test_main_window.py` | 変更 | 接続 menu の構造、チェック状態、候補更新、設定反映を確認する。 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

Connection menu は GUI 層の表示・操作部品である。実デバイスの列挙と fallback 判定は framework 層へ委譲し、menu は `DeviceDiscoveryService` の snapshot と selection policy の結果を描画する。`nyxpy.framework.*` から `nyxpy.gui.*` への依存は追加しない。

### 公開 API 方針

外部公開 API は追加しない。接続 menu は `MainWindow` の private method として実装し、構築責務がさらに増えた時点で `connection_menu.py` への分離を検討する。`ProtocolFactory` の descriptor は menu 表示に使うため、protocol 名、既定 baudrate、対応 baudrate の contract をテストで固定する。

### 後方互換性

破壊的変更あり。`File` menu は廃止し、Settings action はメニューバーへ置かない。`表示` menu の window size preset は維持する。設定ファイルの key 名は変更しない。既存の設定ダイアログと各種項目は廃止しない。

### レイヤー構成

`MainWindow` は QAction の生成、チェック状態更新、settings 更新を担当する。接続候補の解決は framework 層の selection policy を使い、実際の builder 再作成と deferred policy は `GuiAppServices.apply_settings()` に残す。新規 controller class は追加せず、現時点の差分を `MainWindow` 内へ閉じてコードベースの肥大化を抑える。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| メニュー表示時の同期 device discovery | device / window 各 1 回以内 |
| メニュー表示時の UI ブロック | 各検出の timeout budget を 2.0 秒以内に制限する |
| menu action 生成数 | 検出デバイス数 + protocol 数 + FPS/baudrate 候補数 + Dummy/status action 数に比例 |
| protocol 変更時の baudrate 補正 | 同一イベント内で完了 |

### 並行性・スレッド安全性

メニュー表示時に `DeviceDiscoveryService.detect()` と `detect_window_sources_result()` を実行し、現在選択中の入力ソースに依存せず候補を更新する。初期描画時は `last_result` と `last_window_sources` の snapshot だけを読み、起動直後の UI 表示をブロックしない。マクロ実行中の接続切替は即時反映せず、既存の `apply_settings(is_run_active=True)` と同じ deferred policy に従う。実装時に操作を無効化する場合も、設定値だけ保存して即時反映されない状態を作らない。

## 4. 実装仕様

### 公開インターフェース

```python
class MainWindow(QMainWindow):
    def _refresh_connection_menu(self, *, refresh_discovery: bool = False) -> None:
        ...

    def _populate_capture_input_menu(
        self,
        menu: QMenu,
        devices: tuple[DeviceInfo, ...],
        windows: tuple[WindowInfo, ...],
    ) -> None:
        ...

    def _populate_serial_device_menu(
        self,
        menu: QMenu,
        devices: tuple[DeviceInfo, ...],
    ) -> None:
        ...

    def _populate_protocol_menu(self, menu: QMenu) -> None:
        ...


def _device_discovery_snapshot(
    discovery: object,
    *,
    refresh: bool = False,
) -> DeviceDiscoveryResult:
    ...


def _window_discovery_snapshot(
    discovery: object,
    *,
    refresh: bool = False,
) -> tuple[WindowInfo, ...]:
    ...
```

`refresh_discovery=False` は初期描画と設定反映後の lightweight refresh 用である。`refresh_discovery=True` は接続 menu を開く時に使い、現在接続可能な camera / serial / window 候補を再取得する。

### Connection menu tree

推奨するメニュー構造は次のとおりである。`接続` の直接の子は `キャプチャ入力`、`シリアルデバイス`、`プロトコル` の 3 つに固定する。FPS はキャプチャ入力の設定、baudrate はシリアルデバイスの接続設定として扱う。

```text
接続
├─ キャプチャ入力
│  ├─ 入力ソース
│  │  ├─ カメラ
│  │  │  ├─ ダミーデバイス
│  │  │  ├─ 自動フォールバック中: <保存値> 未検出  # 必要時だけ disabled 表示
│  │  │  └─ <現在検出できるカメラ...>
│  │  └─ ウィンドウ
│  │     ├─ 自動フォールバック中: <保存値> 未検出  # 必要時だけ disabled 表示
│  │     └─ <現在検出できるウィンドウ...>
│  ├─ FPS
│  │  ├─ source default
│  │  ├─ 15
│  │  ├─ 30
│  │  └─ 60
├─ シリアルデバイス
│  ├─ ダミーデバイス
│  ├─ 自動フォールバック中: <保存値> 未検出  # 必要時だけ disabled 表示
│  ├─ <現在検出できるシリアル...>
│  ├─ ボーレート
│  │  └─ <現在の protocol が対応する baudrate...>
└─ プロトコル
   ├─ CH552
   ├─ PokeCon
   └─ 3DS
```

`File` menu は廃止する。Settings action はメニューバーへ置かない。既存の設定ダイアログは廃止せず、本仕様は接続関連の主要設定をメニューから直接変更できる経路を追加する。`表示` menu は window size preset の責務を維持する。

### メニュー更新ルール

| 操作 | 検出実行 | 設定保存 | Builder 再作成 | 備考 |
|------|----------|----------|----------------|------|
| メニューを開く | 実行する | しない | しない | device / window 候補を現在状態で更新する。window 候補は `capture_source_type` が `camera` でも列挙する。 |
| 実デバイス選択 | しない | requested を保存 | 実行中でなければ即時再作成 | カメラは `キャプチャ入力 > 入力ソース > カメラ`、window は `キャプチャ入力 > 入力ソース > ウィンドウ` から選ぶ。 |
| Dummy 選択 | しない | `DUMMY_DEVICE_NAME` を保存 | 実行中でなければ即時再作成 | 明示 Dummy として自動復帰しない。 |
| Protocol 選択 | しない | protocol を保存 | 実行中でなければ即時再作成 | `接続 > プロトコル` から選ぶ。baudrate が非対応なら protocol 既定値へ補正する。 |
| Baudrate 選択 | しない | baudrate を保存 | 実行中でなければ即時再作成 | `接続 > シリアルデバイス > ボーレート` から選ぶ。候補は protocol の `supported_baudrates` のみ。 |
| FPS 選択 | しない | capture_fps を保存 | 実行中でなければ即時再作成 | preview の一時停止は許容する。hot apply は別仕様に分離する。 |

### チェック状態

| Menu group | チェック対象 | 判定 |
|------------|--------------|------|
| 入力ソース | `camera` / `window` | `capture_source_type` と一致する action。 |
| キャプチャ入力 > 入力ソース > カメラ | Dummy または検出済み camera | `ResolvedConnection.selected` と一致する action。`USER_SELECTED_DUMMY` の場合だけ Dummy action をチェックする。自動 fallback 時は Dummy をチェックせず、disabled status を表示する。 |
| キャプチャ入力 > 入力ソース > ウィンドウ | 検出済み window | `capture_window_identifier` 優先、なければ title で解決した `ResolvedConnection.selected` と一致する action。missing 時はチェックなしで disabled status を表示する。 |
| FPS | source default / 15 / 30 / 60 | `capture_fps` が `None` なら source default。 |
| シリアルデバイス | Dummy または検出済み serial | `ResolvedConnection.selected` と一致する action。`USER_SELECTED_DUMMY` の場合だけ Dummy action をチェックする。自動 fallback 時は Dummy をチェックせず、disabled status を表示する。 |
| シリアルデバイス > ボーレート | 現在 protocol の supported baudrate | `serial_baud` と一致する action。非対応値は既定値へ補正してから表示する。 |
| プロトコル | `ProtocolFactory.get_protocol_names()` | `serial_protocol` と一致する action。 |

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | `camera` または `window`。接続 menu の入力ソースで切り替える。 |
| `capture_device` | `str` | `""` | カメラ入力の requested target。カメラデバイス menu で更新する。 |
| `capture_window_title` | `str` | `""` | window 入力の requested title。ウィンドウ menu で更新する。 |
| `capture_window_identifier` | `str` | `""` | window 入力の requested identifier。ウィンドウ menu で更新する。 |
| `capture_fps` | `float | None` | `None` | カメラ取得 FPS。`None` は source default。 |
| `serial_device` | `str` | `""` | シリアル入力の requested identifier。シリアルデバイス menu で更新する。 |
| `serial_protocol` | `str` | `"CH552"` | `ProtocolFactory` が解決する protocol 名。 |
| `serial_baud` | `int` | `9600` | 現在の protocol が対応する baudrate。protocol 切替時に非対応なら既定値へ補正する。 |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | menu 操作後の settings apply で `allow_dummy=False` の接続解決に失敗した場合。GUI lifetime では fallback spec に従って Dummy へ落とす。 |
| `ValueError` | 未知の protocol 名や対応外 baudrate を内部 API に渡した場合。 |

メニュー操作は失敗を無視しない。設定反映に失敗した場合は tool log と必要な message box で表示し、action のチェック状態は直前の valid snapshot へ戻す。

### シングルトン管理

新規 singleton は追加しない。接続 menu は `MainWindow` が所有し、`GuiAppServices` の lifetime に従う。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI | `test_connection_menu_replaces_file_menu` | `File` menu がなく、`接続` menu の直接の子が `キャプチャ入力`、`シリアルデバイス`、`プロトコル` である。 |
| GUI | `test_connection_menu_lists_snapshot_without_detecting` | 初期描画や明示 refresh なしの menu 更新では同期 `detect()` を呼ばない。 |
| GUI | `test_connection_menu_refresh_detects_window_sources_when_camera_is_active` | 接続 menu を開く更新では、camera 入力が有効でも window 候補を検出して表示する。 |
| GUI | `test_connection_menu_checks_explicit_dummy_actions` | 明示 Dummy 選択時だけ Dummy action にチェックが付く。 |
| GUI | `test_connection_menu_applies_dummy_device_setting` | Dummy action 選択で `DUMMY_DEVICE_NAME` が保存される。 |
| GUI | `test_connection_menu_shows_auto_fallback_without_checking_dummy` | requested が missing の時、Dummy action をチェックせず disabled status を表示する。 |
| GUI | `test_connection_menu_shows_window_auto_fallback_status` | window source missing 時に disabled status を表示する。 |
| GUI | `test_connection_menu_applies_capture_device_setting` | カメラ選択で `capture_device` が保存され、settings apply が走る。 |
| GUI | `test_connection_menu_applies_window_source_setting` | window 選択で `capture_source_type`、title、identifier が保存される。 |
| GUI | `test_connection_menu_protocol_change_clamps_baudrate` | protocol 変更時、非対応 baudrate が既定値へ補正される。 |
| GUI | `test_apply_settings_defers_builder_swap_during_run` | マクロ実行中の設定反映が deferred として扱われる。 |

## 6. 実装チェックリスト

- [x] `File` menu を廃止し、Settings action をメニューバーへ置かない。
- [x] 初期描画では同期 discovery を呼ばず、接続 menu 表示時に現在候補を更新する。
- [x] キャプチャ入力 menu に入力ソース、カメラデバイス、ウィンドウ、FPS を追加する。
- [x] シリアルデバイス menu にデバイス候補、baudrate を追加する。
- [x] プロトコル menu に protocol 候補を追加する。
- [x] Protocol 変更時に baudrate を対応範囲へ補正する。
- [x] マクロ実行中の接続切替を `GuiAppServices.apply_settings()` の deferred policy に従わせる。
- [x] 既存設定ダイアログを残し、候補列挙を接続 menu と同じ方針へ揃える。
- [x] GUI テスト作成・パス。
- [x] `uv run ruff check` と `uv run ty check src\nyxpy --output-format concise --no-progress` を実行する。
- [x] 明示 Dummy 選択 action と自動 Dummy fallback のチェック状態表示を分ける。
- [x] 明示再読み込み action は接続 menu 表示時の現在候補更新へ統合し、独立 action を追加しない判断を仕様へ反映する。
- [x] `connection_menu.py` 分離は現時点では見送り、MainWindow 内の private method に閉じる判断を仕様へ反映する。

### 後続課題

- 接続 menu 表示時の同期検出による UI ブロックが問題化した場合、`GuiAppServices` に非同期候補更新 API を追加し、menu は前回 snapshot を描画して完了通知で更新する。
- 接続 menu 構築がさらに増える場合、`src/nyxpy/gui/connection_menu.py` へ private controller を切り出す。

# キャプチャ入力 GUI 依存可視性と簡素化 仕様書

> **対象モジュール**: `src/nyxpy/gui/`, `src/nyxpy/framework/core/settings/`
> **目的**: `ponkan-python` 未導入環境では直接接続型キャプチャ導線を GUI に表示せず、導入済み環境でも通常設定画面へ露出する項目を利用者が判断すべき最小限へ絞る。
> **関連ドキュメント**: `spec/agent/complete/local_017/PONKAN_CAPTURE_SOURCE.md`, `spec/agent/complete/local_018/CAPTURE_SOURCE_GUI_SETTINGS.md`
> **既存ソース**: `src/nyxpy/gui/dialogs/settings/device_tab.py`, `src/nyxpy/gui/main_window.py`, `src/nyxpy/gui/app_services.py`, `src/nyxpy/framework/core/hardware/ponkan_capture.py`
> **破壊的変更**: なし。既存 settings key は維持し、GUI の表示・保存対象だけを絞る。

## 1. 概要

### 1.1 目的

local_018 で追加した capture source GUI を、通常利用者向けの操作導線として再整理する。`ponkan-python` が現在の Python 環境に入っていない場合は、メニューバーと設定ダイアログの capture 選択肢を不可視にする。導入済み環境では、provider / profile / queue / timeout / timing などの high-level API 詳細を GUI に出さず、N3DSXL capture source の選択と NyX 側の表示補正だけを扱う。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| capture availability | 現在の GUI 実行環境で `ponkan-python` の import package `ponkan` が見つかり、capture source を利用者に選択肢として提示できる状態 |
| optional dependency gate | `ponkan-python` 未導入環境で capture source の GUI 導線を隠す判定 |
| simple capture UI | 通常設定画面に出す capture source の最小 UI。source 選択と N3DSXL HD aspect box だけを含む |
| advanced ponkan settings | `ponkan_backend`、`ponkan_raw_slots`、`ponkan_output_queue_size`、`ponkan_drop_policy`、`ponkan_poll_interval`、`ponkan_read_timeout`、`ponkan_collect_timing` など、設定ファイルでは保持するが通常 GUI には出さない項目 |
| hidden source settings | GUI に表示しないが、既存 settings 値として保持し runtime builder が引き続き読む項目 |

### 1.3 背景・問題

local_018 は `capture` source を GUI から選べる状態にしたが、`ponkan-python` 未導入環境でも「キャプチャ」メニューと設定項目を表示する設計だった。この場合、利用者は GUI 上では選択できるように見えるが、preview 起動時に依存不足で失敗するため、未接続・未認識と誤解しやすい。

また、設定ダイアログには `Capture Provider`、`Device Profile`、`Raw Slots`、`Output Queue Size`、`Drop Policy`、`Poll Interval`、`Read Timeout`、`Collect Timing`、`Ponkan Backend` が直接露出している。これらは `ponkan-python` の high-level API を NyX が内部で使うための調整値であり、通常の GUI 利用者が毎回判断する項目ではない。結果として、キャプチャ入力設定が camera / window と比べて過度に複雑になっている。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 依存未導入環境の capture 導線 | メニューと source combo に表示され、preview 起動時に失敗する | `ponkan` package が見つからない場合はメニュー・source combo に capture を表示しない |
| 通常設定画面の capture 詳細項目数 | 10 項目 | 2 項目以下。source 選択と N3DSXL HD aspect box だけを表示する |
| advanced ponkan settings の扱い | GUI から直接編集する | settings schema と設定ファイル上は維持し、GUI からは原則編集しない |
| 既存設定値の保持 | GUI 操作で hidden combo が上書きされ得る | 非表示項目は GUI apply で上書きしない |
| dependency blast radius | GUI 表示だけで dependency 有無を説明しない | `importlib.util.find_spec("ponkan")` 相当の軽量判定だけで表示可否を決め、`ponkan` 本体は import しない |

### 1.5 着手条件

- local_017 / local_018 が `master` に merge 済みであること。
- 通常 `.venv` に `ponkan-python` が未導入でも GUI テストを実行できること。
- `ponkan` 本体を import せずに dependency availability を判定できること。
- 変更後に `uv run --no-sync ruff check .`、`uv run --no-sync ty check src/nyxpy --output-format concise --no-progress`、対象 GUI pytest が通ること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/gui/app_services.py` | 変更 | GUI 用 capture availability 判定を追加し、capture source が unavailable のときの active source fallback を定義する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | `ponkan` unavailable 時は source combo から capture を除外し、available 時も詳細 ponkan 設定 row を表示しない |
| `src/nyxpy/gui/main_window.py` | 変更 | `ponkan` unavailable 時は接続メニューの `キャプチャ` subtree と `キャプチャ設定` submenu を表示しない。available 時も `Ponkan Backend` submenu は通常表示しない |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更なし | 既存 capture / ponkan settings key は維持する |
| `src/nyxpy/framework/core/hardware/capture_source.py` | 変更なし | hidden advanced settings は設定ファイル値として引き続き runtime に反映する |
| `tests/gui/test_device_settings_tab.py` | 変更 | dependency availability 別の source options と、非表示 ponkan settings を apply で上書きしないことを検証する |
| `tests/gui/test_main_window.py` | 変更 | dependency unavailable 時の capture menu 非表示、available 時の `キャプチャ > N3DSXL (ponkan-python)` 階層、backend submenu 非表示を検証する |
| `tests/gui/test_app_services.py` | 変更 | capture source active かつ dependency unavailable のときに camera へ fallback し、ponkan settings を保持することを検証する |

## 3. 設計方針

### 3.1 アーキテクチャ上の位置づけ

GUI は capture source を「選べるか」を判断するために package availability だけを確認する。`ponkan.open_capture()`、D3XX runtime、実機接続可否は従来どおり framework hardware adapter の責務とする。

依存方向は次を維持する。

| レイヤー | 許可する依存 | 禁止する依存 |
|----------|--------------|--------------|
| `nyxpy.gui` | `importlib.util.find_spec("ponkan")` などの lightweight availability check | `ponkan` 本体 import、device open、D3XX runtime 初期化 |
| `framework/core/hardware` | `ponkan` 遅延 import と capture reader open | GUI widget |
| `framework/core/settings` | settings schema | GUI visibility policy |

### 3.2 Dependency gate 方針

`ponkan-python` 未導入環境では、capture source は「壊れた選択肢」ではなく「利用できない機能」として扱う。GUI は `ponkan` package が見つからない場合、次を実施する。

| UI | unavailable 時の動作 |
|----|----------------------|
| DeviceSettingsTab source combo | `キャプチャ` option を追加しない |
| MainWindow 接続メニュー | `入力ソース > キャプチャ` subtree を追加しない |
| MainWindow キャプチャ設定 | submenu 自体を追加しない |
| Status bar | active source が fallback された場合は camera/window の通常表示に従う |

availability 判定は `find_spec("ponkan") is not None` 相当でよい。これは package の存在確認に限定し、driver runtime や実機接続までは確認しない。`ponkan` が見つかるが D3XX runtime が使えない、または device open に失敗する場合は、従来どおり preview 起動時の `preview_error` として表示する。

### 3.3 Saved capture source の fallback

settings file に `capture_source_type = "capture"` が保存されているが、現在の GUI 実行環境に `ponkan-python` がない場合、GUI 起動時または settings apply 時に active source を `camera` へ戻す。これは dependency unavailable な capture source を選択中にし続けると、不可視の設定が preview failure を起こし続けるためである。

fallback 時の扱いは次のとおりである。

| 設定キー | 扱い |
|----------|------|
| `capture_source_type` | `"camera"` に変更する |
| `capture_provider` | 変更しない |
| `capture_device_profile` | 変更しない |
| `ponkan_*` | 変更しない |
| `n3dsxl_hd_aspect_box_enabled` | 変更しない |
| camera/window settings | 変更しない。ただし既存 stale check の範囲では破棄され得る |

fallback は user log に残す。ログメッセージは、`ponkan-python` を導入すれば capture source を再び選べることが分かる内容にする。

### 3.4 UI 簡素化方針

通常 GUI は provider / profile の設定値を編集対象として見せない。初期対応では support target が N3DSXL + ponkan だけであるため、接続メニューでは `キャプチャ > N3DSXL (ponkan-python)` の階層を残す。これは「キャプチャ」という入力種別と、具体的な capture adapter / device profile を区別して表示するためであり、provider や profile を任意に変更できる UI ではない。保存値は既存どおり `capture_source_type="capture"`、`capture_provider="ponkan"`、`capture_device_profile="n3dsxl"` を設定する。

DeviceSettingsTab の capture 選択時に表示する項目は次に限定する。

| UI control | settings key | 表示理由 |
|------------|--------------|----------|
| Source | `capture_source_type` | camera / window / capture の切替 |
| HD Aspect Box | `n3dsxl_hd_aspect_box_enabled` | NyX 側の座標・表示補正であり、capture reader の低レベル調整ではない |

次の項目は GUI に表示しない。

| settings key | 非表示理由 |
|--------------|------------|
| `capture_provider` | provider は現時点で `ponkan` 固定で、利用者の選択肢ではない |
| `capture_device_profile` | profile は現時点で `n3dsxl` 固定で、利用者の選択肢ではない |
| `ponkan_backend` | driver/backend 調整であり、通常利用者の設定画面から外す。既存設定ファイル値は尊重する |
| `ponkan_raw_slots` | reader queue tuning であり、通常利用者の設定対象ではない |
| `ponkan_output_queue_size` | reader queue tuning であり、通常利用者の設定対象ではない |
| `ponkan_drop_policy` | frame queue policy であり、通常利用者の設定対象ではない |
| `ponkan_poll_interval` | reader loop tuning であり、通常利用者の設定対象ではない |
| `ponkan_read_timeout` | reader timeout tuning であり、通常利用者の設定対象ではない |
| `ponkan_collect_timing` | diagnostics 用であり、通常利用者の設定対象ではない |

`ponkan_backend` を GUI から完全に削除しても、既存 settings value は `capture_source_from_settings()` が読み続ける。backend を切り替えたい開発者は設定ファイルを編集する。将来 GUI に advanced mode を作る場合は、この仕様とは別に「詳細設定表示を明示的に有効化する」仕様を追加する。

### 3.5 メニューバー方針

`ponkan` available 時の接続メニューは次のように簡素化する。

```text
接続
  キャプチャ入力
    入力ソース
      カメラ >
      ウィンドウ >
      キャプチャ >
        N3DSXL (ponkan-python)
    FPS >
      source default
      15
      30
      60
```

`キャプチャ > N3DSXL (ponkan-python)` は leaf action とする。local_018 の `キャプチャ > ponkan > n3dsxl` のように provider と profile を別々の階層として露出する構造は使わない。action trigger は次の settings を更新する。

| 操作 | 更新する settings | 更新しない settings |
|------|-------------------|----------------------|
| `キャプチャ > N3DSXL (ponkan-python)` | `capture_source_type="capture"`、`capture_provider="ponkan"`、`capture_device_profile="n3dsxl"` | `ponkan_backend`、queue、timeout、timing、camera/window settings |

`キャプチャ設定 > Ponkan Backend` は通常表示から削除する。`FPS` submenu は capture source active 時は従来どおり disabled にする。

### 3.6 Runtime 反映方針

runtime builder の内部 key は local_018 の方針を維持する。GUI 非表示になった advanced settings も、設定ファイルから変更された場合は builder 再生成対象であり続ける。つまり `FRAME_SOURCE_SETTING_KEYS` と `_frame_source_key()` から `ponkan_*` を削らない。

GUI の `apply()` は表示していない advanced settings を set しない。これにより、設定ファイルで調整した値を GUI が既定値で上書きしない。

### 3.7 後方互換性

既存 settings key は削除しない。local_018 で保存済みの `capture_provider`、`capture_device_profile`、`ponkan_*`、`n3dsxl_hd_aspect_box_enabled` は引き続き schema と runtime で有効である。

GUI から消すのは表示と編集導線だけであり、設定ファイル互換性は維持する。ただし dependency unavailable 時に `capture_source_type` は `camera` へ fallback するため、`ponkan-python` を後から導入した利用者は再度 GUI で `キャプチャ > N3DSXL (ponkan-python)` を選ぶ必要がある。

### 3.8 シングルトン管理

新規グローバル singleton は追加しない。availability 判定は `GuiAppServices` または GUI widget 初期化時に注入可能な関数として扱い、テストでは fake を渡せる形にする。

## 4. 実装仕様

### 4.1 Availability helper

GUI 用の availability 判定は、`ponkan` を import せずに package の存在だけを見る。

```python
from importlib.util import find_spec


def is_ponkan_capture_available() -> bool:
    return find_spec("ponkan") is not None
```

実装場所は `src/nyxpy/gui/app_services.py` 内の private helper、または `src/nyxpy/gui/capture_availability.py` の小さな module とする。後者にする場合も framework から GUI へ依存させてはならない。

### 4.2 DeviceSettingsTab

`DeviceSettingsTab` は availability を受け取り、source combo の候補を構築する。

```python
class DeviceSettingsTab(QWidget):
    def __init__(
        self,
        settings: GlobalSettings,
        secrets: SecretsSettings,
        parent=None,
        *,
        device_discovery: DeviceDiscoveryService | None = None,
        ponkan_capture_available: bool | None = None,
    ): ...
```

`ponkan_capture_available is None` の場合は default helper を呼ぶ。テストでは bool を直接渡せるようにする。

Source combo の候補は次のとおりである。

| availability | options |
|--------------|---------|
| unavailable | `カメラ`, `ウィンドウ` |
| available | `カメラ`, `ウィンドウ`, `キャプチャ` |

capture available 時も、capture source で表示する row は source row と `n3dsxl_hd_aspect_box_enabled` だけにする。`apply()` は source type が `capture` の場合、次だけを保存する。

```python
self.settings.set("capture_source_type", "capture")
self.settings.set("capture_provider", "ponkan")
self.settings.set("capture_device_profile", "n3dsxl")
self.settings.set(
    "n3dsxl_hd_aspect_box_enabled",
    self.n3dsxl_hd_aspect_box_enabled.isChecked(),
)
```

`ponkan_backend`、queue、drop policy、poll interval、read timeout、collect timing は `apply()` で set しない。

### 4.3 MainWindow 接続メニュー

`MainWindow` は capture availability を参照し、unavailable 時は capture subtree と capture settings submenu を追加しない。

```python
def _populate_capture_source_type_menu(...):
    self._populate_camera_source_menu(...)
    self._populate_window_source_menu(...)
    if self.services.ponkan_capture_available:
        self._populate_direct_capture_source_action(...)
```

`キャプチャ` は `QMenu` として `入力ソース` menu 直下に追加し、その配下に `N3DSXL (ponkan-python)` action を 1 つ置く。provider 名と profile 名を別々の submenu に分ける nested structure は作らない。

`Ponkan Backend` submenu は削除する。既存 attributes は削除してよい。テストや型チェックで参照される場合は期待値を更新する。

### 4.4 GuiAppServices

`GuiAppServices` は availability を保持し、settings apply 前に dependency unavailable な active capture source を camera へ fallback する。

```python
class GuiAppServices:
    @property
    def ponkan_capture_available(self) -> bool: ...

    def _discard_unavailable_connection_settings(self) -> None:
        ...
        if source_type == "capture" and not self.ponkan_capture_available:
            self.global_settings.set("capture_source_type", "camera")
```

この処理は `capture_provider` や `ponkan_*` を消さない。user log には `ponkan-python` extra が未導入であるため capture source を camera に戻したことを残す。

### 4.5 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | GUI からは dependency available 時だけ `"capture"` を選べる |
| `capture_provider` | `str` | `"ponkan"` | GUI では固定値として保存する。通常表示しない |
| `capture_device_profile` | `str` | `"n3dsxl"` | GUI では固定値として保存する。通常表示しない |
| `ponkan_backend` | `str` | `"auto"` | 設定ファイル向け advanced setting。GUI では通常表示しない |
| `ponkan_raw_slots` | `int` | `2` | 設定ファイル向け advanced setting |
| `ponkan_output_queue_size` | `int` | `2` | 設定ファイル向け advanced setting |
| `ponkan_drop_policy` | `str` | `"drop_oldest"` | 設定ファイル向け advanced setting |
| `ponkan_poll_interval` | `float` | `0.004` | 設定ファイル向け advanced setting |
| `ponkan_read_timeout` | `float | None` | `1.0` | 設定ファイル向け advanced setting |
| `ponkan_collect_timing` | `bool` | `false` | 設定ファイル向け diagnostics setting |
| `n3dsxl_hd_aspect_box_enabled` | `bool` | `true` | GUI に表示する NyX 側の表示補正 |

### 4.6 エラーハンドリング

| 例外・状態 | 発生条件 | GUI の扱い |
|------------|----------|------------|
| package unavailable | `find_spec("ponkan") is None` | capture 導線を非表示。active source が capture なら camera へ fallback |
| `NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE` | package はあるが D3XX runtime が使えない | capture 導線は表示する。preview 起動失敗として status bar に表示 |
| `NYX_PONKAN_CAPTURE_OPEN_FAILED` | device open に失敗 | capture 導線は表示する。preview 起動失敗として status bar に表示 |

### 4.7 シングルトン管理

該当なし。新規 singleton は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI | `test_device_settings_tab_hides_capture_option_when_ponkan_unavailable` | availability false では source combo に `capture` item data がない |
| GUI | `test_device_settings_tab_shows_simple_capture_option_when_ponkan_available` | availability true では source combo に `キャプチャ` が表示される |
| GUI | `test_device_settings_tab_shows_only_hd_aspect_for_capture` | capture 選択時に provider/profile/backend/queue/timing row が表示されない |
| GUI | `test_device_settings_tab_does_not_overwrite_hidden_ponkan_settings` | capture apply が `ponkan_backend` などの hidden settings を変更しない |
| GUI | `test_connection_menu_hides_capture_when_ponkan_unavailable` | availability false では `入力ソース` に capture submenu がない |
| GUI | `test_connection_menu_shows_n3dsxl_action_under_capture_when_ponkan_available` | availability true では `キャプチャ > N3DSXL (ponkan-python)` action がある |
| GUI | `test_connection_menu_removes_ponkan_backend_submenu` | `キャプチャ設定 > Ponkan Backend` が表示されない |
| GUI | `test_connection_menu_applies_fixed_ponkan_profile` | capture action trigger で source/provider/profile が固定値として保存される |
| GUI | `test_app_services_falls_back_from_capture_when_ponkan_unavailable` | active capture source かつ availability false で `capture_source_type` が `camera` になる |
| GUI | `test_app_services_preserves_hidden_ponkan_settings_on_fallback` | fallback 時に `ponkan_*` と `n3dsxl_hd_aspect_box_enabled` が保持される |
| GUI | `test_availability_check_does_not_import_ponkan` | availability 判定で `ponkan` 本体が `sys.modules` に入らない |

実機テストは不要である。本仕様は GUI 表示と settings apply の整理であり、`ponkan-python` が導入済みの場合の実機 capture open は local_017 の hardware test scope とする。

## 6. 実装チェックリスト

- [x] local_018 の GUI 露出項目と dependency 未導入時の挙動を確認
- [x] dependency unavailable 時は capture 導線を不可視にする方針を確定
- [x] 通常 GUI から削る advanced ponkan settings を確定
- [x] availability helper を追加
- [x] `DeviceSettingsTab` の source options を availability で分岐
- [x] `DeviceSettingsTab` の capture 表示を source と HD aspect box に限定
- [x] `DeviceSettingsTab.apply()` が hidden ponkan settings を上書きしないよう更新
- [x] `MainWindow` で unavailable 時の capture menu を非表示
- [x] `MainWindow` の capture menu を `キャプチャ > N3DSXL (ponkan-python)` に簡素化
- [x] `MainWindow` から `Ponkan Backend` submenu を通常表示しないよう削除
- [x] `GuiAppServices` で unavailable active capture source を camera fallback
- [x] fallback 時に `ponkan_*` settings を保持
- [x] GUI tests を追加・更新
- [x] `uv run --no-sync ruff format --check .`
- [x] `uv run --no-sync ruff check .`
- [x] `uv run --no-sync ty check src/nyxpy --output-format concise --no-progress`
- [x] `uv run --no-sync pytest tests/gui/test_device_settings_tab.py tests/gui/test_main_window.py tests/gui/test_app_services.py`
- [x] `uv run --no-sync pytest`

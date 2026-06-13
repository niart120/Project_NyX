# N3DSXL GUI キャプチャ入力設定 仕様書

> **対象モジュール**: `src/nyxpy/gui/`, `src/nyxpy/framework/core/settings/`
> **目的**: `n3dsxl` capture source を GUI から選択・設定・再接続できるようにし、`ponkan-python` 統合を利用者の操作導線へ接続する。
> **関連ドキュメント**: `spec/agent/wip/local_017/PONKAN_N3DSXL_CAPTURE_SOURCE.md`, `spec/agent/complete/local_008/SETTINGS_PREVIEW_CAPTURE_REFRESH.md`
> **既存ソース**: `src/nyxpy/gui/dialogs/settings/device_tab.py`, `src/nyxpy/gui/main_window.py`, `src/nyxpy/gui/app_services.py`
> **破壊的変更**: なし。既存 `camera` / `window` source の設定値と操作導線は維持する。

## 1. 概要

### 1.1 目的

local_017 で追加する `n3dsxl` capture source を、GUI 設定ダイアログとメニューバーの「接続」メニューから選べるようにする。GUI は `ponkan` を直接 import せず、framework settings と runtime builder の既存経路を通じて preview / macro runtime に反映する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| DeviceSettingsTab | `src/nyxpy/gui/dialogs/settings/device_tab.py` の一般設定 tab。キャプチャ入力、シリアルデバイス、外観設定を扱う |
| 接続メニュー | `MainWindow` のメニューバーにある「接続」。キャプチャ入力、シリアルデバイス、プロトコルを即時変更する |
| capture source type | settings の `capture_source_type`。`camera` / `window` / `n3dsxl` のいずれか |
| N3DSXL source | `ponkan-python` を利用して new 3DS XL キャプチャボードを読む source。設定値は `n3dsxl_*` prefix で管理する |
| inactive source settings | 現在選択されていない source の保存済み設定。source を戻したときに復元するため GUI が勝手に消さない値 |
| preview frame source | GUI preview が使う `FrameSourcePort`。`GuiAppServices.apply_settings()` が runtime builder 経由で再生成する |

### 1.3 背景・問題

local_017 は `ponkan-python` を framework の `FrameSourcePort` へ接続する仕様である。一方で GUI 側の記述は対象ファイル表にとどまり、利用者が `n3dsxl` をどこで選び、どの設定を編集し、メニューバーからどう切り替えるかが十分に固定されていない。

現行 GUI は `capture_source_type` を `camera` / `window` の 2 値として扱う。`DeviceSettingsTab` の source combo、`MainWindow` の「接続 > キャプチャ入力 > 入力ソース」、`GlobalSettings` schema、`GuiAppServices.FRAME_SOURCE_SETTING_KEYS`、`_frame_source_key()` はいずれも `n3dsxl` を知らない。このまま local_017 の framework 実装だけを追加すると、設定ファイルを直接編集しない限り GUI から N3DSXL source を有効化できない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| GUI からの N3DSXL 選択 | 不可 | 設定ダイアログと接続メニューの両方から `n3dsxl` を選択できる |
| N3DSXL 設定編集 | 不可 | backend、queue、timeout、timing、HD aspect box を GUI で保存できる |
| メニューバー即時切替 | camera/window のみ | `N3DSXL` action で source type を即時反映し、preview を再生成できる |
| inactive source settings | 一部の hidden combo が上書きし得る | `n3dsxl` 選択時に camera/window の保存値を勝手に消さない |
| optional dependency 影響 | 未定義 | `ponkan-python` 未導入でも GUI 起動と設定画面表示は壊れず、preview 接続時だけ失敗を表示する |
| 実機なしテスト | camera/window GUI のみ | fake settings / fake services で N3DSXL GUI 導線を検証できる |

### 1.5 着手条件

- local_017 の `capture_source_type = "n3dsxl"`、`N3DSXLCaptureSourceConfig`、`n3dsxl_*` settings 名が確定していること。
- `ponkan-python` は NyX の `n3dsxl` optional extra に隔離し、GUI module では import しないこと。
- `uv run pytest tests/gui/test_device_settings_tab.py tests/gui/test_main_window.py tests/gui/test_app_services.py` が実行可能であること。
- 変更後に `uv run ruff check .` と `uv run ty check src/nyxpy --output-format concise --no-progress` が通ること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `capture_source_type` choices に `n3dsxl` を追加し、`n3dsxl_*` settings を schema に追加する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | source combo に `N3DSXL` を追加し、n3dsxl 専用設定行の表示・保存を実装する |
| `src/nyxpy/gui/main_window.py` | 変更 | 「接続 > キャプチャ入力」メニューへ `N3DSXL` action と N3DSXL backend submenu を追加し、status bar 表示を更新する |
| `src/nyxpy/gui/app_services.py` | 変更 | N3DSXL 設定を builder 再生成キーに含め、`_frame_source_key()` と stale 設定破棄を source 別に更新する |
| `tests/gui/test_device_settings_tab.py` | 変更 | source combo、表示切替、N3DSXL 設定保存、inactive source 保存値維持を検証する |
| `tests/gui/test_main_window.py` | 変更 | 接続メニューの `N3DSXL` action、backend submenu、status bar、preview 接続失敗表示を検証する |
| `tests/gui/test_app_services.py` | 変更 | N3DSXL keys による builder 再生成、frame source key、stale camera/window 設定を消さないことを検証する |
| `tests/unit/framework/settings/test_settings_schema.py` | 変更 | `n3dsxl_*` settings の既定値、choices、型検証を追加する |

## 3. 設計方針

### 3.1 アーキテクチャ上の位置づけ

GUI は settings の編集と runtime builder の再生成要求だけを担当する。`ponkan` の import、D3XX backend の open、frame 取得 thread は local_017 の framework 層に閉じ込める。

依存方向は次を維持する。

| レイヤー | 許可する依存 | 禁止する依存 |
|----------|--------------|--------------|
| `nyxpy.gui` | `nyxpy.framework.*` の settings / runtime / device discovery | `ponkan` 直接 import |
| `framework/core/settings` | schema 定義 | GUI widget |
| `framework/core/hardware` | `ponkan` 遅延 import | GUI widget |

### 3.2 UI 表示方針

`DeviceSettingsTab` の source combo は表示名と保存値を分ける。settings に保存する値は従来どおり lowercase の `camera` / `window` / `n3dsxl` とし、UI 表示は日本語またはハードウェア名にする。

| 表示名 | item data | 説明 |
|--------|-----------|------|
| `カメラ` | `camera` | 既存 camera device source |
| `ウィンドウ` | `window` | 既存 window capture source |
| `N3DSXL` | `n3dsxl` | new 3DS XL USB capture source |

既存テストが raw text を見ている箇所は item data を正とする期待へ更新する。settings から未知値を読んだ場合は schema 側で既定値へ戻る前提とし、GUI 内で互換 alias は持たない。

### 3.3 Source 別表示

Source に応じて不要な行は非表示にする。非表示の source 用設定は保持し、別 source を選んだだけで保存値を空にしない。

| Source | 表示する項目 | 非表示にする項目 |
|--------|--------------|------------------|
| `camera` | Source、camera device、camera/window 用 letterbox、Capture FPS | Window、Window Match、Window Backend、N3DSXL 設定 |
| `window` | Source、Window、Window Match、Window Backend、camera/window 用 letterbox、Capture FPS | Camera、N3DSXL 設定 |
| `n3dsxl` | Source、N3DSXL Backend、Raw Slots、Output Queue Size、Drop Policy、Poll Interval、Read Timeout、Collect Timing、N3DSXL HD Aspect Box | Camera、Window、Window Match、Window Backend、camera/window 用 letterbox、Capture FPS |

`capture_aspect_box_enabled` は camera/window 用として維持する。N3DSXL は local_017 の `n3dsxl_hd_aspect_box_enabled` を使い、`400x480` から 3DS HD 座標へ合わせる変換の既定値を true にする。

### 3.4 メニューバー方針

既存の「接続 > キャプチャ入力 > 入力ソース」は camera/window 候補を入れ子メニューとして表示している。N3DSXL は device discovery 候補を持たないため、同じ階層に checkable action として追加する。

```text
接続
  キャプチャ入力
    入力ソース
      カメラ >
      ウィンドウ >
      N3DSXL
    N3DSXL Backend >
      auto
      d3xx
      d3xx-native
    FPS >
      source default
      15
      30
      60
```

`N3DSXL Backend` submenu は current source が `n3dsxl` のときだけ有効化する。`FPS` submenu は `camera` / `window` でのみ有効化し、`n3dsxl` では source cadence を `ponkan-python` / reader 設定へ委譲するため無効化または非表示にする。初期実装は既存 menu 構造への影響を抑えるため、無効化でよい。

`N3DSXL` action を実行すると次の settings だけを更新する。

```python
{
    "capture_source_type": "n3dsxl",
}
```

camera/window の選択値は保持する。利用者があとで camera/window に戻したとき、直前の camera device や window title を復元できるようにする。

### 3.5 Runtime 反映方針

`GuiAppServices.FRAME_SOURCE_SETTING_KEYS` に `n3dsxl_*` keys を追加する。実行中に N3DSXL 設定を変更した場合は、既存どおり `deferred=True` として macro run 完了後に反映する。

`_frame_source_key()` は source type ごとに key を分ける。

```python
def _frame_source_key(settings: Mapping[str, Any]) -> tuple[object, ...]:
    source_type = _dotted_get(settings, "capture_source_type", "camera")
    if source_type == "n3dsxl":
        return (
            "n3dsxl",
            _dotted_get(settings, "n3dsxl_capture_backend", "auto"),
            _dotted_get(settings, "n3dsxl_raw_slots", 2),
            _dotted_get(settings, "n3dsxl_output_queue_size", 2),
            _dotted_get(settings, "n3dsxl_drop_policy", "drop_oldest"),
            _dotted_get(settings, "n3dsxl_poll_interval", 0.004),
            _dotted_get(settings, "n3dsxl_read_timeout", 1.0),
            _dotted_get(settings, "n3dsxl_collect_timing", False),
            _dotted_get(settings, "n3dsxl_hd_aspect_box_enabled", True),
        )
```

`capture_device`、`capture_window_title`、`capture_window_identifier` は N3DSXL key に含めない。inactive source の設定変更や stale check が N3DSXL preview を不要に再起動しないようにするためである。

### 3.6 Stale 設定破棄

`GuiAppServices._discard_unavailable_connection_settings()` は source type ごとに stale check を分岐する。

| Source | stale check |
|--------|-------------|
| `camera` | `capture_device` が検出結果にない場合、既存どおり破棄する |
| `window` | window discovery が成功し、保存済み window が解決できない場合だけ破棄する |
| `n3dsxl` | camera/window 設定は破棄しない。serial device の stale check だけ実施する |

N3DSXL は discovery list を持たないため、未検出扱いで `capture_device` を空にする処理に入れてはならない。接続可否は preview frame source の起動結果、つまり `preview_error` で表示する。

### 3.7 Status bar 方針

`MainWindow._update_connection_status()` は `capture_source_type == "n3dsxl"` を明示的に扱う。

| 条件 | 表示 |
|------|------|
| `preview_connection_error is None` | `映像: N3DSXL 接続中` |
| `preview_connection_error is not None` | 既存どおり `映像: 接続失敗 ({error})` |

N3DSXL は camera/window discovery の対象ではないため、`未検出 (ダミーデバイス使用中)` とは表示しない。local_017 の `allow_dummy=True` fallback が発生した場合の user-facing 表示は別途 framework 側の `preview_error` / log に従う。

### 3.8 後方互換性

既存 `camera` / `window` の設定キー、既定値、メニュー動線は維持する。`capture_source_type` の choices 追加は後方互換であり、保存済み settings の migration は不要である。

`ponkan-python` 未導入環境でも GUI 起動、設定ダイアログ表示、source 選択は成功する。N3DSXL preview 起動時に framework が `ConfigurationError(code="NYX_N3DSXL_CAPTURE_DEPENDENCY_MISSING")` を返した場合、GUI は `preview_error` として status bar に表示し、アプリ全体を落とさない。

### 3.9 シングルトン管理

新規グローバル singleton は追加しない。`GuiAppServices` が既存どおり runtime builder と preview frame source の lifetime を所有し、N3DSXL source でも `FrameSourcePortFactory` の cleanup に委譲する。

## 4. 実装仕様

### 4.1 公開インターフェースと設定 schema

```python
GLOBAL_SETTINGS_SCHEMA = SettingsSchema(
    fields={
        "capture_source_type": SettingField(
            "capture_source_type",
            str,
            "camera",
            choices=("camera", "window", "n3dsxl"),
        ),
        "n3dsxl_capture_backend": SettingField(
            "n3dsxl_capture_backend",
            str,
            "auto",
            choices=("auto", "d3xx", "d3xx-native"),
        ),
        "n3dsxl_raw_slots": SettingField("n3dsxl_raw_slots", int, 2),
        "n3dsxl_output_queue_size": SettingField("n3dsxl_output_queue_size", int, 2),
        "n3dsxl_drop_policy": SettingField(
            "n3dsxl_drop_policy",
            str,
            "drop_oldest",
            choices=("drop_oldest", "drop_newest", "block"),
        ),
        "n3dsxl_poll_interval": SettingField("n3dsxl_poll_interval", float, 0.004),
        "n3dsxl_read_timeout": SettingField(
            "n3dsxl_read_timeout",
            (float, type(None)),
            1.0,
        ),
        "n3dsxl_collect_timing": SettingField("n3dsxl_collect_timing", bool, False),
        "n3dsxl_hd_aspect_box_enabled": SettingField(
            "n3dsxl_hd_aspect_box_enabled",
            bool,
            True,
        ),
    }
)
```

範囲制約は local_017 の `capture_source_from_settings()` で検証する。GUI は極端な値を入力しにくい control を使うが、schema だけで数値範囲を保証しようとしない。

### 4.2 DeviceSettingsTab

`DeviceSettingsTab` は source combo の item data を settings value とする helper を持つ。

```python
class DeviceSettingsTab(QWidget):
    def _capture_source_type(self) -> str: ...

    def _set_capture_source_type(self, value: str) -> None: ...

    def _update_source_field_state(self, source_type: str) -> None: ...
```

N3DSXL 設定 row は `QFormLayout` 上で label と widget を保持し、source 切替で一括表示する。Qt version の差を吸収するため、`QFormLayout.setRowVisible()` へ直接依存せず、既存の label/widget `setVisible()` 方針を継続してよい。

| UI control | settings key | control 種別 | 既定値 |
|------------|--------------|--------------|--------|
| N3DSXL Backend | `n3dsxl_capture_backend` | `QComboBox` | `auto` |
| Raw Slots | `n3dsxl_raw_slots` | `QSpinBox` | `2` |
| Output Queue Size | `n3dsxl_output_queue_size` | `QSpinBox` | `2` |
| Drop Policy | `n3dsxl_drop_policy` | `QComboBox` | `drop_oldest` |
| Poll Interval | `n3dsxl_poll_interval` | `QDoubleSpinBox` | `0.004` |
| Read Timeout | `n3dsxl_read_timeout` | `QDoubleSpinBox` | `1.0` |
| Collect Timing | `n3dsxl_collect_timing` | `QCheckBox` | `false` |
| HD Aspect Box | `n3dsxl_hd_aspect_box_enabled` | `QCheckBox` | `true` |

`n3dsxl_read_timeout` の schema は local_017 と同じく `float | None` を許容する。ただし TOML には null がなく、現行 `SettingsStore` は `None` を保存時に省略する。既定値が `1.0` であるため、GUI MVP では `None` を入力 UI に出さず、有限の float 値だけを保存する。無期限待ちを GUI から扱う場合は、別途 `None` の永続化方式を仕様化してから追加する。

`apply()` は source type と active source の設定を保存する。inactive source の combo が空の場合でも、既存 settings 値を空文字で上書きしてはならない。特に `capture_source_type == "n3dsxl"` のときは `capture_device`、`capture_window_title`、`capture_window_identifier`、`capture_backend` を変更しない。

### 4.3 MainWindow 接続メニュー

`MainWindow` に N3DSXL 用 action group を追加する。

```python
class MainWindow(QMainWindow):
    n3dsxl_source_action: QAction | None
    n3dsxl_backend_menu: QMenu | None
    n3dsxl_backend_action_group: QActionGroup | None
```

`_populate_capture_source_type_menu()` は `N3DSXL` checkable action を追加する。checked 判定は `global_settings.get("capture_source_type") == "n3dsxl"` とする。

```python
action.triggered.connect(
    lambda _checked=False: self._apply_connection_settings(
        {"capture_source_type": "n3dsxl"}
    )
)
```

`_populate_capture_input_menu()` は `N3DSXL Backend` submenu を作成し、`n3dsxl_capture_backend` の choices を checkable action として表示する。backend action は source type を `n3dsxl` に切り替えず、backend 値だけを更新する。source 切替は利用者が明示的に `N3DSXL` action を選ぶ操作に限定する。

`FPS` submenu は `capture_source_type == "n3dsxl"` のとき disabled にする。既存 test が menu action 数に依存する場合は、表示順と enabled 状態を期待値へ更新する。

### 4.4 GuiAppServices

`FRAME_SOURCE_SETTING_KEYS` に次を追加する。

```python
N3DSXL_FRAME_SOURCE_SETTING_KEYS = frozenset(
    {
        "n3dsxl_capture_backend",
        "n3dsxl_raw_slots",
        "n3dsxl_output_queue_size",
        "n3dsxl_drop_policy",
        "n3dsxl_poll_interval",
        "n3dsxl_read_timeout",
        "n3dsxl_collect_timing",
        "n3dsxl_hd_aspect_box_enabled",
    }
)
```

既存 `FRAME_SOURCE_SETTING_KEYS` は `N3DSXL_FRAME_SOURCE_SETTING_KEYS` を union する。`_log_setting_changes()` は source type が `n3dsxl` の場合に `キャプチャ入力設定を更新しました: n3dsxl` と出せばよい。初期実装では backend 名まで user log に含めない。

### 4.5 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | `camera` / `window` / `n3dsxl` |
| `n3dsxl_capture_backend` | `str` | `"auto"` | `auto` / `d3xx` / `d3xx-native` |
| `n3dsxl_raw_slots` | `int` | `2` | `ponkan` backend raw read slot 数 |
| `n3dsxl_output_queue_size` | `int` | `2` | decoded frame queue capacity |
| `n3dsxl_drop_policy` | `str` | `"drop_oldest"` | `drop_oldest` / `drop_newest` / `block` |
| `n3dsxl_poll_interval` | `float` | `0.004` | reader loop の待機秒数 |
| `n3dsxl_read_timeout` | `float | None` | `1.0` | `CaptureReader.read()` timeout。`None` は reader thread 内の無期限待ち |
| `n3dsxl_collect_timing` | `bool` | `false` | `ponkan-python` timing samples を有効化する |
| `n3dsxl_hd_aspect_box_enabled` | `bool` | `true` | N3DSXL frame を 3DS HD 座標へ合わせる |

### 4.6 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError(code="NYX_N3DSXL_CAPTURE_DEPENDENCY_MISSING")` | `ponkan-python` 未導入で preview frame source 起動に失敗した |
| `ConfigurationError(code="NYX_N3DSXL_CAPTURE_DEPENDENCY_UNAVAILABLE")` | `ponkan` は import できるが D3XX runtime dependency が使えない |
| `ConfigurationError(code="NYX_N3DSXL_CAPTURE_OPEN_FAILED")` | N3DSXL device open に失敗した |
| GUI 表示用 `preview_error` | `GuiAppServices.apply_settings()` が preview frame source 起動例外を捕捉した |

GUI は上記を握りつぶさない。`MainWindow.apply_app_settings()` は既存どおり `configuration.preview_failed` technical log を残し、preview pane の frame source を `None` にして status bar に接続失敗を表示する。

### 4.7 シングルトン管理

該当なし。新規 singleton は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI | `test_device_settings_tab_source_options_include_n3dsxl` | Source combo の item data が `camera` / `window` / `n3dsxl` である |
| GUI | `test_device_settings_tab_shows_n3dsxl_fields_only_for_n3dsxl` | `n3dsxl` 選択時だけ N3DSXL 設定行を表示し、camera/window 行を隠す |
| GUI | `test_device_settings_tab_applies_n3dsxl_capture_settings` | backend、queue、drop policy、timeout、timing、HD aspect box を settings に保存する |
| GUI | `test_device_settings_tab_preserves_inactive_capture_settings` | `n3dsxl` 選択時に既存 camera/window 設定を空で上書きしない |
| GUI | `test_connection_menu_lists_n3dsxl_source_action` | 「接続 > キャプチャ入力 > 入力ソース」に `N3DSXL` action が表示される |
| GUI | `test_connection_menu_applies_n3dsxl_source_setting` | `N3DSXL` action trigger で `capture_source_type` が `n3dsxl` になり、settings apply が呼ばれる |
| GUI | `test_connection_menu_has_n3dsxl_backend_submenu` | `N3DSXL Backend` submenu に `auto` / `d3xx` / `d3xx-native` が表示され、current backend が checked になる |
| GUI | `test_connection_menu_disables_capture_fps_for_n3dsxl` | `capture_source_type == "n3dsxl"` のとき FPS submenu が disabled になる |
| GUI | `test_status_bar_displays_n3dsxl_capture_state` | preview error なしなら `映像: N3DSXL 接続中` を表示する |
| GUI | `test_status_bar_displays_n3dsxl_preview_error` | preview 起動失敗時に `映像: 接続失敗 (...)` を表示する |
| GUI | `test_app_services_rebuilds_builder_when_n3dsxl_key_changes` | N3DSXL 設定変更が builder 再生成対象になる |
| GUI | `test_app_services_frame_source_key_uses_n3dsxl_settings` | `_frame_source_key()` が N3DSXL keys を含み、camera/window keys を含まない |
| GUI | `test_app_services_keeps_camera_window_settings_for_n3dsxl_source` | N3DSXL source 中は camera/window stale 設定を破棄しない |
| ユニット | `test_global_settings_schema_accepts_n3dsxl_source_type` | schema が `capture_source_type="n3dsxl"` を受け入れる |
| ユニット | `test_global_settings_schema_rejects_invalid_n3dsxl_backend` | `n3dsxl_capture_backend` の choices 外を拒否する |
| ユニット | `test_global_settings_schema_defaults_include_n3dsxl_settings` | `n3dsxl_*` 既定値が local_017 と一致する |

実機テストは local_017 の scope とする。本仕様の GUI テストは fake services / fake settings で完結させ、`ponkan-python` と D3XX driver を要求しない。

## 6. 実装チェックリスト

- [x] GUI 既存 source 選択、接続メニュー、settings apply 経路の調査
- [x] local_017 との責務分担を確定
- [x] GUI から保存する `n3dsxl_*` settings を確定
- [ ] `GlobalSettings` schema に `n3dsxl` と `n3dsxl_*` keys を追加
- [ ] `DeviceSettingsTab` に source item data と N3DSXL 設定行を追加
- [ ] `DeviceSettingsTab.apply()` で inactive source settings を保持
- [ ] `MainWindow` 接続メニューに `N3DSXL` action を追加
- [ ] `MainWindow` 接続メニューに N3DSXL backend submenu を追加
- [ ] `MainWindow._update_connection_status()` を N3DSXL source に対応
- [ ] `GuiAppServices.FRAME_SOURCE_SETTING_KEYS` と `_frame_source_key()` を更新
- [ ] `GuiAppServices._discard_unavailable_connection_settings()` を source 別 stale check に更新
- [ ] GUI tests を追加・更新
- [ ] settings schema tests を追加・更新
- [ ] `uv run ruff check .`
- [ ] `uv run ty check src/nyxpy --output-format concise --no-progress`
- [ ] `uv run pytest tests/gui/test_device_settings_tab.py tests/gui/test_main_window.py tests/gui/test_app_services.py tests/unit/framework/settings/test_settings_schema.py`

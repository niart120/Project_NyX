# GUI 設定・プレビュー・キャプチャ入力見直し仕様書

> **文書種別**: 実装修正仕様。GUI のウィンドウサイズプリセット、設定ダイアログ構成、キャプチャ入力、backend 選択、シリアルデバイス表示を見直す。  
> **対象モジュール**: `src\nyxpy\gui\`, `src\nyxpy\framework\core\hardware\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\settings\`, `tests\gui\`, `tests\unit\framework\`  
> **関連仕様**: `spec\gui\rearchitecture\IMPLEMENTATION_PLAN.md`, `spec\agent\complete\local_006\WINDOW_SIZE_PRESETS.md`, `spec\agent\complete\local_005\WINDOW_CAPTURE_GUI_SETTINGS.md`

## 1. 目的

HD サイズで GUI を使うとプレビュー領域が小さい。現行の既定プリセットは FullHD で、ウィンドウ `1920x1080`、プレビュー `1280x720` である。HD プリセットはウィンドウ `1280x720`、プレビュー `640x360` であり、HD 画面ではキャプチャ内容の確認がしづらい。

設定ダイアログは「一般」「デバイス」「通知」に分かれているが、利用頻度が高いデバイス設定が 2 番目のタブにあり、ログ設定は通知運用と近いのに一般タブへ置かれている。キャプチャ入力は `screen_region` と Region 入力を持つが、今後は GUI から扱う Source を `camera` / `window` に絞る。

本仕様では次を完了状態にする。

- HD プリセットのプレビューを `640x360` から `768x432` へ拡大する。
- 設定ダイアログを「一般」「通知・ログ」の 2 タブ構成へ変更する。
- `screen_region` Source と Region 入力を削除する。
- Source に応じて Camera 系 UI と Window 系 UI を非表示で切り替える。
- `capture_backend = "auto"` は Windows で `windows_graphics_capture`、失敗時に `mss` の順で試す。
- シリアルデバイスの表示名と識別子を分離し、GUI では表示名、settings では識別子を扱う。
- プレビューサイズ変更が仮想コントローラのタッチ座標変換を壊さないことをテストで固定する。

## 2. 現状

### 2.1 ウィンドウサイズ

`src\nyxpy\gui\layout.py` の現行値は次の通り。

| key | 表示名 | ウィンドウ | プレビュー |
|-----|--------|------------|------------|
| `hd` | HD | `1280x720` | `640x360` |
| `full_hd` | FullHD | `1920x1080` | `1280x720` |
| `wqhd` | WQHD | `2560x1440` | `1600x900` |
| `four_k` | 4K | `3840x2160` | `2560x1440` |

既定値は `DEFAULT_WINDOW_SIZE_PRESET_KEY = "full_hd"` である。保存値が未設定または未知値の場合も FullHD に戻る。

### 2.2 設定ダイアログ

現行 `SettingsTabWidget` は次の順でタブを追加する。

| タブ | 主な内容 |
|------|----------|
| 一般 | 外観、ログ |
| デバイス | キャプチャ入力、シリアルデバイス |
| 通知 | Discord、Bluesky |

ログ設定は `logging.file_level` と `logging.command_debug_enabled` を扱う。通知設定は secrets 側の Discord / Bluesky 設定を扱う。

### 2.3 キャプチャ入力

現行 Source は `camera` / `window` / `screen_region` である。`screen_region` は GUI、settings schema、`CaptureSourceConfig`、`FrameSourcePortFactory`、接続状態表示、テストに残っている。

Window Source では `Window`、`Window Match`、`Backend` が使われる。Camera Source では `Camera` が使われる。現在は不要項目を無効化しているだけで、画面上には表示されたままである。

### 2.4 Backend auto

`capture_backend = "auto"` は現行 `_backend_for()` で `mss` と同じ扱いになっている。Windows 環境でも WGC は自動選択されない。

### 2.5 シリアルデバイス

`DeviceInfo` は `name` と `identifier` を持つが、シリアル検出ではどちらも `port.device` を入れている。GUI は `serial_names()` の文字列だけを combo に入れ、`serial_device` へ `currentText()` を保存する。そのため、現在はシリアルデバイスの表示名と識別子を実質的に区別できていない。

Window 候補だけは `display_name` と `identifier` を combo item data で分けて扱っている。

## 3. 設計方針

### 3.1 HD プレビュー拡大

HD プリセットはウィンドウサイズ `1280x720` を維持し、プレビューだけを `768x432` へ拡大する。これは現行 `640x360` から幅・高さとも 1.2 倍で、16:9 を維持する。

HD の左右ペインは縮小して、プレビュー拡大を優先する。

| key | margin | gap | left_width | preview | tool_log_width | bottom_macro_log_height |
|-----|--------|-----|------------|---------|----------------|-------------------------|
| `hd` | `8` | `8` | `220` | `768x432` | `220` | `120` |

この値では横方向の基礎占有は `8*2 + 220 + 768 + 220 + 8*2 = 1240` となり、HD ウィンドウ内に `40` px の余剰が残る。既存仕様通り余剰は左列と右ツールログへ配分し、最終幅は左列 `240`、右ツールログ `240` になる。

FullHD / WQHD / 4K のプレビューサイズは本変更では維持する。

プレビュー領域の実寸は `PreviewPane.preview_widget_point_to_hd_capture_point()` と 3DS タッチ座標変換に使われる。HD プレビュー拡大後も、プレビュー左上・中央・右下付近の入力点が期待する HD キャプチャ座標へ変換され、仮想コントローラ経由の touch down / move / up が同じ座標系で発行されることを GUI テストで確認する。

### 3.2 設定タブ構成

設定ダイアログは 2 タブにする。タブの順序はアクセス頻度を優先し、デバイス設定を先頭に置く。

| 新タブ | 旧タブ由来 | セクション順 |
|--------|------------|--------------|
| 一般 | デバイス + 一般の外観 | キャプチャ入力、シリアルデバイス、外観 |
| 通知・ログ | 通知 + 一般のログ | Discord 通知、Bluesky 通知、ログ |

`GeneralSettingsTab` は最終状態では残さない。外観セクションは新しい一般タブへ移動し、ログセクションは通知・ログタブへ移動する。既存 class を分割移動の一時経路として使う場合も、公開される最終 UI は 2 タブ構成にする。

設定ダイアログのタイトルは `設定` に変更する。

本変更は破壊的変更を許容する。一時的な移行 class、互換 import、旧タブ名 alias、旧 Source alias は最終コミットに残さない。実装中に段階的な作業用経路を置く場合も、同じ作業内で削除し、テストと import を正経路へ揃える。

### 3.3 `screen_region` 廃止

GUI からの Source は `camera` / `window` の 2 種類にする。`screen_region` と Region 入力は削除する。

フレームワークはアルファ版として扱うため、互換 shim は残さない。settings schema、`CaptureSourceType`、`ScreenRegionCaptureSourceConfig`、`ScreenRegionCaptureDevice` 生成経路、関連テストから `screen_region` を削除する。保存済み `.nyxpy` に `capture_source_type = "screen_region"` がある場合は schema 検証で不正値として扱う。

`capture_region` 設定キーは削除する。将来、固定領域キャプチャが必要になった場合は別仕様で再導入する。

`CaptureRect` は削除しない。`WindowInfo`、ウィンドウ探索、mss / WGC のウィンドウ矩形処理で使う汎用的な矩形値オブジェクトであり、固定領域 Source 専用ではない。削除対象は `ScreenRegionCaptureSourceConfig`、`capture_region` parsing、screen region 用 factory / backend 分岐に限定する。

### 3.4 Source 別 UI 表示

Source に応じて不要項目を無効化するのではなく、行ごと非表示にする。ユーザーが現在の Source に必要な項目だけを見られる状態にする。

| Source | 表示する項目 | 非表示にする項目 |
|--------|--------------|------------------|
| `camera` | Source、レターボックス、Camera、Capture FPS | Window、Window Match、Backend |
| `window` | Source、レターボックス、Window、Window Match、Backend、Capture FPS | Camera |

実装では `QFormLayout.addRow()` に渡す label / field を保持し、`setRowVisible()` 相当の helper で行を表示切り替えする。Qt 版の制約で `setRowVisible()` が使えない場合は、label と field container の `setVisible()` を明示的に切り替える。表示切り替え後も settings の既存値は保持し、Source を戻したときに直前の選択を復元する。

レターボックスは単独行にしない。`Source` 行の `QComboBox` 右側へチェックボックスとして置き、Camera / Window のどちらでも同じ行で切り替えられるようにする。`Preview FPS` はキャプチャ入力ではなく外観グループへ移し、ウィンドウサイズプリセットと同じ表示系設定として扱う。

### 3.5 Backend auto fallback

`capture_backend = "auto"` は次の順で backend を選ぶ。

| OS | auto の試行順 |
|----|---------------|
| Windows | `windows_graphics_capture` -> `mss` |
| Windows 以外 | `mss` |

`windows_graphics_capture` が利用できない条件は次を含む。

- OS が Windows ではない。
- Windows 10 1903 未満。
- optional dependency が未導入。
- 対象ウィンドウの取得または session 開始で WGC backend が初期化に失敗した。

auto fallback は silent にしない。WGC から mss に落ちた場合は technical log に `WARNING` で記録し、最終的に mss も失敗した場合は元の例外情報を保持した `ConfigurationError` または backend 例外を返す。

実装方式は `AutoWindowCaptureBackend` を追加する。`_backend_for("auto")` は単一の `MssWindowCaptureBackend` ではなく、OS に応じた候補 backend を持つ auto backend を返す。`"mss"` と `"windows_graphics_capture"` を明示選択した場合は従来通り、その backend だけを使い、失敗しても自動 fallback しない。

auto backend の fallback は session wrapper の `start()` 内で行う。`_ThreadedSessionCaptureDevice` は `create_session()` を `try` の外で呼ぶため、WGC の optional dependency import や platform check を `create_session()` で発生させると fallback できず thread が落ちる。`AutoWindowCaptureBackend.create_session()` は例外を出さず wrapper session を返し、wrapper session が `start()` で WGC session の生成・開始を試す。WGC の初期化または start が失敗した場合だけ mss session を生成・開始し、`latest_frame()` と `stop()` は選択済み session へ委譲する。開始後の `latest_frame()` 失敗は既存の capture loop の失敗処理に任せ、auto fallback の対象にしない。

### 3.6 シリアルデバイス表示名と識別子

シリアルデバイスは GUI 表示名と接続識別子を分離する。

| 値 | 用途 | 例 |
|----|------|----|
| `display_name` | GUI combo と接続状態表示 | `USB Serial Device (COM5)` |
| `identifier` | settings 保存、接続時に `SerialComm` へ渡す値 | `COM5` |

`DeviceInfo` は表示名を明示的に持つ。既存の `name` を残す場合も、最終的な GUI 表示は `display_name`、検索と接続は `identifier` を正とする。

推奨形は次の通り。

```python
@dataclass(frozen=True)
class DeviceInfo:
    kind: DeviceKind
    identifier: str | int
    display_name: str
    api_pref: int | None = None
```

`DeviceDiscoveryResult.serial_names()` は廃止し、GUI は `serial_devices` を直接使って `QComboBox.addItem(display_name, identifier)` する。settings の `serial_device` は識別子を保存する既存キーとして維持する。既存設定ファイルの `serial_device = "COM5"` はそのまま有効である。

`DeviceDiscoveryService._detect_serial_devices()` は `serial.tools.list_ports.comports()` の `device` を `identifier`、`description` または `name` を表示名に使う。表示名には識別子を含め、同名デバイスが複数あっても区別できるようにする。

例:

```text
USB Serial Device (COM5)
Arduino Leonardo (COM7)
```

`ControllerOutputPortFactory` は `serial_device` を display name ではなく identifier として解釈する。`DeviceDiscoveryService.find_serial()` は identifier 一致で検索する。検出結果から `identifier` が一致する `DeviceInfo` を探し、`SerialComm(str(info.identifier))` で接続する。未検出時のエラー表示には display name と identifier の両方を含める。

## 4. 実装対象

| ファイル | 変更内容 |
|----------|----------|
| `src\nyxpy\gui\layout.py` | HD プリセットと HD 用 `LayoutMetrics` を更新 |
| `src\nyxpy\gui\dialogs\app_settings_dialog.py` | ダイアログタイトルを変更 |
| `src\nyxpy\gui\dialogs\settings\tab_widget.py` | 2 タブ構成へ変更 |
| `src\nyxpy\gui\dialogs\settings\device_tab.py` | 外観セクション統合、`screen_region` / Region 削除、Source 別表示切替、Source 行へのレターボックス移動、Preview FPS の外観移動、serial combo の item data 化 |
| `src\nyxpy\gui\dialogs\settings\notification_tab.py` | ログセクション統合、タブ名変更に合わせて責務を通知・ログへ拡張 |
| `src\nyxpy\gui\dialogs\settings\general_tab.py` | 最終的に削除 |
| `src\nyxpy\gui\main_window.py` | `screen_region` 接続状態表示を削除 |
| `src\nyxpy\gui\panes\macro_browser.py` | マクロ一覧テーブルをマクロ名 1 カラムへ整理 |
| `src\nyxpy\gui\panes\log_pane.py`, `src\nyxpy\gui\main_window.py` | コントローラー、マクロログ、ツールログのタイトル行操作部を右揃えに統一 |
| `src\nyxpy\gui\app_services.py` | `capture_region` 変更判定を削除。serial 表示名が必要なログ文言を調整 |
| `src\nyxpy\framework\core\settings\global_settings.py` | `capture_source_type` choices から `screen_region` を削除し、`capture_region` を削除 |
| `src\nyxpy\framework\core\hardware\capture_source.py` | `CaptureRect` は維持し、`ScreenRegionCaptureSourceConfig` と region parsing を削除 |
| `src\nyxpy\framework\core\hardware\window_capture.py` | auto backend fallback を追加。未使用になる `ScreenRegionCaptureDevice` と screen region 型 union を削除 |
| `src\nyxpy\framework\core\hardware\windows_capture_backend.py` | screen region 型 union と `isinstance(ScreenRegionCaptureSourceConfig)` 分岐を削除 |
| `src\nyxpy\framework\core\io\device_factories.py` | screen region 生成経路を削除。serial identifier 検索へ変更 |
| `src\nyxpy\framework\core\hardware\device_discovery.py` | `DeviceInfo` に表示名を持たせ、serial 検出で display name / identifier を分離 |

## 5. テスト方針

| テスト | 検証内容 |
|--------|----------|
| `test_hd_preview_size_is_enlarged` | HD プリセットのプレビューが `768x432` である |
| `test_layout_horizontal_surplus_is_side_panel_width` | HD の左右ペイン配分が新しい値に合う |
| `test_settings_tabs_are_general_and_notification_log` | 設定タブが 2 個で、順に「一般」「通知・ログ」である |
| `test_settings_dialog_title_is_settings` | 設定ダイアログ名が「設定」である |
| `test_hd_preview_touch_mapping_uses_resized_preview_size` | HD プレビュー拡大後も preview point から HD キャプチャ座標への変換が正しい |
| `test_preview_touch_events_use_resized_preview_mapping` | 仮想コントローラの touch down / move / up が拡大後のプレビューサイズを使って座標変換される |
| `test_preview_touch_mapping_handles_letterboxed_widget` | 16:9 から外れた widget サイズでも黒帯を考慮して座標変換する |
| `test_device_settings_tab_source_options_exclude_screen_region` | Source が `camera` / `window` のみである |
| `test_device_settings_tab_hides_irrelevant_source_fields` | Source 別に Camera 行と Window 系行が非表示で切り替わる |
| `test_device_settings_tab_places_letterbox_on_source_row` | レターボックスが単独行ではなく Source 行に表示される |
| `test_device_settings_tab_places_preview_fps_in_appearance_group` | Preview FPS が外観グループに表示される |
| `test_device_settings_tab_applies_window_capture_settings` | Window 設定保存が維持される |
| `test_notification_log_tab_applies_logging_settings` | ログ設定が通知・ログタブから保存される |
| `test_capture_source_rejects_removed_screen_region` | `screen_region` が不正な Source として扱われる |
| `test_frame_source_factory_no_longer_creates_screen_region_source` | screen region 生成経路が存在しない |
| `test_auto_backend_prefers_wgc_on_windows_and_falls_back_to_mss` | Windows auto で WGC 失敗時に mss へ fallback する |
| `test_auto_backend_fallback_occurs_inside_session_start` | WGC import / platform / start 失敗が `create_session()` ではなく session `start()` 内で fallback される |
| `test_explicit_wgc_backend_does_not_fallback` | 明示 `windows_graphics_capture` は失敗しても mss に落とさない |
| `test_serial_devices_expose_display_name_and_identifier` | serial 検出結果が表示名と識別子を分離する |
| `test_device_settings_tab_saves_serial_identifier` | serial combo は表示名を出し、settings には identifier を保存する |
| `test_controller_factory_uses_serial_identifier` | controller factory が display name ではなく identifier で接続する |
| `test_macro_browser_uses_single_name_column` | マクロ一覧テーブルがマクロ名 1 カラムだけを表示する |
| `test_pane_title_controls_are_right_aligned` | コントローラー、マクロログ、ツールログのタイトル行操作部が右揃えである |

既存テストのうち、screen region を前提にした `tests\unit\framework\hardware\test_capture_source.py`、`tests\unit\framework\hardware\test_window_capture.py`、`tests\integration\test_capture_source_runtime.py`、`tests\unit\framework\io\test_device_factories.py`、`tests\unit\framework\settings\test_settings_schema.py`、`tests\gui\test_device_settings_tab.py` の該当ケースは削除または正 API の期待値へ更新する。

## 6. 完了条件

- [x] HD プリセットでプレビューが `768x432` になる。
- [x] 既定プリセットは引き続き FullHD で、`1920x1080` / `1280x720` のままである。
- [x] HD プレビュー拡大後もプレビュークリックと仮想コントローラのタッチ操作が正しい座標へ変換される。
- [x] 設定ダイアログは「一般」「通知・ログ」の 2 タブだけを表示する。
- [x] 設定ダイアログ名は「設定」である。
- [x] レターボックスは Source 行に配置され、単独の Aspect Box 行は残っていない。
- [x] Preview FPS は外観グループに配置される。
- [x] マクロ一覧テーブルはマクロ名 1 カラムだけを表示する。
- [x] コントローラー、マクロログ、ツールログのタイトル行操作部は右揃えで統一される。
- [x] GUI に `screen_region` と Region 入力が表示されない。
- [x] settings schema と factory に `screen_region` 用の生成経路が残らない。
- [x] `auto` backend は Windows で WGC を先に試し、失敗時のみ mss へ fallback する。
- [x] シリアルデバイスは GUI 表示名と settings 保存値を分離して扱う。
- [x] 一時的な互換経路、旧 class、旧 import、旧テスト名が残っていない。
- [x] `uv run ruff check .` と対象テストが通る。

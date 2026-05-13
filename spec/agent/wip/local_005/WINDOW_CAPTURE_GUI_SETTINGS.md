# ウィンドウキャプチャ GUI 設定 仕様書

> **対象モジュール**: `src/nyxpy/gui/`, `src/nyxpy/framework/core/settings/`
> **目的**: ユーザーが GUI からカメラ、ウィンドウ、画面領域の入力ソースを選択し、Preview と Runtime builder へ同じ設定を反映できるようにする。
> **関連ドキュメント**: `spec/agent/wip/local_005/WINDOW_CAPTURE_SOURCE.md`, `spec/agent/wip/local_005/WINDOW_CAPTURE_MVP.md`

## 1. 概要

### 1.1 目的

既存のデバイス設定画面を拡張し、キャプチャ入力ソース種別、対象ウィンドウ、固定画面領域、backend を設定できるようにする。GUI は設定の入力と候補表示だけを担当し、実際の capture device 生成はフレームワーク層の factory に委譲する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| DeviceSettingsTab | キャプチャデバイス、シリアルデバイス、プレビュー FPS を設定する既存 GUI |
| CaptureSourceConfig | framework 側で定義する入力ソース設定 |
| WindowInfo | framework 側のウィンドウ候補情報 |
| FrameTransformConfig | 入力フレームへ 16:9 の黒帯を付与するかを表す設定 |
| PreviewPane | `FrameSourcePort` から取得したフレームを GUI に表示する pane |
| GuiAppServices | settings 変更を runtime builder、preview、manual controller に反映するサービス |
| 入力ソース種別 | `camera` / `window` / `screen_region` の選択値 |

### 1.3 背景・問題

現行 GUI はキャプチャデバイス一覧を `QComboBox` で選択する前提であり、ウィンドウキャプチャや固定領域を設定する入力欄がない。framework 側で MVP を実装しても、GUI から設定できなければユーザーは直接設定ファイルを編集する必要がある。

また、入力ソースの変更は Preview と Runtime builder の双方に影響する。設定反映時に古い frame source を使い回すと、別ウィンドウや別領域へ切り替わらない不具合につながる。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| GUI で選べる入力 | カメラデバイスのみ | カメラ、ウィンドウ、画面領域 |
| 特殊ウィンドウ補正 | 設定不可 | 600x720 などへ左右または上下の黒帯を追加して 16:9 に整える設定が可能 |
| ウィンドウ候補更新 | 未対応 | リロード操作で候補一覧を更新 |
| 設定反映 | `capture_device` 中心 | source type 変更時に Preview / Runtime builder を再生成 |
| ユーザーの設定ファイル手編集 | 必要 | 不要 |

### 1.5 着手条件

- `WINDOW_CAPTURE_MVP.md` の settings schema と factory 接続が実装済みであること。
- `DeviceDiscoveryService` がカメラ候補とウィンドウ候補を分けて返せること。
- GUI 改修は framework へ依存する一方向の関係を維持し、framework から GUI へ依存させないこと。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | GUI から保存する capture source 設定の schema を確認・補完する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | 入力ソース種別、ウィンドウ候補、backend、固定領域 UI を追加する |
| `src/nyxpy/gui/app_services.py` | 変更 | capture source 設定変更時の builder / preview 再生成判定を拡張する |
| `src/nyxpy/gui/main_window.py` | 変更 | 設定反映結果に応じて PreviewPane を安全に差し替える |
| `tests/gui/test_device_settings_tab.py` | 変更 | GUI 設定項目の初期表示・保存を検証する |
| `tests/gui/test_app_services.py` | 変更 | capture source 変更時の builder 再生成を検証する |
| `tests/gui/test_preview_update.py` | 変更 | frame source 差し替え後のプレビュー更新を検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

GUI は framework の `DeviceDiscoveryService` と settings schema を使う composition layer である。GUI は `CaptureSourceConfig` を直接生成せず、settings に値を保存する。runtime builder が settings から `CaptureSourceConfig` を組み立てる。

### 公開 API 方針

GUI 外部へ新しい公開 API は追加しない。`SettingsApplyOutcome` は `capture_device_changed` という名称が入力ソース全体を表せないため、`frame_source_changed` へ改名する。フレームワーク本体はアルファ版のため互換プロパティは残さない。

### 後方互換性

破壊的変更あり。`SettingsApplyOutcome.capture_device_changed` を `frame_source_changed` へ変更する。ただし GUI 内部型であり、マクロや framework 公開 API への影響はない。

### レイヤー構成

| レイヤー | 役割 |
|----------|------|
| settings schema | 保存可能な capture source 設定を定義する |
| `DeviceSettingsTab` | ユーザー入力、候補リロード、設定保存 |
| `GuiAppServices` | 設定変更差分を判定し、runtime builder と preview frame source を再生成 |
| `MainWindow` | PreviewPane と controller への反映 |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| ウィンドウ候補リロード | UI 操作から 2 秒以内。timeout 時は空候補と警告扱い |
| 設定反映 | builder 再生成と preview 差し替えを 1 回に集約 |
| アスペクトボックス設定 | 600x720 入力に対して 16:9 黒帯付与の有効 / 無効を保存できる |
| Preview 停止時間 | source 切替時のみ pause / resume |

### 並行性・スレッド安全性

候補リロードは既存 `DeviceDiscoveryService.detect(timeout_sec=2.0)` の timeout を使い、GUI を長時間ブロックしない。Preview 差し替え時は既存と同じく pause、set frame source、resume の順で実行する。古い builder は `GuiAppServices._shutdown_builder()` で閉じる。

## 4. 実装仕様

### 公開インターフェース

```python
@dataclass(frozen=True)
class SettingsApplyOutcome:
    changed_keys: frozenset[str]
    builder_replaced: bool
    frame_source_changed: bool
    preview_frame_source: FrameSourcePort | None
    manual_controller: ControllerOutputPort | None
    deferred: bool = False
```

`DeviceSettingsTab` は以下の UI を持つ。

| UI | 保存先 | 説明 |
|----|--------|------|
| 入力ソース種別 combo | `capture_source_type` | `camera` / `window` / `screen_region` |
| カメラ候補 combo | `capture_device` | `camera` 選択時に有効 |
| ウィンドウ候補 combo | `capture_window_title`, `capture_window_identifier` | framework が列挙したキャプチャ対象ウィンドウ候補を表示し、`window` 選択時に有効 |
| backend combo | `capture_backend` | `auto` / `mss` / `windows_graphics_capture` |
| 領域入力 | `capture_region` | `screen_region` 選択時に有効。`left` / `top` / `width` / `height` の 4 個の `QSpinBox` で入力する |
| アスペクトボックス checkbox | `capture_aspect_box_enabled` | 有効時は 16:9 になるよう黒帯を中央揃えで追加する |
| FPS combo | `capture_fps` または `preview_fps` | capture FPS と preview FPS の扱いを明示する |

### 内部設計

`DeviceSettingsTab.refresh_capture_devices()` はカメラ候補だけを更新する。`refresh_window_sources()` は framework の `DeviceDiscoveryService.detect_window_sources()` を呼び、キャプチャ対象ウィンドウ候補の表示名と識別子を combo item data に保持する。通常の `detect()` にウィンドウ列挙を混ぜず、既存のカメラ・シリアルリロードを遅くしない。ユーザーがウィンドウ候補を選択した場合、タイトルと識別子を settings へ保存する。GUI は候補を表示するだけで、アクティブウィンドウ判定や OS API への直接アクセスは行わない。

`GuiAppServices.apply_settings()` は以下の keys のいずれかが変更された場合に frame source 変更とみなす。

| key |
|-----|
| `capture_source_type` |
| `capture_device` |
| `capture_window_title` |
| `capture_window_identifier` |
| `capture_window_match_mode` |
| `capture_backend` |
| `capture_region` |
| `capture_fps` |
| `capture_aspect_box_enabled` |

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | 入力ソース種別 |
| `capture_device` | `str` | `""` | カメラ候補 |
| `capture_window_title` | `str` | `""` | ウィンドウ候補のタイトル |
| `capture_window_identifier` | `str` | `""` | ウィンドウ候補の識別子 |
| `capture_window_match_mode` | `str` | `"exact"` | タイトル照合方式 |
| `capture_backend` | `str` | `"auto"` | backend 選択 |
| `capture_region` | `dict[str, int]` | `{}` | 固定領域 |
| `capture_fps` | `float` | source type 依存 | capture thread の目標 FPS |
| `capture_aspect_box_enabled` | `bool` | `false` | 有効時は 16:9 になるよう黒帯を追加する |
| `preview_fps` | `int` | `60` | GUI Preview 更新 FPS |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | 保存済み settings が不正で builder 再生成に失敗した |
| `ExceptionGroup` | 古い builder shutdown に複数失敗がある |

GUI は設定保存時に値の型を可能な範囲で検証する。実際の backend 初期化失敗は framework 側の例外を既存ログ経路へ流す。

### シングルトン管理

新規 singleton は追加しない。`DeviceSettingsTab` は注入された `DeviceDiscoveryService` を使い、`GuiAppServices` が builder lifetime を所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI | `test_device_settings_tab_shows_capture_source_type` | 入力ソース種別 combo が表示される |
| GUI | `test_device_settings_tab_applies_window_capture_settings` | ウィンドウ候補の title / identifier を保存する |
| GUI | `test_device_settings_tab_applies_screen_region_settings` | 固定領域の数値を保存する |
| GUI | `test_device_settings_tab_applies_aspect_box_setting` | アスペクトボックス有効 / 無効を保存する |
| GUI | `test_device_settings_tab_disables_irrelevant_fields` | source type に応じて不要な入力欄を無効化する |
| ユニット | `test_app_services_rebuilds_builder_when_frame_source_key_changes` | frame source 関連 key 変更時に builder を再生成する |
| ユニット | `test_app_services_does_not_rebuild_for_unrelated_setting` | 無関係な設定変更では frame source を差し替えない |
| GUI | `test_main_window_pauses_preview_when_frame_source_changed` | frame source 変更時に PreviewPane を pause / resume する |

## 6. 実装チェックリスト

- [x] settings schema の capture source 項目確認
- [x] `DeviceSettingsTab` の UI 追加
- [x] ウィンドウ候補リロード実装
- [x] 固定領域入力実装
- [x] アスペクトボックス有効 / 無効入力実装
- [x] `SettingsApplyOutcome.frame_source_changed` へ改名
- [x] `GuiAppServices` の変更判定拡張
- [x] `MainWindow` の Preview 差し替え条件更新
- [x] GUI テスト作成・パス
- [x] `uv run ruff check .` パス
- [x] `uv run pytest tests/gui/` パス

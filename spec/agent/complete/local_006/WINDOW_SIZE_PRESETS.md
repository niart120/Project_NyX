# GUI 外観再設計: ウィンドウサイズプリセット詳細仕様

> **文書種別**: 詳細仕様。ウィンドウサイズプリセット、固定プレビューサイズ、レイアウトメトリクス、保存設定を定義する。  
> **親仕様**: `spec\agent\local_006\WINDOW_SIZE_AND_PANEL_LAYOUT.md`  
> **対象モジュール**: `src\nyxpy\gui\layout.py`, `src\nyxpy\gui\main_window.py`, `tests\gui\`

## 1. 方針

ウィンドウサイズは HD / FullHD / WQHD / 4K の規定値だけを許可する。手動リサイズは初期実装では扱わない。各プリセットは、一般的な 16:9 のプレビュー固定サイズを中心に、左列、右マクロログ、プレビュー下ログの寸法を決める。

サイズ値は Qt 論理ピクセルを基準にする。Windows の表示スケール差分は DPI 調査項目として扱い、物理ピクセル完全一致を要件にしない。

## 2. プリセット定義

| key | 表示名 | ウィンドウサイズ | プレビュー固定サイズ | サイズ名 |
|-----|--------|------------------|----------------------|----------|
| `hd` | HD | `1280x720` | `640x360` | 360p |
| `full_hd` | FullHD | `1920x1080` | `1280x720` | 720p |
| `wqhd` | WQHD | `2560x1440` | `1600x900` | 900p |
| `four_k` | 4K | `3840x2160` | `2560x1440` | 1440p |

`full_hd` を既定値にする。`.nyxpy` 配下の保存値が存在しない、または未知値だった場合も `full_hd` に戻す。

## 3. レイアウトメトリクス

| key | margin | gap | left_width | controller_initial_height | preview | macro_log_width | preview_tool_log_height | horizontal_surplus |
|-----|--------|-----|------------|-------------------|---------|-----------------|-------------------------|--------------------|
| `hd` | `8` | `8` | `260` | `220` | `640x360` | `260` | `120` | `88` |
| `full_hd` | `10` | `10` | `280` | `280` | `1280x720` | `320` | `180` | `260` |
| `wqhd` | `12` | `12` | `360` | `320` | `1600x900` | `440` | `240` | `108` |
| `four_k` | `16` | `16` | `420` | `360` | `2560x1440` | `560` | `320` | `236` |

左・中央エリアは 2x2 grid で構成する。row 0 は「マクロ一覧パネル + プレビュー」、row 1 は「仮想コントローラ + プレビュー下ツールログ」とする。仮想コントローラは row 1 の実寸に追従し、`controller_initial_height` はプリセット適用直後の初期目安として扱う。

`horizontal_surplus` は `window_width - (margin * 2 + left_width + preview_width + macro_log_width + gap * 2)` で算出する。余剰幅はプレビュー周囲の空白ではなく、左列と右マクロログへ半分ずつ加算する。プレビュー固定サイズは変更しない。

縦方向はプレビュー高さを基準にする。左・中央 grid の row 0 では `macro_explorer_height = preview_height` とし、マクロ一覧パネルをその高さに固定する。row 1 では仮想コントローラ見出しの上端をプレビュー下ツールログ見出しと揃え、仮想コントローラ本体とプレビュー下ツールログが余剰高さを吸収する。

## 4. 保存設定

| キー | 型 | 既定値 | 説明 |
|------|----|--------|------|
| `gui.window_size_preset` | `str` | `"full_hd"` | 最後に選択したウィンドウサイズプリセット |

保存対象はプリセット key だけにする。ウィンドウ位置、任意サイズ、splitter の手動調整値は本仕様の保存対象にしない。

## 5. UI 入口

- `表示` メニューに HD / FullHD / WQHD / 4K を置く。
- 設定ダイアログにも同じ選択肢を置く。
- メニューと設定ダイアログは同じ適用処理を呼ぶ。
- 現在値と異なるプリセットを選んだ場合、ウィンドウサイズとレイアウトメトリクスを即時適用し、`.nyxpy` に保存する。
- ユーザーが列幅や行高をドラッグ変更できる splitter は使わない。

## 6. テスト

| テスト | 検証内容 |
|--------|----------|
| `test_window_size_presets_are_defined` | 4 種類のプリセットが定義される |
| `test_unknown_window_size_preset_falls_back_to_fullhd` | 未知値が FullHD に戻る |
| `test_preview_sizes_use_standard_16_9_dimensions` | 各プレビューサイズが 16:9 である |
| `test_window_size_menu_updates_settings` | メニュー選択が保存設定へ反映される |
| `test_settings_dialog_updates_window_size_preset` | 設定ダイアログ選択が同じ適用処理を使う |
| `test_layout_horizontal_surplus_is_preview_margin` | 余剰幅が pane 幅へ加算されず中央列余白になる |
| `test_macro_explorer_absorbs_vertical_surplus` | 左列の余剰高さをマクロ一覧パネルが吸収する |


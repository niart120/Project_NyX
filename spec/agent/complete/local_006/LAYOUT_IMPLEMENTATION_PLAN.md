# GUI 外観再設計 実装計画

> **文書種別**: 実装計画。ウィンドウサイズ規定、マクロ一覧パネル、プレビュー/ログ配置を段階的に実装する順序を定義する。  
> **親仕様**: `spec\agent\local_006\WINDOW_SIZE_AND_PANEL_LAYOUT.md`  
> **詳細仕様**: `WINDOW_SIZE_PRESETS.md`, `MACRO_EXPLORER_PANEL.md`, `PREVIEW_AND_LOG_LAYOUT.md`, `VIRTUAL_CONTROLLER_LAYOUT.md`

## 1. 実装方針

レイアウト値を `MainWindow.setup_ui()` に直接埋め込まず、プリセット定義とメトリクスを `src\nyxpy\gui\layout.py` へ分離する。最初にデータ構造とテストを作り、その後 UI の組み替えを進める。

## 2. フェーズ

| フェーズ | 対象 | 内容 | 完了条件 |
|----------|------|------|----------|
| Phase 1 | レイアウト定義 | `WindowSizePreset` と `LayoutMetrics` を追加する | 4 プリセットと固定プレビューサイズの単体テストが通る |
| Phase 2 | 保存設定 | `gui.window_size_preset` を `.nyxpy` 設定へ追加する | 未知値 fallback と保存復元を検証できる |
| Phase 3 | MainWindow | 固定レイアウトで左列、中央列、右列、状態バーを組む | FullHD で `280 + 1280 + 320` の基準配置になり、余剰幅が中央列余白になる |
| Phase 4 | マクロ一覧パネル | 検索を外し、一覧主体 + 操作フッターへ整理する | 接続状態がパネルに出ず、実行系操作が下部に固定される |
| Phase 5 | プレビュー/ログ | プレビュー固定サイズ、右ツールログ、プレビュー下マクロログを適用する | マクロログが仮想コントローラ下へ掛からない |
| Phase 6 | 回帰 | 既存の実行、停止、設定、プレビュー更新を確認する | GUI テストと関連単体テストが通る |
| Phase 7 | 仮想コントローラ | プリセット別固定キャンバスと部品サイズを適用する | FullHD `280x280` でも部品が上下に散らばらず、全プリセットでキャンバス内に収まる |

## 3. 想定変更ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src\nyxpy\gui\layout.py` | 新規。プリセットとメトリクス定義 |
| `src\nyxpy\gui\main_window.py` | レイアウト構成、メニュー、状態バー、設定反映 |
| `src\nyxpy\gui\panes\macro_browser.py` | 検索欄削除、ヘッダー/一覧構造整理 |
| `src\nyxpy\gui\panes\control_pane.py` | 操作フッター化、接続状態表示の削除 |
| `src\nyxpy\gui\panes\preview_pane.py` | 固定 16:9 サイズの適用 |
| `src\nyxpy\gui\panes\log_pane.py` | プレビュー下マクロログと右ツールログの表示分離 |
| `src\nyxpy\gui\panes\virtual_controller_pane.py` | プリセット別固定キャンバス配置 |
| `src\nyxpy\gui\widgets\controller\*.py` | 仮想コントローラ部品の段階サイズ対応 |
| `tests\gui\` | 各 pane と MainWindow のレイアウト検証 |

## 4. 実装上の注意

- 接続状態の常時表示は状態バーに集約する。
- マクロ一覧パネルに接続ボタン、接続状態、再接続ボタンを置かない。
- 設定ダイアログが接続先変更と再接続導線を持つ。足りない場合は設定ダイアログ仕様を別途更新する。
- 仮想コントローラは左列下部で状態バー側に接地する。
- プレビュー下マクロログは中央列のみに配置し、左列下部へ広げない。
- 検索/タグ絞り込みは初期実装に含めない。
- ユーザーが列幅や行高をドラッグ変更できる splitter は初期実装に含めない。
- 実行中と中断要求中はスナップショットを無効化する。
- 仮想コントローラは nested layout の余白分配に依存させず、プリセット別固定キャンバスへ配置する。

## 5. テスト一覧

| テスト | 対象 |
|--------|------|
| `test_window_size_presets_are_defined` | Phase 1 |
| `test_unknown_window_size_preset_falls_back_to_fullhd` | Phase 2 |
| `test_main_window_applies_saved_window_size_preset` | Phase 2-3 |
| `test_macro_search_is_not_rendered_in_initial_layout` | Phase 4 |
| `test_connection_status_is_not_rendered_in_macro_explorer` | Phase 4 |
| `test_status_bar_displays_capture_and_serial_state` | Phase 3 |
| `test_layout_horizontal_surplus_is_preview_margin` | Phase 3 |
| `test_macro_explorer_absorbs_vertical_surplus` | Phase 3 |
| `test_bottom_macro_log_does_not_span_under_controller` | Phase 5 |
| `test_preview_keeps_fixed_16_9_size_for_preset` | Phase 5 |
| `test_virtual_controller_preset_sizes_keep_children_inside_canvas` | Phase 7 |
| `test_virtual_controller_button_sizes_scale_by_preset` | Phase 7 |
| `test_main_window_applies_virtual_controller_preset_metrics` | Phase 7 |


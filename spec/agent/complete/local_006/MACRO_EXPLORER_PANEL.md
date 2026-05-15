# GUI 外観再設計: マクロ一覧パネル詳細仕様

> **文書種別**: 詳細仕様。左列上部のマクロ一覧パネルと操作フッターを定義する。  
> **親仕様**: `spec\agent\local_006\WINDOW_SIZE_AND_PANEL_LAYOUT.md`  
> **対象モジュール**: `src\nyxpy\gui\panes\macro_browser.py`, `src\nyxpy\gui\panes\control_pane.py`, `tests\gui\`

## 1. 目的

左上パネルは「マクロ一覧を選び、下部フッターで実行する」領域にする。VS Code の Explorer のように、一覧を主役にし、実行ボタンや設定入口は下部へ固定する。

## 2. 構成

```text
マクロ一覧パネル
  ├─ ヘッダー
  │   └─ マクロ再読み込み
  ├─ マクロ一覧
  │   ├─ マクロ名
  │   ├─ タグまたは短い説明
  │   └─ 選択状態
  └─ 操作フッター
      ├─ 実行 split button
      ├─ 停止 / 中断
      ├─ スナップショット
      └─ 設定
```

接続状態はこのパネルに置かない。キャプチャとシリアルの状態は状態バーへ集約する。接続先変更や再接続は設定ダイアログから行う。

## 3. 初期実装で扱わないもの

| 項目 | 扱い |
|------|------|
| マクロ検索 | 現状の有効性が低いため、初期レイアウトから外す |
| タグ絞り込み | 別仕様で検討する |
| 詳細ペイン | 別仕様で検討する |
| 一時停止 / 再開 | Runtime 側の要件が固まるまで置かない |
| 接続 / 再接続ボタン | 設定ダイアログへ統一し、フッターには置かない |
| ウィンドウサイズプリセット表示 | 表示メニューと設定ダイアログに任せ、マクロ一覧ヘッダーには置かない |

## 4. 現行との差分

| 項目 | 現行 | 再設計後 |
|------|------|----------|
| 検索ボックス | `MacroBrowserPane` 上部にある | 初期実装では削除 |
| 再読み込み | 検索行に同居 | ヘッダー右側へ移動 |
| マクロ一覧 | `マクロ名` / `説明文` / `タグ` の 3 列 | 一覧を主役にし、HD では説明文を省略 |
| 実行 | `ControlPane` に横並び | 操作フッター左上に固定し、他の操作ボタンと高さを揃える |
| 停止 | `キャンセル` 表示 | 実行状態に応じて `停止` / `中断要求中` を明確にする |
| 設定 | `ControlPane` の右端 | 操作フッター末尾に固定 |

## 5. 状態別表示

| 状態 | 実行 | 停止 / 中断 | スナップショット | 設定 |
|------|------|-------------|------------------|------|
| マクロ未選択 | 無効 | 無効 | 有効 | 有効 |
| 実行可能 | 有効 | 無効 | 有効 | 有効 |
| 実行中 | 無効 | 有効 | 無効 | 無効 |
| 中断要求中 | 無効 | 無効 | 無効 | 無効 |

## 6. テスト

| テスト | 検証内容 |
|--------|----------|
| `test_macro_explorer_footer_keeps_run_controls_visible` | 実行系ボタンが一覧下部に固定される |
| `test_macro_search_is_not_rendered_in_initial_layout` | 初期レイアウトに検索ボックスが出ない |
| `test_connection_status_is_not_rendered_in_macro_explorer` | 接続状態がマクロ一覧パネルに出ない |
| `test_macro_explorer_footer_disables_settings_while_running` | 実行中に設定入口が無効化される |
| `test_macro_explorer_footer_disables_snapshot_while_running` | 実行中にスナップショットが無効化される |
| `test_macro_explorer_footer_uses_2x2_grid_for_all_presets` | 全プリセットで操作フッターが 2x2 配置になる |
| `test_macro_explorer_footer_unifies_control_button_height` | split button の実行と他の操作ボタンの高さが揃う |


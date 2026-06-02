# マクロ一覧表示の階層化と検索切替 仕様書

> **文書種別**: 詳細仕様。GUI のマクロ一覧 pane を Explorer / Search 切替と階層表示へ拡張する。
> **作業ブランチ**: `docs/macro-explorer-tree-search`
> **対象モジュール**: `src\nyxpy\gui\panes\macro_browser.py`, `src\nyxpy\gui\macro_catalog.py`, `src\nyxpy\gui\`, `tests\gui\`
> **関連仕様**: `spec\agent\complete\local_006\MACRO_EXPLORER_PANEL.md`, `spec\agent\complete\local_008\SETTINGS_PREVIEW_CAPTURE_REFRESH.md`, `spec\gui\rearchitecture\IMPLEMENTATION_PLAN.md`
> **元 dev-journal**: `2026-05-17: マクロ一覧表示の階層化と検索切替`

## 1. 概要

### 1.1 目的

マクロ数が増えた場合でも、GUI 左上のマクロ一覧 pane で配置場所とメタデータの関係を失わずに目的のマクロを選択できる状態にする。通常時は配置場所に基づく Explorer 表示、検索時はマクロ名、説明文、タグ名に基づく Search 表示へ切り替え、実行対象の stable `macro_id` 選択契約を維持する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| MacroBrowserPane | GUI 左上のマクロ一覧 pane。現行は `QTableWidget` 1 列でマクロ名を表示する。 |
| MacroCatalog | GUI 表示用に `MacroDefinition` を stable ID で保持する catalog。 |
| MacroDefinition | registry が読み込んだマクロ定義。`id`, `display_name`, `macro_root`, `source_path`, `description`, `tags` を持つ。 |
| Explorer view | マクロの配置場所を軸に階層表示する通常表示。 |
| Search view | 検索語に一致するマクロを flat list で表示する検索表示。 |
| search token | 空白で分割した検索語。マクロ名、`macro_id`、class name、説明文、タグ名に照合する。 |
| tag filter | `tag:<query>` または `#<query>` 形式でタグ名だけに照合する検索 token。 |

### 1.3 背景・問題

`spec\agent\complete\local_008\SETTINGS_PREVIEW_CAPTURE_REFRESH.md` では、HD レイアウトでの情報密度を優先し、マクロ一覧は `マクロ名` 1 カラムへ縮約した。現行 `src\nyxpy\gui\panes\macro_browser.py` はその通り `QTableWidget(0, 1)` を使い、説明文とタグは tooltip に退避している。

一方で、マクロが増えると単純な名前順テーブルでは、workspace のローカルマクロ、公開 examples、将来の追加 search root、タグの関係が見えにくい。初期外観仕様では検索を外したが、探索性を戻すには検索 box を常時表示するのではなく、Explorer / Search の表示切替として責務を分ける必要がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 通常表示で確認できる分類軸 | 名前順のみ | source root と配置 path |
| 検索対象 | なし | `display_name`, `id`, `class_name`, `description`, `tags` |
| マクロ選択値 | `QTableWidgetItem.UserRole` の `macro_id` | view 切替後も stable `macro_id` |
| タグ探索 | tooltip 表示のみ | Search view の検索対象 |
| HD pane での常時占有 UI | 検索 box なし | Explorer / Search 切替のみ常時表示し、検索入力は Search view 内に限定 |

### 1.5 着手条件

- `MacroDefinition.id` を GUI 実行 ID として使う仕様が実装済みである。
- `MacroDefinition.tags` と `display_name` が `MacroBase` または `macro.toml` 由来で取得できる。
- `MacroBrowserPane.selected_macro_id()` が table cell text ではなく item data から ID を返している。
- `spec\agent\complete\local_006\MACRO_EXPLORER_PANEL.md` の「接続状態をマクロ一覧 pane に置かない」方針を維持する。

### 1.6 確定事項

dev-journal からの仕様化時点で次の方針を確定する。

| 項目 | 方針 |
|------|------|
| Explorer の階層軸 | 配置場所を主軸にする。タグ別 virtual folder は作らない。 |
| UI 表示名 | 切替ラベルは英名の `Explorer` / `Search` とする。 |
| Search の照合対象 | `display_name`, `id`, `class_name`, `description`, `tags` を対象にする。 |
| tag filter | `tag:<query>` と `#<query>` によるタグ専用検索を実装する。 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src\nyxpy\gui\macro_catalog.py` | 変更 | `MacroDefinition` から GUI 表示用の location metadata を取得できる helper を追加する。 |
| `src\nyxpy\gui\macro_explorer_model.py` | 新規 | Explorer tree と Search result を構築する純粋ロジックを置く。 |
| `src\nyxpy\gui\panes\macro_browser.py` | 変更 | `QTableWidget` 1 列から Explorer / Search 切替 UI、tree view、search result view へ置き換える。 |
| `src\nyxpy\gui\main_window.py` | 変更なし | `selected_macro_id()` と `selection_changed` 契約を維持するため、通常は変更しない。 |
| `tests\gui\test_macro_catalog.py` | 変更 | location metadata と既存 stable ID 契約を検証する。 |
| `tests\gui\test_macro_explorer_model.py` | 新規 | 階層構築、検索 token、並び順、選択維持の純粋ロジックを検証する。 |
| `tests\gui\test_macro_browser_pane.py` | 新規 | Qt widget と signal、view 切替、reload 後の選択維持を検証する。既存 test が `test_macro_catalog.py` に同居している場合は分離する。 |
| `spec\agent\complete\local_016\MACRO_EXPLORER_HIERARCHY_AND_SEARCH.md` | 新規 | 本仕様書。 |
| `spec\dev-journal.md` | 変更 | 仕様へ昇格した dev-journal エントリを削除する。 |

## 3. 設計方針

### 3.1 アーキテクチャ上の位置づけ

Explorer / Search は GUI adapter の表示モデルであり、framework registry の探索仕様を変更しない。`MacroRegistry` は引き続き `MacroDefinition` を列挙するだけに留め、階層 node、検索 score、選択状態は `nyxpy.gui` 側で扱う。

GUI 層だけが Qt widget に依存する。階層構築と検索判定は `macro_explorer_model.py` の純粋関数として分離し、`Command`、Runtime、hardware port、Qt widget に依存させない。

### 3.2 Explorer view

Explorer view は配置場所を主軸にする。階層は次の順で構築する。

1. `MacroCatalog` が registry の `macro_search_roots` と `MacroDefinition.macro_root` / `source_path` から source root label を決定する。
2. source root が 1 つだけの場合、root label は表示せず、配下の path node から始める。
3. source root が複数ある場合、先頭に `workspace`、`examples`、`external` などの root node を表示する。
4. `MacroDefinition.macro_root` が search root 直下の package である場合は、余分な package folder を作らず leaf として表示する。
5. nested path がある場合は path segment を folder node として表示する。
6. leaf は `display_name` を主表示、tooltip に `id`, `class_name`, `description`, `tags` を表示する。

現行 `MacroRegistry.reload()` は search root 直下だけを探索する。本仕様は registry の recursive discovery を追加しない。将来 registry が nested discovery を扱う場合でも、Explorer view は `MacroDefinition.macro_root` から相対 path を組み立てるため、GUI 側の基本設計を変えずに追従できる。

### 3.3 Search view

Search view は query 入力と flat result list で構成する。検索語は `str.casefold()` と前後空白除去で正規化し、空白区切り token を AND 条件で照合する。

| token 形式 | 照合対象 |
|------------|----------|
| `abc` | `display_name`, `id`, `class_name`, `description`, `tags` の部分一致 |
| `tag:abc` | `tags` の部分一致 |
| `#abc` | `tag:abc` と同じ扱い |

空 query では全マクロを flat list で表示する。Search view へ入った時点で既存選択がある場合は、その macro を result list 上でも選択する。query 変更後に選択中 macro が結果から外れた場合、選択を解除し `selection_changed(False)` を emit する。

検索結果は次の score 降順、同点時は `(display_name.casefold(), id)` 昇順で並べる。

| score | 条件 |
|-------|------|
| 100 | `display_name`, `id`, `class_name` の完全一致 |
| 80 | `display_name`, `id`, `class_name` の前方一致 |
| 70 | tag 完全一致 |
| 50 | tag 前方一致 |
| 30 | `display_name`, `id`, `class_name`, tag の部分一致 |
| 20 | `description` の部分一致 |

複数 token がある場合は token ごとの最大 score の合計を macro の score とする。`tag:` token は `tags` だけへ照合し、`display_name`, `id`, `class_name`, `description` へ照合しない。

### 3.4 UI 構成

`MacroBrowserPane` は次の構成にする。

```text
マクロ pane
  ├─ ヘッダー
  │   ├─ タイトル: マクロ
  │   ├─ 表示切替: Explorer / Search
  │   └─ リロード
  ├─ QStackedWidget
  │   ├─ Explorer
  │   │   └─ 階層 tree
  │   └─ Search
  │       ├─ query input
  │       └─ result list
  └─ 操作フッター
      └─ 既存 ControlPane 側に維持
```

切替 UI は pane header 内の checkable `QToolButton` または同等の segmented control とする。`Search` を選んだ場合だけ query input を表示する。HD レイアウトで常時検索 box を表示しない。

`リロード` は現在の view mode と query を維持する。reload 後も同じ `macro_id` が存在する場合は再選択し、存在しない場合は選択解除する。

### 3.5 選択契約

`MacroBrowserPane` の外部契約は維持する。

```python
class MacroBrowserPane(QWidget):
    selection_changed = Signal(bool)

    def selected_macro_id(self) -> str | None: ...
    def selected_macro_display_name(self) -> str | None: ...
    def update_macro_view(self) -> None: ...
```

Explorer view と Search view の内部 widget が異なっても、選択値は pane が保持する `selected_macro_id` を正とする。`MainWindow` は view mode、tree row、list row を知らない。選択変更時は次の順で処理する。

1. item data から `macro_id` を読む。
2. `MacroCatalog.get(macro_id)` で definition が存在することを確認する。
3. pane の `self._selected_macro_id` を更新する。
4. `selection_changed(True)` を emit する。

folder node、root node、検索結果 0 件 placeholder は実行対象ではない。これらを選択しても `selected_macro_id()` は `None` を返す。

### 3.6 後方互換性

破壊的変更あり。`MacroBrowserPane.table` を直接参照する GUI テストや内部コードは tree / list API へ更新する。外部契約として維持するのは `selected_macro_id()`, `selected_macro_display_name()`, `selection_changed`, `reload_button` の操作結果だけである。

旧テーブル表示、旧検索 box、互換 alias は残さない。アルファ版方針に従い、呼び出し元とテストを同一変更で正 API へ更新する。

### 3.7 性能要件

| 指標 | 目標値 |
|------|--------|
| 100 件のマクロで Explorer tree 構築 | 50 ms 未満 |
| 100 件のマクロで Search query 更新 | 50 ms 未満 |
| reload 後の選択復元 | 追加 I/O なし。reload 済み catalog 内で完結 |
| UI thread blocking | registry reload 以外で filesystem I/O を行わない |

### 3.8 並行性・スレッド安全性

`MacroBrowserPane` は Qt UI thread 上で動作する。検索と tree 構築は catalog snapshot に対する同期処理とし、background thread は追加しない。`MacroRegistry.reload()` の thread safety は registry 側の lock に委譲する。検索中に catalog reload が起きた場合は、reload 完了後の snapshot で view model を再構築する。

## 4. 実装仕様

### 4.1 表示モデル

`macro_explorer_model.py` に GUI 非依存の model を置く。

```python
from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.macro.registry import MacroDefinition


@dataclass(frozen=True)
class MacroLocation:
    root_label: str
    relative_parts: tuple[str, ...]


@dataclass(frozen=True)
class MacroExplorerNode:
    label: str
    macro_id: str | None
    children: tuple["MacroExplorerNode", ...] = ()


@dataclass(frozen=True)
class MacroSearchResult:
    macro_id: str
    display_name: str
    score: int
    matched_tags: tuple[str, ...]


def location_for_definition(definition: MacroDefinition, roots: tuple[Path, ...]) -> MacroLocation:
    ...


def build_explorer_tree(
    definitions: tuple[MacroDefinition, ...],
    roots: tuple[Path, ...],
) -> tuple[MacroExplorerNode, ...]:
    ...


def search_macros(
    definitions: tuple[MacroDefinition, ...],
    query: str,
) -> tuple[MacroSearchResult, ...]:
    ...
```

`MacroExplorerNode.macro_id is None` は folder node を表す。leaf node は `macro_id` を持ち、children を持たない。`display_name`、tooltip 用 metadata は `MacroCatalog.get(macro_id)` から取得する。

### 4.2 MacroCatalog

`MacroCatalog` は root 情報を GUI 表示用に公開する。

```python
class MacroCatalog:
    definitions_by_id: dict[str, MacroDefinition]

    def list(self) -> list[MacroDefinition]: ...
    def get(self, macro_id: str) -> MacroDefinition: ...
    def search_roots(self) -> tuple[Path, ...]: ...
```

`search_roots()` は `registry.macro_search_roots` がある場合は各 `macros_dir` を返し、ない場合は `registry.macros_dir` を返す。fake registry でも使えるよう、属性がなければ空 tuple を返す。空の場合、`location_for_definition()` は `definition.macro_root` の親を root とみなす。

### 4.3 MacroBrowserPane

`MacroBrowserPane` は内部状態として `view_mode`, `query`, `selected_macro_id` を持つ。

```python
class MacroBrowserPane(QWidget):
    def set_view_mode(self, mode: Literal["explorer", "search"]) -> None: ...
    def set_search_query(self, query: str) -> None: ...
    def selected_macro_id(self) -> str | None: ...
    def selected_macro_display_name(self) -> str | None: ...
```

表示更新は `update_macro_view()` に集約する。既存 `update_macro_table()` は削除する。`on_reload_button_clicked()` は次を行う。

1. 現在の `selected_macro_id`, `view_mode`, `query` を保存する。
2. `catalog.reload_macros()` を呼ぶ。
3. `update_macro_view()` で Explorer tree と Search result を再構築する。
4. 保存した `selected_macro_id` が残っていれば再選択する。
5. 残っていなければ選択解除し、`selection_changed(False)` を emit する。

### 4.4 Tooltip と補助表示

leaf tooltip は次の順で組み立てる。

```text
{display_name}
ID: {id}
Class: {class_name}
Tags: {tag1, tag2}
{description}
```

空の値は行を省略する。Search result は `display_name` を主表示し、タグ一致がある場合は行内の補助 text または tooltip に `#tag` を表示する。HD レイアウトで文字が詰まる場合は tooltip に退避し、pane 幅を広げるための固定幅変更は行わない。

### 4.5 Keyboard 操作

| 操作 | 動作 |
|------|------|
| `Ctrl+F` | Search view へ切り替え、query input に focus する。 |
| `Esc` in Search query | query が空でなければ clear する。空なら Explorer view へ戻る。 |
| `Enter` in Search result | 選択中 macro を維持し、実行は ControlPane の実行 button に委譲する。 |
| `Up` / `Down` | 現在 view 内の選択を移動する。folder node は実行対象にしない。 |

`Enter` で即実行しない。マクロ実行の明示操作は既存通り ControlPane に集約する。

### 4.6 エラーハンドリング

| 事象 | 表示 / 動作 |
|------|-------------|
| reload で macro load diagnostic が発生 | 既存 registry diagnostics の扱いに従い、一覧には読み込めた macro だけを表示する。 |
| Search query が `tag:` または `#` だけ | tag filter の空 token とみなし、結果 0 件ではなく全件表示する。 |
| `MacroCatalog.get(macro_id)` が失敗 | 選択を解除し、`selection_changed(False)` を emit する。 |
| folder node が選択された | `selected_macro_id()` は `None` を返す。 |

新規例外クラスは追加しない。UI status へ内部 traceback を出さない。

### 4.7 シングルトン管理

該当なし。新規 singleton は追加しない。`MacroCatalog` と表示 model は `MainWindow` / pane の lifetime に従う。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI model | `test_build_explorer_tree_groups_by_macro_location` | `macro_root` の相対 path から folder node と leaf node を構築する。 |
| GUI model | `test_build_explorer_tree_omits_single_root_label` | search root が 1 つだけの場合、root label を表示しない。 |
| GUI model | `test_build_explorer_tree_keeps_multiple_root_labels` | 複数 search root の場合、root node を表示する。 |
| GUI model | `test_search_macros_matches_display_name_and_macro_id` | plain token が `display_name` と `id` に一致する。 |
| GUI model | `test_search_macros_matches_description` | plain token が `description` に一致する。 |
| GUI model | `test_search_macros_matches_tags` | plain token が tag に一致する。 |
| GUI model | `test_search_macros_supports_tag_filter` | `tag:` と `#` が tag だけへ照合される。 |
| GUI model | `test_search_macros_uses_and_between_tokens` | 複数 token が AND 条件になる。 |
| GUI model | `test_search_macros_orders_by_score_then_display_name` | score と安定 sort が仕様通りである。 |
| GUI | `test_macro_browser_defaults_to_explorer_view` | 初期表示が Explorer view で、検索 input が常時表示されない。 |
| GUI | `test_macro_browser_switches_to_search_view` | Search 切替で query input と result list が表示される。 |
| GUI | `test_macro_browser_selection_returns_macro_id_in_explorer` | Explorer leaf 選択で stable `macro_id` を返す。 |
| GUI | `test_macro_browser_selection_returns_macro_id_in_search` | Search result 選択で stable `macro_id` を返す。 |
| GUI | `test_macro_browser_folder_selection_is_not_runnable` | folder node 選択時に `selection_changed(False)` になる。 |
| GUI | `test_macro_browser_reload_preserves_mode_query_and_selection` | reload 後も mode、query、存在する選択が維持される。 |
| GUI | `test_macro_browser_reload_clears_missing_selection` | reload 後に macro が消えた場合、選択が解除される。 |
| GUI | `test_macro_browser_ctrl_f_focuses_search` | `Ctrl+F` で Search view に切り替わる。 |
| GUI | `test_macro_browser_search_escape_clears_or_returns_to_explorer` | `Esc` の二段階動作を検証する。 |
| GUI | `test_macro_browser_does_not_render_connection_state` | マクロ一覧 pane に接続状態が表示されない。 |

## 6. 実装チェックリスト

- [x] ユーザ確認事項を確定する。
- [x] `MacroCatalog.search_roots()` を追加する。
- [x] `macro_explorer_model.py` を追加し、階層構築と検索を純粋関数で実装する。
- [x] `MacroBrowserPane` を Explorer / Search 切替 UI へ置き換える。
- [x] `selected_macro_id()` と `selection_changed` の外部契約を維持する。
- [x] reload 後の view mode、query、選択復元を実装する。
- [x] keyboard 操作を実装する。
- [x] 旧 `update_macro_table()` と table 直接参照テストを削除または正 API へ更新する。
- [x] GUI model のユニットテストを追加する。
- [x] GUI widget テストを追加する。
- [x] `uv run ruff check src\nyxpy\gui tests\gui` を実行する。
- [x] `uv run pytest tests\gui\test_macro_catalog.py tests\gui\test_macro_explorer_model.py tests\gui\test_macro_browser_pane.py` を実行する。

## 7. 完了ゲート

| ゲート | 判定 |
|--------|------|
| Stable identity gate | Explorer / Search のどちらでも `selected_macro_id()` が stable `MacroDefinition.id` を返す。 |
| Location gate | Explorer view が配置場所を階層として表示する。 |
| Search gate | Search view が名前、説明文、タグに基づいて結果を返し、空 query で全件を表示する。 |
| Layout gate | HD pane で検索 input が常時表示されず、切替 UI と reload が header 内に収まる。 |
| Runtime isolation gate | GUI 表示 model が Runtime、Command、hardware port に依存しない。 |
| Core dependency gate | framework 層が `nyxpy.gui` を import しない。 |
| Legacy removal gate | 旧 table 表示を前提にした公開 API とテストが残っていない。 |

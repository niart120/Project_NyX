# GUI 再設計 Phase 1: AppServices と MacroCatalog

> **文書種別**: Phase 仕様。GUI 再設計追従のうち、composition root と macro identity を扱う。  
> **対象モジュール**: `src\nyxpy\gui\app_services.py`, `src\nyxpy\gui\macro_catalog.py`, `src\nyxpy\gui\panes\macro_browser.py`, `src\nyxpy\gui\main_window.py`  
> **親仕様**: `IMPLEMENTATION_PLAN.md`

## 1. 目的

`MainWindow` に集中している logging、registry、runtime builder、device 設定反映を `GuiAppServices` 相当の collaborator へ切り出す。あわせて、GUI のマクロ選択値を class name から stable `MacroDefinition.id` へ移す。

この phase では実行状態や preview pause は変更しない。後続 phase が安全に Runtime 実行制御へ手を入れられるよう、依存生成と macro identity の土台だけを固定する。

## 2. 現状と問題

| 項目 | 現状 | 問題 |
|------|------|------|
| `MainWindow.__init__()` | logging、manager 初期化、registry、catalog、UI をまとめて生成 | テスト差し替え点が少なく、設定反映と実行制御が密結合 |
| `MacroCatalog.macros` | `definition.class_name` を key にする | class name 衝突や display name 変更で実行 ID が揺れる |
| `MacroBrowserPane` | table 表示値から選択対象を復元しやすい構造 | Runtime / Resource / log correlation に stable ID を渡せない |
| builder 生成 | `MainWindow._create_runtime_builder()` が直接生成 | settings / secrets / notification / device の組み立て責務が UI に混在 |

## 3. 実装仕様

### 3.1 `GuiAppServices`

新規 `src\nyxpy\gui\app_services.py` を追加する。最小 API は次の通り。

```python
class GuiAppServices:
    def __init__(self, *, project_root: Path) -> None: ...
    def create_runtime_builder(self) -> MacroRuntimeBuilder: ...
    def apply_settings(self) -> None: ...
    def close(self) -> None: ...
```

責務:

- `create_default_logging(base_dir=project_root / "logs", console_enabled=False)` を生成する。
- `MacroRegistry(project_root)` を生成し、`MacroCatalog` へ渡す。
- `ProtocolFactory`、serial / capture manager、notification handler、settings / secrets から Runtime builder を構成する。
- `apply_settings()` で serial、capture、protocol、notification の変更反映を扱う。
- `close()` で manager release と logging close を扱う。例外記録の詳細は Phase 4 に委譲する。

`GuiAppServices` は singleton ではない。`MainWindow` の lifetime に 1 個だけ持ち、テストでは fake service に差し替える。

### 3.2 `MacroCatalog`

`MacroCatalog` は stable ID を key にする。

```python
class MacroCatalog:
    definitions_by_id: dict[str, MacroDefinition]

    def reload_macros(self) -> None: ...
    def list(self) -> list[MacroDefinition]: ...
    def get(self, macro_id: str) -> MacroDefinition: ...
```

互換上 `macros` 属性を残す場合も、値は `definitions_by_id` と同じ stable ID key にする。class name key の辞書は作らない。

### 3.3 `MacroBrowserPane`

`MacroBrowserPane` は表示と実行 ID を分離する。

- 表示列: `definition.display_name` を優先し、なければ `definition.class_name`。
- 非表示または item data: `definition.id`。
- public method: `selected_macro_id() -> str | None`。

`MainWindow` は table cell text を直接読まず、`selected_macro_id()` を使う。

## 4. テスト方針

| テスト名 | 検証内容 |
|----------|----------|
| `test_macro_catalog_keys_by_definition_id` | `MacroCatalog` が `definition.id` を key にする |
| `test_macro_catalog_reload_preserves_stable_ids` | reload 後も stable ID で参照できる |
| `test_macro_browser_selection_returns_macro_id` | 表示名ではなく `macro_id` を返す |
| `test_main_window_uses_selected_macro_id` | `_start_macro()` が `RuntimeBuildRequest.macro_id` に stable ID を渡す |
| `test_app_services_creates_runtime_builder_from_settings` | settings / secrets から builder を構成する |

## 5. 完了ゲート

| ゲート | 判定 |
|--------|------|
| Service boundary gate | `MainWindow` が Runtime builder 構成の詳細を直接持たない |
| Stable ID gate | GUI 実行要求の `macro_id` が `MacroDefinition.id` である |
| Testability gate | `MainWindow` テストで fake service を注入できる |
| No cross-layer gate | framework 層に GUI import が増えていない |


# GUI 再設計 Phase 5: 旧経路と FW 残存経路の整理

> **文書種別**: Phase 仕様。GUI 追従実装後に残る旧 EventBus 経路、仮想コントローラー旧入力、framework 旧経路参照を棚卸しし、削除条件と検証方法を定義する。
> **対象モジュール**: `src\nyxpy\gui\events.py`, `src\nyxpy\gui\models\virtual_controller_model.py`, `src\nyxpy\gui\app_services.py`, `src\nyxpy\framework\`, `tests\gui\`, `tests\integration\`
> **親仕様**: `IMPLEMENTATION_PLAN.md`
> **先行条件**: Phase 1-4 完了。

## 1. 目的

Phase 1-4 で GUI の Runtime 入口、stable macro ID、preview 差し替え、close cleanup は整理済みである。一方、旧 Manager / EventBus 時代の「状態変更をグローバル通知で拾う」経路と、framework 側の旧 API 参照検出は別論点として残っている。

Phase 5 では、実装上の互換面ではない旧経路を削除する。互換 shim を追加せず、呼び出し元とテストを正 API へ寄せる。

## 2. 現状

| 項目 | 現状 | 判断 |
|------|------|------|
| `EventBus.CAPTURE_DEVICE_CHANGED` | Phase 4 で削除済み | 完了 |
| `EventBus.PROTOCOL_CHANGED` | `GuiAppServices` が publish し、`VirtualControllerModel` が subscribe する | 削除候補 |
| `EventBus.SERIAL_DEVICE_CHANGED` | publish 側は実装上残っていない。テストだけが publish する | 削除候補 |
| `VirtualControllerModel.serial_device` | `ControllerOutputPort` 導入前の旧入力として残る | 削除候補 |
| `VirtualControllerModel.protocol` | `serial_device` から `SerialControllerOutputPort` を組み立てるために残る | `serial_device` と同時削除 |
| `GuiAppServices` -> `EventBus` | protocol 変更時だけ残るグローバル通知 | manual controller 再構成へ置換 |
| framework 旧経路 | GUI からの参照は減ったが、FW 側の旧 API / singleton / alias は別途棚卸しが必要 | 静的検査と削除条件を追加 |

## 3. 実装方針

### 3.1 EventBus 削除

`VirtualControllerModel` は `ControllerOutputPort` だけを受け取り、serial device と protocol を直接保持しない。protocol 変更や serial device 変更は `GuiAppServices.apply_settings()` が Runtime builder と manual controller を再構成し、`MainWindow` が `VirtualControllerModel.set_controller()` へ渡す。

削除対象:

- `src\nyxpy\gui\events.py`
- `EventBus` / `EventType` import
- `VirtualControllerModel.on_serial_device_changed()`
- `VirtualControllerModel.on_protocol_changed()`
- `VirtualControllerModel.set_serial_device()`
- `VirtualControllerModel.set_protocol()`
- `VirtualControllerModel.serial_device`
- `VirtualControllerModel.protocol`

残す API:

- `VirtualControllerModel.set_controller(controller: ControllerOutputPort | None) -> None`
- `VirtualControllerModel.button_press()` / `button_release()` / stick / hat 操作

### 3.2 framework 旧経路の棚卸し

GUI から参照しないだけでは削除完了としない。framework 側に次の残存がないかを静的検査とテストで固定する。

- `MacroExecutor` import / shim
- `DefaultCommand` 旧コンストラクタ経路
- `LogManager` / `log_manager` singleton
- `singletons.py` 経由で Runtime 実行に使われる manager
- `legacy` を含む builder / adapter / helper
- 旧 static resource fallback
- `Path.cwd()` 固定の settings / resource fallback

本 phase で削除可否を判断できないものは、残す理由を仕様へ明記する。単に「念のため」「既存テストが触るため」は理由にしない。

## 4. テスト方針

| テスト名 | 検証内容 |
|----------|----------|
| `test_virtual_controller_model_has_no_event_bus_dependency` | `VirtualControllerModel` が `EventBus` / `EventType` を import しない |
| `test_virtual_controller_model_uses_only_controller_output_port` | serial device / protocol を直接受け取らず、`ControllerOutputPort` 経由で送信する |
| `test_gui_has_no_event_bus_module` | `src\nyxpy\gui\events.py` が存在しない、または GUI から参照されない |
| `test_gui_settings_change_updates_manual_controller_without_event_bus` | 設定変更後の manual controller 差し替えが `set_controller()` だけで完結する |
| `test_framework_has_no_removed_legacy_runtime_routes` | framework 旧経路が import / public API として残っていない |

## 5. 完了ゲート

| ゲート | 判定 |
|--------|------|
| EventBus removal gate | GUI 実装とテストから `EventBus` / `EventType` 参照が消えている |
| Controller port gate | 仮想コントローラーは `ControllerOutputPort` だけへ依存する |
| Framework legacy gate | framework 旧経路の削除または残置理由が仕様とテストで固定されている |
| No shim gate | 互換 shim / alias / deprecated wrapper を追加していない |
| Regression gate | `uv run pytest tests\gui tests\integration\test_macro_runtime_entrypoints.py tests\unit\framework\runtime\test_removed_api_imports.py` が通る |

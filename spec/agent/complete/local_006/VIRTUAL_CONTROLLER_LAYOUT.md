# GUI 外観再設計: 仮想コントローラ固定レイアウト追補仕様

> **対象タイトル**: NyX GUI
> **目的**: ウィンドウサイズプリセットごとに仮想コントローラの表示領域、ボタン、スティック、文字サイズを固定し、Qt レイアウトの余白分配による崩れを防ぐ。
> **関連仕様**: `WINDOW_SIZE_AND_PANEL_LAYOUT.md`, `WINDOW_SIZE_PRESETS.md`, `PREVIEW_AND_LOG_LAYOUT.md`

## 1. 概要

### 1.1 目的

`local_006` の固定カラムレイアウトでは、左列下部の仮想コントローラ領域がプリセットごとに固定される。既存の仮想コントローラは自然サイズ `288x141` 付近を前提にした nested layout であり、`280x280` などの固定領域に入れると余白が各行へ分配されて配置が崩れる。本追補では、仮想コントローラをプリセット別の固定キャンバスとして扱い、各部品の寸法と座標を段階固定する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| 仮想コントローラキャンバス | 左列下部に確保する仮想コントローラ全体の固定表示領域 |
| 部品 | `ControllerButton`, `AnalogStick`, `DPad` の各 widget |
| 基準座標 | FullHD 相当の `280x240` を基準にした相対配置 |
| 段階固定 | プリセットごとにキャンバスサイズ、部品サイズ、文字サイズを離散値で切り替えること |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src\nyxpy\gui\layout.py` | 変更 | 仮想コントローラ用メトリクスを追加する |
| `src\nyxpy\gui\main_window.py` | 変更 | `VirtualControllerPane` へプリセット別メトリクスを適用する |
| `src\nyxpy\gui\panes\virtual_controller_pane.py` | 変更 | nested layout 依存をやめ、固定キャンバス上の座標配置へ変更する |
| `src\nyxpy\gui\widgets\controller\analog_stick.py` | 変更 | スティック径を可変にする |
| `src\nyxpy\gui\widgets\controller\dpad.py` | 変更 | 十字キー径を可変にする |
| `src\nyxpy\gui\widgets\controller\button.py` | 変更 | ボタン寸法、角丸、文字サイズを可変にする |
| `tests\gui\test_virtual_controller_layout.py` | 新規 | プリセット別レイアウト崩れの回帰テストを追加する |

## 3. 設計方針

### アルゴリズム概要

仮想コントローラは `QHBoxLayout` / `QVBoxLayout` の伸縮計算に任せず、固定キャンバス上に各部品を `setGeometry()` で配置する。基準座標は `280x240` とし、プリセットごとに `scale = min(canvas_width / 280, canvas_height / 240)` を計算する。算出した content size をキャンバス中央へ寄せ、余白はキャンバス外周にだけ出す。丸め誤差で部品が 1 px はみ出さないよう、右端と下端はキャンバス内へ clamp する。

```text
scaled_x = offset_x + round(base_x * scale)
scaled_y = offset_y + round(base_y * scale)
scaled_w = round(base_w * scale)
scaled_h = round(base_h * scale)
```

### 性能要件

| 指標 | 目標値 |
|------|--------|
| レイアウト再計算 | プリセット切替時のみ |
| 描画更新 | 既存の Qt repaint 範囲内 |
| 入力遅延 | 既存の仮想コントローラ操作から増加させない |

### レイヤー構成

| レイヤー | 責務 |
|----------|------|
| `layout.py` | プリセットキーから仮想コントローラメトリクスを返す |
| `MainWindow` | 現在プリセットのメトリクスを `VirtualControllerPane` に渡す |
| `VirtualControllerPane` | キャンバスサイズと部品座標を適用し、既存 signal 接続を維持する |
| controller widgets | 指定された寸法で描画し、入力座標を自身のサイズから計算する |

### 再利用性・依存設計

GUI 層内の変更に閉じる。framework 層、macro 層、実行時の `Command` / `ControllerOutputPort` 契約は変更しない。ボタン押下、スティック、十字キーの signal とモデル更新は既存実装を維持する。

## 4. 実装仕様

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| なし | - | - | ユーザー設定は追加しない。ウィンドウサイズプリセットから自動決定する |

### プリセット別メトリクス

| key | キャンバス | scale 目安 | 主要丸ボタン | スティック | 十字キー | 文字サイズ |
|-----|------------|------------|--------------|------------|----------|------------|
| `hd` | `260x220` | `0.91` | `26x26` | `59x59` | `66x66` | `8px` |
| `full_hd` | `280x280` | `1.00` | `28x28` | `64x64` | `72x72` | `9px` |
| `wqhd` | `360x320` | `1.28` | `36x36` | `82x82` | `93x93` | `11px` |
| `four_k` | `420x360` | `1.50` | `42x42` | `96x96` | `108x108` | `13px` |

キャンバスサイズは既存の `left_width` と `controller_height` を使用する。部品はキャンバス内に収め、キャンバス外へはみ出さない。FullHD の余剰高さは nested layout の行間ではなく、キャンバス外周余白として扱う。

### 基準座標

主要操作部は横一列に詰め込まない。実際のゲームパッドに近い関係として、上段に `LStick` と `ABXY`、下段に `D-Pad` と `RStick` を置く。横幅 `280` の FullHD 基準でも D-Pad と ABXY が近接しすぎないよう、左右の操作クラスタを段で分ける。スティック押し込みは `LS` / `RS` より `L3` / `R3` の表示名にし、上段のトリガー列へ `ZL, L, L3, R3, R, ZR` の順で置く。

| 部品 | 基準矩形 `(x, y, w, h)` |
|------|--------------------------|
| `btn_zl` | `(8, 4, 34, 22)` |
| `btn_l` | `(52, 4, 34, 22)` |
| `btn_ls` | `(96, 4, 34, 22)` |
| `btn_rs` | `(150, 4, 34, 22)` |
| `btn_r` | `(194, 4, 34, 22)` |
| `btn_zr` | `(238, 4, 34, 22)` |
| `btn_minus` | `(56, 38, 30, 24)` |
| `btn_capture` | `(92, 38, 30, 24)` |
| `btn_home` | `(158, 38, 30, 24)` |
| `btn_plus` | `(194, 38, 30, 24)` |
| `left_stick` | `(20, 74, 64, 64)` |
| `btn_x` | `(204, 64, 28, 28)` |
| `btn_y` | `(174, 94, 28, 28)` |
| `btn_a` | `(234, 94, 28, 28)` |
| `btn_b` | `(204, 124, 28, 28)` |
| `dpad` | `(38, 158, 72, 72)` |
| `right_stick` | `(174, 162, 64, 64)` |

`AnalogStick` と `DPad` は、描画座標、中心座標、最大移動距離、dead zone を固定値ではなく自身の `width()` / `height()` から計算する。プリセット切替時は cached position を新しい中心へ戻す。HD / FullHD のボタンラベルは従来より 1px 大きくし、最小プリセットでも `L3` / `R3` 等を読み取れるようにする。

### メインフロー

**Step 0**: プリセット適用
- `MainWindow.apply_window_size_preset()` が `LayoutMetrics` を取得する。

**Step 1**: 仮想コントローラメトリクス適用
- `VirtualControllerPane.apply_layout_size(width, height)` を呼び出し、キャンバスを固定する。

**Step 2**: 部品配置
- `VirtualControllerPane` は基準座標を scale し、各 widget に `setGeometry()` と寸法設定を適用する。

**Step 3**: 入力処理
- `AnalogStick` と `DPad` は現在の widget サイズから中心、半径、判定閾値を計算する。
- `VirtualControllerModel` への signal 接続は変更しない。

### インターフェース

```python
def apply_layout_size(self, width: int, height: int) -> None:
    """プリセットに対応したキャンバスサイズと部品配置を適用する。"""
```

```python
def set_diameter(self, diameter: int) -> None:
    """スティックまたは十字キーの描画サイズを変更する。"""
```

```python
def configure_size(
    self,
    size: tuple[int, int],
    *,
    radius: int,
    font_size: int,
) -> None:
    """コントローラーボタンの表示サイズと文字サイズを変更する。"""
```

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI | `test_virtual_controller_preset_sizes_keep_children_inside_canvas` | 全プリセットで部品がキャンバス外へ出ない |
| GUI | `test_virtual_controller_button_sizes_scale_by_preset` | HD / FullHD の文字サイズを 1px 上げ、4K では従来どおり段階的に大きくする |
| GUI | `test_virtual_controller_layout_does_not_stretch_rows_vertically` | FullHD の `280x280` 領域でもトリガー、システム、主要操作が順序を保つ |
| GUI | `test_virtual_controller_uses_two_rows_for_main_controls` | `LStick` と `ABXY` が上段、`D-Pad` と `RStick` が下段に並び、下段の中心軸が揃う |
| GUI | `test_virtual_controller_places_l3_r3_on_trigger_row` | 上段に `ZL, L, L3, R3, R, ZR` の順で並ぶ |
| GUI | `test_main_window_applies_virtual_controller_preset_metrics` | `MainWindow` のプリセット切替が仮想コントローラへ反映される |
| GUI | `test_analog_stick_uses_scaled_center_after_resize` | サイズ変更後のスティック中心と最大移動距離が新サイズ基準になる |
| GUI | `test_dpad_uses_scaled_hit_test_after_resize` | サイズ変更後の十字キー方向判定が新サイズ基準になる |

## 6. 実装チェックリスト

- [x] 仮想コントローラ仕様追補を `local_006` に追加
- [x] `AnalogStick` の可変サイズ対応
- [x] `DPad` の可変サイズ対応
- [x] `ControllerButton` の可変サイズ・文字サイズ対応
- [x] `VirtualControllerPane` の固定キャンバス配置化
- [x] `L3` / `R3` をトリガー列へ移動
- [x] `MainWindow` からプリセットメトリクスを適用
- [x] GUI レイアウト回帰テスト作成・パス
- [x] 全体リント・テスト通過

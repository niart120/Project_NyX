# Nintendo 3DS スライドパッド New Firmware 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`
> **目的**: 3DS プロトコルのスライドパッド入力を New Firmware の StickPad DAC 仕様へ更新する。
> **関連ドキュメント**: `../local_001/NINTENDO_3DS_SERIAL_PROTOCOL.md`, `../../../framework/archive/protocol_design.md`
> **既存ソース**: `src/nyxpy/framework/core/hardware/protocol.py`
> **破壊的変更**: あり

## 1. 概要

### 1.1 目的

Nintendo 3DS 向け `ThreeDSSerialProtocol` が生成する `LStick` の軸値を、New Firmware の StickPad DAC 仕様へ更新する。`RStick` は C スティック仕様のままとし、スライドパッドと C スティックを別々の変換規則として実装する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作（ボタン入力・キャプチャ・ログ）を行うための高レベル API |
| SerialProtocolInterface | キー操作をシリアル送信データへ変換する抽象インターフェース |
| ThreeDSSerialProtocol | 3DS 向け S2/T3 系シリアルプロトコルの実装クラス |
| LStick | NyX の左スティック入力。3DS プロトコルではスライドパッドとして送信する |
| RStick | NyX の右スティック入力。3DS プロトコルでは C スティックとして送信する |
| StickPad DAC | New Firmware のスライドパッド軸値。中央 `80`、負方向 `FF`、正方向 `00` を使う |
| C スティック仕様 | `0..255` の NyX 軸値を、中央 `00`、負方向 `80..FF`、正方向 `01..7F` の符号付き 8 bit オフセットへ変換する仕様 |

### 1.3 背景・問題

3DS プロトコルのスライドパッド (`A2`) は、当初 `RIGHT/DOWN=FA`、`LEFT/UP=7E` の旧 DAC 範囲で実装していた。その後 C スティック仕様への統一と解釈したが、正しい New Firmware 仕様は `CENTER=A2 80 80`、`LEFT=A2 FF 80`、`DOWN=A2 80 00`、`RIGHT=A2 00 80`、`UP=A2 80 FF` である。旧仕様および C スティック仕様のままでは、3DS デバイス側が期待するスライドパッド入力値と一致しない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 3DS `LStick.CENTER` の送信値 | `A2 80 80` | `A2 80 80` |
| 3DS `LStick.LEFT` の送信値 | `A2 7E 80` | `A2 FF 80` |
| 3DS `LStick.RIGHT` の送信値 | `A2 FA 80` | `A2 00 80` |
| 3DS `LStick.UP` の送信値 | `A2 80 7E` | `A2 80 FF` |
| 3DS `LStick.DOWN` の送信値 | `A2 80 FA` | `A2 80 00` |
| 3DS `RStick` の送信値 | C スティック仕様 | 変更なし |
| CH552 / PokeCon のスティック送信値 | 変更対象外 | 変更なし |

### 1.5 着手条件

- `ThreeDSSerialProtocol` の `A2` / `A4` サブパケット構造は維持する。
- 旧スライドパッド仕様の互換 shim、別名、設定フラグは追加しない。
- `RStick` の C スティック仕様は変更しない。
- 3DS 以外の `CH552SerialProtocol` / `PokeConSerialProtocol` は変更しない。
- 既存テスト (`uv run pytest tests/unit/`) がすべてパスすること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/constants/stick.py` | 変更 | `LStick` / `RStick` の中立座標と仮想コントローラー入力の軸変換を `128, 128` 中心へ補正する |
| `src/nyxpy/framework/core/hardware/protocol.py` | 変更 | 3DS の `LStick` 変換を New Firmware StickPad DAC 仕様へ更新し、`RStick` 変換と分離する |
| `tests/unit/framework/constants/test_stick.py` | 新規 | スティック定数の中立座標と上下左右の垂直軸が `128` であることを検証する |
| `tests/unit/protocol/test_3ds_protocol.py` | 変更 | 3DS スライドパッド送信値とニュートラルフレームの期待値を New Firmware 仕様へ更新する |
| `tests/integration/test_3ds_runtime_serial_protocol.py` | 変更 | `Command.touch` / `Command.press` 経由の 3DS ニュートラルフレーム期待値を更新する |
| `tests/gui/test_virtual_controller_model.py` | 変更 | 仮想コントローラー経由の 3DS スティック送信値と解放時ニュートラルフレームを検証する |
| `spec/agent/complete/local_001/NINTENDO_3DS_SERIAL_PROTOCOL.md` | 変更 | 既存 3DS プロトコル仕様のスライドパッド変換、ニュートラル値、テスト方針を更新する |
| `docs/macro-development/nintendo-3ds.md` | 変更 | 3DS 向けスティック入力の公開ドキュメントに New Firmware の送信値を追記する |
| `spec/agent/complete/local_009/NINTENDO_3DS_STICKPAD_NEW_FIRMWARE.md` | 新規 | 本変更仕様を記録する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

本変更はハードウェア抽象層の `ThreeDSSerialProtocol` 内部変換に閉じる。`Command`、`SerialProtocolInterface`、`ProtocolFactory` の公開 API は変更しない。GUI、CLI、マクロは従来どおり `LStick` / `RStick` を渡し、プロトコル層が 3DS デバイス向けのバイト列へ変換する。

### 公開 API 方針

新しい公開 API は追加しない。`LStick` / `RStick` の Python オブジェクト表現は従来の `0..255` 軸値のままとし、3DS プロトコルの送信バイト列だけを変更する。プロトコル変更への追従が目的であり、利用者に旧仕様選択の分岐を公開しない。

### 後方互換性

破壊的変更を行う。3DS プロトコル選択時の `LStick` 送信値は旧スライドパッド仕様から New Firmware StickPad DAC 仕様へ変わる。旧値を必要とするデバイス向けの互換モード、警告、alias は追加しない。`RStick`、`CH552SerialProtocol`、`PokeConSerialProtocol` の変換は変更しない。

### レイヤー構成

依存方向は以下を維持する。

```text
macros/*  -> nyxpy.framework.core.macro.Command
Command   -> SerialProtocolInterface + SerialCommInterface
Protocol  -> constants
```

`nyxpy.framework.core.hardware` から GUI、CLI、個別マクロへの依存は追加しない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 3DS スティック軸値変換時間 | 1 呼び出しあたり 1 ms 未満 |
| 3DS 通常入力フレーム長 | 14 バイト固定 |
| 3DS `LStick` 変換規則 | New Firmware StickPad DAC 仕様 |
| 3DS `RStick` 変換規則 | C スティック仕様 |
| 既存 CH552 / PokeCon のコマンド生成結果 | 変更なし |

### 並行性・スレッド安全性

`ThreeDSSerialProtocol` は入力状態をインスタンス変数に保持する。既存設計と同じく、単一マクロ実行スレッドから単一プロトコルインスタンスを利用する前提である。本変更は変換関数と初期値を変更するだけであり、ロックや共有状態は追加しない。

## 4. 実装仕様

### 公開インターフェース

公開シグネチャは変更しない。

```python
class ThreeDSSerialProtocol(SerialProtocolInterface):
    supports_touch = True

    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes: ...
    def build_hold_command(self, keys: tuple[KeyType, ...]) -> bytes: ...
    def build_release_command(self, keys: tuple[KeyType, ...]) -> bytes: ...
    def build_touch_down_command(self, x: int, y: int) -> bytes: ...
    def build_touch_up_command(self) -> bytes: ...
```

内部変換関数は `LStick` と `RStick` で分ける。

```python
class ThreeDSSerialProtocol(SerialProtocolInterface):
    @staticmethod
    def _convert_slide_pad_axis(value: int) -> int:
        if not 0 <= value <= 255:
            raise ValueError("Stick axis must be in range 0..255")
        if value <= 128:
            return round(0xFF - (value / 128) * (0xFF - 0x80))
        return round(0x80 - ((value - 128) / 127) * 0x80)

    @staticmethod
    def _convert_c_stick_axis(value: int) -> int:
        if not 0 <= value <= 255:
            raise ValueError("Stick axis must be in range 0..255")
        if value in (127, 128):
            return 0x00
        return max(-128, min(127, value - 128)) & 0xFF
```

### スティック入力フレーム

| 入力 | サブパケット | 中央 | LEFT / UP | RIGHT / DOWN |
|------|--------------|------|-----------|--------------|
| `LStick` | `A2 x y` | `A2 80 80` | `A2 FF 80` / `A2 80 FF` | `A2 00 80` / `A2 80 00` |
| `RStick` | `A4 x y` | `A4 00 00` | `A4 80 00` / `A4 00 80` | `A4 7F 00` / `A4 00 7F` |

全ニュートラルフレームは以下とする。

```text
A1 00 00 A2 80 80 A4 00 00 B2 00 00 00 00
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `serial_protocol` | `str` | `"CH552"` | `"3DS"` 選択時に本仕様の変換を使う |
| `serial_baud` | `int` | プロトコル依存 | 本変更では変更しない |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ValueError` | `LStick` / `RStick` の軸値が `0..255` の範囲外 |
| `UnsupportedKeyError` | 3DS プロトコルで表現できないキーが指定された |
| `NotImplementedError` | 3DS が対応しないキーボード入力 API が呼ばれた |

### シングルトン管理

該当なし。新しいシングルトンは追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_3ds_press_single_button` | ボタンのみの 3DS フレームでスライドパッド中央が `A2 80 80` になる |
| ユニット | `test_3ds_slide_pad_presets_use_new_firmware_dac_spec` | `LStick.CENTER` / `LEFT` / `RIGHT` / `UP` / `DOWN` が New Firmware StickPad DAC 仕様の値になる |
| ユニット | `test_3ds_c_stick_presets` | `RStick.CENTER` / `LEFT` / `RIGHT` / `UP` / `DOWN` が従来どおり C スティック仕様の値になる |
| ユニット | `test_3ds_mixed_input_fixed_frame` | ボタン、`LStick`、`RStick`、タッチを含む固定長 14 バイトフレームが新仕様値になる |
| ユニット | `test_stick_center_uses_protocol_neutral_axis` | `LStick.CENTER` / `RStick.CENTER` が `(128, 128)` を返す |
| ユニット | `test_stick_cardinal_presets_keep_perpendicular_axis_neutral` | スティック上下左右の垂直軸が `128` になる |
| GUI | `test_virtual_controller_left_stick_uses_3ds_new_firmware_dac_spec` | 仮想コントローラー左スティックが `A2 00 80` と解放時 `A2 80 80` を送る |
| GUI | `test_virtual_controller_right_stick_uses_3ds_c_stick_axis_spec` | 仮想コントローラー右スティックが `A4 00 80` と解放時 `A4 00 00` を送る |
| 結合 | `test_3ds_runtime_command_touch_with_fake_serial` | `Command.touch` の押下・解放フレームが新しい 3DS ニュートラル値を使う |
| 結合 | `test_3ds_runtime_keeps_basic_button_input_with_touch_support` | `Command.press(Button.A)` の押下・解放フレームが新しい 3DS ニュートラル値を使う |
| ハードウェア | `test_3ds_device_button_touch` | `@pytest.mark.realdevice`。実機接続時の代表コマンド送信を継続確認する |
| パフォーマンス | 既存対象なし | 変換処理は整数演算のみであり、性能テストは追加しない |

## 6. 実装チェックリスト

- [x] 公開 API のシグネチャ確定
- [x] `ThreeDSSerialProtocol` のスライドパッド初期値を `80 80` へ変更
- [x] `LStick` の軸値変換を `_convert_slide_pad_axis` に分離
- [x] `RStick` の軸値変換を `_convert_c_stick_axis` に維持
- [x] `LStick` / `RStick` の中立座標生成を `(128, 128)` に補正
- [x] ユニットテスト期待値の更新
- [x] 仮想コントローラー経由の 3DS スティック送信テスト追加
- [x] 統合テスト期待値の更新
- [x] 既存 3DS プロトコル仕様書の更新
- [x] マクロ開発ドキュメントの更新
- [x] 型ヒントの整合性チェック（ruff）

# Nintendo 3DS シリアル通信プロトコル対応 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`
> **目的**: Nintendo 3DS 向けシリアル通信デバイスを NyX の `SerialProtocolInterface` 経由で利用可能にする。
> **関連ドキュメント**: `docs/protocol_design.md`, `docs/hardware_design.md`
> **参考資料**: ユーザ提供の通信仕様スクリーンショット、<https://www.3dscontroller.com/>
> **破壊的変更**: なし

## 1. 概要

### 1.1 目的

Nintendo 3DS 向けシリアル通信デバイスのボタン、スライドパッド、C スティック、タッチ、スリープ抑止コマンドをフレームワーク層で生成できるようにする。既存の `Command.press` / `Command.hold` / `Command.release` は維持し、3DS 固有操作は任意機能として追加する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作（ボタン入力・キャプチャ・ログ）を行うための高レベル API |
| DefaultCommand | `SerialProtocolInterface` で生成したバイト列を `SerialCommInterface` に送信する標準実装 |
| SerialProtocolInterface | キー操作をシリアル送信データへ変換する抽象インターフェース |
| ThreeDSSerialProtocol | 3DS 向け S2/T3 系シリアルプロトコルの実装クラス |
| KeyType | `Button` / `Hat` / `LStick` / `RStick` / `TouchState` など、コントローラー入力状態を表す型 |
| ThreeDSButton | Switch 互換の `Button` では表現できない 3DS 専用ボタンを表す定数 |
| TouchState | 3DS タッチパネルの押下状態と座標を表す入力状態型 |
| スライドパッド | 3DS の左アナログ入力。NyX では `LStick` から変換する |
| C スティック | New 3DS 系の右アナログ入力。NyX では `RStick` から変換する |
| タッチ座標 | 下画面のタッチ位置。X は `0..320`、Y は `0..240` の整数で指定する |
| S2/T3 | 参考スクリーンショットに記載された `DS・3DS Serial Protocol: Button Data Map (S2・T3)` の通信仕様 |

### 1.3 背景・問題

現状のフレームワークは CH552 と PokeCon 向けのプロトコル生成に対応しているが、3DS 向けデバイスのパケット形式を生成できない。3DS では Switch 系入力にないタッチ、POWER、スリープ抑止などが存在し、単純なボタンビット列の追加だけでは対応できない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| `ProtocolFactory` で選択可能なプロトコル数 | 2 (`CH552`, `PokeCon`) | 3 (`CH552`, `PokeCon`, `3DS`) |
| 3DS プロトコル選択時の既定ボーレート | 9600 | 115200 |
| 実機なしで検証可能な 3DS パケット種別 | 0 | ボタン、スライドパッド、C スティック、タッチ、スリープ抑止 |
| 通常入力の送信長 | 入力種別ごとの可変長 | ボタン・スティック・タッチを含む固定長 14 バイト |
| 既存マクロ API の破壊的変更 | なし | なし |
| 3DS 固有操作の座標バリデーション | なし | X/Y 範囲外を例外化 |

### 1.5 着手条件

- 既存の `SerialProtocolInterface` / `SerialCommInterface` の責務を維持する。
- FT DS Initial Version の 6 バイト形式は今回の対象外とし、S2/T3 の 3DS 形式を対象にする。
- バージョン照会とボーレート変更パケットは今回の `Command` API と `ThreeDSSerialProtocol` 実装対象に含めない。
- タッチキャリブレーション書き込み系はプロトコルビルダーのみ実装し、`Command` の通常マクロ API からは直接公開しない。
- 既存テスト (`uv run pytest tests/unit/`) がすべてパスすること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/constants/controller.py` | 変更 | `ThreeDSButton` と `TouchState` を追加し、POWER とタッチ入力状態を定義する |
| `src/nyxpy/framework/core/constants/types.py` | 変更 | `KeyType` に `ThreeDSButton` と `TouchState` を追加する |
| `src/nyxpy/framework/core/constants/__init__.py` | 変更 | `ThreeDSButton` と `TouchState` を公開する |
| `src/nyxpy/framework/core/hardware/protocol.py` | 変更 | `ThreeDSSerialProtocol` と 3DS 固有パケット生成メソッドを追加する |
| `src/nyxpy/framework/core/hardware/protocol_factory.py` | 変更 | `3DS` / `ThreeDS` / `Nintendo3DS` のプロトコル名、既定ボーレート、対応ボーレートを持つプロトコルメタデータを登録する |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `touch` / `touch_down` / `touch_up` / `disable_sleep` を非抽象の任意 API として追加し、`DefaultCommand` で対応プロトコルのみ実行する |
| `src/nyxpy/__main__.py` | 変更 | CLI の `cli` サブコマンドに `--baud` を追加し、省略時はプロトコル既定ボーレートを使う |
| `src/nyxpy/cli/run_cli.py` | 変更 | CLI 側のプロトコル生成を `ProtocolFactory` に寄せ、シリアル接続前にプロトコル既定ボーレートを解決する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | プロトコル選択時に既定ボーレートを候補へ反映し、3DS 選択時は 115200 を初期選択する |
| `tests/unit/protocol/test_3ds_protocol.py` | 新規 | 3DS プロトコルのバイト列生成を検証する |
| `tests/unit/command/test_default_command.py` | 変更 | 3DS 固有 Command API の送信順と未対応プロトコル時の例外を検証する |
| `tests/unit/cli/test_main.py` | 変更 | `create_protocol("3DS")` の生成結果を検証する |
| `tests/gui/` 配下の設定ダイアログテスト | 変更 | プロトコル選択肢に `3DS` が含まれることを検証する |
| `tests/hardware/test_3ds_serial_protocol_device.py` | 新規 | 実機接続時の代表コマンド送信を `@pytest.mark.realdevice` で検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

3DS 対応はハードウェア抽象層の `SerialProtocolInterface` 実装として追加する。`Command` は高レベル操作、`ThreeDSSerialProtocol` は操作からバイト列への変換、`SerialCommInterface` は送信のみを担当する。GUI と CLI はプロトコル名と任意のボーレート上書きを指定するだけで、3DS のパケット詳細には依存しない。

### 公開 API 方針

既存の `SerialProtocolInterface` は変更しない。`build_press_command` / `build_hold_command` / `build_release_command` は `ThreeDSSerialProtocol` でも実装し、既存マクロの `cmd.press(Button.A)` や `cmd.hold(Hat.UP)` を 3DS デバイスで動作させる。タッチは `TouchState` を `KeyType` に追加し、ボタン・スティックと同じ入力状態として扱う。

3DS 固有操作は、`ThreeDSSerialProtocol` の具象メソッドとして追加する。`Command.touch()` / `touch_down()` / `touch_up()` は `TouchState.down()` / `TouchState.up()` を使う便利 API として追加し、未対応プロトコルでは `NotImplementedError` を送出する。抽象メソッドを増やさないため、既存の `Command` 派生実装は壊れない。

### 後方互換性

破壊的変更は行わない。`Button.MINUS` は 3DS の SELECT、`Button.PLUS` は START に変換し、Switch 向けマクロで使われる既存定数を最大限再利用する。`Button.CAP` / `Button.LS` / `Button.RS` は 3DS の S2/T3 仕様に対応する入力がないため、3DS プロトコルでは `UnsupportedKeyError` を送出する。

### レイヤー構成

依存方向は以下を維持する。

```text
macros/*  -> nyxpy.framework.core.macro.Command
Command   -> SerialProtocolInterface + SerialCommInterface
Protocol  -> constants
GUI/CLI   -> ProtocolFactory
```

`nyxpy.framework.core.hardware` は GUI、CLI、マクロ個別実装に依存しない。`ProtocolFactory` は具象プロトコルの登録とプロトコルメタデータの解決だけを担当し、設定保存やシリアルポートの開閉は扱わない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 3DS ボタンコマンド生成時間 | 1 呼び出しあたり 1 ms 未満 |
| 3DS タッチコマンド生成時間 | 1 呼び出しあたり 1 ms 未満 |
| 通常入力フレーム長 | 14 バイト固定 |
| 3DS 既定ボーレート | 115200 bps |
| 既存 CH552 / PokeCon のコマンド生成結果 | 変更なし |

### 並行性・スレッド安全性

`ThreeDSSerialProtocol` は既存の `CH552SerialProtocol` と同じく入力状態を保持する。単一の `DefaultCommand` インスタンスが単一マクロ実行スレッドから利用する前提であり、プロトコルインスタンスの共有は行わない。複数スレッドで同一プロトコルを共有する用途は対象外である。

## 4. 実装仕様

### 公開インターフェース

```python
from enum import IntEnum
from dataclasses import dataclass

from nyxpy.framework.core.constants import (
    Button,
    Hat,
    KeyboardOp,
    KeyCode,
    KeyType,
    LStick,
    RStick,
    SpecialKeyCode,
)
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface


@dataclass(frozen=True)
class ProtocolDescriptor:
    name: str
    protocol_cls: type[SerialProtocolInterface]
    default_baudrate: int
    supported_baudrates: tuple[int, ...]
    aliases: tuple[str, ...] = ()


class ThreeDSButton(IntEnum):
    POWER = 0x0020


@dataclass(frozen=True)
class TouchState:
    pressed: bool
    x: int = 0
    y: int = 0

    @classmethod
    def down(cls, x: int, y: int) -> "TouchState": ...

    @classmethod
    def up(cls) -> "TouchState": ...


class UnsupportedKeyError(ValueError):
    """指定されたキーが対象プロトコルで表現できない場合の例外。"""


class ThreeDSSerialProtocol(SerialProtocolInterface):
    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes: ...
    def build_hold_command(self, keys: tuple[KeyType, ...]) -> bytes: ...
    def build_release_command(self, keys: tuple[KeyType, ...]) -> bytes: ...
    def build_keyboard_command(self, text: str) -> bytes: ...
    def build_keytype_command(self, key: KeyCode | SpecialKeyCode, op: KeyboardOp) -> bytes: ...

    def build_touch_down_command(self, x: int, y: int) -> bytes: ...
    def build_touch_up_command(self) -> bytes: ...
    def build_disable_sleep_command(self, enabled: bool) -> bytes: ...
    def build_touch_calibration_write_command(
        self,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        *,
        factory: bool = False,
    ) -> bytes: ...
    def build_touch_calibration_read_command(self) -> bytes: ...
    def build_touch_calibration_factory_reset_command(self) -> bytes: ...


class ProtocolFactory:
    @classmethod
    def get_protocol_names(cls) -> list[str]: ...

    @classmethod
    def get_descriptor(cls, protocol_name: str) -> ProtocolDescriptor: ...

    @classmethod
    def get_default_baudrate(cls, protocol_name: str) -> int: ...

    @classmethod
    def resolve_baudrate(cls, protocol_name: str, baudrate: int | None = None) -> int: ...

    @classmethod
    def create_protocol(cls, protocol_name: str) -> SerialProtocolInterface: ...
```

```python
class Command(ABC):
    def touch(self, x: int, y: int, dur: float = 0.1, wait: float = 0.1) -> None:
        raise NotImplementedError("Current serial protocol does not support touch input.")

    def touch_down(self, x: int, y: int) -> None:
        raise NotImplementedError("Current serial protocol does not support touch input.")

    def touch_up(self) -> None:
        raise NotImplementedError("Current serial protocol does not support touch input.")

    def disable_sleep(self, enabled: bool = True) -> None:
        raise NotImplementedError("Current serial protocol does not support sleep control.")
```

### 混在入力と固定長フレーム

既存の `Command.press(*keys)` は `Button`、`Hat`、`LStick`、`RStick` を同時に受け取れる。3DS では `TouchState` も同じ `KeyType` として扱い、タッチを入力状態の一部に含める。3DS の S2/T3 仕様は入力種別ごとにヘッダーが分かれるため、独自ヘッダーを追加せず、仕様上のサブパケットを固定順で連結した 14 バイトの入力状態フレームとして扱う。

| 位置 | 入力種別 | サブパケット | バイト数 |
|------|----------|--------------|----------|
| 1 | ボタン / 方向キー | `A1 button_low button_high` | 3 |
| 2 | スライドパッド (`LStick`) | `A2 x y` | 3 |
| 3 | C スティック (`RStick`) | `A4 x y` | 3 |
| 4 | タッチ | `B2 touch_flag x_high x_low y_low` | 5 |

`build_press_command` / `build_hold_command` / `build_release_command` / `build_touch_down_command` / `build_touch_up_command` は、常にこの 14 バイトを返す。例: `build_press_command((Button.A, Hat.UP, LStick.RIGHT, RStick.UP, TouchState.down(320, 240)))` は `A1 18 00 A2 FA 80 A4 00 80 B2 01 01 40 F0` を返す。タッチ押下中にボタンやスティックを変更した場合は、最後の `B2` サブパケットに現在のタッチ状態を維持する。

全ニュートラル状態は `A1 00 00 A2 80 80 A4 00 00 B2 00 00 00 00` とする。`SerialComm.send()` は 1 回の `write()` で 14 バイトを送るが、デバイス側は先頭バイトを各サブパケットのヘッダーとして順に解釈する想定である。

### 3DS ボタン変換

ボタン入力は `A1 button_low button_high` の 3 バイトで送信する。複数ボタン同時押しは `button_low` と `button_high` のビット OR で表現する。解放は対象ビットをクリアし、引数なしの `release()` は `A1 00 00` を返す。

| NyX 入力 | 3DS 入力 | Byte 1 | Byte 2 | Byte 3 |
|----------|----------|--------|--------|--------|
| `Hat.LEFT` | LEFT | `A1` | `01` | `00` |
| `Hat.DOWN` | DOWN | `A1` | `02` | `00` |
| `Hat.RIGHT` | RIGHT | `A1` | `04` | `00` |
| `Hat.UP` | UP | `A1` | `08` | `00` |
| `Button.A` | A | `A1` | `10` | `00` |
| `Button.B` | B | `A1` | `20` | `00` |
| `Button.X` | X | `A1` | `40` | `00` |
| `Button.Y` | Y | `A1` | `80` | `00` |
| `Button.L` | L | `A1` | `00` | `01` |
| `Button.R` | R | `A1` | `00` | `02` |
| `Button.HOME` | HOME | `A1` | `00` | `04` |
| `Button.PLUS` | START | `A1` | `00` | `08` |
| `Button.MINUS` | SELECT | `A1` | `00` | `10` |
| `ThreeDSButton.POWER` | POWER | `A1` | `00` | `20` |
| `Button.ZL` | ZL | `A1` | `00` | `40` |
| `Button.ZR` | ZR | `A1` | `00` | `80` |

`Hat.UPRIGHT` などの斜め入力は、対応する 2 方向のビット OR とする。例: `Hat.UPRIGHT` は `A1 0C 00`。

### スライドパッド変換

スライドパッドは `A2 x y` の 3 バイトで送信する。既存の `LStick` は `x` / `y` が `0..255` であるため、3DS の DAC 範囲へ変換する。

| 入力 | Byte 1 | Byte 2 | Byte 3 |
|------|--------|--------|--------|
| CENTER | `A2` | `80` | `80` |
| LEFT | `A2` | `7E` | `80` |
| DOWN | `A2` | `80` | `FA` |
| RIGHT | `A2` | `FA` | `80` |
| UP | `A2` | `80` | `7E` |

変換規則は以下である。

```python
def convert_slide_axis(value: int) -> int:
    if value < 0 or value > 255:
        raise ValueError("Stick axis must be in range 0..255")
    if value <= 128:
        return round(0x7E + (value / 128) * (0x80 - 0x7E))
    return round(0x80 + ((value - 128) / 127) * (0xFA - 0x80))
```

### C スティック変換

C スティックは `A4 x y` の 3 バイトで送信する。既存の `RStick` を符号付き 8 ビット相当のオフセットへ変換する。

| 入力 | Byte 1 | Byte 2 | Byte 3 |
|------|--------|--------|--------|
| CENTER | `A4` | `00` | `00` |
| LEFT | `A4` | `80` | `00` |
| DOWN | `A4` | `00` | `7F` |
| RIGHT | `A4` | `7F` | `00` |
| UP | `A4` | `00` | `80` |

変換規則は以下である。

```python
def convert_c_stick_axis(value: int) -> int:
    if value < 0 or value > 255:
        raise ValueError("Stick axis must be in range 0..255")
    signed = max(-128, min(127, value - 128))
    return signed & 0xFF
```

### タッチ変換

タッチは 5 バイトで送信する。X は `0..320`、Y は `0..240` の範囲だけ許可する。3DS のタッチ画面は横幅 320 であり、X 座標は 1 バイト (`0..255`) に収まらないため 16 bit 相当の `x_high` / `x_low` に分割する。Y 座標は `0..240` で 1 バイトに収まるため `y_low` のみを送信する。

| 操作 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 |
|------|--------|--------|--------|--------|--------|
| TouchUp | `B2` | `00` | `00` | `00` | `00` |
| TouchDown | `B2` | `01` | `x_high` | `x_low` | `y_low` |

| フィールド | 定義 | 例 (`x=320`, `y=240`) |
|------------|------|-----------------------|
| `x_high` | `x` の上位 8 bit。`(x >> 8) & 0xFF` | `0x01` |
| `x_low` | `x` の下位 8 bit。`x & 0xFF` | `0x40` |
| `y_low` | `y` の下位 8 bit。`y & 0xFF`。Y は `0..240` のため上位バイトを持たない | `0xF0` |

```python
def build_touch_down_command(x: int, y: int) -> bytes:
    if not 0 <= x <= 320:
        raise ValueError("Touch X must be in range 0..320")
    if not 0 <= y <= 240:
        raise ValueError("Touch Y must be in range 0..240")
    return bytes([0xB2, 0x01, (x >> 8) & 0xFF, x & 0xFF, y & 0xFF])
```

`TouchState.down(x, y)` はタッチ押下、`TouchState.up()` はタッチ解放を表す。`build_press_command((TouchState.down(x, y),))` と `build_touch_down_command(x, y)` は同じタッチ状態を生成する。`build_release_command((TouchState.down(x, y),))` と `build_release_command((TouchState.up(),))` はどちらもタッチ状態を解放する。`build_touch_down_command(x, y)` は内部のタッチ状態を押下中に更新し、ボタン・スティック状態を含む 14 バイトの入力状態フレームを返す。`build_touch_up_command()` はタッチ状態だけを解放し、ボタン・スティック状態は維持した 14 バイトを返す。

`Command.touch(x, y, dur, wait)` は `TouchState.down(x, y) -> wait(dur) -> TouchState.up() -> wait(wait)` の順に送信する便利 API である。`TouchState.down()` 後に `TouchState.up()` しない状態は他操作を阻害するため、`Command.touch` は必ず解放まで行う。

### 補助制御コマンド

| 操作 | 入力 | 送信バイト |
|------|------|------------|
| スリープ抑止有効 | `enabled=True` | `FC 01` |
| スリープ抑止無効 | `enabled=False` | `FC 00` |
| Touch Calibration Data Write | `x_min, x_max, y_min, y_max` | `B3 Xmin Xmax Ymin Ymax` |
| Touch Calibration Data Read | なし | `B4` |
| Touch Calibration Factory Reset | なし | `B5` |
| Touch Calibration Factory Write | `factory=True, x_min, x_max, y_min, y_max` | `B6 Xmin Xmax Ymin Ymax` |

バージョン照会 (`B1`) とボーレート変更 (`A3 ...`) は、通常マクロ操作で使うコマンドではないため初回実装の対象外とする。ボーレートは NyX 側のシリアル接続設定で扱う。キャリブレーション値はプロトコル表の 1 バイト値として扱い、各値は `0..255` の範囲だけ許可する。

### プロトコル別ボーレート解決

3DS デバイスの既定ボーレートは 115200 bps とする。シリアル接続時は、プロトコル名を先に解決し、明示的なボーレート指定がない場合にプロトコル既定値を使う。

| プロトコル | 既定ボーレート | 対応ボーレート | 備考 |
|------------|----------------|----------------|------|
| `CH552` | `9600` | `9600` | 既存挙動を維持する |
| `PokeCon` | `9600` | `9600`, `19200`, `38400`, `57600`, `115200` | 既存挙動を維持する |
| `3DS` | `115200` | `9600`, `19200`, `57600`, `115200` | `ThreeDS`, `Nintendo3DS` を別名として受け付ける |

CLI の接続順は以下に変更する。

```python
protocol_name = args.protocol
baudrate = ProtocolFactory.resolve_baudrate(protocol_name, args.baud)
serial_manager.set_active(args.serial, baudrate)
protocol = ProtocolFactory.create_protocol(protocol_name)
```

GUI ではプロトコル選択時に `ProtocolFactory.get_default_baudrate(protocol_name)` を参照し、`serial_baud` の選択値を更新する。ユーザがボーレートを明示選択した場合はその値を優先するが、3DS を新規選択した直後の初期値は `115200` とする。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `serial_protocol` | `str` | `"CH552"` | `"3DS"` を追加する。既存値は変更しない |
| `serial_baud` | `int` | プロトコル依存 | シリアル接続時のボーレート。`CH552` / `PokeCon` は `9600`、`3DS` は `115200` を既定値とする。明示値がある場合は明示値を優先する |
| `--baud` | `int \| None` | `None` | CLI の任意引数。省略時は `ProtocolFactory.resolve_baudrate()` でプロトコル既定値を使う |
| `touch_x_min` | `int` | `0` | タッチ X の最小値。初回実装では定数として扱い、設定永続化はしない |
| `touch_x_max` | `int` | `320` | タッチ X の最大値。初回実装では定数として扱い、設定永続化はしない |
| `touch_y_min` | `int` | `0` | タッチ Y の最小値。初回実装では定数として扱い、設定永続化はしない |
| `touch_y_max` | `int` | `240` | タッチ Y の最大値。初回実装では定数として扱い、設定永続化はしない |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `UnsupportedKeyError` | `Button.CAP` / `Button.LS` / `Button.RS` など 3DS 仕様にない入力が指定された、または `TouchState` が未対応プロトコルで指定された |
| `ValueError` | タッチ座標、スティック軸、キャリブレーション値、プロトコル非対応ボーレートが許容範囲外 |
| `NotImplementedError` | 3DS が対応しない `build_keyboard_command` / `build_keytype_command` が呼ばれた、または未対応プロトコルで `Command.touch` 等が呼ばれた |

エラーは握りつぶさず呼び出し元へ伝播する。`DefaultCommand` は送信前にプロトコルが必要メソッドを持つことを検査し、未対応時は `NotImplementedError` を送出する。

### シングルトン管理

新しいシングルトンは追加しない。既存の `serial_manager` がアクティブなシリアルデバイスを管理し、`ProtocolFactory` がプロトコルインスタンスを生成する。テストでは既存の `reset_for_testing()` 方針に従い、プロトコルインスタンスをテストごとに新規作成する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_3ds_press_single_button` | `Button.A` が `A1 10 00 A2 80 80 A4 00 00 B2 00 00 00 00` に変換される |
| ユニット | `test_3ds_press_multiple_buttons` | `Button.A`, `Button.B`, `Hat.UP`, `Button.MINUS` が OR され、固定長 14 バイトで返る |
| ユニット | `test_3ds_press_diagonal_hat` | `Hat.UPRIGHT` がボタン部 `A1 0C 00` に反映される |
| ユニット | `test_3ds_release_specific_button` | 押下済みボタンの対象ビットだけがクリアされる |
| ユニット | `test_3ds_release_all` | 引数なし解放が全ニュートラルの 14 バイトになる |
| ユニット | `test_3ds_slide_pad_presets` | `LStick.CENTER` / `LEFT` / `RIGHT` / `UP` / `DOWN` が資料値と一致する |
| ユニット | `test_3ds_c_stick_presets` | `RStick.CENTER` / `LEFT` / `RIGHT` / `UP` / `DOWN` が資料値と一致する |
| ユニット | `test_3ds_mixed_input_fixed_frame` | ボタン・スライドパッド・C スティック・`TouchState.down()` が固定順の 14 バイトに結合される |
| ユニット | `test_3ds_touch_state_keytype` | `TouchState.down(320, 240)` が末尾に `B2 01 01 40 F0` を含む 14 バイトになる |
| ユニット | `test_3ds_touch_state_release` | `build_release_command((TouchState.down(320, 240),))` がタッチ状態だけを解放する |
| ユニット | `test_3ds_touch_down` | `touch_down(320, 240)` が末尾に `B2 01 01 40 F0` を含む 14 バイトになる |
| ユニット | `test_3ds_touch_up` | `touch_up()` が末尾に `B2 00 00 00 00` を含む 14 バイトになる |
| ユニット | `test_3ds_touch_out_of_range` | X/Y 範囲外で `ValueError` が送出される |
| ユニット | `test_3ds_disable_sleep` | `enabled=True` が `FC 01`、`False` が `FC 00` になる |
| ユニット | `test_3ds_unsupported_key` | 3DS 非対応キーで `UnsupportedKeyError` が送出される |
| ユニット | `test_protocol_factory_creates_3ds` | `ProtocolFactory.create_protocol("3DS")` が `ThreeDSSerialProtocol` を返す |
| ユニット | `test_protocol_factory_3ds_default_baudrate` | `ProtocolFactory.get_default_baudrate("3DS")` が `115200` を返す |
| ユニット | `test_protocol_factory_rejects_unsupported_baudrate` | プロトコル非対応ボーレートで `ValueError` が送出される |
| ユニット | `test_cli_create_protocol_3ds` | CLI の `create_protocol("3DS")` が GUI と同じ生成経路を使う |
| ユニット | `test_cli_uses_3ds_default_baudrate` | `--protocol 3DS` かつ `--baud` 省略時に `serial_manager.set_active(..., 115200)` が呼ばれる |
| ユニット | `test_cli_baud_override` | `--baud` 指定時はプロトコル既定値ではなく明示値が使われる |
| ユニット | `test_default_command_touch_sequence` | `Command.touch` が TouchDown、待機、TouchUp、待機の順で送信する |
| GUI | `test_device_tab_protocol_options_include_3ds` | 設定ダイアログのプロトコル選択肢に `3DS` が含まれる |
| GUI | `test_device_tab_selects_3ds_default_baudrate` | 3DS 選択時にボーレート選択が `115200` になる |
| 結合 | `test_3ds_command_with_dummy_serial` | DummySerialComm 相当の送信履歴で代表操作の送信順を確認する |
| ハードウェア | `test_3ds_device_button_touch` | `@pytest.mark.realdevice` で実機へ A ボタンとタッチを送信する |
| パフォーマンス | `test_3ds_protocol_build_perf` | 代表コマンド生成が 1 ms 未満であることを確認する |

## 6. 実装チェックリスト

- [x] 公開 API のシグネチャ確定
- [x] `ThreeDSButton` / `TouchState` と `KeyType` の追加
- [x] `ThreeDSSerialProtocol` の内部状態とボタン変換実装
- [x] スライドパッド / C スティック変換実装
- [x] `TouchState` によるタッチ状態変換実装
- [x] タッチ便利 API / スリープ抑止 / キャリブレーション系コマンド実装
- [x] `ProtocolFactory` への `3DS` 登録
- [x] `ProtocolFactory` へのプロトコル別既定ボーレート登録
- [x] CLI のプロトコル生成経路を `ProtocolFactory` に統一
- [x] CLI の `--baud` 追加と省略時のプロトコル既定ボーレート解決
- [x] GUI のプロトコル選択時の既定ボーレート反映
- [x] `Command` / `DefaultCommand` の 3DS 専用任意 API 実装
- [x] 既存テストが破壊されないことの確認
- [x] ユニットテスト作成・パス
- [x] GUI テスト作成・パス
- [ ] 統合テスト作成・パス
- [ ] 実機テストを `@pytest.mark.realdevice` として追加
- [x] 型ヒントの整合性チェック（ruff）
- [x] ドキュメントコメント（公開 API のみ）

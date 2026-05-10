# Nintendo 3DS シリアル通信プロトコル追加修正仕様書

> **文書種別**: 追加修正仕様。Nintendo 3DS シリアル通信プロトコル実装後、フレームワーク再設計との照合で見つかった Runtime / I/O Port 経路の不足を補う。
> **対象モジュール**: `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\hardware\`
> **親仕様**: `NINTENDO_3DS_SERIAL_PROTOCOL.md`
> **関連ドキュメント**: `..\..\..\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `..\..\..\framework\rearchitecture\FW_REARCHITECTURE_OVERVIEW.md`, `..\..\..\framework\rearchitecture\TEST_STRATEGY.md`
> **破壊的変更**: なし。既存 `Command` API、`DefaultCommand` import path、`ControllerOutputPort` 基本 API は維持する。

## 1. 概要

### 1.1 目的

Nintendo 3DS 向け touch / sleep 制御を、リアーキテクチャ後の `DefaultCommand -> ControllerOutputPort -> SerialProtocolInterface` 経路で実行可能にする。`DefaultCommand` は引き続き Runtime 内で生成される `Command` 実装として維持し、3DS 固有処理は controller 出力 Port の任意操作として接続する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがコントローラー操作、待機、キャプチャ、画像入出力、通知、ログを行うための高レベル API |
| DefaultCommand | `ExecutionContext` を受け取り、Ports へ委譲する標準 `Command` 実装。Runtime が実行ごとに生成する |
| ControllerOutputPort | コントローラー入力を出力する Port。基本操作を必須、touch / sleep を任意操作として扱う |
| SerialControllerOutputPort | `SerialCommInterface` と `SerialProtocolInterface` を接続し、生成されたバイト列をシリアル送信する adapter |
| 任意操作 | controller や protocol によって対応可否が異なる操作。非対応時は `NotImplementedError` を送出する |
| SerialProtocolInterface | 入力操作から送信バイト列を生成する抽象インターフェース |
| SerialCommInterface | バイト列送信だけを担当する抽象インターフェース |

### 1.3 背景・問題

3DS プロトコル本体は `build_touch_down_command()`、`build_touch_up_command()`、`build_disable_sleep_command()` を実装済みであり、ユニットテストも存在する。一方、リアーキテクチャ後の Runtime 実行経路では `DefaultCommand` が `ExecutionContext.controller` へ委譲し、実機シリアル経路の controller は `SerialControllerOutputPort` になる。

現行 `SerialControllerOutputPort` は `ControllerOutputPort` の基本操作だけを実装している。そのため、3DS protocol を選んでいても `cmd.touch()` や `cmd.disable_sleep()` は実シリアル経路へ接続されていない。

既存テストは `FakeFullCapabilityController` を使って `DefaultCommand.touch()` を検証しているため、この実シリアル adapter 経路の欠落を検出できていない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 3DS Runtime 経路の `cmd.touch()` | 実シリアル adapter 経路へ接続されていない | 3DS protocol 選択時に touch down / up frame をシリアル送信する |
| 3DS Runtime 経路の `cmd.disable_sleep()` | 実シリアル adapter 経路へ接続されていない | `FC 01` / `FC 00` をシリアル送信する |
| 非 3DS protocol の任意操作 | 実装方針が未整理 | `NotImplementedError` で明示的に失敗する |
| 統合テスト | 未整備 | fake serial / fake capture で Runtime 経路を検証する |
| 実機テスト | 未整備 | `@pytest.mark.realdevice` 付き 3DS smoke test を追加する |

### 1.5 着手条件

- `NINTENDO_3DS_SERIAL_PROTOCOL.md` の 3DS protocol、`ProtocolFactory`、CLI / GUI protocol 選択の実装が完了している。
- `RUNTIME_AND_IO_PORTS.md` の方針どおり、`DefaultCommand` は Runtime が `ExecutionContext` から生成する。
- `Command` はマクロ向け API、`ControllerOutputPort` は controller 出力 I/O 境界として扱う。
- 実機依存テストは `@pytest.mark.realdevice` を付け、通常テストから分離する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\agent\complete\local_001\FOLLOWUP_FIXES.md` | 新規 | 本仕様書 |
| `src\nyxpy\framework\core\io\ports.py` | 変更 | `ControllerOutputPort` に touch / sleep の非抽象任意メソッドを追加する |
| `src\nyxpy\framework\core\io\adapters.py` | 変更 | `SerialControllerOutputPort` で 3DS touch / sleep command を serial 送信へ橋渡しする |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `DefaultCommand` の touch / sleep を capability 判定ではなく Port 委譲へ簡素化する |
| `tests\unit\framework\io\test_adapters.py` | 変更 | 3DS / 非 3DS protocol の任意操作と送信バイト列を検証する |
| `tests\unit\framework\runtime\test_default_command_ports.py` | 変更 | `DefaultCommand` が Port へ委譲し、非対応時の例外を伝播することを検証する |
| `tests\integration\test_3ds_runtime_serial_protocol.py` | 新規 | Runtime + fake serial + fake capture で `cmd.touch()` / `cmd.disable_sleep()` を検証する |
| `tests\hardware\test_3ds_serial_protocol_device.py` | 新規 | 実機接続時の代表 3DS コマンド送信を `@pytest.mark.realdevice` で検証する |
| `spec\agent\complete\local_001\NINTENDO_3DS_SERIAL_PROTOCOL.md` | 変更 | 本仕様への参照と実装チェックリストの完了状態を反映する |

## 3. 設計方針

### 3.1 アーキテクチャ上の位置づけ

`DefaultCommand` は削除対象ではない。再設計後の実行経路では、Runtime が `DefaultCommand(context=...)` を生成し、`DefaultCommand` は `ExecutionContext.controller` へ操作を委譲する。

```text
MacroRuntime
  -> DefaultCommand(context=ExecutionContext)
    -> ControllerOutputPort
      -> SerialControllerOutputPort
        -> SerialProtocolInterface
        -> SerialCommInterface.send(bytes)
```

3DS 固有操作の責務は `DefaultCommand` ではなく、controller 出力 Port と protocol adapter の境界に置く。`DefaultCommand` は touch / sleep に対しても protocol や serial device を直接参照しない。

### 3.2 採用方針

採用する方針は、`ControllerOutputPort` に任意操作の既定実装を置き、`DefaultCommand` が Port へ直接委譲する方式である。`ControllerOutputPort` は基本操作を抽象メソッドとして持ち、touch / sleep は非抽象の任意メソッドとして持つ。既定実装は `NotImplementedError` を送出する。

`DefaultCommand` は `isinstance(..., TouchInputCapability)` のような capability 判定を行わず、controller Port へ委譲する。非対応 controller では Port 側の `NotImplementedError` がそのまま呼び出し元へ伝播する。

`SerialControllerOutputPort` は、注入された protocol が touch / sleep command builder を持つ場合にだけ該当 bytes を送信する。対応しない protocol の場合は `NotImplementedError` を送出する。

```text
cmd.touch(x, y)
  -> DefaultCommand.touch()
    -> controller.touch_down(x, y)
      -> SerialControllerOutputPort.touch_down()
        -> protocol.build_touch_down_command(x, y)
        -> serial_device.send(bytes)
```

### 3.3 却下する方針

| 方針 | 却下理由 |
|------|----------|
| `ThreeDSCommand` を追加する | 3DS 差分は controller 出力の一部だけであり、capture / resource / notify / log / wait を含む `Command` 全体を分岐させる必要がない |
| `ControllerOutputPort` に touch / sleep を抽象メソッドとして追加する | すべての controller fake / adapter に空実装を強制し、任意操作という性質が薄れる |
| `DefaultCommand` が `SerialProtocolInterface` や `SerialCommInterface` を直接参照する | Port 分離を壊し、GUI / CLI / テストで再び具象 I/O に依存する |
| `Command.touch()` を廃止して `TouchState` だけに寄せる | 既に `Command` 公開 API として固定されており、Runtime シリアル経路の欠落も解消しない |
| `ProtocolFactory` が controller adapter まで選択する | protocol 生成責務と controller adapter 生成責務が混ざる |

### 3.4 Command と ControllerOutputPort の責務

| 層 | 責務 | touch / sleep で扱うこと |
|----|------|--------------------------|
| `Command` | マクロ作者向け API。待機、ログ、中断確認、capture / resource / notify を含む実行文脈を扱う | `touch(dur, wait)` の順序、待機、中断確認、ログ |
| `DefaultCommand` | `Command` の標準実装。Port へ委譲する | `touch_down -> wait -> touch_up -> wait` を実行し、実送信は Port へ委譲する |
| `ControllerOutputPort` | controller 出力の I/O 境界 | touch down / up、sleep control を即時出力操作として受ける。非対応なら例外 |
| `SerialProtocolInterface` | 操作を送信 bytes へ変換する | 3DS touch / sleep の bytes を生成する |
| `SerialCommInterface` | bytes を送信する | 生成済み bytes を送る |

`Command` は「何をマクロ操作として実行するか」を表し、`ControllerOutputPort` は「controller 出力として何を送るか」を表す。任意操作を Port に置く理由は、3DS 以外の将来デバイスでも controller 出力として同じ操作を実装できる余地を残し、`Command` が具象 protocol を知らない状態を維持するためである。

### 3.5 公開 API 方針

`Command.touch()`、`Command.touch_down()`、`Command.touch_up()`、`Command.disable_sleep()` のシグネチャは変更しない。

`ControllerOutputPort` へ追加する touch / sleep は非抽象メソッドであり、既存の派生 fake / adapter は変更なしでも動作する。非対応時の既定挙動は `NotImplementedError` である。

### 3.6 後方互換性

破壊的変更は行わない。CH552 / PokeCon など touch / sleep 非対応 protocol は、これまでどおり `cmd.touch()` / `cmd.disable_sleep()` 呼び出し時に `NotImplementedError` になる。

`TouchInputCapability` / `SleepControlCapability` のような別 interface は追加しない。既存実装に残っている場合は、本追加修正で参照を解消し、互換 shim として残さない。

### 3.7 レイヤー構成

| レイヤー | 責務 |
|----------|------|
| `Command` | マクロ公開 API と中断・待機・ログ処理を提供する |
| `DefaultCommand` | Port へ委譲する |
| `ControllerOutputPort` | 基本操作を必須、touch / sleep を任意操作として受ける |
| `SerialControllerOutputPort` | serial device と protocol を接続し、protocol が生成した bytes を送信する |
| `SerialProtocolInterface` / 具象 protocol | 入力操作から送信 bytes を生成する |
| `SerialCommInterface` | bytes 送信のみを担当する |

### 3.8 性能要件

| 指標 | 目標値 |
|------|--------|
| touch command 送信 | protocol の `build_touch_down_command()` / `build_touch_up_command()` 呼び出しと `send()` 以外の追加 I/O なし |
| sleep command 送信 | protocol の `build_disable_sleep_command()` 呼び出しと `send()` 以外の追加 I/O なし |
| 非対応 protocol の基本操作 | 既存 `press` / `hold` / `release` の送信 bytes と呼び出し回数を変更しない |

### 3.9 並行性・スレッド安全性

`SerialControllerOutputPort` は既存と同じく、単一マクロ実行スレッドまたは GUI manual input から使う前提である。protocol は入力状態を保持するため、同一 protocol インスタンスを複数スレッドで共有しない。今回の追加修正では新しい lock や singleton を追加しない。

## 4. 実装仕様

### 4.1 公開インターフェース

`ControllerOutputPort` に任意操作の既定実装を追加する。

```python
class ControllerOutputPort(ABC):
    @abstractmethod
    def press(self, keys: tuple[KeyType, ...]) -> None: ...

    @abstractmethod
    def hold(self, keys: tuple[KeyType, ...]) -> None: ...

    @abstractmethod
    def release(self, keys: tuple[KeyType, ...] = ()) -> None: ...

    @abstractmethod
    def keyboard(self, text: str) -> None: ...

    @abstractmethod
    def type_key(self, key: KeyCode | SpecialKeyCode) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def touch_down(self, x: int, y: int) -> None:
        raise NotImplementedError("Current controller output does not support touch input.")

    def touch_up(self) -> None:
        raise NotImplementedError("Current controller output does not support touch input.")

    def disable_sleep(self, enabled: bool = True) -> None:
        raise NotImplementedError("Current controller output does not support sleep control.")
```

`DefaultCommand` は任意操作を Port へ直接委譲する。

```python
def touch_down(self, x: int, y: int) -> None:
    self.log(f"Touch down: ({x}, {y})", level="DEBUG")
    self.context.controller.touch_down(x, y)


def touch_up(self) -> None:
    self.log("Touch up", level="DEBUG")
    self.context.controller.touch_up()


def disable_sleep(self, enabled: bool = True) -> None:
    self.log(f"Disable sleep: {enabled}", level="DEBUG")
    self.context.controller.disable_sleep(enabled)
```

### 4.2 `SerialControllerOutputPort` の任意操作

`SerialControllerOutputPort` は protocol に対応 builder がある場合だけ bytes を送信する。対応 builder がない場合は `NotImplementedError` を送出する。

```python
def touch_down(self, x: int, y: int) -> None:
    builder = getattr(self.protocol, "build_touch_down_command", None)
    if builder is None:
        raise NotImplementedError("Current serial protocol does not support touch input.")
    self.serial_device.send(builder(x, y))


def touch_up(self) -> None:
    builder = getattr(self.protocol, "build_touch_up_command", None)
    if builder is None:
        raise NotImplementedError("Current serial protocol does not support touch input.")
    self.serial_device.send(builder())


def disable_sleep(self, enabled: bool = True) -> None:
    builder = getattr(self.protocol, "build_disable_sleep_command", None)
    if builder is None:
        raise NotImplementedError("Current serial protocol does not support sleep control.")
    self.serial_device.send(builder(enabled))
```

この `getattr()` は対応可否の判定であり、例外を握りつぶす用途では使わない。builder 呼び出しで発生した `ValueError`、`UnsupportedKeyError`、`RuntimeError` は呼び出し元へ伝播させる。

### 4.3 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `serial_protocol` | `str` | `"CH552"` | `"3DS"` の場合、`SerialControllerOutputPort` が 3DS touch / sleep command を送信できる |
| `serial_baud` | `int` | protocol 依存 | 3DS は `ProtocolFactory.resolve_baudrate("3DS", None)` により `115200` を使う |
| `NYX_REAL_3DS_SERIAL_PORT` | `str` | なし | 3DS 実機テストで使用する任意の環境変数名。実装時に既存 `NYX_REAL_SERIAL_PORT` と統合するか決める |
| `NYX_REAL_3DS_BAUD` | `int` | `115200` | 3DS 実機テスト用ボーレート。省略時は protocol 既定値を使う |

### 4.4 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `NotImplementedError` | 非対応 controller / protocol で `DefaultCommand.touch()` / `disable_sleep()` が呼ばれた |
| `ValueError` | 3DS touch 座標、stick 軸、非対応 baudrate が範囲外 |
| `UnsupportedKeyError` | 3DS protocol で表現できないキーが指定された |
| `RuntimeError` | serial device が未 open の状態で `send()` された |

`DefaultCommand` と `SerialControllerOutputPort` は、これらの例外を成功扱いに変換しない。

### 4.5 シングルトン管理

新しいシングルトンは追加しない。Runtime は `MacroRuntimeBuilder` が注入した Port を使う。`ProtocolFactory` は引き続き protocol instance と baudrate metadata の解決だけを担当し、controller adapter の lifetime を所有しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_controller_output_port_optional_methods_raise_by_default` | 基本 fake controller で touch / sleep が `NotImplementedError` になる |
| ユニット | `test_serial_controller_touch_sends_3ds_frames` | `touch_down(320, 240)` / `touch_up()` が 3DS frame を `send()` する |
| ユニット | `test_serial_controller_disable_sleep_sends_3ds_command` | `disable_sleep(True)` / `False` が `FC 01` / `FC 00` を送信する |
| ユニット | `test_serial_controller_touch_unsupported_protocol_raises` | CH552 protocol で `touch_down()` が `NotImplementedError` になる |
| ユニット | `test_serial_controller_basic_input_unchanged_for_ch552` | CH552 の `press` / `release` 送信が既存と変わらない |
| ユニット | `test_default_command_touch_delegates_to_controller_port` | `DefaultCommand.touch()` が Port の `touch_down()` / `touch_up()` を順に呼ぶ |
| ユニット | `test_default_command_unsupported_touch_error_propagates` | Port 既定実装の `NotImplementedError` が伝播する |
| 結合 | `test_3ds_runtime_command_touch_with_fake_serial` | Runtime で実行したマクロの `cmd.touch()` が fake serial へ TouchDown / TouchUp frame を送る |
| 結合 | `test_3ds_runtime_command_disable_sleep_with_fake_serial` | Runtime で実行したマクロの `cmd.disable_sleep()` が fake serial へ `FC 01` を送る |
| 結合 | `test_non_touch_protocol_runtime_touch_fails_explicitly` | CH552 protocol の Runtime 経路で `cmd.touch_down()` が `NotImplementedError` になる |
| ハードウェア | `test_3ds_device_button_touch` | `@pytest.mark.realdevice`。実機へ A ボタン、touch down / up、sleep control の代表コマンドを送信する |
| 静的 | `test_default_command_does_not_import_serial_protocol` | `DefaultCommand` が protocol / serial 具象実装を直接 import しない |

## 6. 実装チェックリスト

- [x] `ControllerOutputPort` に touch / sleep の非抽象任意メソッドを追加する。
- [x] `DefaultCommand` の touch / sleep を Port 直接委譲へ簡素化する。
- [x] `SerialControllerOutputPort` で touch / sleep command を serial 送信へ橋渡しする。
- [x] CH552 / PokeCon の非対応任意操作が `NotImplementedError` で失敗することを固定する。
- [x] `DefaultCommand` が protocol / serial を直接参照しないことを固定する。
- [x] Runtime 統合テストで 3DS touch / sleep 送信経路を検証する。
- [x] 実機テストを `@pytest.mark.realdevice` として追加する。
- [x] `NINTENDO_3DS_SERIAL_PROTOCOL.md` の実装チェックリストを更新する。

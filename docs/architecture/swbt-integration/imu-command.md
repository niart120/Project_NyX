# IMU command

IMU 入力は、controller backend 全体の公開命令として `Command` と `ControllerOutputPort` に追加する。swbt backend は実装し、対応しない backend は既定の unsupported として扱う。

GUI manual input から IMU は操作しない。

## Public API

`IMUFrame` は NyXPy 側の入力 model である。swbt の `IMUFrame` とは mapper 内で変換する。

```python
from dataclasses import dataclass

Vector3 = tuple[int, int, int]

@dataclass(frozen=True)
class IMUFrame:
    accelerometer: Vector3 = (0, 0, 0)
    gyroscope: Vector3 = (0, 0, 0)

    @classmethod
    def neutral(cls) -> "IMUFrame":
        return cls()

    @classmethod
    def raw(
        cls,
        *,
        accel: Vector3 | None = None,
        gyro: Vector3 | None = None,
    ) -> "IMUFrame":
        return cls(
            accelerometer=accel or (0, 0, 0),
            gyroscope=gyro or (0, 0, 0),
        )

    @classmethod
    def accel(cls, *, x: int = 0, y: int = 0, z: int = 0) -> "IMUFrame":
        return cls(accelerometer=(x, y, z))

    @classmethod
    def gyro(cls, *, x: int = 0, y: int = 0, z: int = 0) -> "IMUFrame":
        return cls(gyroscope=(x, y, z))
```

`Command` には `imu(...)` を追加する。

```python
class Command(ABC):
    ...

    def imu(self, *frames: IMUFrame) -> None:
        """IMU 入力を現在状態へ反映する。対応しない backend は NotImplementedError。"""
        raise NotImplementedError("Current controller output does not support IMU input.")
```

`DefaultCommand` は controller port へ委譲する。

```python
@check_interrupt
def imu(self, *frames: IMUFrame) -> None:
    self._debug_command(f"Sending IMU frames: {frames}")
    self.context.controller.imu(*frames)
```

## ControllerOutputPort

`ControllerOutputPort` に既定 unsupported の `imu(...)` を追加する。既存 backend は override しなくても動作する。

```python
class ControllerOutputPort(ABC):
    ...

    @property
    def supports_imu(self) -> bool:
        return False

    def imu(self, *frames: IMUFrame) -> None:
        raise NotImplementedError("Current controller output does not support IMU input.")
```

swbt backend だけが `supports_imu=True` として override する。

```python
class SwbtControllerOutputPort(ControllerOutputPort):
    @property
    def supports_imu(self) -> bool:
        return True

    def imu(self, *frames: IMUFrame) -> None:
        with self._lock:
            self._ensure_open()
            self._mapper.set_imu(self._state, frames)
            self._apply_locked()
```

## frame count

`cmd.imu(...)` は 1 frame または 3 frame を受ける。

| 呼び出し | 意味 |
|---|---|
| `cmd.imu(frame)` | 1 frame を 3 frame 分に複製して使う |
| `cmd.imu(frame1, frame2, frame3)` | 3 frame を順に使う |
| `cmd.imu()` | invalid input |
| `cmd.imu(frame1, frame2)` | invalid input |
| `cmd.imu(frame1, frame2, frame3, frame4)` | invalid input |

swbt の `InputState.with_imu(...)` と同じ規則に合わせる。

## semantics

IMU は現在入力状態の一部である。`cmd.imu(...)` は button / stick を変更せず、IMU 部分だけを置き換える。

```python
cmd.hold(Button.A)
cmd.imu(IMUFrame.gyro(x=100, y=0, z=0))
# A は押下されたまま、IMU だけ更新される
```

`cmd.release()` または port close は全入力 neutral として扱い、IMU も neutral に戻す。IMU だけを neutral に戻す場合は次を使う。

```python
cmd.imu(IMUFrame.neutral())
```

## unsupported backend

serial backend と既存 protocol は、`ControllerOutputPort.imu()` の既定実装により unsupported になる。

| backend | `supports_imu` | 動作 |
|---|---:|---|
| swbt | true | `InputState.with_imu(...)` へ変換して送信 |
| serial CH552 | false | `NotImplementedError` |
| 3DS touch 対応 protocol | false | `NotImplementedError` |
| dummy swbt | true | state を記録する |
| dummy serial | false | `NotImplementedError` |

silent no-op にはしない。IMU を必要とする macro を非対応 backend で実行した場合は、早く明確に失敗させる。

## GUI scope

今回の GUI に次は入れない。

- preset gesture
- pose editor
- raw frame editor
- IMU recording
- IMU replay
- mouse-to-gyro mapping

IMU の検証は programmatic test または developer tool に寄せる。

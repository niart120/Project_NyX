"""IMU 入力の共通 model。"""

from dataclasses import dataclass

type Vector3 = tuple[int, int, int]

_ZERO_VECTOR: Vector3 = (0, 0, 0)


@dataclass(frozen=True, slots=True)
class IMUFrame:
    """Controller backend へ渡す 1 frame 分の IMU 入力。"""

    accelerometer: Vector3 = _ZERO_VECTOR
    gyroscope: Vector3 = _ZERO_VECTOR

    @classmethod
    def neutral(cls) -> "IMUFrame":
        """加速度とジャイロを中立値にした frame を返す。"""
        return cls()

    @classmethod
    def raw(
        cls,
        *,
        accel: Vector3 | None = None,
        gyro: Vector3 | None = None,
    ) -> "IMUFrame":
        """生の加速度・ジャイロ値から frame を作る。"""
        return cls(
            accelerometer=accel or _ZERO_VECTOR,
            gyroscope=gyro or _ZERO_VECTOR,
        )

    @classmethod
    def accel(cls, *, x: int = 0, y: int = 0, z: int = 0) -> "IMUFrame":
        """加速度だけを指定した frame を作る。"""
        return cls(accelerometer=(x, y, z))

    @classmethod
    def gyro(cls, *, x: int = 0, y: int = 0, z: int = 0) -> "IMUFrame":
        """ジャイロだけを指定した frame を作る。"""
        return cls(gyroscope=(x, y, z))

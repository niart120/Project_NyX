"""swbt controller 種別と設定 model。"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class SwbtControllerType(StrEnum):
    """swbt backend が扱う controller 種別。"""

    PRO_CONTROLLER = "pro-controller"
    JOY_CON_L = "joy-con-l"
    JOY_CON_R = "joy-con-r"


@dataclass(frozen=True, slots=True)
class SwbtInputCapabilities:
    """NyX 入力単位で見た swbt controller の対応範囲。"""

    buttons: frozenset[Button]
    left_stick: bool
    right_stick: bool
    imu: bool


@dataclass(frozen=True, slots=True)
class SwbtControllerModel:
    """Project NyX 側の swbt controller 定義。"""

    controller_type: SwbtControllerType
    display_name: str
    default_key_store_name: str
    capabilities: SwbtInputCapabilities

    @property
    def settings_value(self) -> str:
        """Settings / CLI に保存する文字列表現。"""
        return self.controller_type.value

    def default_key_store_path(self, base_dir: Path = Path(".nyxpy/swbt")) -> Path:
        """Controller type ごとの既定 pairing key path を返す。"""
        return base_dir / self.default_key_store_name


@dataclass(frozen=True, slots=True)
class SwbtControllerConfig:
    """settings / CLI / GUI から正規化した swbt backend 設定。"""

    model: SwbtControllerModel
    adapter: str | None
    key_store_path: Path
    connect_timeout_sec: float = 30.0
    report_period_us: int | None = 8000


_PRO_BUTTONS = frozenset(Button)
_JOY_CON_L_BUTTONS = frozenset(
    {
        Button.L,
        Button.ZL,
        Button.MINUS,
        Button.LS,
        Button.CAP,
    }
)
_JOY_CON_R_BUTTONS = frozenset(
    {
        Button.A,
        Button.B,
        Button.X,
        Button.Y,
        Button.R,
        Button.ZR,
        Button.PLUS,
        Button.RS,
        Button.HOME,
    }
)

SUPPORTED_CONTROLLER_MODELS: dict[SwbtControllerType, SwbtControllerModel] = {
    SwbtControllerType.PRO_CONTROLLER: SwbtControllerModel(
        controller_type=SwbtControllerType.PRO_CONTROLLER,
        display_name="Pro Controller",
        default_key_store_name="pro-controller-bond.json",
        capabilities=SwbtInputCapabilities(
            buttons=_PRO_BUTTONS,
            left_stick=True,
            right_stick=True,
            imu=True,
        ),
    ),
    SwbtControllerType.JOY_CON_L: SwbtControllerModel(
        controller_type=SwbtControllerType.JOY_CON_L,
        display_name="Joy-Con L",
        default_key_store_name="joy-con-l-bond.json",
        capabilities=SwbtInputCapabilities(
            buttons=_JOY_CON_L_BUTTONS,
            left_stick=True,
            right_stick=False,
            imu=True,
        ),
    ),
    SwbtControllerType.JOY_CON_R: SwbtControllerModel(
        controller_type=SwbtControllerType.JOY_CON_R,
        display_name="Joy-Con R",
        default_key_store_name="joy-con-r-bond.json",
        capabilities=SwbtInputCapabilities(
            buttons=_JOY_CON_R_BUTTONS,
            left_stick=False,
            right_stick=True,
            imu=True,
        ),
    ),
}


def supported_controller_models() -> tuple[SwbtControllerModel, ...]:
    """GUI / CLI choices の正本になる controller model 一覧を返す。"""
    return tuple(SUPPORTED_CONTROLLER_MODELS.values())


def parse_controller_type(value: str | SwbtControllerType) -> SwbtControllerType:
    """Settings / CLI 入力を controller type に正規化する。"""
    if isinstance(value, SwbtControllerType):
        return value
    try:
        return SwbtControllerType(str(value))
    except ValueError as exc:
        raise ConfigurationError(
            f"unsupported swbt controller type: {value}",
            code="NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED",
            component="SwbtControllerConfig",
            details={"controller_type": str(value)},
            cause=exc,
        ) from exc


def resolve_controller_model(value: str | SwbtControllerType) -> SwbtControllerModel:
    """Controller type から Project NyX 側 model を取得する。"""
    return SUPPORTED_CONTROLLER_MODELS[parse_controller_type(value)]

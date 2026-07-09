# Controller model

controller type は単なる文字列ではなく、domain object として扱う。設定値や CLI option は文字列だが、`SwbtControllerConfig` に入る時点で `SwbtControllerType` と `SwbtControllerModel` に変換する。

実装 module は `nyxpy.framework.core.hardware.swbt.config` とする。`models.py` を分けるほどの独立した layer は作らない。

## 永続化値

| 値 | 表示名 | swbt class |
|---|---|---|
| `pro-controller` | Pro Controller | `ProController` |
| `joy-con-l` | Joy-Con L | `JoyConL` |
| `joy-con-r` | Joy-Con R | `JoyConR` |

TOML 例:

```toml
[controller.swbt]
controller_type = "pro-controller"
```

CLI 例:

```console
nyxpy run sample_macro --controller swbt --swbt-controller-type pro-controller
```

## 内部型

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TextIO

from swbt import (
    Button as SwbtButton,
    DiagnosticsConfig,
    JoyConL,
    JoyConR,
    ProController,
    SwitchGamepad,
)


class SwbtControllerType(str, Enum):
    PRO_CONTROLLER = "pro-controller"
    JOY_CON_L = "joy-con-l"
    JOY_CON_R = "joy-con-r"


@dataclass(frozen=True)
class SwbtInputCapabilities:
    buttons: frozenset[SwbtButton]
    left_stick: bool
    right_stick: bool
    imu: bool


@dataclass(frozen=True)
class SwbtControllerModel:
    controller_type: SwbtControllerType
    display_name: str
    controller_cls: type[SwitchGamepad]
    default_key_store_name: str
    capabilities: SwbtInputCapabilities

    @property
    def settings_value(self) -> str:
        return self.controller_type.value

    def default_key_store_path(self, base_dir: Path) -> Path:
        return base_dir / self.default_key_store_name
```

`SwbtControllerModel` は controller class と capability をまとめる immutable definition である。settings には保存しない。

## registry

```python
SUPPORTED_CONTROLLER_MODELS: dict[SwbtControllerType, SwbtControllerModel] = {
    SwbtControllerType.PRO_CONTROLLER: SwbtControllerModel(...),
    SwbtControllerType.JOY_CON_L: SwbtControllerModel(...),
    SwbtControllerType.JOY_CON_R: SwbtControllerModel(...),
}


def supported_controller_models() -> tuple[SwbtControllerModel, ...]:
    return tuple(SUPPORTED_CONTROLLER_MODELS.values())


def parse_controller_type(value: str | SwbtControllerType) -> SwbtControllerType:
    if isinstance(value, SwbtControllerType):
        return value
    try:
        return SwbtControllerType(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"unsupported swbt controller type: {value}",
            code="NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED",
            component="SwbtControllerConfig",
        ) from exc


def resolve_controller_model(value: str | SwbtControllerType) -> SwbtControllerModel:
    return SUPPORTED_CONTROLLER_MODELS[parse_controller_type(value)]
```

GUI choices と CLI choices は `supported_controller_models()` から作る。

## config

```python
@dataclass(frozen=True)
class SwbtControllerConfig:
    model: SwbtControllerModel
    adapter: str
    key_store_path: Path | None
    connect_timeout_sec: float = 30.0
    operation_timeout_sec: float = 5.0
    report_period_us: int | None = 8000
    diagnostics_path: Path | None = None
    reset_on_port_create: bool = True
```

`SwbtControllerConfig` は `controller_type: str` を持たない。設定 parser が `model` へ正規化する。

## capability validation

Joy-Con L/R では存在しない input がある。mapper は `SwbtControllerModel.capabilities` を参照し、非対応 input を silent no-op にしない。

| input | Pro Controller | Joy-Con L | Joy-Con R |
|---|---:|---:|---:|
| A/B/X/Y | yes | subset | subset |
| L/ZL | yes | yes | no |
| R/ZR | yes | no | yes |
| left stick | yes | yes | no |
| right stick | yes | no | yes |
| IMU | yes | yes | yes |

具体的な対応 button は swbt profile の `UnsupportedInputError` と実機確認を基準にする。Project_NyX 側では事前 validation で明らかに送れない入力を拒否する。

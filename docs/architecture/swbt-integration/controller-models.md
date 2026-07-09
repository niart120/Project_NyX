# Controller model

controller type は単なる文字列ではなく、domain object として扱う。設定値や CLI option は文字列だが、`SwbtControllerConfig` に入る時点で `SwbtControllerType` と `SwbtControllerModel` に変換する。

実装 module は `nyxpy.framework.core.hardware.swbt.config` とする。`models.py` を分けるほどの独立した layer は作らない。

## 永続化値

| 値 | 表示名 | 既定 key store |
|---|---|---|
| `pro-controller` | Pro Controller | `pro-controller-bond.json` |
| `joy-con-l` | Joy-Con L | `joy-con-l-bond.json` |
| `joy-con-r` | Joy-Con R | `joy-con-r-bond.json` |

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

from nyxpy.framework.core.constants import Button


class SwbtControllerType(str, Enum):
    PRO_CONTROLLER = "pro-controller"
    JOY_CON_L = "joy-con-l"
    JOY_CON_R = "joy-con-r"


@dataclass(frozen=True)
class SwbtInputCapabilities:
    buttons: frozenset[Button]
    left_stick: bool
    right_stick: bool
    imu: bool


@dataclass(frozen=True)
class SwbtControllerModel:
    controller_type: SwbtControllerType
    display_name: str
    default_key_store_name: str
    capabilities: SwbtInputCapabilities

    @property
    def settings_value(self) -> str:
        return self.controller_type.value

    def default_key_store_path(self, base_dir: Path = Path(".nyxpy/swbt")) -> Path:
        return base_dir / self.default_key_store_name
```

`SwbtControllerModel` は Project_NyX 側の controller 定義である。swbt の `ProController`、`JoyConL`、`JoyConR` などの runtime class は保持しない。session 作成時に `controller_type` から swbt controller class を解決する。

`capabilities` は NyX 側の入力可否の正本である。swbt runtime の `UnsupportedInputError` は防御的に map するが、通常の入力拒否は mapper の事前検証で行う。

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
    adapter: str | None = None
    key_store_path: Path | None = None
    connect_timeout_sec: float = 30.0
    report_period_us: int | None = 8000
```

`SwbtControllerConfig` は `controller_type: str` を持たない。設定 parser が `model` へ正規化する。

`adapter` は settings 上では空を許容する。pair / reconnect / run の直前に空なら `NYX_SWBT_ADAPTER_NOT_SELECTED` にする。

`key_store_path` が `None` の場合は、`model.default_key_store_path()` で `.nyxpy/swbt/<controller>-bond.json` を補う。

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

具体的な対応 button は Project_NyX 側の capabilities を正とする。swbt profile から `UnsupportedInputError` が返った場合も `NYX_SWBT_INPUT_UNSUPPORTED` に map する。

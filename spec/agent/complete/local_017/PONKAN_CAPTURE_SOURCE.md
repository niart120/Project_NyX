# ponkan-python キャプチャ入力ソース 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`, `src/nyxpy/framework/core/io/`
> **目的**: `ponkan-python` を利用し、直接接続型キャプチャデバイスから取得した画面を NyX の `FrameSourcePort` へ供給する。
> **関連ドキュメント**: `spec/framework/rearchitecture/RUNTIME_AND_IO_PORTS.md`, `spec/agent/complete/local_007/NINTENDO_3DS_SCREEN_COORDINATES_AND_TOUCH.md`, `spec/agent/complete/local_008/SETTINGS_PREVIEW_CAPTURE_REFRESH.md`, `spec/agent/wip/local_018/CAPTURE_SOURCE_GUI_SETTINGS.md`
> **外部調査日**: 2026-06-13

## 1. 概要

### 1.1 目的

`ponkan-python` の high-level capture API を NyX の画面取得経路へ組み込み、直接接続型キャプチャデバイスを `camera` / `window` と同じ `FrameSourcePort` として扱えるようにする。初期 device profile は new 3DS XL キャプチャボードである。マクロ・画像処理・通知は従来どおり OpenCV 互換の BGR frame を受け取り、USB backend や D3XX 依存は framework の hardware adapter に閉じ込める。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| ponkan-python | PyPI 配布名 `ponkan-python`。import package は `ponkan` |
| ponkan | 直接接続型キャプチャデバイスから frame を取得する外部ライブラリの package root |
| open_capture | `ponkan` の high-level reader 生成関数 |
| CaptureReader | `read()` / `read_frame()` / `stats()` / `close()` を持つ `ponkan` の reader |
| CaptureOutput.BOTH_VERTICAL | top 画面と bottom 画面を縦結合し、bottom を中央寄せした `400x480` 相当の出力 |
| capture source | GUI / settings 上の source type。`camera` / `window` / `capture` の 3 種類を扱う |
| capture provider | `capture` source の実装 provider。初期値は `ponkan` |
| capture device profile | provider 内の device model / layout profile。初期値は `n3dsxl` |
| physical capture device | 同じ provider / profile に一致する実物のキャプチャデバイス個体。初期実装では個体選択を扱わない |
| PonkanCaptureDevice | NyX 側で追加する `CaptureDeviceInterface` 互換 adapter |
| FrameSourcePort | Runtime が最新 frame を取得するための入力 port |
| D3XX backend | FTDI D3XX driver / PyD3XX を使う `ponkan-python` の USB backend。`ponkan-python 0.1.2` では PyD3XX は Windows 向け通常依存であり、`d3xx` extra ではない |
| aspect box | `400x480` の 3DS 画面を 16:9 canvas に黒帯付きで配置し、`Command.capture()` 後に `1280x720` の既存 3DS HD 座標へ合わせる変換 |

### 1.3 背景・問題

現行 NyX の画面取得は `camera` と `window` を入力ソースとして扱う。USB 等で直接読むキャプチャデバイス向けの source はなく、3DS 用の座標定数や touch 変換は存在しても、画面入力は外部 viewer やカメラデバイス化に依存する。

`ponkan-python 0.1.2` は現時点では new 3DS XL キャプチャボード向けの導線が整備された pre-alpha ライブラリで、`open_capture()` / `CaptureReader.read()` による薄い high-level API を提供する。将来ほかの device profile を扱う可能性があるため、NyX の source type は device model 名の `n3dsxl` ではなく、直接接続型キャプチャを表す `capture` とする。0.1.1 で package root は旧 `py3dscapture` から `ponkan` に変更され、0.1.2 では D3XX 用の PyD3XX が `d3xx` extra から Windows 向け通常依存へ移った。PyPI metadata と GitHub `pyproject.toml` は Python `>=3.12`、MIT license classifier / project license、Windows classifier、必須依存 `libusb1>=3.3.1` / `numpy>=2.0` / `pyd3xx>=1.1.4; sys_platform == "win32"` を示している。NyX 本体の Python 範囲は `>=3.12,<3.14` のまま扱い、`ponkan-python` は NyX の通常依存へ直置きしない。

`CaptureReader.read()` は timeout まで待つ API である。これを `FrameSourcePort.latest_frame()` の lock 内で直接呼ぶと GUI preview と Runtime capture が詰まるため、NyX adapter は独自の reader thread で最新 frame を cache し、`get_frame()` は copy を返すだけにする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 直接接続型キャプチャ入力 | 未対応 | `capture_source_type = "capture"`、`capture_provider = "ponkan"`、`capture_device_profile = "n3dsxl"` で `FrameSourcePort` に接続できる |
| マクロ API 変更 | なし | `Command.capture()` の呼び出しは変更しない |
| frame 形式 | camera/window ごとに BGR ndarray | capture source も BGR `uint8` ndarray copy |
| 3DS HD 座標 | 定数のみ存在 | `capture_device_profile = "n3dsxl"` では既定で aspect box を有効化し、`THREEDS_HD_*` と一致させる |
| 複数物理デバイス | 未定義 | 初期実装では個体選択を持たず、`ponkan.open_capture()` の既定選択に委譲する。複数台接続時にどの個体へ接続するかは保証しない |
| dependency blast radius | 依存なし | `ponkan-python` 本体を optional extra `ponkan` に隔離する。PyD3XX は上流の Windows platform-gated 通常依存として解決させる |
| GUI preview 競合 | `FrameSourcePort.try_latest_frame()` は非 blocking | capture source でも非 blocking を維持する |
| 実機なしテスト | Dummy capture 中心 | fake `CaptureReader` / fake opener で adapter と factory を単体テスト可能にする |

### 1.5 着手条件

- `ponkan-python` の PyPI metadata と GitHub API docs を実装直前に再確認すること。
- `ponkan-python 0.1.2` の `auto` backend は D3XX へ解決される前提で設計するが、backend 仕様が変わった場合は本仕様を更新すること。
- Windows の D3XX driver / PyD3XX 導入は実機テスト環境だけの前提にし、通常開発環境の必須条件にしないこと。
- `uv lock --check`、`uv run ruff check .`、`uv run ty check src/nyxpy --output-format concise --no-progress`、変更範囲の pytest が通ること。
- 実機確認は `@pytest.mark.realdevice` と明示的な環境変数で gate し、通常 CI では skip すること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | optional extra `ponkan` として `ponkan-python>=0.1.2,<0.2.0 ; sys_platform == "win32"` を追加する |
| `src/nyxpy/framework/core/hardware/camera_capture.py` | 変更 | capture device の not-ready / fatal-read 例外を分離し、`CaptureFrameSourcePort` が `FrameNotReadyError` と `FrameReadError` を区別できるようにする |
| `src/nyxpy/framework/core/hardware/ponkan_capture.py` | 新規 | `PonkanCaptureDevice` と `ponkan` adapter 実装を追加する |
| `src/nyxpy/framework/core/hardware/capture_source.py` | 変更 | `CaptureSourceType` と `CaptureSourceConfig` に `capture` / `PonkanCaptureSourceConfig` を追加し、settings から構築する |
| `src/nyxpy/framework/core/hardware/__init__.py` | 変更 | 必要な公開型を export する。optional dependency import はここで発生させない |
| `src/nyxpy/framework/core/io/adapters.py` | 変更 | capture device not-ready / read-failed 例外を `FrameNotReadyError` / `FrameReadError` に変換する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | `FrameSourcePortFactory` に capture source 分岐と injectable `ponkan_capture_factory` を追加する |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `capture_source_type` choices と capture / ponkan 専用 settings を追加する |
| `src/nyxpy/framework/core/runtime/device_selection.py` | 変更なし | capture source は既存 camera discovery に混ぜず、source type 選択で open する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更なし | GUI からの source 選択・ponkan 設定編集は `local_018` で扱う |
| `src/nyxpy/gui/app_services.py` | 変更なし | GUI preview / runtime builder の再生成キー追加は `local_018` で扱う |
| `tests/unit/framework/hardware/test_ponkan_capture.py` | 新規 | fake reader による adapter 単体テスト |
| `tests/unit/framework/hardware/test_capture_source.py` | 変更 | `capture` settings parsing と `n3dsxl` profile の既定 aspect box を検証する |
| `tests/unit/framework/io/test_device_factories.py` | 変更 | capture source で factory が adapter を生成・cache・close することを検証する |
| `tests/integration/test_capture_source_runtime.py` | 変更 | fake capture source が Runtime / `Command.capture()` へ接続されることを検証する |
| `tests/hardware/test_ponkan_n3dsxl_capture_device.py` | 新規 | `@pytest.mark.realdevice`。実機で `open_capture(backend="auto")` 経由の ready / capture / close を確認する |
| `tests/perf/test_ponkan_frame_source_contention.py` | 新規 | preview と Runtime capture の同時取得時に lock 待ちが増えないことを確認する |

## 3. 設計方針

### 3.1 調査結果

| 項目 | 確認結果 |
|------|----------|
| PyPI version | `ponkan-python 0.1.2` |
| upload time | wheel `2026-06-12T18:02:26Z`、sdist `2026-06-12T18:02:27Z` |
| Python | `>=3.12`。NyX 側は当面 `>=3.12,<3.14` を維持する |
| license | GitHub `pyproject.toml` 上は MIT |
| development status | `Development Status :: 2 - Pre-Alpha` |
| import package | `ponkan` |
| wheel root | `ponkan/` と `ponkan_python-0.1.2.dist-info/` |
| high-level entry | `open_capture(...) -> CaptureReader` |
| read API | `CaptureReader.read()` は `numpy.ndarray` または timeout 時 `None` を返す |
| frame API | `CaptureReader.read_frame()` は top `(240, 400, 3)`、bottom `(240, 320, 3)` の `CaptureFrame` を返す |
| layout | `CaptureOutput.BOTH_VERTICAL` は `400x480` RGB/BGR mosaic を返す |
| backend | API 上は `auto` / `libusb` / `d3xx` / `d3xx-native`。0.1.2 の hardware opener は `libusb` を `UnsupportedOperation` とし、`auto` は D3XX 経路で開く |
| dependencies | `libusb1>=3.3.1`、`numpy>=2.0`、Windows のみ `pyd3xx>=1.1.4` |
| optional extras | `image` は Pillow、`opencv` は `opencv-python`。`d3xx` extra は存在しない |
| console scripts | `ponkan-list-devices`、`ponkan-capture-raw`、`ponkan-raw-to-png`、`ponkan-stream-n3dsxl` |
| error base | package-level failure は `CaptureError` 継承。runtime dependency 不足は `DependencyUnavailableError` |

依存関係の正本は PyPI metadata と GitHub `pyproject.toml` とする。2026-06-13 時点の API docs は installation 節で D3XX backend が Windows platform-gated 通常依存であることを示している一方、`CaptureConfig` 表には `d3xx` extra への旧注記が残っている。NyX 仕様では metadata / `pyproject.toml` に従い、`ponkan-python[d3xx]` は使わない。

外部参照:

| 種別 | URL |
|------|-----|
| PyPI | <https://pypi.org/project/ponkan-python/> |
| API docs | <https://github.com/niart120/ponkan-python/blob/master/docs/api.md> |
| high-level facade | <https://github.com/niart120/ponkan-python/blob/master/src/ponkan/capture.py> |
| frame model | <https://github.com/niart120/ponkan-python/blob/master/src/ponkan/image/frame.py> |
| package metadata | <https://github.com/niart120/ponkan-python/blob/master/pyproject.toml> |

### 3.2 アーキテクチャ上の位置づけ

`ponkan-python` は `core/hardware` の具象 capture device 実装として扱う。`core/io` は既存どおり `CaptureFrameSourcePort` でラップし、Runtime / GUI preview へは `FrameSourcePort` だけを公開する。

`nyxpy.framework.core.hardware.ponkan_capture` だけが `ponkan` を import する。import は `initialize()` または opener factory 内で遅延実行し、`ponkan-python` 未導入環境でも `nyxpy` の通常 import、camera/window source、CLI help、GUI 起動が壊れないようにする。

### 3.3 公開 API 方針

マクロ向け公開 API は変更しない。`Command.capture()` は引き続き `FrameSourcePort.latest_frame()` を `1280x720` へ resize し、crop / grayscale を適用する。

設定上の source type と framework 内部 dataclass は追加する。ライブラリ名や device model 名を直接 source type にしない。ユーザーが選ぶ大分類は入力方式であるため、source type は `capture` とする。provider は `capture_provider`、device model / layout は `capture_device_profile` で分離する。

```python
CaptureSourceType = Literal["camera", "window", "capture"]

@dataclass(frozen=True)
class PonkanCaptureSourceConfig:
    source_type: Literal["capture"] = "capture"
    provider: Literal["ponkan"] = "ponkan"
    device_profile: Literal["n3dsxl"] = "n3dsxl"
    ponkan_backend: Literal["auto", "d3xx", "d3xx-native"] = "auto"
    raw_slots: int = 2
    output_queue_size: int = 2
    drop_policy: Literal["drop_oldest", "drop_newest", "block"] = "drop_oldest"
    poll_interval: float = 0.004
    read_timeout: float | None = 1.0
    collect_timing: bool = False
    transform: FrameTransformConfig = field(
        default_factory=lambda: FrameTransformConfig(aspect_box_enabled=True)
    )
```

`libusb` は `ponkan-python` API 上の値として存在するが、0.1.2 の high-level opener では `UnsupportedOperation` である。NyX の initial settings では `libusb` を choices に含めず、libusb support が high-level API で検証できた時点で別仕様として追加する。

初期実装では physical capture device の個体選択を追加しない。`PonkanCaptureSourceConfig` は `capture_device_identifier` 相当の field を持たず、production opener は device selector を指定しないまま `ponkan.open_capture()` を呼ぶ。サポート対象は一致する `ponkan` / `n3dsxl` device が 1 台だけ接続されている状態である。複数台接続時は upstream の既定選択に委譲し、NyX はどの個体へ接続するかを保証しない。

将来 `ponkan-python` が安定した device identifier と high-level opener の選択 API を提供した場合は、別仕様で `capture_device_identifier` を追加する。その場合も provider / profile と物理個体は分離し、`capture_device_profile` を個体識別に流用しない。

### 3.4 後方互換性

既存 `camera` / `window` source の設定値と動作は維持する。`capture_source_type` に `capture` を追加するだけで、既定値は `camera` のままである。

`CaptureDeviceInterface` の例外 contract を明確化する変更は破壊的変更として扱うが、Project NyX はアルファ版であり互換 shim は追加しない。既存 `CameraCaptureDevice`、`DummyCaptureDevice`、`WindowCaptureDevice`、テストを同じ変更内で正 API へ更新する。

`capture_device_profile = "n3dsxl"` では `n3dsxl_hd_aspect_box_enabled = true` を既定にする。これは 3DS touch / HD 座標の既存仕様に合わせるためであり、camera/window の `capture_aspect_box_enabled = false` 既定は変更しない。

### 3.5 レイヤー構成

| レイヤー | 責務 | 依存先 |
|----------|------|--------|
| `core/hardware/ponkan_capture.py` | `ponkan` reader の生成、reader thread、BGR frame cache、close | `ponkan` optional import、`LoggerPort` |
| `core/hardware/capture_source.py` | settings から source config を構築 | `FrameTransformConfig` |
| `core/io/device_factories.py` | source config から `FrameSourcePort` を生成し lifetime を所有 | `core/hardware` |
| `core/io/adapters.py` | capture device 例外を `FrameSourcePort` 例外へ変換 | `FrameSourcePort` |
| `gui` | source selection と settings 保存 | `nyxpy.framework.*` |

フレームワーク層から GUI へは依存しない。`macros/` は `nyxpy.framework.*` だけを使い、`ponkan` へ直接依存しない。

### 3.6 依存追加方針

`ponkan-python` は NyX の必須依存にしない。`ponkan-python 0.1.2` では PyD3XX が Windows 向け通常依存になったため、NyX 側では `ponkan-python[d3xx]` を指定しない。NyX の `ponkan` extra は、ponkan provider を使う直接接続型キャプチャ経路を通常導入から隔離するために追加する。

```toml
[project.optional-dependencies]
ponkan = [
    "ponkan-python>=0.1.2,<0.2.0 ; sys_platform == 'win32'",
]
```

通常の `uv sync` では `ponkan-python` を解決しない。実機開発者は `uv sync --extra ponkan` または package install 時の `nyxpy-fw[ponkan]` を使う。Windows ではこの extra により `ponkan-python` 経由で PyD3XX も解決される。実装側は `ponkan` package 未導入と、上流が `DependencyUnavailableError` で示す runtime dependency 不足を分けて扱う。

### 3.7 性能要件

| 指標 | 目標値 |
|------|--------|
| `FrameSourcePort.latest_frame()` lock 取得 timeout | 100 ms 以内。既存 `CaptureFrameSourcePort` と同じ |
| `PonkanCaptureDevice.get_frame()` | reader API を呼ばず、cache copy のみを行う |
| frame cache copy | `400x480x3` または aspect box 後 frame で 10 ms 未満 |
| GUI preview | `try_latest_frame()` が reader timeout に巻き込まれない |
| reader thread shutdown | `release()` から 2 秒以内 |
| hardware smoke | 5 秒以上の連続取得で decoded / delivered counter が増える |
| timing report | `collect_timing=true` 時は `CaptureReader.stats()` の snapshot を technical log または artifact に出せる |

fps は primary 指標にしない。3DS 側の表示更新に依存するため、実機性能は read latency、jitter、post-read cache 更新時間、shutdown quality を併記して判断する。

### 3.8 並行性・スレッド安全性

`PonkanCaptureDevice.initialize()` は `open_capture()` で reader を開き、専用 daemon thread を開始する。reader thread は `CaptureReader.read(output=BOTH_VERTICAL, colorspace="BGR", timeout=read_timeout)` を繰り返し、返却 frame が `None` でなければ `_latest_frame` を lock 下で差し替える。

`get_frame()` は `_latest_frame` を copy して返すだけであり、USB read、decode、`CaptureReader.read()`、sleep を実行しない。初回 frame 前は `CaptureDeviceNotReady`、reader thread が fatal error で停止した場合は `CaptureDeviceReadFailed` を送出する。

`release()` は idempotent とし、reader thread 停止要求、join、`CaptureReader.close()` を必ず行う。`close()` が失敗した場合は technical log に出し、factory close 時は既存方針に従って `ExceptionGroup` に集約する。

## 4. 実装仕様

### 4.1 公開インターフェース

```python
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

import cv2

from nyxpy.framework.core.hardware.frame_transform import FrameTransformConfig


class CaptureDeviceNotReady(RuntimeError):
    """Capture device がまだ frame を返せない状態。"""


class CaptureDeviceReadFailed(RuntimeError):
    """Capture device の取得 thread が復旧不能な失敗で停止した状態。"""


class PonkanReader(Protocol):
    def read(
        self,
        *,
        output: object | str | None = None,
        colorspace: str | None = None,
        timeout: float | None = None,
    ) -> cv2.typing.MatLike | None: ...

    def stats(self) -> object: ...

    def close(self) -> None: ...


type PonkanOpenCapture = Callable[["PonkanCaptureSourceConfig"], PonkanReader]


@dataclass(frozen=True)
class PonkanCaptureSourceConfig:
    source_type: Literal["capture"] = "capture"
    provider: Literal["ponkan"] = "ponkan"
    device_profile: Literal["n3dsxl"] = "n3dsxl"
    ponkan_backend: Literal["auto", "d3xx", "d3xx-native"] = "auto"
    raw_slots: int = 2
    output_queue_size: int = 2
    drop_policy: Literal["drop_oldest", "drop_newest", "block"] = "drop_oldest"
    poll_interval: float = 0.004
    read_timeout: float | None = 1.0
    collect_timing: bool = False
    transform: FrameTransformConfig = field(
        default_factory=lambda: FrameTransformConfig(aspect_box_enabled=True)
    )


class PonkanCaptureDevice(CaptureDeviceInterface):
    def __init__(
        self,
        config: PonkanCaptureSourceConfig,
        *,
        opener: PonkanOpenCapture | None = None,
        logger: LoggerPort | None = None,
    ) -> None: ...

    def initialize(self) -> None: ...

    def get_frame(self) -> cv2.typing.MatLike: ...

    def release(self) -> None: ...
```

`PonkanCaptureSourceConfig` は既存 source config と同じ `capture_source.py` に置く。`ponkan_capture.py` は `PonkanCaptureDevice` と external adapter に集中し、source config parsing と optional dependency import を混在させない。

production opener は次の形で `ponkan` を遅延 import する。

```python
def _open_ponkan_capture(config: PonkanCaptureSourceConfig) -> PonkanReader:
    try:
        from ponkan import CaptureConfig, CaptureOutput, open_capture
        from ponkan.errors import CaptureError, DependencyUnavailableError
    except ImportError as exc:
        raise ConfigurationError(
            "ponkan-python is required for capture source",
            code="NYX_PONKAN_CAPTURE_DEPENDENCY_MISSING",
            component="PonkanCaptureDevice",
            details={"extra": "ponkan", "provider": config.provider},
        ) from exc

    ponkan_config = CaptureConfig(
        backend=config.ponkan_backend,
        output=CaptureOutput.BOTH_VERTICAL,
        colorspace="BGR",
        raw_slots=config.raw_slots,
        output_queue_size=config.output_queue_size,
        drop_policy=config.drop_policy,
        poll_interval=config.poll_interval,
        read_timeout=config.read_timeout,
        collect_timing=config.collect_timing,
    )
    try:
        # device selector は指定しない。複数台接続時の個体選択は upstream default に委譲する。
        return open_capture(config=ponkan_config)
    except DependencyUnavailableError as exc:
        raise ConfigurationError(
            "ponkan capture dependency is unavailable",
            code="NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE",
            component="PonkanCaptureDevice",
            details={"backend": config.ponkan_backend, "cause": type(exc).__name__},
            cause=exc,
        ) from exc
    except CaptureError as exc:
        raise ConfigurationError(
            "failed to open ponkan capture source",
            code="NYX_PONKAN_CAPTURE_OPEN_FAILED",
            component="PonkanCaptureDevice",
            details={"backend": config.ponkan_backend, "cause": type(exc).__name__},
            cause=exc,
        ) from exc
```

実装では `CaptureError` 型 import を function 内に閉じ込める。test では `opener` injection で `ponkan` を import せずに検証する。

### 4.2 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | `camera` / `window` / `capture` |
| `capture_provider` | `str` | `"ponkan"` | capture source の provider。初期実装では `ponkan` のみ |
| `capture_device_profile` | `str` | `"n3dsxl"` | provider 内の device profile。初期実装では `n3dsxl` のみ |
| `ponkan_backend` | `str` | `"auto"` | `auto` / `d3xx` / `d3xx-native`。0.1.2 では `auto` は D3XX 経路 |
| `ponkan_raw_slots` | `int` | `2` | backend raw read slot 数 |
| `ponkan_output_queue_size` | `int` | `2` | decoded frame queue capacity |
| `ponkan_drop_policy` | `str` | `"drop_oldest"` | `drop_oldest` / `drop_newest` / `block` |
| `ponkan_poll_interval` | `float` | `0.004` | reader が frame 待ちで sleep する秒数 |
| `ponkan_read_timeout` | `float | None` | `1.0` | `CaptureReader.read()` の timeout。`None` は無期限待ちだが reader thread 内に限定する |
| `ponkan_collect_timing` | `bool` | `false` | `ponkan-python` の timing samples を有効化する |
| `n3dsxl_hd_aspect_box_enabled` | `bool` | `true` | `400x480` 画面を NyX 既存の 3DS HD 座標へ合わせるため 16:9 黒帯を付ける |

`capture_backend` は window capture backend の設定として維持する。ponkan provider では `ponkan_backend` を使い、`mss` / `windows_graphics_capture` と `d3xx` を同じ key に混在させない。

初期実装では `capture_device_identifier` を設定 schema に追加しない。物理個体選択が必要になった場合は、ponkan provider 専用 setting として追加し、`capture_device` には混在させない。

### 4.3 設定 parsing

`capture_source_from_settings()` は `capture_source_type == "capture"` かつ `capture_provider == "ponkan"` の場合に `PonkanCaptureSourceConfig` を返す。数値項目は正値を要求し、`read_timeout` は `None` または `>= 0` とする。

`n3dsxl_hd_aspect_box_enabled` は device profile 固有の既定値を持つ。既存 `capture_aspect_box_enabled` は camera/window 用のまま維持し、capture source の既定値を巻き込まない。

### 4.4 FrameSourcePortFactory

`FrameSourcePortFactory.__init__()` に `ponkan_capture_factory` を追加する。

```python
class FrameSourcePortFactory:
    def __init__(
        self,
        *,
        discovery: DeviceDiscoveryService,
        logger: LoggerPort | None = None,
        capture_factory: Callable[..., object] = CameraCaptureDevice,
        ponkan_capture_factory: Callable[..., object] = PonkanCaptureDevice,
        window_locator_factory: Callable[[], WindowLocatorBackend] | None = None,
        window_backend_factory: Callable[[str], WindowCaptureBackend] | None = None,
    ) -> None: ...
```

`create()` は `PonkanCaptureSourceConfig` を match し、`_create_ponkan_capture_source()` を呼ぶ。capture source は camera discovery を必要としないため、`select_capture_target()` を通らない。

`capture_provider == "ponkan"` では、`ponkan-python` 未導入、runtime dependency 不足、device open 失敗を `DummyCaptureDevice` へ fallback してはならない。これらは利用者が導入状態または接続状態を修正すべき設定・環境エラーであり、dummy frame を表示すると capture source が有効になったように誤認させるためである。`allow_dummy=True` は既存 camera/window source の fallback 方針として維持し、ponkan capture source では `ConfigurationError` を呼び出し元へ返す。

cache key は source type、backend、queue 設定、timing 設定、transform を含める。`read_timeout` や `poll_interval` が変わった場合、古い reader を再利用しない。

### 4.5 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError(code="NYX_PONKAN_CAPTURE_DEPENDENCY_MISSING")` | `ponkan` package が import できない |
| `ConfigurationError(code="NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE")` | `ponkan` は import できるが、選択 backend の runtime dependency が利用できない |
| `ConfigurationError(code="NYX_PONKAN_CAPTURE_OPEN_FAILED")` | `open_capture()` が `DeviceNotFound`、`UnsupportedOperation`、`Ftd3CommandError` などの `CaptureError` を送出した |
| `ConfigurationError(code="NYX_CAPTURE_SOURCE_INVALID")` | `capture_source_type` が `camera` / `window` / `capture` 以外 |
| `ConfigurationError(code="NYX_CAPTURE_PROVIDER_INVALID")` | `capture_provider` が `ponkan` 以外 |
| `ConfigurationError(code="NYX_CAPTURE_DEVICE_PROFILE_INVALID")` | `capture_device_profile` が choices 外 |
| `ConfigurationError(code="NYX_PONKAN_CAPTURE_BACKEND_INVALID")` | `ponkan_backend` が choices 外 |
| `CaptureDeviceNotReady` | reader thread がまだ最初の frame を cache していない |
| `CaptureDeviceReadFailed` | reader thread が `CaptureError` または想定外例外で停止した |
| `FrameNotReadyError` | `CaptureFrameSourcePort` が `CaptureDeviceNotReady` を受け取った |
| `FrameReadError` | `CaptureFrameSourcePort` が `CaptureDeviceReadFailed` を受け取った |

`CaptureReader.read()` が `None` を返す timeout は fatal error ではない。reader thread は継続し、rate limit した technical log だけを出す。連続 timeout を fatal とするかは initial implementation では扱わない。

### 4.6 シングルトン管理

新規グローバル singleton は追加しない。`FrameSourcePortFactory` が `PonkanCaptureDevice` の lifetime を所有し、`close()` で `release()` を呼ぶ。GUI preview と Runtime が同じ source key を使う場合は既存 `_SharedCaptureDevice` により reader を共有する。

### 4.7 実装手順

| Step | 内容 | 完了条件 |
|------|------|----------|
| 1 | optional dependency と settings schema を追加 | `capture_source_type="capture"`、`capture_provider="ponkan"`、`capture_device_profile="n3dsxl"` が schema validation を通る |
| 2 | `PonkanCaptureSourceConfig` と parsing を追加 | unit test で default aspect box と validation を確認 |
| 3 | `PonkanCaptureDevice` を fake opener で実装 | 実機なしで start / cache / close / fatal error を検証 |
| 4 | `FrameSourcePortFactory` に capture / ponkan 分岐を追加 | fake factory で reuse / error propagation / close を検証 |
| 5 | GUI settings の詳細を local_018 に分離 | framework settings schema の追加までを local_017 で完了し、GUI 操作導線は `local_018` で実装する |
| 6 | 実機 gate を追加 | `--realdevice`、`NYX_REALDEVICE=1`、`NYX_N3DSXL_CAPTURE=1` のときだけ実行 |
| 7 | perf smoke を追加 | reader timeout が `try_latest_frame()` を block しないことを確認 |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_capture_source_from_settings_creates_ponkan_capture_source` | settings から `PonkanCaptureSourceConfig` を構築し、`n3dsxl` profile の aspect box 既定が true である |
| ユニット | `test_capture_source_rejects_invalid_ponkan_backend` | `ponkan_backend` の choices 外を `ConfigurationError` にする |
| ユニット | `test_ponkan_capture_device_caches_bgr_frame_copy` | fake reader の BGR frame が copy として返る |
| ユニット | `test_ponkan_capture_device_raises_not_ready_before_first_frame` | 初回 frame 前の `get_frame()` が `CaptureDeviceNotReady` を送出する |
| ユニット | `test_ponkan_capture_device_close_is_idempotent` | `release()` 複数回で reader close が一度だけ行われる |
| ユニット | `test_ponkan_capture_device_reports_reader_failure` | fake reader の fatal error を `CaptureDeviceReadFailed` として保持する |
| ユニット | `test_ponkan_capture_missing_dependency_is_configuration_error` | `ponkan` import 失敗時に install extra を含む `ConfigurationError` を出す |
| ユニット | `test_ponkan_capture_dependency_unavailable_is_configuration_error` | 上流 `DependencyUnavailableError` を `NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE` に変換する |
| ユニット | `test_capture_frame_source_maps_capture_device_read_failed` | fatal read error を `FrameReadError` に変換する |
| ユニット | `test_frame_source_factory_creates_ponkan_capture_source` | capture source で `PonkanCaptureDevice` を生成する |
| ユニット | `test_frame_source_factory_recreates_capture_source_when_backend_changes` | backend / queue 設定変更で cache key が変わる |
| ユニット | `test_frame_source_factory_does_not_dummy_fallback_for_ponkan_configuration_error` | `allow_dummy=True` でも ponkan dependency / open error は `ConfigurationError` として返る |
| ユニット | `test_ponkan_open_capture_uses_upstream_default_device_selection` | physical device selector を指定せずに `open_capture()` を呼ぶ |
| 結合 | `test_runtime_uses_ponkan_capture_frame_source` | fake capture source から `Command.capture()` が `1280x720` BGR frame を返す |
| GUI | `local_018` で追加 | GUI settings で source / provider / profile / backend / timing を保存する |
| ハードウェア | `test_ponkan_n3dsxl_capture_device_realdevice` | `@pytest.mark.realdevice`。D3XX 接続、ready、capture shape、close を確認する |
| パフォーマンス | `test_ponkan_capture_frame_source_try_latest_frame_is_nonblocking` | reader timeout 中でも `try_latest_frame()` が即時 `None` または copy を返す |

実機テストの gate:

```python
pytestmark = [
    pytest.mark.realdevice,
    pytest.mark.skipif(
        os.environ.get("NYX_N3DSXL_CAPTURE") != "1",
        reason="set NYX_N3DSXL_CAPTURE=1 to run n3dsxl capture tests",
    ),
]
```

実機テストでは `CaptureReader.stats().snapshot()` または `to_dict()` 相当の counter を artifact に保存し、少なくとも submitted / completed / decoded / delivered が増えていることを確認する。fps 単体では pass/fail を決めず、read latency、jitter、post-read cache 更新時間、shutdown 時間を記録する。

## 6. 実装チェックリスト

- [x] PyPI metadata と GitHub API docs の調査
- [x] NyX 既存 `FrameSourcePort` / `CaptureDeviceInterface` / settings 経路の調査
- [x] source type 名を `capture` に確定し、provider / device profile を分離
- [x] `ponkan-python` 本体を NyX の `ponkan` optional extra に隔離する方針を確定
- [x] `pyproject.toml` に optional extra `ponkan` を追加
- [x] capture device 例外 contract を実装
- [x] `PonkanCaptureSourceConfig` と settings parsing を実装
- [x] `PonkanCaptureDevice` を fake opener で単体テスト可能に実装
- [x] `FrameSourcePortFactory` に capture / ponkan source 分岐を追加
- [x] ponkan dependency / open error を `DummyCaptureDevice` へ fallback しないことを実装
- [x] physical capture device の個体選択を scope 外とし、`open_capture()` の既定選択へ委譲する
- [x] GUI settings の詳細実装を `local_018` に分離
- [x] unit / integration test を追加
- [x] `@pytest.mark.realdevice` の実機 gate を追加
- [x] performance smoke test を追加
- [x] `uv lock --check`
- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run ty check src/nyxpy --output-format concise --no-progress`
- [x] 変更範囲の `uv run pytest ...`
- [x] `uv run pytest`

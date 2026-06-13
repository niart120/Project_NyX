# ponkan-python N3DSXL キャプチャ入力ソース 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`, `src/nyxpy/framework/core/io/`
> **目的**: `ponkan-python` を利用し、new 3DS XL キャプチャボードから取得した画面を NyX の `FrameSourcePort` へ供給する。
> **関連ドキュメント**: `spec/framework/rearchitecture/RUNTIME_AND_IO_PORTS.md`, `spec/agent/complete/local_007/NINTENDO_3DS_SCREEN_COORDINATES_AND_TOUCH.md`, `spec/agent/complete/local_008/SETTINGS_PREVIEW_CAPTURE_REFRESH.md`
> **外部調査日**: 2026-06-12

## 1. 概要

### 1.1 目的

`ponkan-python` の high-level capture API を NyX の画面取得経路へ組み込み、new 3DS XL キャプチャボードを `camera` / `window` と同じ `FrameSourcePort` として扱えるようにする。マクロ・画像処理・通知は従来どおり OpenCV 互換の BGR frame を受け取り、USB backend や D3XX 依存は framework の hardware adapter に閉じ込める。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| ponkan-python | PyPI 配布名 `ponkan-python`。import package は `ponkan` |
| ponkan | new 3DS XL キャプチャボードから frame を取得する外部ライブラリの package root |
| open_capture | `ponkan` の high-level reader 生成関数 |
| CaptureReader | `read()` / `read_frame()` / `stats()` / `close()` を持つ `ponkan` の reader |
| CaptureOutput.BOTH_VERTICAL | top 画面と bottom 画面を縦結合し、bottom を中央寄せした `400x480` 相当の出力 |
| N3DSXLCaptureDevice | NyX 側で追加する `CaptureDeviceInterface` 互換 adapter |
| FrameSourcePort | Runtime が最新 frame を取得するための入力 port |
| D3XX backend | FTDI D3XX driver / PyD3XX を使う `ponkan-python` の USB backend |
| aspect box | `400x480` の 3DS 画面を 16:9 canvas に黒帯付きで配置し、`Command.capture()` 後に `1280x720` の既存 3DS HD 座標へ合わせる変換 |

### 1.3 背景・問題

現行 NyX の画面取得は `camera` と `window` を入力ソースとして扱う。new 3DS XL の USB キャプチャボードを直接読む経路はなく、3DS 用の座標定数や touch 変換は存在しても、画面入力は外部 viewer やカメラデバイス化に依存する。

`ponkan-python 0.1.1` は new 3DS XL キャプチャボード向けの pre-alpha ライブラリで、`open_capture()` / `CaptureReader.read()` による薄い high-level API を提供する。0.1.1 では package root が旧 `py3dscapture` から `ponkan` に変更されている。PyPI metadata と GitHub `pyproject.toml` は Python `>=3.12,<3.14`、MIT license classifier / project license、Windows classifier、必須依存 `libusb1>=3.3.1` / `numpy>=2.0`、D3XX extra `pyd3xx>=1.1.4` を示している。NyX と Python version 範囲は一致するが、D3XX は Windows / driver / optional dependency を伴うため、必須依存へ直置きしない。

`CaptureReader.read()` は timeout まで待つ API である。これを `FrameSourcePort.latest_frame()` の lock 内で直接呼ぶと GUI preview と Runtime capture が詰まるため、NyX adapter は独自の reader thread で最新 frame を cache し、`get_frame()` は copy を返すだけにする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 3DS USB 直接入力 | 未対応 | `capture_source_type = "n3dsxl"` で `FrameSourcePort` に接続できる |
| マクロ API 変更 | なし | `Command.capture()` の呼び出しは変更しない |
| frame 形式 | camera/window ごとに BGR ndarray | n3dsxl も BGR `uint8` ndarray copy |
| 3DS HD 座標 | 定数のみ存在 | n3dsxl source 既定で aspect box を有効化し、`THREEDS_HD_*` と一致させる |
| dependency blast radius | 依存なし | `ponkan-python[d3xx]` は optional extra `n3dsxl` に隔離する |
| GUI preview 競合 | `FrameSourcePort.try_latest_frame()` は非 blocking | n3dsxl source でも非 blocking を維持する |
| 実機なしテスト | Dummy capture 中心 | fake `CaptureReader` / fake opener で adapter と factory を単体テスト可能にする |

### 1.5 着手条件

- `ponkan-python` の PyPI metadata と GitHub API docs を実装直前に再確認すること。
- `ponkan-python 0.1.1` の `auto` backend は D3XX へ解決される前提で設計するが、backend 仕様が変わった場合は本仕様を更新すること。
- Windows の D3XX driver / PyD3XX 導入は実機テスト環境だけの前提にし、通常開発環境の必須条件にしないこと。
- `uv lock --check`、`uv run ruff check .`、`uv run ty check src/nyxpy --output-format concise --no-progress`、変更範囲の pytest が通ること。
- 実機確認は `@pytest.mark.realdevice` と明示的な環境変数で gate し、通常 CI では skip すること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | optional extra `n3dsxl` として `ponkan-python[d3xx]>=0.1.1,<0.2.0 ; sys_platform == "win32"` を追加する |
| `src/nyxpy/framework/core/hardware/camera_capture.py` | 変更 | capture device の not-ready / fatal-read 例外を分離し、`CaptureFrameSourcePort` が `FrameNotReadyError` と `FrameReadError` を区別できるようにする |
| `src/nyxpy/framework/core/hardware/ponkan_capture.py` | 新規 | `N3DSXLCaptureDevice` と `ponkan` adapter 実装を追加する |
| `src/nyxpy/framework/core/hardware/capture_source.py` | 変更 | `CaptureSourceType` と `CaptureSourceConfig` に `n3dsxl` / `N3DSXLCaptureSourceConfig` を追加し、settings から構築する |
| `src/nyxpy/framework/core/hardware/__init__.py` | 変更 | 必要な公開型を export する。optional dependency import はここで発生させない |
| `src/nyxpy/framework/core/io/adapters.py` | 変更 | capture device not-ready / read-failed 例外を `FrameNotReadyError` / `FrameReadError` に変換する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | `FrameSourcePortFactory` に n3dsxl source 分岐と injectable `n3dsxl_capture_factory` を追加する |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `capture_source_type` choices と n3dsxl 専用 settings を追加する |
| `src/nyxpy/framework/core/runtime/device_selection.py` | 変更なし | n3dsxl MVP では既存 camera discovery に混ぜず、source type 選択で open する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | Source 選択に `N3DSXL` を追加し、n3dsxl 専用 backend / timing 設定を表示する |
| `src/nyxpy/gui/app_services.py` | 変更 | n3dsxl source 設定変更時に preview / runtime builder を再生成する |
| `tests/unit/framework/hardware/test_ponkan_capture.py` | 新規 | fake reader による adapter 単体テスト |
| `tests/unit/framework/hardware/test_capture_source.py` | 変更 | `n3dsxl` settings parsing と既定 aspect box を検証する |
| `tests/unit/framework/io/test_device_factories.py` | 変更 | n3dsxl source で factory が adapter を生成・cache・close することを検証する |
| `tests/integration/test_capture_source_runtime.py` | 変更 | fake n3dsxl source が Runtime / `Command.capture()` へ接続されることを検証する |
| `tests/hardware/test_ponkan_n3dsxl_capture_device.py` | 新規 | `@pytest.mark.realdevice`。実機で `open_capture(backend="auto")` 経由の ready / capture / close を確認する |
| `tests/perf/test_ponkan_frame_source_contention.py` | 新規 | preview と Runtime capture の同時取得時に lock 待ちが増えないことを確認する |

## 3. 設計方針

### 3.1 調査結果

| 項目 | 確認結果 |
|------|----------|
| PyPI version | `ponkan-python 0.1.1` |
| upload time | wheel `2026-06-11T15:40:57Z`、sdist `2026-06-11T15:40:59Z` |
| Python | `>=3.12,<3.14` |
| license | GitHub `pyproject.toml` 上は MIT |
| development status | `Development Status :: 2 - Pre-Alpha` |
| import package | `ponkan` |
| wheel root | `ponkan/` と `ponkan_python-0.1.1.dist-info/` |
| high-level entry | `open_capture(...) -> CaptureReader` |
| read API | `CaptureReader.read()` は `numpy.ndarray` または timeout 時 `None` を返す |
| frame API | `CaptureReader.read_frame()` は top `(240, 400, 3)`、bottom `(240, 320, 3)` の `CaptureFrame` を返す |
| layout | `CaptureOutput.BOTH_VERTICAL` は `400x480` RGB/BGR mosaic を返す |
| backend | API 上は `auto` / `libusb` / `d3xx` / `d3xx-native`。0.1.1 の hardware opener は `libusb` を `UnsupportedOperation` とし、`auto` は D3XX 経路で開く |
| optional extras | `d3xx` は `pyd3xx>=1.1.4`、`image` は Pillow、`opencv` は `opencv-python` |
| console scripts | `ponkan-list-devices`、`ponkan-capture-raw`、`ponkan-raw-to-png`、`ponkan-stream-n3dsxl` |
| error base | package-level failure は `CaptureError` 継承 |

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

設定上の source type と framework 内部 dataclass は追加する。ライブラリ名を直接 source type にしない。ユーザーが選ぶ対象は library ではなく hardware source であるため、設定名は `n3dsxl` とする。

```python
CaptureSourceType = Literal["camera", "window", "n3dsxl"]

@dataclass(frozen=True)
class N3DSXLCaptureSourceConfig:
    source_type: Literal["n3dsxl"] = "n3dsxl"
    backend: Literal["auto", "d3xx", "d3xx-native"] = "auto"
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

`libusb` は `ponkan-python` API 上の値として存在するが、0.1.1 の high-level opener では `UnsupportedOperation` である。NyX の initial settings では `libusb` を choices に含めず、libusb support が high-level API で検証できた時点で別仕様として追加する。

### 3.4 後方互換性

既存 `camera` / `window` source の設定値と動作は維持する。`capture_source_type` に `n3dsxl` を追加するだけで、既定値は `camera` のままである。

`CaptureDeviceInterface` の例外 contract を明確化する変更は破壊的変更として扱うが、Project NyX はアルファ版であり互換 shim は追加しない。既存 `CameraCaptureDevice`、`DummyCaptureDevice`、`WindowCaptureDevice`、テストを同じ変更内で正 API へ更新する。

`n3dsxl` source では `n3dsxl_hd_aspect_box_enabled = true` を既定にする。これは 3DS touch / HD 座標の既存仕様に合わせるためであり、camera/window の `capture_aspect_box_enabled = false` 既定は変更しない。

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

`ponkan-python` は必須依存にしない。D3XX driver / PyD3XX は特定 hardware 環境のため、optional extra として追加する。

```toml
[project.optional-dependencies]
n3dsxl = [
    "ponkan-python[d3xx]>=0.1.1,<0.2.0 ; sys_platform == 'win32'",
]
```

通常の `uv sync` では `ponkan-python` を解決しない。実機開発者は `uv sync --extra n3dsxl` または package install 時の `nyxpy-fw[n3dsxl]` を使う。実装側は missing dependency を `ConfigurationError` として扱い、解決策に `uv sync --extra n3dsxl` を含める。

### 3.7 性能要件

| 指標 | 目標値 |
|------|--------|
| `FrameSourcePort.latest_frame()` lock 取得 timeout | 100 ms 以内。既存 `CaptureFrameSourcePort` と同じ |
| `N3DSXLCaptureDevice.get_frame()` | reader API を呼ばず、cache copy のみを行う |
| frame cache copy | `400x480x3` または aspect box 後 frame で 10 ms 未満 |
| GUI preview | `try_latest_frame()` が reader timeout に巻き込まれない |
| reader thread shutdown | `release()` から 2 秒以内 |
| hardware smoke | 5 秒以上の連続取得で decoded / delivered counter が増える |
| timing report | `collect_timing=true` 時は `CaptureReader.stats()` の snapshot を technical log または artifact に出せる |

fps は primary 指標にしない。3DS 側の表示更新に依存するため、実機性能は read latency、jitter、post-read cache 更新時間、shutdown quality を併記して判断する。

### 3.8 並行性・スレッド安全性

`N3DSXLCaptureDevice.initialize()` は `open_capture()` で reader を開き、専用 daemon thread を開始する。reader thread は `CaptureReader.read(output=BOTH_VERTICAL, colorspace="BGR", timeout=read_timeout)` を繰り返し、返却 frame が `None` でなければ `_latest_frame` を lock 下で差し替える。

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


type PonkanOpenCapture = Callable[["N3DSXLCaptureSourceConfig"], PonkanReader]


@dataclass(frozen=True)
class N3DSXLCaptureSourceConfig:
    source_type: Literal["n3dsxl"] = "n3dsxl"
    backend: Literal["auto", "d3xx", "d3xx-native"] = "auto"
    raw_slots: int = 2
    output_queue_size: int = 2
    drop_policy: Literal["drop_oldest", "drop_newest", "block"] = "drop_oldest"
    poll_interval: float = 0.004
    read_timeout: float | None = 1.0
    collect_timing: bool = False
    transform: FrameTransformConfig = field(
        default_factory=lambda: FrameTransformConfig(aspect_box_enabled=True)
    )


class N3DSXLCaptureDevice(CaptureDeviceInterface):
    def __init__(
        self,
        config: N3DSXLCaptureSourceConfig,
        *,
        opener: PonkanOpenCapture | None = None,
        logger: LoggerPort | None = None,
    ) -> None: ...

    def initialize(self) -> None: ...

    def get_frame(self) -> cv2.typing.MatLike: ...

    def release(self) -> None: ...
```

`N3DSXLCaptureSourceConfig` は既存 source config と同じ `capture_source.py` に置く。`ponkan_capture.py` は `N3DSXLCaptureDevice` と external adapter に集中し、source config parsing と optional dependency import を混在させない。

production opener は次の形で `ponkan` を遅延 import する。

```python
def _open_ponkan_capture(config: N3DSXLCaptureSourceConfig) -> PonkanReader:
    try:
        from ponkan import CaptureConfig, CaptureOutput, open_capture
        from ponkan.errors import CaptureError
    except ImportError as exc:
        raise ConfigurationError(
            "ponkan-python is required for n3dsxl capture source",
            code="NYX_N3DSXL_CAPTURE_DEPENDENCY_MISSING",
            component="N3DSXLCaptureDevice",
            details={"extra": "n3dsxl"},
        ) from exc

    ponkan_config = CaptureConfig(
        backend=config.backend,
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
        return open_capture(config=ponkan_config)
    except CaptureError as exc:
        raise ConfigurationError(
            "failed to open n3dsxl capture source",
            code="NYX_N3DSXL_CAPTURE_OPEN_FAILED",
            component="N3DSXLCaptureDevice",
            details={"backend": config.backend, "cause": type(exc).__name__},
            cause=exc,
        ) from exc
```

実装では `CaptureError` 型 import を function 内に閉じ込める。test では `opener` injection で `ponkan` を import せずに検証する。

### 4.2 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | `camera` / `window` / `n3dsxl` |
| `n3dsxl_capture_backend` | `str` | `"auto"` | `auto` / `d3xx` / `d3xx-native`。0.1.1 では `auto` は D3XX 経路 |
| `n3dsxl_raw_slots` | `int` | `2` | backend raw read slot 数 |
| `n3dsxl_output_queue_size` | `int` | `2` | decoded frame queue capacity |
| `n3dsxl_drop_policy` | `str` | `"drop_oldest"` | `drop_oldest` / `drop_newest` / `block` |
| `n3dsxl_poll_interval` | `float` | `0.004` | reader が frame 待ちで sleep する秒数 |
| `n3dsxl_read_timeout` | `float | None` | `1.0` | `CaptureReader.read()` の timeout。`None` は無期限待ちだが reader thread 内に限定する |
| `n3dsxl_collect_timing` | `bool` | `false` | `ponkan-python` の timing samples を有効化する |
| `n3dsxl_hd_aspect_box_enabled` | `bool` | `true` | `400x480` 画面を NyX 既存の 3DS HD 座標へ合わせるため 16:9 黒帯を付ける |

`capture_backend` は window capture backend の設定として維持する。n3dsxl では `n3dsxl_capture_backend` を使い、`mss` / `windows_graphics_capture` と `d3xx` を同じ key に混在させない。

### 4.3 設定 parsing

`capture_source_from_settings()` は `capture_source_type == "n3dsxl"` の場合に `N3DSXLCaptureSourceConfig` を返す。数値項目は正値を要求し、`read_timeout` は `None` または `>= 0` とする。

`n3dsxl_hd_aspect_box_enabled` は source 固有の既定値を持つ。既存 `capture_aspect_box_enabled` は camera/window 用のまま維持し、n3dsxl の既定値を巻き込まない。

### 4.4 FrameSourcePortFactory

`FrameSourcePortFactory.__init__()` に `n3dsxl_capture_factory` を追加する。

```python
class FrameSourcePortFactory:
    def __init__(
        self,
        *,
        discovery: DeviceDiscoveryService,
        logger: LoggerPort | None = None,
        capture_factory: Callable[..., object] = CameraCaptureDevice,
        n3dsxl_capture_factory: Callable[..., object] = N3DSXLCaptureDevice,
        window_locator_factory: Callable[[], WindowLocatorBackend] | None = None,
        window_backend_factory: Callable[[str], WindowCaptureBackend] | None = None,
    ) -> None: ...
```

`create()` は `N3DSXLCaptureSourceConfig` を match し、`_create_n3dsxl_source()` を呼ぶ。n3dsxl source は camera discovery を必要としないため、`select_capture_target()` を通らない。`allow_dummy=True` の場合は open / initialize 失敗時に既存 `_FallbackCaptureDevice` で `DummyCaptureDevice` へ fallback する。

cache key は source type、backend、queue 設定、timing 設定、transform を含める。`read_timeout` や `poll_interval` が変わった場合、古い reader を再利用しない。

### 4.5 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError(code="NYX_N3DSXL_CAPTURE_DEPENDENCY_MISSING")` | `ponkan` または D3XX extra が import できない |
| `ConfigurationError(code="NYX_N3DSXL_CAPTURE_OPEN_FAILED")` | `open_capture()` が `DeviceNotFound`、`UnsupportedOperation`、`Ftd3CommandError` などの `CaptureError` を送出した |
| `ConfigurationError(code="NYX_CAPTURE_SOURCE_INVALID")` | `capture_source_type` が `camera` / `window` / `n3dsxl` 以外 |
| `ConfigurationError(code="NYX_N3DSXL_CAPTURE_BACKEND_INVALID")` | `n3dsxl_capture_backend` が choices 外 |
| `CaptureDeviceNotReady` | reader thread がまだ最初の frame を cache していない |
| `CaptureDeviceReadFailed` | reader thread が `CaptureError` または想定外例外で停止した |
| `FrameNotReadyError` | `CaptureFrameSourcePort` が `CaptureDeviceNotReady` を受け取った |
| `FrameReadError` | `CaptureFrameSourcePort` が `CaptureDeviceReadFailed` を受け取った |

`CaptureReader.read()` が `None` を返す timeout は fatal error ではない。reader thread は継続し、rate limit した technical log だけを出す。連続 timeout を fatal とするかは initial implementation では扱わない。

### 4.6 シングルトン管理

新規グローバル singleton は追加しない。`FrameSourcePortFactory` が `N3DSXLCaptureDevice` の lifetime を所有し、`close()` で `release()` を呼ぶ。GUI preview と Runtime が同じ source key を使う場合は既存 `_SharedCaptureDevice` により reader を共有する。

### 4.7 実装手順

| Step | 内容 | 完了条件 |
|------|------|----------|
| 1 | optional dependency と settings schema を追加 | `capture_source_type="n3dsxl"` が schema validation を通る |
| 2 | `N3DSXLCaptureSourceConfig` と parsing を追加 | unit test で default aspect box と validation を確認 |
| 3 | `N3DSXLCaptureDevice` を fake opener で実装 | 実機なしで start / cache / close / fatal error を検証 |
| 4 | `FrameSourcePortFactory` に n3dsxl 分岐を追加 | fake factory で reuse / fallback / close を検証 |
| 5 | GUI settings に source 選択を追加 | n3dsxl settings 保存と preview rebuild を GUI test で確認 |
| 6 | 実機 gate を追加 | `NYX_REALDEVICE=1` かつ `NYX_N3DSXL_CAPTURE=1` のときだけ実行 |
| 7 | perf smoke を追加 | reader timeout が `try_latest_frame()` を block しないことを確認 |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_capture_source_from_settings_creates_n3dsxl_source` | settings から `N3DSXLCaptureSourceConfig` を構築し、aspect box 既定が true である |
| ユニット | `test_capture_source_rejects_invalid_n3dsxl_backend` | `n3dsxl_capture_backend` の choices 外を `ConfigurationError` にする |
| ユニット | `test_n3dsxl_capture_device_caches_bgr_frame_copy` | fake reader の BGR frame が copy として返る |
| ユニット | `test_n3dsxl_capture_device_raises_not_ready_before_first_frame` | 初回 frame 前の `get_frame()` が `CaptureDeviceNotReady` を送出する |
| ユニット | `test_n3dsxl_capture_device_close_is_idempotent` | `release()` 複数回で reader close が一度だけ行われる |
| ユニット | `test_n3dsxl_capture_device_reports_reader_failure` | fake reader の fatal error を `CaptureDeviceReadFailed` として保持する |
| ユニット | `test_n3dsxl_capture_missing_dependency_is_configuration_error` | `ponkan` import 失敗時に install extra を含む `ConfigurationError` を出す |
| ユニット | `test_capture_frame_source_maps_capture_device_read_failed` | fatal read error を `FrameReadError` に変換する |
| ユニット | `test_frame_source_factory_creates_n3dsxl_source` | n3dsxl source で `N3DSXLCaptureDevice` を生成する |
| ユニット | `test_frame_source_factory_recreates_n3dsxl_when_backend_changes` | backend / queue 設定変更で cache key が変わる |
| ユニット | `test_frame_source_factory_falls_back_to_dummy_when_n3dsxl_open_fails` | `allow_dummy=True` では open 失敗時に Dummy へ fallback する |
| 結合 | `test_runtime_uses_n3dsxl_frame_source` | fake n3dsxl source から `Command.capture()` が `1280x720` BGR frame を返す |
| GUI | `test_device_settings_tab_applies_n3dsxl_capture_settings` | GUI settings で source / backend / timing を保存する |
| ハードウェア | `test_ponkan_n3dsxl_capture_device_realdevice` | `@pytest.mark.realdevice`。D3XX 接続、ready、capture shape、close を確認する |
| パフォーマンス | `test_n3dsxl_frame_source_try_latest_frame_is_nonblocking` | reader timeout 中でも `try_latest_frame()` が即時 `None` または copy を返す |

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
- [x] source type 名を `n3dsxl` に確定
- [x] dependency を optional extra に隔離する方針を確定
- [ ] `pyproject.toml` に optional extra `n3dsxl` を追加
- [ ] capture device 例外 contract を実装
- [ ] `N3DSXLCaptureSourceConfig` と settings parsing を実装
- [ ] `N3DSXLCaptureDevice` を fake opener で単体テスト可能に実装
- [ ] `FrameSourcePortFactory` に n3dsxl source 分岐を追加
- [ ] GUI settings に n3dsxl source 設定を追加
- [ ] unit / integration test を追加
- [ ] `@pytest.mark.realdevice` の実機 gate を追加
- [ ] performance smoke test を追加
- [ ] `uv lock --check`
- [ ] `uv run ruff check .`
- [ ] `uv run ty check src/nyxpy --output-format concise --no-progress`
- [ ] 変更範囲の `uv run pytest ...`

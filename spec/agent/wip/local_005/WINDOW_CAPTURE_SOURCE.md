# ウィンドウキャプチャ入力ソース 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`, `src/nyxpy/framework/core/io/`
> **目的**: カメラデバイス以外の画面取得経路として、PC 上の既存ウィンドウまたは画面領域をフレーム入力ソースにする。
> **関連ドキュメント**: `src/nyxpy/framework/core/hardware/capture.py`, `src/nyxpy/framework/core/io/device_factories.py`

## 1. 概要

### 1.1 目的

現行の `cv2.VideoCapture` ベースのカメラ入力に加え、PC 上で表示されているビュアーウィンドウをキャプチャして `FrameSourcePort` へ供給する。フレームワーク層は入力元の違いを `CaptureDeviceInterface` 相当の抽象で隔離し、マクロ・画像処理・通知は従来どおり OpenCV 互換の BGR フレームを扱う。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| CaptureDeviceInterface | `initialize` / `get_frame` / `release` を持つ画面取得デバイス抽象 |
| AsyncCaptureDevice | 現行のカメラデバイス実装。`cv2.VideoCapture` から非同期に最新フレームを取得する |
| FrameSourcePort | マクロ実行基盤へ最新フレームを供給する I/O ポート |
| カメラキャプチャ | OS にカメラデバイスとして認識されたキャプチャカードから画面を取得する方式 |
| ウィンドウキャプチャ | PC 上のアプリケーションウィンドウを対象に画面を取得する方式 |
| 画面領域キャプチャ | ウィンドウ追跡を行わず、指定した矩形領域を対象に画面を取得する方式 |
| ウィンドウ列挙 | OS から可視ウィンドウのタイトル・ハンドル・座標を取得する処理 |
| ウィンドウロケータ | ウィンドウ列挙と対象ウィンドウ解決だけを担当する実装 |
| キャプチャバックエンド | OS API または外部ライブラリを用いて実際に画素を取得する実装 |
| キャプチャセッション | バックエンド固有の初期化済み状態。同期取得・イベント駆動取得の差を吸収する |
| アスペクトボックス | 入力フレームへ黒帯を追加し、縦横比を 16:9 に整える処理 |
| ピラーボックス | 横幅が足りない入力に左右の黒帯を追加する処理 |
| レターボックス | 高さが足りない入力に上下の黒帯を追加する処理 |
| オクルージョン | 対象ウィンドウが別ウィンドウに隠れている状態 |
| DPI awareness | Windows の論理座標と物理ピクセル座標のずれを避けるためのプロセス DPI 認識設定 |

### 1.3 背景・問題

現在の画面取得経路は `AsyncCaptureDevice` と `DeviceDiscoveryService._detect_capture_devices()` がカメラデバイスを前提としている。特定のゲーム・キャプチャ機器では映像が独自ビュアーにのみ表示され、OS のカメラデバイスとして取得できないため、現行設計ではマクロへフレームを供給できない。

ウィンドウキャプチャは OS ごとに制約が異なる。Windows は Windows Graphics Capture によるウィンドウ単位キャプチャが候補になる一方、Linux Wayland は任意ウィンドウの自動キャプチャを意図的に制限している。したがって、単一ライブラリに直接依存せず、バックエンド差し替え可能な設計にする。

既存マクロと画像リソースは、標準の `Command.capture()` が最終的に 1280x720 へリサイズすることを前提にしている。対象ビュアーによっては 600x720 のように横幅が狭いウィンドウを取得するため、入力フレームをそのまま渡すと現行どおり横方向に引き伸ばされる。必要な入力ソースだけ 16:9 のアスペクトボックスを有効化し、左右または上下に黒帯を追加してから既存のリサイズ経路へ渡す。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 入力ソース種別 | カメラデバイスのみ | カメラ、ウィンドウ、画面領域を同じ `FrameSourcePort` で扱える |
| 既存マクロ変更 | カメラ入力前提 | マクロ側の変更なし |
| フレーム形式 | `numpy.ndarray` / BGR | すべての入力ソースで `numpy.ndarray` / BGR に正規化 |
| 出力フレームサイズ | `FrameSourcePort` は raw frame、`Command.capture()` が 1280x720 へリサイズ | 既定は raw frame 維持。必要なソースだけ 16:9 黒帯付与を選択可能 |
| 特殊ウィンドウ対応 | 600x720 は 1280x720 へ横伸びする | アスペクトボックス有効時は 600x720 に左右黒帯を追加し、後段 resize で歪ませない |
| 実機なしテスト | `DummyCaptureDevice` 中心 | ウィンドウ列挙・矩形計算・色変換を Dummy backend で単体テスト可能 |
| プレビュー用途の目標 FPS | カメラ設定依存 | 汎用バックエンドで 30 FPS、Windows 専用バックエンドで 60 FPS を目標 |

### 1.5 着手条件

- 既存テスト (`uv run pytest tests/unit/`) がすべてパスすること。
- 採用候補ライブラリの Python `>=3.12,<3.14` 対応、ライセンス、配布形式を確認すること。
- `PyWinCtl`、`windows-capture` は Python 3.13 wheel 提供状況と OS 別依存を検証してから必須依存にすること。
- `mss` を使う backend は `mss.mss()` インスタンスをスレッド間共有しない設計にすること。
- Windows ではウィンドウ座標と `mss` の物理ピクセル座標が一致するよう、DPI awareness の方針を先に決めること。
- macOS は画面収録権限、Linux Wayland は portal によるユーザー許可が必要になる制約を UI・エラー文言に反映すること。
- Windows 以外の OS では「任意ウィンドウを隠れた状態で取得する」ことを要件に含めない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | 汎用キャプチャ候補ライブラリを追加する。MVP では `mss` を第一候補とし、OS 専用バックエンドは任意依存として扱う |
| `src/nyxpy/framework/core/hardware/capture.py` | 変更 | カメラ実装と入力ソース共通抽象を分離し、既存 `AsyncCaptureDevice` の責務を明確化する |
| `src/nyxpy/framework/core/hardware/window_capture.py` | 新規 | ウィンドウ・画面領域キャプチャデバイスとバックエンド抽象を実装する |
| `src/nyxpy/framework/core/hardware/frame_transform.py` | 新規 | 入力フレームへ 16:9 の黒帯を追加するアスペクトボックス処理を実装する |
| `src/nyxpy/framework/core/hardware/window_discovery.py` | 新規 | ウィンドウ列挙、タイトル照合、クライアント領域解決を実装する |
| `src/nyxpy/framework/core/hardware/device_discovery.py` | 変更 | カメラデバイスとウィンドウ候補を区別して検出結果に含める |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | 設定された入力ソース種別に応じてカメラまたはウィンドウキャプチャを生成する |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | `FrameSourcePortFactory.create()` に入力ソース設定を渡す |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `capture_source_type`、`capture_window_title`、`capture_region` などの設定項目を追加する |
| `src/nyxpy/gui/dialogs/settings/device_tab.py` | 変更 | 入力ソース種別、ウィンドウ候補、画面領域指定を設定できる UI を追加する |
| `src/nyxpy/gui/app_services.py` | 変更 | 入力ソース設定変更時に Preview と Runtime builder を再生成する |
| `tests/unit/hardware/test_window_capture.py` | 新規 | Dummy backend によるウィンドウキャプチャの単体テスト |
| `tests/unit/hardware/test_window_discovery.py` | 新規 | タイトル照合、候補重複、矩形解決の単体テスト |
| `tests/unit/io/test_frame_source_factory.py` | 変更 | 入力ソース種別ごとの factory 分岐を検証する |
| `tests/hardware/test_window_capture_device.py` | 新規 | 実画面を使うウィンドウキャプチャ確認。`@pytest.mark.realdevice` を付ける |

## 3. 設計方針

### アーキテクチャ上の位置づけ

ウィンドウキャプチャは `core/hardware` の画面取得デバイス実装として扱う。`core/io` は既存どおり `CaptureFrameSourcePort` でラップし、マクロ実行基盤へ `FrameSourcePort` として渡す。GUI は設定・候補選択のみを担当し、フレームワーク層は GUI に依存しない。

### 公開 API 方針

`FrameSourcePort` の公開 API は変更しない。入力ソースごとの差異は `CaptureDeviceInterface` と factory の内部で吸収する。

現行の `AsyncCaptureDevice` はカメラ専用であることが分かる名前へ変更する案を採る。Project NyX のフレームワーク本体はアルファ版であるため、互換 alias は追加しない。既存呼び出し元とテストは同じ変更内で正 API へ更新する。

```python
class CaptureDeviceInterface(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def get_frame(self) -> cv2.typing.MatLike: ...

    @abstractmethod
    def release(self) -> None: ...


@dataclass(frozen=True)
class WindowInfo:
    title: str
    identifier: str | int
    rect: CaptureRect
    app_name: str | None = None


@dataclass(frozen=True)
class CaptureRect:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class FrameTransformConfig:
    aspect_box_enabled: bool = False
    background_bgr: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class WindowCaptureConfig:
    title_pattern: str
    match_mode: Literal["exact", "contains"] = "exact"
    identifier: str | int | None = None
    client_area: bool = True
    fps: float = 30.0
    backend: Literal["auto", "mss", "windows_graphics_capture"] = "auto"
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


class WindowLocatorBackend(ABC):
    @abstractmethod
    def list_windows(self) -> tuple[WindowInfo, ...]: ...

    @abstractmethod
    def resolve(self, config: WindowCaptureConfig) -> WindowInfo: ...


class WindowCaptureSession(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def latest_frame(self) -> cv2.typing.MatLike: ...

    @abstractmethod
    def stop(self) -> None: ...


class WindowCaptureBackend(ABC):
    @abstractmethod
    def create_session(
        self,
        config: WindowCaptureConfig,
        locator: WindowLocatorBackend,
    ) -> WindowCaptureSession: ...

    @abstractmethod
    def release(self) -> None: ...


class WindowCaptureDevice(CaptureDeviceInterface):
    def __init__(
        self,
        config: WindowCaptureConfig,
        *,
        locator: WindowLocatorBackend | None = None,
        backend: WindowCaptureBackend | None = None,
        logger: LoggerPort | None = None,
    ) -> None: ...
```

### ライブラリ選定

| 候補 | 役割 | 採用判断 | 理由 |
|------|------|----------|------|
| `mss` | 画面・矩形キャプチャ | MVP の第一候補 | Python 3.12 対応、依存なし、Windows/macOS/Linux 対応、NumPy/OpenCV 連携が容易 |
| `PyWinCtl` | ウィンドウ列挙・座標取得 | 要検証の任意候補 | クロスプラットフォームのウィンドウ情報取得が目的に合う。ただし画素取得は担わず、PyPI の分類は Python 3.12 を明示していない。Wayland 制約もある |
| `windows-capture` | Windows Graphics Capture | Windows 専用バックエンド候補 | ウィンドウ名指定と Windows Graphics Capture API を提供する。イベント駆動 API と Rust wheel 依存のため任意依存として隔離する |
| `dxcam` | Windows 高速画面キャプチャ | 性能改善候補 | DXGI / WinRT による高速取得が可能。ただし主用途は画面・領域キャプチャで、クロスプラットフォームではない |
| `pyautogui` / `pyscreenshot` | スクリーンショット | 採用しない | 依存が重く、保守・性能面で `mss` を優先する理由が強い |

MVP は `mss` による「対象ウィンドウの現在位置を矩形として取得する」方式にする。この方式では対象ウィンドウが他のウィンドウに隠れると隠れた後のデスクトップ領域を取得するため、オクルージョン非対応である。Windows では後続ステップで Windows Graphics Capture backend を追加し、隠れているが最小化されていないウィンドウの取得を改善する。

`mss` backend はキャプチャスレッド内で `mss.mss()` を生成し、他スレッドへ共有しない。ウィンドウ列挙は `WindowLocatorBackend`、画素取得は `WindowCaptureBackend` に分け、列挙処理とキャプチャ処理の依存・スレッド制約を混在させない。

### アスペクトボックス方針

既定では backend から取得した frame を raw frame として保持し、現行どおり Preview と `Command.capture()` 側で個別にリサイズする。`aspect_box_enabled=true` の入力ソースだけ、raw frame の縦横比を 16:9 にするために黒帯を追加してから `latest_frame` へ保存する。600x720 の入力では高さ 720 を維持し、幅 1280 になるよう左右に 340 px ずつ黒帯を追加する。

16:9 は `Command.capture()` の標準出力 1280x720 と同じ比率であり、アスペクトボックス側だけ比率を変更できる設定は追加しない。比率が二重定義されると、黒帯付与後に `Command.capture()` で再度歪むためである。

| 入力 | `aspect_box_enabled=false` | `aspect_box_enabled=true` |
|------|----------------------------|---------------------------|
| 1280x720 | raw frame を返す | 16:9 のため raw frame を返す |
| 600x720 | raw frame を返し、`Command.capture()` が横へ伸ばす | 左右黒帯を追加した 1280x720 相当の比率で返す |
| 800x600 | raw frame を返し、`Command.capture()` が 16:9 へ伸ばす | 上下黒帯を追加して 16:9 にして返す |

黒帯は中央揃え固定、色は黒固定である。位置調整が必要な場合は入力領域を `capture_region` で切り直す。任意 offset 貼り付けは MVP の責務に含めない。

### 後方互換性

破壊的変更を許容する。`AsyncCaptureDevice` をカメラ専用名へ変更する場合は alias を残さず、`FrameSourcePortFactory`、GUI、テストを同時に更新する。ただし `FrameSourcePort` と `CaptureFrameSourcePort` の API は維持し、マクロ側の呼び出し変更は発生させない。

`capture_aspect_box_enabled` の既定値は `false` とし、16:9 ソースでは現行と同じ frame が後段へ渡る。非 16:9 ソースで `capture_aspect_box_enabled=true` を選んだ場合だけ、現行の単純引き伸ばしから黒帯付きの縦横比維持へ挙動が変わる。この場合、非 16:9 ソースを前提に作ったテンプレート画像や crop 座標は見直しが必要になる。

### レイヤー構成

| レイヤー | 責務 | 依存先 |
|----------|------|--------|
| `core/hardware/window_discovery.py` | キャプチャ対象ウィンドウ候補の列挙と照合 | OS API / 任意ライブラリ |
| `core/hardware/window_capture.py` | 画素取得、色変換、非同期フレームキャッシュ | `WindowCaptureBackend`, `LoggerPort` |
| `core/io/device_factories.py` | 設定値から `CaptureDeviceInterface` を生成 | `core/hardware` |
| `gui/dialogs/settings/device_tab.py` | ユーザー設定 UI | `DeviceDiscoveryService` |

フレームワーク層から GUI へは依存しない。外部ライブラリ依存は backend 実装内へ閉じ込め、import 失敗時は明示的な設定エラーとして扱う。

`DeviceDiscoveryResult.capture_devices` にウィンドウ候補を混在させない。カメラは既存の `detect()` / `capture_devices`、キャプチャ対象ウィンドウ候補は `DeviceDiscoveryService.detect_window_sources()` で扱い、既存の `find_capture()` はカメラ専用として維持する。GUI はこの framework API から取得した `WindowInfo` をプルダウンに表示し、選択結果の title / identifier を settings へ保存する。アクティブウィンドウの推定や GUI 側での OS API 呼び出しは行わない。

### キャッシュキーと lifetime

`FrameSourcePortFactory` の `_devices` は入力ソース設定を含むキーで管理する。キーは `source_type`、対象識別子、領域、backend、fps を含めた immutable な dataclass にし、設定変更時に古いデバイスを再利用しない。

```python
@dataclass(frozen=True)
class CaptureSourceKey:
    source_type: CaptureSourceType
    identifier: str
    backend: str
    fps: float
    region: CaptureRect | None = None
```

GUI の設定変更では Runtime builder を再生成し、古い `FrameSourcePortFactory.close()` を通じてキャプチャセッションを停止する。

### Windows DPI 方針

Windows ではウィンドウ矩形と画面キャプチャ矩形を物理ピクセル座標へ統一する。実装候補は以下の順に検証する。

| 方針 | 採否 | 理由 |
|------|------|------|
| プロセス起動時に Per-Monitor DPI Aware を設定 | 第一候補 | `mss` の物理ピクセル座標と一致させやすい |
| ウィンドウロケータ側で物理座標へ変換 | 代替 | 他ライブラリとの副作用を抑えられるが、OS API 分岐が増える |
| 論理座標のまま `mss` に渡す | 採用しない | 125% / 150% スケーリングで切り抜き位置がずれる |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 汎用 backend のプレビュー取得 | 1280x720 相当で 30 FPS |
| Windows 専用 backend のプレビュー取得 | 1920x1080 相当で 60 FPS |
| `get_frame()` のロック保持時間 | フレームコピー時間を除き 5 ms 未満 |
| 初期化失敗時の検出 | `initialize()` 内で即時例外化 |
| リソース解放 | `release()` を複数回呼んでも例外なし |
| アスペクトボックス処理 | 16:9 黒帯付与を有効化しても 30 FPS を阻害しない |

### 並行性・スレッド安全性

`WindowCaptureDevice` は現行 `AsyncCaptureDevice` と同じく専用スレッドで最新フレームを更新する。`latest_frame` への読み書きは `threading.Lock` で保護し、`get_frame()` はコピー済みフレームを返す。backend がスレッドセーフでない場合は、キャプチャスレッド内でのみ backend API を呼び出す。

Windows Graphics Capture のようなイベント駆動 backend は、`WindowCaptureSession.start()` が内部で必要なイベントループまたは callback thread を所有する。`WindowCaptureDevice` は session から `latest_frame()` を読むだけにし、backend 固有のイベント処理を呼び出し元へ漏らさない。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass, field


CaptureSourceType = Literal["camera", "window", "screen_region"]


@dataclass(frozen=True)
class CameraCaptureSourceConfig:
    source_type: Literal["camera"] = "camera"
    device_name: str = ""
    fps: float = 60.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


@dataclass(frozen=True)
class WindowCaptureSourceConfig:
    source_type: Literal["window"] = "window"
    title_pattern: str = ""
    match_mode: Literal["exact", "contains"] = "exact"
    identifier: str | int | None = None
    backend: Literal["auto", "mss", "windows_graphics_capture"] = "auto"
    fps: float = 30.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


@dataclass(frozen=True)
class ScreenRegionCaptureSourceConfig:
    region: CaptureRect
    source_type: Literal["screen_region"] = "screen_region"
    fps: float = 60.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


CaptureSourceConfig = (
    CameraCaptureSourceConfig
    | WindowCaptureSourceConfig
    | ScreenRegionCaptureSourceConfig
)


class FrameSourcePortFactory:
    def create(
        self,
        *,
        source: CaptureSourceConfig,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> FrameSourcePort: ...
```

`FrameSourcePortFactory.create()` は `source.source_type` で分岐する。

| `source_type` | 生成対象 | 説明 |
|---------------|----------|------|
| `camera` | `CameraCaptureDevice` | 現行 `cv2.VideoCapture` 経路 |
| `window` | `WindowCaptureDevice` | タイトルまたは識別子で選択したウィンドウを追跡 |
| `screen_region` | `ScreenRegionCaptureDevice` | 固定矩形を取得。ウィンドウ列挙に依存しない |

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | `camera` / `window` / `screen_region` |
| `capture_device` | `str` | `""` | カメラ入力時のデバイス名。既存設定を引き続き使用する |
| `capture_window_title` | `str` | `""` | ウィンドウ入力時の対象タイトル |
| `capture_window_match_mode` | `str` | `"exact"` | タイトル照合方式。`exact` または `contains` |
| `capture_window_identifier` | `str` | `""` | GUI で選択したウィンドウのハンドル等。再解決の第一候補 |
| `capture_window_client_area` | `bool` | `true` | ウィンドウ装飾を除いたクライアント領域を優先する |
| `capture_backend` | `str` | `"auto"` | `auto` / `mss` / `windows_graphics_capture` |
| `capture_region` | `dict[str, int]` | `{}` | 画面領域入力時の `left` / `top` / `width` / `height` |
| `capture_fps` | `float` | source type 依存 | カメラ・画面領域は `60.0`、ウィンドウは `30.0` |
| `capture_aspect_box_enabled` | `bool` | `false` | `true` の場合、raw frame に黒帯を追加して 16:9 に整える |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | 入力ソース種別が不正、対象ウィンドウが未指定、必要ライブラリが未導入、OS が backend をサポートしない |
| `RuntimeError` | 初期化済み backend がフレームを取得できない、対象ウィンドウが閉じられた |
| `FrameNotReadyError` | `CaptureFrameSourcePort.latest_frame()` が初回フレーム到着前に呼ばれた |

外部ライブラリの import 失敗を握りつぶさない。ユーザー向けログには解決策を含め、技術ログには backend 名、OS、対象タイトルを含める。

対象ウィンドウが消失した場合、`WindowCaptureDevice` は一定間隔で `WindowLocatorBackend.resolve()` を再試行する。再解決中は最後のフレームを使い回さず `FrameNotReadyError` 相当の状態にする。再試行の上限を超えた場合は `RuntimeError` として明示的に失敗させる。

### OS 別制約

| OS | MVP 動作 | 制約 |
|----|---------|------|
| Windows | `mss` による画面領域取得、後続で Windows Graphics Capture backend | `mss` は隠れたウィンドウを取得できない。最小化ウィンドウは Windows Graphics Capture でも新規描画されない |
| macOS | `mss` による画面領域取得 | 画面収録権限が必要。権限がない場合は初期化時に失敗させる |
| Linux X11 | `mss` による画面領域取得 | ウィンドウ座標取得は環境差がある |
| Linux Wayland | 原則として自動ウィンドウキャプチャ非対応 | portal のユーザー許可が必要で、任意ウィンドウをプログラムから直接指定できない |

### シングルトン管理

新規グローバル singleton は追加しない。`FrameSourcePortFactory` が capture device の lifetime を所有し、`close()` で backend リソースを解放する。

### 実装計画

| Step | 仕様書 | 目的 | 完了条件 |
|------|--------|------|----------|
| 1 | `WINDOW_CAPTURE_MVP.md` | framework 側に `mss` ベースの入力ソース、16:9 アスペクトボックス、settings 接続を実装する | 設定値だけで `window` / `screen_region` を取得でき、必要なソースだけ黒帯付き 16:9 frame として扱える |
| 2 | `WINDOW_CAPTURE_WINDOWS_BACKEND.md` | Windows Graphics Capture backend を検討・実装する | `capture_backend=windows_graphics_capture` で最小化されていない隠れたウィンドウを取得できる |
| 3 | `WINDOW_CAPTURE_GUI_SETTINGS.md` | GUI から入力ソース、対象ウィンドウ、領域、アスペクトボックス設定を編集できるようにする | 設定画面から source 切替と 600x720 等の黒帯付与設定を保存・反映できる |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_window_capture_device_returns_bgr_copy` | Dummy backend の BGRA 入力が BGR のコピーとして返る |
| ユニット | `test_window_capture_device_raises_before_first_frame` | 初回フレーム前の `get_frame()` が `RuntimeError` を出す |
| ユニット | `test_window_capture_device_release_is_idempotent` | `release()` の複数回呼び出しが安全である |
| ユニット | `test_window_title_exact_match` | 完全一致で対象ウィンドウを選択する |
| ユニット | `test_window_title_contains_match_rejects_ambiguous_candidates` | 部分一致が複数候補になる場合に明示エラーにする |
| ユニット | `test_frame_source_factory_creates_window_source` | `capture_source_type=window` で `WindowCaptureDevice` が生成される |
| ユニット | `test_frame_source_factory_keeps_camera_source_default` | 既定値ではカメラ経路が使われる |
| ユニット | `test_frame_source_factory_recreates_device_when_source_key_changes` | 入力ソース設定が変わった場合に古いキャッシュを再利用しない |
| ユニット | `test_mss_backend_creates_mss_instance_inside_capture_thread` | `mss.mss()` をスレッド間共有しない |
| ユニット | `test_window_capture_re_resolves_window_after_handle_disappears` | ウィンドウ消失時にハンドル、PID、タイトルの順で再解決する |
| ユニット | `test_window_rect_is_normalized_to_physical_pixels` | DPI スケーリング時に物理ピクセル座標へ正規化する |
| ユニット | `test_aspect_box_adds_pillarbox_to_600x720` | 600x720 入力へ左右黒帯を追加して 16:9 にする |
| ユニット | `test_aspect_box_adds_letterbox_to_wide_input` | 横長入力へ上下黒帯を追加して 16:9 にする |
| ユニット | `test_aspect_box_disabled_keeps_raw_frame` | 無効時は raw frame のサイズを変えない |
| 結合 | `test_runtime_builder_passes_capture_source_config` | Runtime builder から factory へ入力ソース設定が渡る |
| GUI | `test_device_settings_tab_applies_window_capture_settings` | 設定画面がウィンドウキャプチャ設定を保存する |
| ハードウェア | `test_window_capture_device_real_window` | 実ウィンドウを取得できる。`@pytest.mark.realdevice` を付ける |
| パフォーマンス | `test_window_capture_preview_fps` | Dummy またはローカル固定領域で目標 FPS を下回らない |

## 6. 実装チェックリスト

- [x] 調査結果の整理
- [x] 公開 API の初期案作成
- [x] 採用ライブラリの Python 3.12/3.13 インストール検証
- [x] `mss` backend のプロトタイプ作成
- [x] 16:9 アスペクトボックス設定の実装
- [x] Windows Graphics Capture backend の採否判断
- [x] 内部実装
- [x] 型ヒントの整合性チェック（ruff）
- [x] 既存テストが破壊されないことの確認
- [x] ユニットテスト作成・パス
- [x] 統合テスト作成・パス
- [x] GUI 設定テスト作成・パス
- [x] ドキュメントコメント（公開 API のみ）

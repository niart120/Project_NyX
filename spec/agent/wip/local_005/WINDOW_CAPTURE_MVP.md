# ウィンドウキャプチャ MVP 実装 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`, `src/nyxpy/framework/core/io/`, `src/nyxpy/framework/core/runtime/`
> **目的**: `mss` ベースの画面領域キャプチャを `FrameSourcePort` に接続し、GUI なしでも設定値からウィンドウまたは固定領域をフレーム入力にできる MVP を実装する。
> **関連ドキュメント**: `spec/agent/wip/local_005/WINDOW_CAPTURE_SOURCE.md`

## 1. 概要

### 1.1 目的

フレームワーク層に `camera` / `window` / `screen_region` の入力ソース抽象を追加し、既存マクロへ影響を出さずに `FrameSourcePort` へ BGR フレームを供給する。MVP では `mss` による画面領域取得を採用し、ウィンドウキャプチャは「対象ウィンドウの現在位置を矩形として取得する」方式で実現する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| CaptureDeviceInterface | `initialize` / `get_frame` / `release` を持つ画面取得デバイス抽象 |
| FrameSourcePort | マクロ実行基盤へ最新フレームを供給する I/O ポート |
| CaptureSourceConfig | 入力ソース種別と対象情報を表す設定 dataclass |
| WindowLocatorBackend | ウィンドウ列挙と対象ウィンドウ解決を担当する backend |
| MssCaptureSession | `mss.mss()` をキャプチャスレッド内で所有する画素取得 session |
| FrameTransformConfig | 入力フレームへ 16:9 の黒帯を付与するかを表す設定 |
| FrameTransformer | BGR frame を必要に応じて 16:9 のアスペクトボックスへ整形する純粋ロジック |
| ScreenRegionCaptureDevice | 固定矩形を `mss` で取得する capture device |
| WindowCaptureDevice | locator で解決したウィンドウ矩形を `mss` で取得する capture device |
| CaptureSourceKey | `FrameSourcePortFactory` が共有デバイスをキャッシュするための immutable key |

### 1.3 背景・問題

現行の `FrameSourcePortFactory` は `capture_device` 名をカメラデバイスとして解決し、`AsyncCaptureDevice` を生成する。ウィンドウまたは画面領域を入力にするには、カメラ名だけではなく入力ソース種別、ウィンドウ識別子、矩形、backend を runtime まで渡す必要がある。

`mss` は画面全体または矩形領域の取得に適しているが、ウィンドウ列挙機能を持たない。また `mss.mss()` インスタンスのスレッド共有は避ける必要があるため、ウィンドウ解決と画素取得を分離する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 入力ソース種別 | カメラのみ | `camera` / `window` / `screen_region` |
| マクロ側 API 変更 | なし | なし |
| フレーム形式 | BGR `numpy.ndarray` | すべて BGR `numpy.ndarray` |
| 出力フレームサイズ | `FrameSourcePort` は raw frame、`Command.capture()` が 1280x720 へリサイズ | 既定は raw frame 維持。必要なソースだけ 16:9 黒帯付与を選択可能 |
| 汎用 backend 目標 FPS | 未対応 | 1280x720 相当で 30 FPS |
| 実機なしテスト | カメラ Dummy 中心 | locator / session / factory を Dummy で検証 |

### 1.5 着手条件

- `spec/agent/wip/local_005/WINDOW_CAPTURE_SOURCE.md` の方針が合意済みであること。
- `mss` の Python 3.12 / 3.13 動作とライセンスを確認すること。
- `uv run pytest tests/unit/` が開始時点でパスすること。
- GUI からの選択 UI は本仕様の範囲外とし、設定値または CLI 引数から構成可能な状態を MVP とする。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | `mss` を依存に追加する |
| `src/nyxpy/framework/core/hardware/capture.py` | 変更 | `AsyncCaptureDevice` をカメラ専用名へ整理し、共通インターフェースを維持する |
| `src/nyxpy/framework/core/hardware/capture_source.py` | 新規 | `CaptureSourceConfig`、`CaptureSourceKey`、`CaptureRect` を定義する |
| `src/nyxpy/framework/core/hardware/frame_transform.py` | 新規 | `FrameTransformConfig` と 16:9 アスペクトボックス用 `FrameTransformer` を実装する |
| `src/nyxpy/framework/core/hardware/platform_capture.py` | 新規 | Windows DPI awareness など OS 別の capture 前処理を実装する |
| `src/nyxpy/framework/core/hardware/window_discovery.py` | 新規 | `WindowInfo`、`WindowLocatorBackend`、タイトル照合ロジックを実装する |
| `src/nyxpy/framework/core/hardware/window_capture.py` | 新規 | `WindowCaptureBackend`、`WindowCaptureSession`、`WindowCaptureDevice`、`ScreenRegionCaptureDevice`、`MssCaptureSession` を実装する |
| `src/nyxpy/framework/core/hardware/device_discovery.py` | 変更 | `detect_window_sources()` を追加し、カメラ候補とウィンドウ候補の列挙を分離する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | `CaptureSourceConfig` に基づく device 生成と cache key 管理を追加する |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | settings から `CaptureSourceConfig` を組み立てて factory へ渡す |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | MVP に必要な capture source 設定を追加する |
| `tests/unit/hardware/test_capture_source.py` | 新規 | config / key / rect の単体テスト |
| `tests/unit/hardware/test_frame_transform.py` | 新規 | 16:9 黒帯付与、無効時 passthrough の単体テスト |
| `tests/unit/hardware/test_window_discovery.py` | 新規 | タイトル照合と曖昧候補の単体テスト |
| `tests/unit/hardware/test_window_capture.py` | 新規 | Dummy session による frame 取得・release の単体テスト |
| `tests/unit/hardware/test_platform_capture.py` | 新規 | Windows DPI awareness 初期化と座標正規化の単体テスト |
| `tests/unit/io/test_frame_source_factory.py` | 変更 | 入力ソース種別ごとの factory 分岐と cache key を検証する |
| `tests/integration/test_capture_source_runtime.py` | 新規 | settings から runtime builder まで `CaptureSourceConfig` が渡ることを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

MVP は `core/hardware` と `core/io` の責務に閉じる。GUI は本仕様では変更せず、既存 settings に新規キーを追加して runtime builder が読み取る。マクロ、画像処理、通知は既存 `FrameSourcePort` を通じてフレームを取得するため変更しない。

### 公開 API 方針

`FrameSourcePort` と `CaptureFrameSourcePort` の公開 API は維持する。`FrameSourcePortFactory.create()` は `name` ではなく `CaptureSourceConfig` を受け取る形へ変更する。フレームワーク本体はアルファ版のため、旧 `name` 引数の互換 shim は追加しない。

### 後方互換性

破壊的変更あり。`FrameSourcePortFactory.create()` と `create_device_runtime_builder()` の内部接続を同じ変更で更新し、呼び出し元のテストも正 API へ更新する。マクロ作者が利用する `Command` / `FrameSourcePort` は変更しないため、マクロコードの移行は不要である。

`capture_aspect_box_enabled=false` を既定値にし、現行の raw frame 受け渡しと `Command.capture()` 側の 1280x720 リサイズを維持する。非 16:9 ソースで `capture_aspect_box_enabled=true` を選んだ場合は、引き伸ばしではなく黒帯付きの縦横比維持に変わるため、その入力ソース向けのテンプレート画像・crop 座標は再確認が必要である。

### レイヤー構成

| レイヤー | 役割 |
|----------|------|
| `capture_source.py` | 入力ソース設定と cache key の純粋データ定義 |
| `frame_transform.py` | 入力 frame を必要に応じて 16:9 アスペクトボックスへ整形する純粋ロジック |
| `platform_capture.py` | OS ごとの capture 前処理。Windows では物理ピクセル座標へ統一する |
| `window_discovery.py` | ウィンドウ候補の列挙・照合。MVP では Dummy / OS 別最小実装を許容する |
| `window_capture.py` | `mss` による画面領域取得、色変換、非同期フレームキャッシュ |
| `device_factories.py` | `CaptureSourceConfig` から shared device を生成する composition root |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `screen_region` 取得 | 1280x720 相当で 30 FPS |
| `window` 取得 | 1280x720 相当で 30 FPS |
| frame 正規化 | 600x720 入力へ左右黒帯を追加して 16:9 に整え、30 FPS を維持 |
| `get_frame()` | 最新フレームの copy を返す。未準備時は `RuntimeError` |
| release | 複数回呼び出しても例外なし |

### 並行性・スレッド安全性

`MssCaptureSession` はキャプチャスレッド内で `mss.mss()` を生成し、同一インスタンスを他スレッドへ渡さない。`WindowCaptureDevice` と `ScreenRegionCaptureDevice` は `threading.Lock` で `latest_frame` を保護し、`get_frame()` は copy を返す。locator は初期解決と再解決時だけ呼び出し、画素取得ループと責務を混在させない。

Windows では `mss` が物理ピクセル座標を扱うため、capture 初期化前に Per-Monitor DPI Aware を設定する。すでに DPI awareness が設定済みで変更できない場合は、locator 側で物理座標へ正規化する。どちらも失敗した場合は `ConfigurationError` とする。

アスペクトボックス処理はキャプチャスレッド内で行い、`aspect_box_enabled=true` の場合だけ `latest_frame` に黒帯付与後の BGR frame を保存する。無効時は raw frame を保存し、現行どおり Preview と `Command.capture()` が後段でリサイズする。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass, field


CaptureSourceType = Literal["camera", "window", "screen_region"]


@dataclass(frozen=True)
class CaptureRect:
    left: int
    top: int
    width: int
    height: int

    def to_mss_monitor(self) -> dict[str, int]: ...


@dataclass(frozen=True)
class FrameTransformConfig:
    aspect_box_enabled: bool = False
    background_bgr: tuple[int, int, int] = (0, 0, 0)


class FrameTransformer:
    def transform(
        self,
        frame: cv2.typing.MatLike,
        config: FrameTransformConfig,
    ) -> cv2.typing.MatLike: ...


@dataclass(frozen=True)
class CameraCaptureSourceConfig:
    device_name: str = ""
    source_type: Literal["camera"] = "camera"
    fps: float = 60.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


@dataclass(frozen=True)
class WindowCaptureSourceConfig:
    title_pattern: str
    source_type: Literal["window"] = "window"
    match_mode: Literal["exact", "contains"] = "exact"
    identifier: str | int | None = None
    process_id: int | None = None
    backend: Literal["auto", "mss"] = "auto"
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
        config: WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig,
        locator: WindowLocatorBackend | None,
    ) -> WindowCaptureSession: ...

    @abstractmethod
    def release(self) -> None: ...


class MssWindowCaptureBackend(WindowCaptureBackend):
    def create_session(
        self,
        config: WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig,
        locator: WindowLocatorBackend | None,
    ) -> WindowCaptureSession: ...

    def release(self) -> None: ...


class FrameSourcePortFactory:
    def create(
        self,
        *,
        source: CaptureSourceConfig,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> FrameSourcePort: ...
```

### 内部設計

`FrameSourcePortFactory.create()` は以下の順で分岐する。

| source type | 処理 |
|-------------|------|
| `camera` | 既存カメラ検出と `CameraCaptureDevice` 生成を行う |
| `window` | `WindowCaptureSourceConfig` を検証し、locator と `WindowCaptureDevice` を生成する |
| `screen_region` | `CaptureRect` を検証し、`ScreenRegionCaptureDevice` を生成する |

MVP では `capture_backend=auto` を常に `mss` へ解決する。Windows backend 仕様の実装後に、Windows かつ optional dependency が使用可能な場合だけ `auto` の解決先を `windows_graphics_capture` へ変更する余地を残す。

`DeviceDiscoveryService.detect()` はカメラ候補とシリアル候補の既存挙動を維持する。ウィンドウ候補は新規 `detect_window_sources(timeout_sec: float = 2.0) -> tuple[WindowInfo, ...]` で列挙し、GUI やテストが必要なときだけ呼び出す。通常の `detect()` にウィンドウ列挙を混ぜず、既存のデバイス設定リロードを遅くしない。

`WindowCaptureDevice.initialize()` は locator で初回 `WindowInfo` を解決してから session を開始する。対象ウィンドウが消失した場合は以下の状態機械で再解決する。

| 状態 | 条件 | `get_frame()` の挙動 |
|------|------|----------------------|
| `capturing` | session が frame を取得中 | 最新 frame copy を返す |
| `resolving` | 連続 3 回 frame 取得に失敗した | `RuntimeError` を発生させ、`CaptureFrameSourcePort` が `FrameNotReadyError` に変換する |
| `failed` | 再解決を 10 秒継続しても対象が見つからない | `RuntimeError` を発生させる |

再解決中に最後の成功 frame を使い回さない。古い画面を成功扱いにすると画像認識結果が実画面と乖離するためである。

`FrameSourcePortFactory` は `CaptureSourceKey` が一致する source を共有する。同一 key では Preview と Runtime が同じ `_SharedCaptureDevice` を参照し、別 key では必ず別 device を生成する。`FrameSourcePortFactory.close()` は所有する全 shared device を停止し、参照カウントは持たない。

`FrameTransformer` は以下の規則で frame を処理する。

| 条件 | 処理 |
|------|------|
| `aspect_box_enabled=false` | raw frame をそのまま返す |
| 入力が 16:9 | raw frame をそのまま返す |
| 入力が 16:9 より縦長 | 左右へ黒帯を追加し、中央揃えで 16:9 にする |
| 入力が 16:9 より横長 | 上下へ黒帯を追加し、中央揃えで 16:9 にする |

600x720 入力は高さ 720 を維持し、幅 1280 になるよう左右に 340 px ずつ黒帯を追加する。1280x600 入力は幅 1280 を維持し、高さ 720 になるよう上下に 60 px ずつ黒帯を追加する。黒帯色は黒固定である。任意 offset 貼り付けは MVP の責務に含めず、位置調整が必要な場合は `capture_region` で入力領域を切り直す。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_source_type` | `str` | `"camera"` | `camera` / `window` / `screen_region` |
| `capture_device` | `str` | `""` | カメラ入力時のデバイス名 |
| `capture_window_title` | `str` | `""` | ウィンドウ入力時のタイトルパターン |
| `capture_window_match_mode` | `str` | `"exact"` | `exact` または `contains` |
| `capture_window_identifier` | `str` | `""` | 空文字列は `None` に正規化する。Windows handle も永続化時は文字列で保存する |
| `capture_window_process_id` | `int | None` | `None` | 正の整数のみ採用し、それ以外は `None` |
| `capture_backend` | `str` | `"auto"` | MVP では `auto` と `mss` のみ |
| `capture_region` | `dict[str, int]` | `{}` | `left` / `top` / `width` / `height` を必須キーとする |
| `capture_fps` | `float | None` | `None` | `None` の場合は source type ごとの既定値を使う。カメラ・固定領域は 60、ウィンドウは 30 |
| `capture_aspect_box_enabled` | `bool` | `false` | `true` の場合、raw frame に黒帯を追加して 16:9 に整える |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | source type 不正、必須設定不足、矩形が 0 以下、候補が曖昧 |
| `ValueError` | `FrameTransformConfig` の値が不正、または入力 frame サイズが 0 |
| `RuntimeError` | 初期化済み device がフレームを取得できない、再解決上限を超えた |
| `FrameNotReadyError` | 既存 `nyxpy.framework.core.io.ports.FrameNotReadyError`。`CaptureFrameSourcePort` が初回フレーム前または再解決中の `RuntimeError` を変換する |

### シングルトン管理

新規 singleton は追加しない。`FrameSourcePortFactory` が capture device の lifetime を所有し、`close()` で session と device を解放する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_capture_rect_to_mss_monitor` | `CaptureRect` が `mss` 形式へ変換される |
| ユニット | `test_frame_transform_keeps_raw_when_disabled` | 無効時に raw frame サイズを維持する |
| ユニット | `test_frame_transform_keeps_16x9_input` | 16:9 入力を変更しない |
| ユニット | `test_frame_transform_adds_pillarbox_to_600x720` | 600x720 入力へ左右黒帯を追加して 16:9 にする |
| ユニット | `test_frame_transform_adds_letterbox_to_wide_input` | 横長入力へ上下黒帯を追加して 16:9 にする |
| ユニット | `test_command_capture_keeps_content_aspect_after_aspect_box` | 黒帯付与後に `Command.capture()` の 1280x720 resize を通しても内容が歪まない |
| ユニット | `test_window_title_exact_match` | 完全一致で対象候補を解決する |
| ユニット | `test_window_title_contains_match_rejects_ambiguous_candidates` | 部分一致が複数候補のとき `ConfigurationError` |
| ユニット | `test_screen_region_capture_device_returns_bgr_copy` | Dummy session の BGRA 入力を BGR copy で返す |
| ユニット | `test_mss_session_created_in_capture_thread` | `mss.mss()` をキャプチャスレッド内で生成する |
| ユニット | `test_frame_source_factory_recreates_device_when_key_changes` | source key 変更時に古い device を再利用しない |
| ユニット | `test_frame_source_factory_shares_same_source_key` | 同一 source key では shared device を共有する |
| ユニット | `test_capture_region_settings_requires_left_top_width_height` | `capture_region` の必須キーを検証する |
| ユニット | `test_capture_fps_uses_source_default_when_missing` | `capture_fps=None` 時に source type 既定値を使う |
| ユニット | `test_windows_dpi_awareness_or_coordinate_normalization` | Windows の DPI 方針が物理座標へ統一される |
| ユニット | `test_window_capture_enters_resolving_after_repeated_failures` | 連続失敗後に再解決状態へ移行する |
| 結合 | `test_runtime_builder_passes_capture_source_config` | settings から factory へ `CaptureSourceConfig` が渡る |
| パフォーマンス | `test_screen_region_capture_preview_fps` | Dummy またはローカル固定領域で 30 FPS 相当を確認する |

## 6. 実装チェックリスト

- [x] `mss` の依存追加
- [x] `CaptureSourceConfig` / `CaptureSourceKey` 定義
- [x] `FrameTransformConfig` / `FrameTransformer` 実装
- [x] `WindowCaptureBackend` / `WindowCaptureSession` 定義
- [x] Windows DPI awareness / 物理座標正規化方針の実装
- [x] `WindowLocatorBackend` とタイトル照合実装
- [x] `MssCaptureSession` 実装
- [x] `MssWindowCaptureBackend` 実装
- [x] `WindowCaptureDevice` / `ScreenRegionCaptureDevice` 実装
- [x] `FrameSourcePortFactory` と runtime builder の接続変更
- [x] 設定 schema 追加
- [x] 600x720 入力に左右黒帯を追加するテスト作成・パス
- [x] ユニットテスト作成・パス
- [x] 結合テスト作成・パス
- [x] `uv run ruff check .` パス
- [x] `uv run pytest tests/unit/` パス

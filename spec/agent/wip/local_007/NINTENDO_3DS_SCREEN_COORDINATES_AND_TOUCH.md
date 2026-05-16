# Nintendo 3DS 画面座標・プレビュータッチ 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/constants/`, `src/nyxpy/gui/`  
> **目的**: Nintendo 3DS の上下結合キャプチャ画像に対する画面領域定数、座標変換補助関数、GUI プレビュー上の下画面タッチ操作を定義する。  
> **関連ドキュメント**: `..\complete\local_001\NINTENDO_3DS_SERIAL_PROTOCOL.md`, `..\complete\local_006\VIRTUAL_CONTROLLER_LAYOUT.md`  
> **破壊的変更**: あり。3DS タッチ座標の公開補助 API は画像ピクセル添字に合わせ、右下端を `x=319`, `y=239` とする。  

## 1. 概要

### 1.1 目的

Nintendo 3DS の `400x480` 上下結合画面と、`Command.capture()` が返す `1280x720` アスペクトボックス画像の対応をフレームワーク層で扱えるようにする。マクロ実装と GUI が同じ画面領域定数・座標変換規則を参照できる状態にし、GUI プレビューでは表示中の下画面実領域に対する押下・ドラッグ・解放を 3DS タッチ入力へ変換する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| 3DS 正規化座標 | 3DS の上下結合画面を `400x480` とみなした座標。左上を `(0, 0)`、右下ピクセルを `(399, 479)` とする |
| 3DS HD キャプチャ座標 | `Command.capture()` が返す `1280x720` 画像上の座標。`400x480` の 3DS 正規化画面を `600x720` に拡大し、左右 `340px` の黒帯付きで中央配置した座標である |
| 上画面 | 3DS 正規化座標の `x=0, y=0, width=400, height=240`、3DS HD キャプチャ座標の `x=340, y=0, width=600, height=360` にある 3DS 上画面 |
| 下画面実領域 | 3DS 正規化座標の `x=40, y=240, width=320, height=240`、3DS HD キャプチャ座標の `x=400, y=360, width=480, height=360` にあるタッチ可能な下画面 |
| 下画面ピラーボックス領域 | 3DS 正規化座標の `x=0..39, y=240..479` と `x=360..399, y=240..479` にある左右余白。3DS HD キャプチャ座標では `x=340..399, y=360..719` と `x=880..939, y=360..719` に対応する |
| 画面全体 | 3DS 正規化座標の `x=0, y=0, width=400, height=480`、3DS HD キャプチャ座標の `x=340, y=0, width=600, height=720` の上下結合画面 |
| タッチ座標 | 下画面実領域内の座標。左上を `(0, 0)`、右下ピクセルを `(319, 239)` とする |
| トリミング済み座標 | `Command.capture(crop_region=...)` などで切り出された画像内の座標。`crop_region` は 3DS HD キャプチャ座標で指定され、切り出し後の左上を `(0, 0)` とする |
| PreviewPane | GUI でキャプチャフレームを表示し、スナップショットを扱う widget |
| VirtualControllerModel | GUI の仮想コントローラ状態を `ControllerOutputPort` へ送るモデル |
| ControllerOutputPort | GUI またはマクロからのコントローラ操作をシリアル出力へ渡す Port |

### 1.3 背景・問題

既存の 3DS シリアルプロトコル対応では `Command.touch_down(x, y)` が存在するが、キャプチャ画像上の座標と 3DS 下画面の実タッチ座標を変換する共通 API がない。`Command.capture()` は `1280x720` のアスペクトボックス画像を返す想定であり、3DS の `400x480` 画面は `600x720` に拡大されて左右 `340px` の黒帯付きで配置される。3DS の下画面には本体由来の左右ピラーボックスもあるため、HD キャプチャ上の下画面実領域は `x=400, y=360, width=480, height=360` になる。この補正を各マクロ・GUI 実装で重複させると、クリック位置とタッチ座標がずれやすい。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 3DS 画面領域定数 | なし | 上画面、下画面実領域、画面全体を公開定数化 |
| HD キャプチャ上の 3DS 画面オフセット | 呼び出し元ごとに実装が必要 | `x=340, y=0, scale=1.5` の補正を補助関数へ集約 |
| 下画面ピラーボックス補正 | 呼び出し元ごとに実装が必要 | HD キャプチャでは `x=400, y=360`、正規化座標では `x=40, y=240` の補正を補助関数へ集約 |
| プレビュー下画面タッチ | 未対応 | 下画面実領域の押下・ドラッグ・解放を `touch_down` / `touch_up` へ送信 |
| 3DS タッチ座標の範囲 | 既存プロトコルは `0..320`, `0..240` を許容 | 画像ピクセル添字として `0..319`, `0..239` に統一 |
| 実機なしの検証 | プロトコル単体のみ | 座標変換と GUI タッチ送信をユニット / GUI テストで検証 |

### 1.5 着手条件

- 既存の 3DS シリアル通信プロトコル対応が利用可能であること。
- GUI は `ControllerOutputPort.touch_down()` / `touch_up()` を利用し、プロトコル詳細へ依存しないこと。
- 下画面のトリミング定数はタッチ可能な実領域 `x=40, y=240, width=320, height=240` を正とする。
- `Command.capture()` で 3DS 画面を扱う場合、返却画像は `1280x720` のアスペクトボックス画像とし、3DS 画面本体は `x=340, y=0, width=600, height=720` に配置される。
- `Command.capture(crop_region=...)` の `crop_region` は `1280x720` の 3DS HD キャプチャ座標で指定する。
- ピラーボックス領域へのプレビュー操作はタッチ送信しない。
- プレビュー操作は押下・ドラッグ・解放を扱う。
- 既存テスト (`uv run pytest tests/unit/`) がすべてパスすること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src\nyxpy\framework\core\constants\screen.py` | 新規 | 画面サイズ、矩形、点、3DS 正規化座標 / HD キャプチャ座標の画面領域定数、座標変換関数を追加する |
| `src\nyxpy\framework\core\constants\__init__.py` | 変更 | 3DS 画面領域定数と座標変換 API を公開する |
| `src\nyxpy\framework\core\hardware\protocol.py` | 変更 | 3DS タッチ座標の検証範囲を `0..319`, `0..239` へ統一する |
| `src\nyxpy\framework\core\io\ports.py` | 変更 | `ControllerOutputPort` にタッチ対応 capability を追加する |
| `src\nyxpy\framework\core\io\adapters.py` | 変更 | `SerialControllerOutputPort` が protocol のタッチ対応有無を報告する |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `Command.capture()` の 3DS HD キャプチャ座標仕様を docstring に明記する |
| `src\nyxpy\gui\panes\preview_pane.py` | 変更 | 表示中 pixmap の実フレーム座標算出と下画面タッチ signal を追加する |
| `src\nyxpy\gui\models\virtual_controller_model.py` | 変更 | タッチ押下・移動・解放を `ControllerOutputPort` へ送る API を追加する |
| `src\nyxpy\gui\main_window.py` | 変更 | `PreviewPane` のタッチ signal を `VirtualControllerModel` へ接続し、非対応時はステータス表示する |
| `tests\unit\framework\constants\test_3ds_screen.py` | 新規 | 3DS 画面領域定数と座標変換を検証する |
| `tests\unit\framework\io\test_adapters.py` | 変更 | controller port のタッチ対応 capability を検証する |
| `tests\unit\protocol\test_3ds_protocol.py` | 変更 | 3DS タッチ座標の境界値を `319,239` に更新する |
| `tests\support\fakes.py` | 変更 | テスト用 controller port にタッチ対応 capability を追加する |
| `tests\gui\test_preview_pane.py` | 変更 | プレビュー座標からフレーム座標への変換を検証する |
| `tests\gui\test_virtual_controller_model.py` | 変更 | タッチ対応判定とタッチ操作が controller port に送られることを検証する |
| `tests\gui\test_main_window.py` | 変更 | プレビュー下画面操作、非対応 protocol 時の no-op とステータス表示を検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

画面領域定数と座標変換関数は framework の constants 層に置く。これは 3DS の画面幾何が GUI 固有ではなく、マクロの画像認識・トリミング・タッチ操作でも共有する値であるためである。GUI は framework の補助 API を利用してプレビュー上のポインタ座標をタッチ座標へ変換するが、framework は GUI や Qt に依存しない。

3DS 正規化座標は機種固有の基準座標であり、3DS HD キャプチャ座標は `Command.capture()` の戻り値に対応する操作座標である。GUI プレビュー座標はウィンドウサイズプリセットごとの表示サイズに依存するため、3DS HD キャプチャ座標と同一視しない。プレビュー上でタッチ領域を判定するときは、HD キャプチャ座標上の下画面実領域を preview size へ射影し、その射影矩形内の相対位置を `320x240` のタッチ座標へ量子化する。マクロが `Command.capture(crop_region=THREEDS_HD_BOTTOM_SCREEN.tuple)` のように下画面を切り出した場合、切り出し後の座標は `cropped_hd_point_to_3ds_touch()` でタッチ座標へ変換する。

### 公開 API 方針

3DS 正規化座標を主 API としつつ、`Command.capture()` で直接使う 3DS HD キャプチャ座標の定数と変換関数を同時に提供する。GUI 向けには、プリセット別 preview size の widget 座標からタッチ座標を直接求める補助関数を用意する。無効座標を例外にしたい用途と、GUI のようにピラーボックス操作を無視したい用途を分けるため、strict 系の変換関数は `ValueError` を送出し、`try_*` 関数は `None` を返す。

3DS 以外の protocol が選択されている場合、プレビュータッチは `ControllerOutputPort.supports_touch` で無効扱いにする。GUI は `touch_down()` を呼ばず、クリックごとにステータスバーへ「現在のプロトコルは 3DS タッチ入力に対応していません」を表示する。これはエラーではなく、protocol capability に基づく非操作である。`ControllerOutputPort.touch_down()` を直接呼んだ場合の `NotImplementedError` は維持する。

### 後方互換性

3DS タッチ座標の右下端を `320,240` から `319,239` へ変更する。既存の 3DS プロトコル対応はアルファ版の拡張であり、画像ピクセル添字と異なる半開区間外の座標を許容すると GUI マッピングと単体テストが不一致になるため、破壊的変更として統一する。互換 shim や旧範囲の alias は追加しない。

### レイヤー構成

```text
macros/*                         -> nyxpy.framework.core.constants.screen
Command.capture docs             -> nyxpy.framework.core.constants.screen の座標定義
nyxpy.gui.panes.preview_pane     -> nyxpy.framework.core.constants.screen
nyxpy.gui.models                 -> ControllerOutputPort
MainWindow                       -> VirtualControllerModel.supports_touch_input()
nyxpy.framework.core.constants   -> GUI に依存しない
nyxpy.framework.core.hardware    -> constants の TouchState 範囲に従う
```

`PreviewPane` は座標変換と signal 発火だけを担当する。実際の送信は `VirtualControllerModel` が `ControllerOutputPort` 経由で行う。これにより GUI widget とシリアルプロトコルの直接依存を避ける。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 座標変換関数 | 1 呼び出しあたり 0.1 ms 未満 |
| プレビュー mouse move 処理 | 1 event あたり 1 ms 未満 |
| プレビュー描画 | フレーム縦横比を維持し、既存 FPS 設定を維持 |
| タッチ move 送信 | 有効下画面領域内で座標が変化した場合のみ送信 |

### 並行性・スレッド安全性

座標変換関数は不変 dataclass と純粋関数で構成し、スレッド共有状態を持たない。GUI の mouse event は Qt の UI thread 上で処理する。`VirtualControllerModel` は既存のボタン操作と同じく GUI lifetime の `ControllerOutputPort` を利用し、送信エラーは logger へ記録して再送出する。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class ScreenSize:
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ScreenPoint:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class ScreenRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int: ...

    @property
    def bottom(self) -> int: ...

    def contains(self, point: ScreenPoint) -> bool: ...


@dataclass(frozen=True, slots=True)
class TouchPoint:
    x: int
    y: int


class ScaleRounding(StrEnum):
    FLOOR = "floor"
    ROUND = "round"


THREEDS_CAPTURE_SIZE = ScreenSize(400, 480)
THREEDS_TOP_SCREEN = ScreenRect(0, 0, 400, 240)
THREEDS_BOTTOM_SCREEN = ScreenRect(40, 240, 320, 240)
THREEDS_BOTTOM_PILLARBOXED_AREA = ScreenRect(0, 240, 400, 240)
THREEDS_FULL_SCREEN = ScreenRect(0, 0, 400, 480)

THREEDS_HD_CAPTURE_SIZE = ScreenSize(1280, 720)
THREEDS_HD_CONTENT = ScreenRect(340, 0, 600, 720)
THREEDS_HD_TOP_SCREEN = ScreenRect(340, 0, 600, 360)
THREEDS_HD_BOTTOM_SCREEN = ScreenRect(400, 360, 480, 360)
THREEDS_HD_BOTTOM_PILLARBOXED_AREA = ScreenRect(340, 360, 600, 360)
THREEDS_HD_FULL_SCREEN = THREEDS_HD_CONTENT


def validate_3ds_touch_point(point: TouchPoint) -> TouchPoint: ...


def normalized_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint: ...


def try_normalized_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint | None: ...


def touch_point_to_3ds_normalized(point: TouchPoint) -> ScreenPoint: ...


def normalized_point_to_hd_capture(point: ScreenPoint) -> ScreenPoint: ...


def hd_capture_point_to_normalized(point: ScreenPoint) -> ScreenPoint: ...


def hd_capture_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint: ...


def try_hd_capture_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint | None: ...


def touch_point_to_3ds_hd_capture(point: TouchPoint) -> ScreenPoint: ...


def cropped_normalized_point_to_normalized(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> ScreenPoint: ...


def normalized_point_to_cropped(point: ScreenPoint, crop_region: ScreenRect) -> ScreenPoint: ...


def cropped_normalized_point_to_3ds_touch(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> TouchPoint: ...


def try_cropped_normalized_point_to_3ds_touch(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> TouchPoint | None: ...


def cropped_hd_point_to_3ds_touch(point: ScreenPoint, crop_region: ScreenRect) -> TouchPoint: ...


def try_cropped_hd_point_to_3ds_touch(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> TouchPoint | None: ...


def scale_point(
    point: ScreenPoint,
    *,
    source_size: ScreenSize,
    target_size: ScreenSize = THREEDS_CAPTURE_SIZE,
    rounding: ScaleRounding = ScaleRounding.FLOOR,
) -> ScreenPoint: ...


def scaled_source_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    source_size: ScreenSize,
) -> TouchPoint: ...


def try_scaled_source_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    source_size: ScreenSize,
) -> TouchPoint | None: ...


def aspect_fit_rect(source_size: ScreenSize, target_size: ScreenSize) -> ScreenRect: ...


def project_hd_rect_to_preview(rect: ScreenRect, *, preview_size: ScreenSize) -> ScreenRect: ...


def preview_touch_rect(preview_size: ScreenSize) -> ScreenRect: ...


def preview_point_to_hd_capture(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
    hd_capture_size: ScreenSize = THREEDS_HD_CAPTURE_SIZE,
) -> ScreenPoint: ...


def try_preview_point_to_hd_capture(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
    hd_capture_size: ScreenSize = THREEDS_HD_CAPTURE_SIZE,
) -> ScreenPoint | None: ...


def preview_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
) -> TouchPoint: ...


def try_preview_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
) -> TouchPoint | None: ...
```

```python
class ControllerOutputPort(ABC):
    @property
    def supports_touch(self) -> bool:
        return False

    def touch_down(self, x: int, y: int) -> None:
        raise NotImplementedError("Current controller output does not support touch input.")

    def touch_up(self) -> None:
        raise NotImplementedError("Current controller output does not support touch input.")


class SerialControllerOutputPort(ControllerOutputPort):
    @property
    def supports_touch(self) -> bool: ...
```

```python
class PreviewPane(QWidget):
    touch_down_requested = Signal(int, int)
    touch_move_requested = Signal(int, int)
    touch_up_requested = Signal()

    def preview_widget_point_to_hd_capture_point(self, point: QPoint) -> ScreenPoint | None: ...
```

```python
class VirtualControllerModel(QObject):
    def supports_touch_input(self) -> bool: ...
    def touch_down(self, x: int, y: int) -> None: ...
    def touch_move(self, x: int, y: int) -> None: ...
    def touch_up(self) -> None: ...
```

```python
class MainWindow(QMainWindow):
    def _handle_preview_touch_down(self, x: int, y: int) -> None: ...
    def _handle_preview_touch_move(self, x: int, y: int) -> None: ...
    def _handle_preview_touch_up(self) -> None: ...
```

### 座標変換規則

| 変換 | 入力 | 出力 | 規則 |
|------|------|------|------|
| 正規化座標 → タッチ座標 | `ScreenPoint(x, y)` | `TouchPoint` | `THREEDS_BOTTOM_SCREEN` 内なら `x-40`, `y-240` |
| タッチ座標 → 正規化座標 | `TouchPoint(x, y)` | `ScreenPoint` | `x+40`, `y+240` |
| 正規化座標 → HD キャプチャ座標 | `ScreenPoint(x, y)` | `ScreenPoint` | `x=340 + floor(x * 1.5)`, `y=floor(y * 1.5)` |
| HD キャプチャ座標 → 正規化座標 | `ScreenPoint(x, y)` | `ScreenPoint` | `x=floor((x - 340) / 1.5)`, `y=floor(y / 1.5)` |
| HD キャプチャ座標 → タッチ座標 | `ScreenPoint(x, y)` | `TouchPoint` | `THREEDS_HD_BOTTOM_SCREEN` 内なら `x=floor((x - 400) / 1.5)`, `y=floor((y - 360) / 1.5)` |
| タッチ座標 → HD キャプチャ座標 | `TouchPoint(x, y)` | `ScreenPoint` | `x=400 + floor(x * 1.5)`, `y=360 + floor(y * 1.5)` |
| トリミング済み HD 座標 → HD キャプチャ座標 | `point`, `crop_region` | `ScreenPoint` | `point.x + crop_region.x`, `point.y + crop_region.y` |
| HD キャプチャ座標 → トリミング済み HD 座標 | `point`, `crop_region` | `ScreenPoint` | `point.x - crop_region.x`, `point.y - crop_region.y` |
| 任意サイズ座標 → 正規化座標 | `point`, `source_size` | `ScreenPoint` | `x * 400 / source_width`, `y * 480 / source_height` |
| 任意サイズ画面 → アスペクト内接矩形 | `source_size`, `target_size` | `ScreenRect` | `target_size` 内で縦横比を維持して最大化し、中央配置する |
| プレビュー座標 → HD キャプチャ座標 | `point`, `preview_size` | `ScreenPoint` | `aspect_fit_rect(1280x720, preview_size)` 内なら、表示倍率を逆算して `1280x720` へ戻す |
| HD 領域 → プレビュー領域 | `rect`, `preview_size` | `ScreenRect` | `THREEDS_HD_CAPTURE_SIZE` と preview size の倍率で矩形を射影する |
| プレビュー座標 → タッチ座標 | `point`, `preview_size` | `TouchPoint` | `preview_touch_rect(preview_size)` 内なら、矩形内の相対位置を `320x240` へ量子化する |

`ScreenRect.right` と `ScreenRect.bottom` は Python slice と同じ半開区間の終端を返す。たとえば `THREEDS_HD_BOTTOM_SCREEN.right == 880`、有効な最大 X は `879` である。`TouchPoint` の最大値は `x=319`, `y=239` であり、`x=320`, `y=240` は無効である。

`Command.capture()` の 3DS HD キャプチャ座標では、`400x480` の 3DS 正規化画面を `600x720` に拡大して `1280x720` 内へ中央配置する。具体値は以下で固定する。

| 領域 | 3DS 正規化座標 | 3DS HD キャプチャ座標 |
|------|----------------|-----------------------|
| 画面全体 | `(0, 0, 400, 480)` | `(340, 0, 600, 720)` |
| 上画面 | `(0, 0, 400, 240)` | `(340, 0, 600, 360)` |
| 下画面ピラーボックス込み | `(0, 240, 400, 240)` | `(340, 360, 600, 360)` |
| 下画面実領域 | `(40, 240, 320, 240)` | `(400, 360, 480, 360)` |

マクロで下画面実領域のみを取得する場合は `crop_region=(400, 360, 480, 360)` を使う。このトリミング済み画像上の `(0, 0)` はタッチ座標 `(0, 0)`、`(479, 359)` はタッチ座標 `(319, 239)` に対応する。上画面の切り出しは `crop_region=(340, 0, 600, 360)`、3DS 画面全体の切り出しは `crop_region=(340, 0, 600, 720)` を使う。

### GUI タッチ処理

`PreviewPane` はプリセット別の preview size と表示 pixmap の実表示矩形を使い、mouse event の widget 座標をプレビュー内の下画面実領域へ照合する。プレビュー label の余白、device pixel ratio、フレーム縦横比による letterbox / pillarbox はこの段階で除外する。フレーム座標へ変換できない場合、または `preview_touch_rect(preview_size)` 外の場合はタッチを開始しない。

押下後のドラッグでは、有効な下画面実領域内で座標が変化した場合だけ `touch_move_requested(x, y)` を発火する。ドラッグ中にピラーボックスまたはプレビュー外へ移動した場合は座標更新を送らない。押下が開始済みであれば、解放位置にかかわらず mouse release で `touch_up_requested` を 1 回発火する。

`MainWindow` は preview touch signal を直接 `VirtualControllerModel.touch_*` へ接続しない。`_handle_preview_touch_down()` で `virtual_controller.model.supports_touch_input()` を確認し、非対応なら controller へ送信せず、クリックごとにステータスバーへ「現在のプロトコルは 3DS タッチ入力に対応していません」を表示する。非対応状態で drag / release signal が届いた場合も送信しない。3DS protocol 選択中だけ `touch_down`、座標変化を伴う `touch_move`、`touch_up` を controller port へ渡す。

プレビュー描画は `Command.capture()` と同じ `1280x720` の HD キャプチャ座標を基準にする。3DS 画面本体はプレビュー内でも `5:6` の `600x720` 相当で表示され、左右の黒帯込みで `16:9` のプレビュー枠へ収まる。

ウィンドウサイズプリセット別のプレビュー領域とタッチ可能領域は以下である。いずれも preview size が `16:9` のため、表示 pixmap は preview 領域全体に一致する。将来 preview size が `16:9` 以外になった場合は `aspect_fit_rect(THREEDS_HD_CAPTURE_SIZE, preview_size)` の戻り値を差し引いてから同じ逆変換を行う。

| プリセット | preview size | 表示倍率 | 3DS 画面全体 | 下画面実領域 | 変換例 |
|------------|--------------|----------|--------------|--------------|--------|
| `hd` | `640x360` | `0.5` | `(170, 0, 300, 360)` | `(200, 180, 240, 180)` | `(200,180) -> touch(0,0)`, `(439,359) -> touch(319,239)` |
| `full_hd` | `1280x720` | `1.0` | `(340, 0, 600, 720)` | `(400, 360, 480, 360)` | `(400,360) -> touch(0,0)`, `(879,719) -> touch(319,239)` |
| `wqhd` | `1600x900` | `1.25` | `(425, 0, 750, 900)` | `(500, 450, 600, 450)` | `(500,450) -> touch(0,0)`, `(1099,899) -> touch(319,239)` |
| `four_k` | `2560x1440` | `2.0` | `(680, 0, 1200, 1440)` | `(800, 720, 960, 720)` | `(800,720) -> touch(0,0)`, `(1759,1439) -> touch(319,239)` |

クリック座標からタッチ座標への変換は、HD キャプチャ座標へ戻した整数値から再計算しない。低解像度プリセットでは `hd` の下画面実領域 `240x180` を `320x240` タッチ座標へ拡大するため、整数 HD 座標を経由すると右端・下端が丸めで到達不能になりやすい。`preview_point_to_3ds_touch()` は `preview_touch_rect(preview_size)` 内の相対位置を次の式で直接量子化し、最後に有効範囲へ clamp する。

```text
touch_x = clamp(floor((point.x - rect.x + 0.5) * 320 / rect.width), 0, 319)
touch_y = clamp(floor((point.y - rect.y + 0.5) * 240 / rect.height), 0, 239)
```

これにより、`hd` プリセットの preview 座標 `(200,180)` は `touch(0,0)`、`(439,359)` は `touch(319,239)` へ対応する。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| なし | - | - | 3DS 画面幾何は固定値として扱い、ユーザー設定を追加しない |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ValueError` | `ScreenSize` の幅または高さが 1 未満 |
| `ValueError` | `ScreenRect` の幅または高さが 1 未満 |
| `ValueError` | `TouchPoint` が `x=0..319`, `y=0..239` の範囲外 |
| `ValueError` | strict 系変換関数で入力座標が変換対象領域外 |
| `NotImplementedError` | GUI gate を経由せず、タッチ非対応の `ControllerOutputPort.touch_down()` / `touch_up()` を直接呼んだ場合 |

GUI のピラーボックス操作は例外にせず、`try_*` 関数で `None` として扱う。これは無効クリックを正常な非操作として区別するための明示的な API 契約であり、送信失敗を隠すものではない。3DS 以外の protocol 選択中のプレビュータッチも capability による非操作として扱い、送信を試みない。3DS protocol で送信時に発生した例外は既存の仮想コントローラ操作と同じく logger へ記録して再送出する。

### シングルトン管理

該当なし。新規グローバル singleton は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_3ds_screen_constants_define_normalized_rects` | 正規化座標の上画面、下画面実領域、ピラーボックス込み下画面、画面全体の矩形値を検証する |
| ユニット | `test_3ds_screen_constants_define_hd_capture_rects` | HD キャプチャ座標の `x=340,y=0,w=600,h=720` と下画面実領域 `x=400,y=360,w=480,h=360` を検証する |
| ユニット | `test_normalized_point_to_3ds_touch_offsets_lower_screen` | 正規化座標 `(40,240)` が `(0,0)`、`(359,479)` が `(319,239)` へ変換される |
| ユニット | `test_hd_capture_point_to_3ds_touch_offsets_aspect_box` | HD キャプチャ座標 `(400,360)` が `(0,0)`、`(879,719)` が `(319,239)` へ変換される |
| ユニット | `test_hd_capture_point_to_3ds_touch_rejects_outer_and_inner_pillarbox` | 左右黒帯と下画面ピラーボックスが strict 系では `ValueError`、try 系では `None` になる |
| ユニット | `test_touch_point_to_3ds_hd_capture_offsets_to_lower_screen` | タッチ座標から HD キャプチャ座標へ戻せる |
| ユニット | `test_cropped_hd_point_to_3ds_touch_uses_crop_origin` | `crop_region=(400,360,480,360)` のトリミング済み座標 `(0,0)` がタッチ `(0,0)` へ変換される |
| ユニット | `test_scaled_source_point_to_3ds_touch_normalizes_source_size` | 任意サイズのフレーム座標を `400x480` 正規化後にタッチ座標へ変換する |
| ユニット | `test_aspect_fit_rect_places_3ds_screen_in_hd_box` | `400x480` を `1280x720` へ内接させると `(340,0,600,720)` になる |
| ユニット | `test_preview_touch_rect_scales_by_window_size_preset` | `hd` / `full_hd` / `wqhd` / `four_k` の preview size で下画面実領域の射影矩形が期待値になる |
| ユニット | `test_preview_point_to_3ds_touch_preserves_edges` | 各プリセットで下画面実領域の左上が `(0,0)`、右下が `(319,239)` になる |
| ユニット | `test_serial_controller_reports_touch_capability_by_protocol` | 3DS protocol では `supports_touch=True`、CH552 / PokeCon では `False` になる |
| ユニット | `test_3ds_protocol_touch_rejects_pixel_index_out_of_range` | `x=320` または `y=240` のタッチ送信が `ValueError` になる |
| GUI | `test_preview_maps_widget_point_to_hd_capture_point` | プレビュー label 内の余白を除外して 3DS HD キャプチャ座標を返す |
| GUI | `test_preview_uses_current_preset_size_for_touch_mapping` | プリセット切替後の preview size に合わせてタッチ領域が更新される |
| GUI | `test_preview_touch_ignores_pillarbox_press` | 下画面左右ピラーボックスへの押下でタッチ signal が出ない |
| GUI | `test_preview_touch_emits_press_move_release_inside_bottom_screen` | 下画面実領域の押下・ドラッグ・解放が touch signal になる |
| GUI | `test_virtual_controller_model_reports_touch_support` | controller port の capability に応じて `supports_touch_input()` が変わる |
| GUI | `test_virtual_controller_model_sends_touch_events` | touch 対応 controller では model の `touch_down` / `touch_move` / `touch_up` が `ControllerOutputPort` に送られる |
| GUI | `test_main_window_wires_preview_touch_to_virtual_controller_model` | MainWindow が preview touch signal と model を接続する |
| GUI | `test_main_window_ignores_preview_touch_when_controller_does_not_support_touch` | CH552 / PokeCon 相当の controller では preview touch を送信しない |
| GUI | `test_main_window_shows_touch_unsupported_status_on_each_preview_press` | touch 非対応 controller で preview 下画面をクリックするたびにステータスバーへ非対応メッセージを表示する |
| 結合 | `test_3ds_preview_touch_sends_serial_frames` | 3DS protocol の controller port へプレビュータッチが接続されたとき、touch frame が送信される |
| 結合 | `test_non_3ds_preview_touch_does_not_send_serial_frames` | CH552 / PokeCon protocol の controller port では preview touch が送信されない |
| ハードウェア | `test_3ds_preview_touch_realdevice` | `@pytest.mark.realdevice` で代表点のプレビュータッチが実機へ送信される |

## 6. 実装チェックリスト

- [x] 仕様初期決定の反映
- [x] `Command.capture()` の 1280x720 アスペクトボックス座標前提を反映
- [ ] 公開 API のシグネチャ確定
- [ ] 3DS 画面領域定数の追加
- [ ] 3DS HD キャプチャ座標定数の追加
- [ ] プリセット別プレビュー座標変換の追加
- [ ] 座標変換補助関数の追加
- [ ] 3DS タッチ座標範囲の `0..319`, `0..239` 統一
- [ ] PreviewPane のフレーム縦横比維持と座標変換
- [ ] PreviewPane のタッチ signal 追加
- [ ] ControllerOutputPort のタッチ対応 capability 追加
- [ ] VirtualControllerModel のタッチ送信 API 追加
- [ ] MainWindow の signal 接続と非対応時 no-op / ステータス表示
- [ ] ユニットテスト作成・パス
- [ ] GUI テスト作成・パス
- [ ] 統合テスト作成・パス
- [ ] 型ヒントの整合性チェック（ruff）
- [ ] 既存テストが破壊されないことの確認
- [ ] ドキュメントコメント（公開 API のみ）

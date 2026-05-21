# 3DS 向け補足

NyX の 3DS 向け補助 API は、3DS キャプチャの座標変換と touch 入力を扱います。通常の Switch ボタン入力には `Button`, `Hat`, `LStick`, `RStick` を使い、3DS 固有操作には `ThreeDSButton`, `TouchState`, `Command.touch*()` を使います。

## 座標系

| 定数 | 値 | 用途 |
|------|----|------|
| `THREEDS_CAPTURE_SIZE` | 400x480 | 3DS 上画面と下画面を縦に並べた正規化座標です。 |
| `THREEDS_TOP_SCREEN` | `(0, 0, 400, 240)` | 正規化座標の上画面です。 |
| `THREEDS_BOTTOM_SCREEN` | `(40, 240, 320, 240)` | 正規化座標の下画面です。 |
| `THREEDS_HD_CAPTURE_SIZE` | 1280x720 | NyX の HD キャプチャ基準です。 |
| `THREEDS_HD_CONTENT` | `(340, 0, 600, 720)` | HD キャプチャ内の 3DS 画面本体です。 |
| `THREEDS_HD_BOTTOM_SCREEN` | `(400, 360, 480, 360)` | HD キャプチャ内の下画面です。 |
| `THREEDS_TOUCH_SIZE` | 320x240 | 3DS touch 座標です。 |

`Command.capture()` は HD キャプチャ基準の画像を返します。下画面だけを扱う場合は次のように crop します。

```python
frame = cmd.capture(crop_region=THREEDS_HD_BOTTOM_SCREEN.tuple)
if frame is None:
    return
```

## touch 入力

```python
cmd.touch(120, 80, dur=0.1, wait=0.05)
cmd.touch_down(120, 80)
cmd.touch_up()
```

`x` は `0..319`、`y` は `0..239` です。対応していないシリアルプロトコルでは `NotImplementedError` が送出されます。

## 座標変換

| 関数 | 用途 |
|------|------|
| `validate_3ds_touch_point(point)` | touch 座標の範囲を検証します。範囲外は `ValueError` です。 |
| `normalized_point_to_3ds_touch(point)` | 400x480 正規化座標から touch 座標へ変換します。 |
| `hd_capture_point_to_3ds_touch(point)` | 1280x720 HD キャプチャ座標から touch 座標へ変換します。 |
| `cropped_hd_point_to_3ds_touch(point, crop_region)` | crop 済み HD 座標から touch 座標へ変換します。 |
| `preview_point_to_3ds_touch(point, preview_size=...)` | GUI プレビュー座標から touch 座標へ変換します。 |

`try_*` で始まる関数は、変換できない座標に対して `ValueError` ではなく `None` を返します。

```python
touch = hd_capture_point_to_3ds_touch(ScreenPoint(400, 360))
assert touch == TouchPoint(0, 0)
```

## 3DS 固有ボタン

```python
cmd.press(ThreeDSButton.POWER)
```

3DS 固有ボタンや touch 入力は、対応プロトコルでのみ使えます。


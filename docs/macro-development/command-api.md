# Command API

`Command` は、マクロが NyX の実行環境へ操作を依頼するための公開 API です。コントローラー操作、待機、キャプチャ、画像入出力、通知、ログは `Command` 経由で行います。

## 入力と待機

| API | 説明 |
|-----|------|
| `cmd.press(*keys, dur=0.1, wait=0.1)` | 指定したキーを押し、`dur` 秒後に離し、必要に応じて `wait` 秒待ちます。 |
| `cmd.hold(*keys)` | 現在の入力状態を指定キーの押下状態へ変更します。 |
| `cmd.release(*keys)` | 指定キーを離します。引数なしの場合は全解除として扱います。 |
| `cmd.wait(sec)` | 中断要求を確認しながら待機します。長い待機では `time.sleep()` ではなくこちらを使います。 |
| `cmd.stop()` | マクロの協調キャンセルを要求します。 |

```python
cmd.press(Button.A, dur=0.06, wait=0.08)
cmd.hold(Button.L, Button.R)
cmd.wait(1.0)
cmd.release()
```

## キャプチャ

```python
frame = cmd.capture()
cmd.save_img("snapshot.png", frame)
```

`cmd.capture(crop_region=None, grayscale=False)` は、最新フレームを 1280x720 へリサイズして返します。`crop_region` は `(x, y, width, height)` です。範囲外の crop は `ValueError` になります。フレームがまだ取得できない場合は `FrameNotReadyError` を送出します。

フレーム未準備を通常分岐として扱う場合は `cmd.try_capture()` を使います。

```python
frame = cmd.try_capture()
if frame is None:
    cmd.log("capture skipped: frame is not ready", level="WARNING")
    return
cmd.save_img("snapshot.png", frame)
```

3DS の HD キャプチャでは、画面本体を `THREEDS_HD_CONTENT = (340, 0, 600, 720)`、下画面を `THREEDS_HD_BOTTOM_SCREEN = (400, 360, 480, 360)` として扱います。

## 画像入出力と成果物

| API | 説明 |
|-----|------|
| `cmd.load_img(name, grayscale=False)` | `resources\<macro_id>\assets` を優先して画像を読み込みます。 |
| `cmd.save_img(name, image)` | 実行ごとの出力先へ画像を保存します。 |
| `cmd.artifacts.open_output(name, ...)` | 実行ごとの出力先に任意のバイナリファイルを書きます。 |

`name` はリソース起点または出力先起点の相対パスです。設定ファイルに保存するパス表記では `/` を使います。

## ログと通知

```python
cmd.log("search started", level="INFO")
cmd.notify("macro completed")
cmd.notify("macro completed with image", frame)
```

`cmd.log()` はユーザ向けログを出します。`level` には `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` を指定できます。`cmd.notify()` は設定済みの外部通知へ送信します。`img=None` は画像添付なしの正常な通知です。

## キーボード入力

| API | 説明 |
|-----|------|
| `cmd.keyboard(text)` | 英数字テキストを送信します。 |
| `cmd.type(key)` | `KeyCode` または `SpecialKeyCode` を 1 キー送信します。 |

## 3DS 向け追加操作

| API | 説明 |
|-----|------|
| `cmd.touch(x, y, dur=0.1, wait=0.1)` | 3DS touch 対応プロトコルで touch down / wait / touch up を行います。 |
| `cmd.touch_down(x, y)` | 指定座標を押し続けます。 |
| `cmd.touch_up()` | touch 入力を離します。 |
| `cmd.disable_sleep(enabled=True)` | 対応プロトコルでスリープ制御を切り替えます。 |

対応していないプロトコルでは `NotImplementedError` が送出されます。

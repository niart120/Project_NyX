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

## IMU 入力

swbt backend では `cmd.imu(...)` で IMU frame を送れます。1 frame を渡した場合は swbt の規則に合わせて 3 frame 分に複製します。3 frame を渡した場合は、その順番で送信します。0、2、4 個以上の frame は不正です。

```python
from nyxpy.framework.core.constants import IMUFrame

cmd.imu(IMUFrame.neutral())
cmd.imu(IMUFrame.gyro(x=100, y=0, z=0))
```

IMU は現在の入力状態の一部として扱われます。`cmd.imu(...)` は button や stick を解放しません。IMU を扱わない backend では `NotImplementedError` が送出されます。

## キャプチャ

```python
frame = cmd.capture()
cmd.save_artifact_img("snapshot.png", frame)
```

`cmd.capture(crop_region=None, grayscale=False)` は、最新フレームを 1280x720 へリサイズして返します。`crop_region` は `(x, y, width, height)` です。範囲外の crop は `ValueError` になります。フレームがまだ取得できない場合は `FrameNotReadyError` を送出します。

3DS の HD キャプチャでは、画面本体を `THREEDS_HD_CONTENT = (340, 0, 600, 720)`、下画面を `THREEDS_HD_BOTTOM_SCREEN = (400, 360, 480, 360)` として扱います。

## 画像入出力と成果物

| API | 説明 |
|-----|------|
| `cmd.load_img(name, grayscale=False)` | `resources/<macro_id>/assets` を優先して画像 asset を読み込みます。 |
| `cmd.load_blob(name)` | `resources/<macro_id>/assets` から任意 bytes asset を読み込みます。 |
| `cmd.save_artifact_img(name, image)` | `resources/<macro_id>/artifacts/<artifact_dir_name>` へ画像 artifact を保存します。 |
| `cmd.save_artifact_blob(name, data)` | `resources/<macro_id>/artifacts/<artifact_dir_name>` へ任意 bytes artifact を保存します。 |
| `cmd.load_artifact_img(ref_or_name)` | 保存済み画像 artifact を読み戻します。 |
| `cmd.load_artifact_blob(ref_or_name)` | 保存済み bytes artifact を読み戻します。 |

`name` は assets root または artifact scope からの相対パスです。固定して再利用したい生成物は `scope=ArtifactScope.STABLE` を指定して `resources/<macro_id>/artifacts/stable` に保存します。設定ファイルに保存するパス表記では `/` を使います。

画像入出力の失敗は `ResourceError` 系で送出されます。安全でない path は `ResourcePathError`、資材や artifact が見つからない場合は `ResourceNotFoundError`、画像や bytes として読み込めない場合は `ResourceReadError`、artifact を書き込めない場合は `ResourceWriteError` です。

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

## backend ごとの非対応入力

`swbt` backend は Switch controller 入力を扱うため、3DS touch、keyboard、sleep control は対応しません。Joy-Con L は右 stick、Joy-Con R は左 stick を持たないため、その入力は `NYX_SWBT_INPUT_UNSUPPORTED` として失敗します。非対応入力は silent no-op にはしません。

# マクロフレームワーク設計詳細

このドキュメントは、ユーザー作成マクロの設計とフレームワーク側のマクロ実行機能について説明します。旧 `docs` から移設したアーカイブであり、現行コードでは `src/nyxpy/framework/core/macro/` が正本です。

## ユーザー作成マクロの仕様

### マクロライフサイクル
各マクロは以下の3つのフェーズに沿って実行されます：
1. **initialize(cmd, args):**  
   - マクロ実行前の初期化処理  
   - `static/{macro_name}/settings.toml` と CLI/GUI から渡された実行引数をマージした `args` を受け取る
   - 例：リソース確保、初期ログ出力

2. **run(cmd):**  
   - マクロのメイン処理  
   - フレームワーク側から渡される `Command` インターフェースを利用し、操作を実行

3. **finalize(cmd):**  
   - マクロ実行後のクリーンアップ処理  
   - 例：リソース解放、終了ログ出力

ユーザーは `MacroBase` を継承してこれらのメソッドを実装します。

## Command インターフェース

### 提供する操作
- **press(*keys, dur, wait):**  
  - 指定されたキーの押下操作を発行  
  - フレームワーク側で `dur` 秒待機後に解放操作を実行し、さらに `wait` 秒待機する
- **hold(*keys):**  
  - キーの長押し操作を発行（1回の操作として送信）
- **release(*keys):**  
  - キーの解放操作を発行
- **keyboard(text):**  
  - キーボードの文字列入力操作を発行
- **type(key):**  
  - キーボードのキータイプ操作を発行
- **notify(text, img):**  
  - Discord / Bluesky などの外部通知を発行
- **save_img(filename, image) / load_img(filename, grayscale):**  
  - `StaticResourceIO` 経由で画像を保存・読込
- **touch(x, y, dur, wait) / touch_down(x, y) / touch_up():**  
  - 3DS 対応プロトコルでタッチ入力を発行。未対応プロトコルでは `NotImplementedError`
- **disable_sleep(enabled):**  
  - 3DS 対応プロトコルでスリープ抑止を切り替える。未対応プロトコルでは `NotImplementedError`
- **stop():**  
  - `CancellationToken` に中断要求を立て、`MacroStopException` を送出
- **wait(wait):**  
  - 指定秒数の待機を実行
- **capture():**  
  - 画面キャプチャ操作（ハードウェア連携層へ委譲）

### 定数クラスの利用
キー情報は以下の定数クラスで明示します：
- **Button, Hat:** IntEnum で各ボタン・方向を定義
- **LStick, RStick:** 角度と倍率から X, Y 座標を算出するクラス（プリセットも定義）

## MacroExecutor

- **役割:**  
  ユーザー作成マクロを動的にロードし、ライフサイクルに従って順次実行します。  
  例外発生時でも必ず `finalize()` が呼ばれるよう設計されています。
- **主なメソッド:**
  - `reload_macros()`: `macros` 直下の単一ファイル型マクロとパッケージ型マクロを読み込み直す
  - `set_active_macro(macro_name)`: 実行対象マクロを選択する
  - `execute(cmd, exec_args)`: `initialize -> run -> finalize` を実行する

## 拡張性
- マクロ中断は `CancellationToken` と `@check_interrupt` により実装済みです。中断後の再開、複数マクロの同時実行、詳細な例外階層化は再設計時の検討対象です。

この設計により、マクロ開発者は高レベルな操作に専念でき、フレームワーク側で操作のタイミングや待機制御が一元管理されるため、ユーザー側の実装がシンプルになります。

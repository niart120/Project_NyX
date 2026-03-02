# FRLG 初期Seed特定マクロ 仕様書

> **元ファイル**: `初期Seed特定.csx`（C# Script / NX Macro Controller 向け）  
> **対象タイトル**: ポケットモンスター ファイアレッド・リーフグリーン (FRLG)  
> **目的**: ゲーム起動後のフレーム指定で初期Seed（16bit）を自動収集し、乱数テーブルを構築する  
> **移植スコープ**: Switch (720p) のみ。GC 固有処理・1080p 固有 ROI はスコープ外

---

## 1. 概要

ゲームのソフトリセット → 「つづきからはじめる」で再開 → 固定シンボル（ルギア Lv.70）に話しかけてエンカウント → 捕獲 → 捕獲した個体の
**性格**と**実数値**を画像認識で取得し、それらの組み合わせからフレーム範囲内の**初期Seed（16bit）**を逆算するマクロである。

指定されたフレーム範囲を1Fずつ走査し、各フレームについて初期Seedを **`trials` 回** 繰り返し測定して CSV へ書き出す。
同一フレームでも毎回同じ Seed が出るとは限らないため、複数回測定の結果をそのまま記録する。
収集した初期Seedテーブルは、後続のID調整マクロ等で使用される。

> **前提**: セーブデータは「へそのいわ」でルギアの目の前に立っている状態で保存済み。
> 手持ちにはマスターボールを入れたポケモンがおり、即座に捕獲できるようにしておく。

> **キー入力調査モード**: 元スクリプトにはゲーム起動時のキー入力パターンが初期Seedに与える影響を調べる
> 「キー入力調査モード」が存在したが、本マクロとは独立した仕様として別途整備する（Phase 2）。

---

## 1.1 用語定義

| 用語 | 定義 |
|------|------|
| **フレーム (F)** | 1/60 秒を 1F とする時間単位。実時間との変換: `seconds = frames / fps`, `frames = seconds × fps`。`time.perf_counter()` で取得した実時間 (秒) と `fps` (= 60.0) を介して相互変換する |
| **frame1** | ゲーム起動からOP送り直前まで（≒ 初期Seed決定タイミング）の待機フレーム数。ループ変数として `min_frame` 〜 `max_frame` を 1F ずつ走査する |
| **frame2** | 初期Seed決定（= frame1 タイマー消化完了）からエンカウント直前までの待機フレーム数。この区間には OP 送り・つづきからはじめる・回想スキップなどの操作が含まれ、それらの所要時間はタイマーにより自然に吸収される |
| **frame1_offset** | frame1 に加算するユーザー調整オフセット (default: 0)。他ツールとの帳尻合わせ用 |
| **frame2_offset** | frame2 に加算するユーザー調整オフセット (default: 0)。同上 |
| **advance** | GBA ポケモンの LCG32 乱数生成器が 1 回 `seed = A × seed + C` を適用する操作。wall-clock frame と 1:1 では対応しない（Switch では特に乖離する） |
| **min_advance / max_advance** | Seed 逆算時に探索する LCG advance 数の閉区間。frame2 を目安にユーザーが手動で設定する |
| **fps** | フレームレート。Switch = 60.0。`_consume_timer()` でフレーム数を秒数に変換する際に使用: `target_seconds = total_frames / fps` |

---

## 2. 設定パラメータ

元スクリプトの `Settings` クラスから抽出。NyX移植時は TOML 設定ファイルで管理し、`initialize()` の `args` dict 経由で受け取る。

### 2.1 基本設定

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `file_name` | `str` | `"Switch"` | 出力ファイル名（拡張子なし） |
| `output_dir` | `str` | `"static/frlg_initial_seed"` | 出力ディレクトリ（マクロルートからの相対パス） |
| `sound` | `str` | `"モノラル"` | ゲーム内「せってい」のサウンド設定。`"モノラル"` / `"ステレオ"` |
| `button_mode` | `str` | `"ヘルプ"` | ゲーム内「せってい」のボタンモード設定。`"ヘルプ"` / `"LR"` / `"かたて"` |

> **`sound` / `button_mode` の意味**: FRLG の「せってい」はセーブデータに保存されており、
> 「つづきからはじめる」でロードした際の RNG 消費量に影響する。
> 同じカートリッジでも設定の組み合わせごとに Seed テーブルが異なるため、この 2 パラメータで区別する。
> CSV 出力時には `sound` と `button_mode` がそれぞれ独立のカラムとして記録される。

### 2.2 フレームタイミング

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `min_frame` | `int` | `2090` | frame1 走査の開始フレーム |
| `max_frame` | `int` | `4500` | frame1 走査の上限フレーム |
| `trials` | `int` | `5` | フレームあたりの測定回数 |
| `frame2` | `int` | `745` | 初期Seed決定からエンカウントまでの待機フレーム数 |
| `frame1_offset` | `int` | `0` | frame1 に加算する微調整オフセット |
| `frame2_offset` | `int` | `0` | frame2 に加算する微調整オフセット |
| `min_advance` | `int` | `600` | Seed逆算時の LCG advance 探索下限（閉区間） |
| `max_advance` | `int` | `1500` | Seed逆算時の LCG advance 探索上限（閉区間） |
| `fps` | `float` | `60.0` | フレームレート (1F = 1/fps 秒) |

> **タイマー実待機**: `_consume_timer(cmd, start_time, frameN + frameN_offset, fps)` で
> 「タイマー起点 + 指定フレーム数」に達するまで待機し、操作の所要時間は自然に吸収される（→ §10）。  
> **Seed逆算の探索範囲**: `[min_advance, max_advance]` の閉区間。frame2 の値を目安にユーザーが設定する。

### 2.3 自動再開

既存の CSV ファイルが存在する場合、測定が `trials` 回に満たない最初のフレームから自動的に再開する。
ファイルが存在しない場合は `min_frame` から新規開始する。

---

## 3. メインループ フロー

> **ループ**: 各フレームについて Step 1〜12 を `trials` 回繰り返す。全フレームの測定が完了したら終了。

### Step 0: 初期化

- 設定読み込み
- 既存 CSV があれば解析し、測定が `trials` 回に満たない最初のフレームから再開
- CSV がなければ `min_frame` から新規開始（ヘッダー行付きでファイル作成）
- ループ変数 `frame1` を開始フレームに設定

### Step 1: ゲーム再起動（Switch）

初期Seedはゲームプロセスの起動時に決定されるため、ゲーム内ソフトリセット（`A+B+X+Y` でタイトル画面に戻る方式）では初期Seedを変更できない。
そのため本マクロでは **HOME メニュー経由でゲームを終了→再起動** する方式を採用している。

```
HOME (dur=0.15, wait=0.50)   # ホームメニューに戻る
X    (dur=0.20, wait=0.30)   # ゲーム終了メニューを開く
A    (dur=0.20, wait=0.50)   # 終了を確定
A    (dur=0.20, wait=0.50)   # ホーム画面からゲームを再選択
                             # ★ t1 = _start_timer()
A    (dur=0.20)              # ゲーム起動（A の所要時間はタイマーに自然吸収される）
```

> **GC版**（スコープ外）: `ZR → A → ← → A → A → PLUS+Y(3.50s)` でGBAPlayer経由のリセット
>
> **ID調整マクロとの違い**: ID調整マクロ (`frlg_id_rng`) はゲーム内ソフトリセット (`A+B+X+Y`) を使用する。
> ID調整では初期Seedの変更が不要（既知のSeedテーブルに対してフレーム調整するだけ）なため、
> より高速なソフトリセットで十分である。

### Step 2: frame1 タイマー消化

- タイマーは Step 1 のゲーム起動 A **直前**に開始済み (`t1`)
- `_consume_timer(cmd, t1, frame1 + frame1_offset, fps)` で消化
- A(dur=0.20) の所要時間はタイマーの一部として自然に吸収される
- **消化完了 = 初期Seed決定タイミング**

### Step 3: frame2 タイマー開始 → OP送り → つづきからはじめる → 回想スキップ → frame2 タイマー消化

frame1 タイマー消化完了直後に frame2 タイマーを開始し、以降の操作はすべて frame2 タイマー内で実行される。

```python
t2 = _start_timer()                    # ★ frame2 タイマー開始

cmd.press(Button.A, dur=3.50, wait=1.00)   # OP をAで飛ばす
cmd.press(Button.A, dur=0.20, wait=1.50)   # つづきからはじめる
cmd.press(Button.B, dur=0.50, wait=2.00)   # 回想をBで飛ばす

_consume_timer(cmd, t2, frame2 + frame2_offset, fps)  # ★ frame2 タイマー消化
```

> OP送り・つづきから・回想スキップの所要時間（合計 ≈ 8.7 秒）はタイマーにより自然に吸収される。
> frame2 = 745 の場合、操作に費やした時間を差し引いた残りフレーム分だけ追加待機する。

### Step 4: 個体生成（ルギアに話しかける）

```
A    (dur=0.10, wait=1.00)  # ルギアに話しかける → エンカウント発生（これ以降 PID/IV が確定）
A    (dur=0.10, wait=3.00)  # 「やせいの ルギアが とびだしてきた！」を送る
```

> 個体値 (PID/IV) はこのエンカウント時点で乱数 (LCG32) から決定される。

### Step 5: 捕獲操作

```
→    (dur=0.10, wait=0.30)  # 「バッグ」を選択
A    (dur=0.10, wait=0.50)  # バッグを開く
→    (dur=0.10, wait=0.30)  # ポケット移動
→    (dur=0.10, wait=0.30)  # ポケット移動
A    (dur=0.10, wait=0.50)  # マスターボールを選択
A    (dur=0.10, wait=5.00)  # 「つかう」→ 捕獲アニメーション → 「ルギアを つかまえた！」
```

> **Note**: マスターボール使用を前提。
> バッグ内のポケット・カーソル位置はセーブデータの状態に依存する。
> ボタンシーケンス・ウェイトは実機計測で確定する。

### Step 6: 捕獲後ダイアログ処理 → ステータス画面を開く

捕獲後の各種ダイアログ（図鑑登録・ニックネーム確認・戦闘終了等）は B ボタン連打で一括処理する。

```
# B ボタン連打（約10秒間、約25回）
B    (dur=0.10, wait=0.30)  × 25   # 図鑑登録・ニックネーム辞退・戦闘終了 etc.

# ステータス画面を開く
PLUS (dur=0.10, wait=0.30)  # メニューを開く
↑    (dur=0.10, wait=0.10)  # カーソルを移動
A    (dur=0.10, wait=1.20)  # ポケモンを選択
A    (dur=0.10, wait=0.30)  # ルギアを選択（手持ち最後尾）
A    (dur=0.10, wait=0.30)  # 「つよさをみる」を選択
A    (dur=0.10, wait=2.40)  # ステータス画面表示
```

> **Note**: カーソル位置・手持ちの位置はセーブデータ依存。図鑑登録の有無も初回捕獲かどうかで変わる。
> ボタンシーケンス・ウェイトは実機計測で確定する。

### Step 7: 性格認識

- OCR で性格を画像認識（→ §6.2）
- 認識失敗、または性格テーブルに存在しない → **Step 1 に戻ってリトライ**（最大 3 回）

### Step 8: 実数値認識

```
→ (dur=0.10, wait=1.00)     # 実数値画面に切替
```

- OCR で HP / Atk / Def / SpA / SpD / Spe の6項目を認識（→ §6.3）
- いずれか認識失敗 → **Step 1 に戻ってリトライ**（最大 3 回）

### Step 9: 初期Seed逆算

- 性格 + 実数値から初期Seedを逆算（→ §7）
- 結果:
  - Seed特定成功 → Step 10 へ
  - `"False"`（見つからない） → そのまま記録し Step 10 へ
  - `"MultipleSeeds"`（複数候補） → そのまま記録し Step 10 へ

> **リトライポリシー**: 認識失敗（性格・ステータスの OCR が null を返す場合）のみ再試行対象。
> リトライ時も frame2 は設定値のまま変更しない。リトライ上限（`_MAX_RETRIES = 3`）を超えた場合は
> `"False"` として記録する。Seed 逆算結果が `"False"` / `"MultipleSeeds"` の場合はリトライせず、
> そのまま CSV に書き込んで次の trial へ進む。

### Step 10: 結果出力

- CSV の当該フレーム行の次の空き `seed_N` カラムに結果を書き込み
  - Seed特定成功: 4桁 HEX（例: `A3F1`）
  - `"False"`: 候補が見つからない
  - `"MultipleSeeds"`: 候補が2つ以上
- CSV の `frame` カラムには `frame1 + frame1_offset` の値を記録する
- コンソールに `"{frame1+frame1_offset}F ({trial}/{trials})：{Seed}"` を出力
- 現在のフレームの測定が `trials` 回完了したら次のフレームへ移行

### Step 11: フレーム更新

- `frame1 += 1`, `frame1 > max_frame` でループ終了

### Step 12: 完了通知

- Discord Webhook で完了メッセージ + キャプチャ画像を送信

---

## 4. 対象ポケモン — ルギア (Lv.70)

本マクロは「へそのいわ」でルギアの固定シンボルに話しかけてエンカウント → 捕獲し、その個体のステータスを読み取る前提。

| ステータス | 種族値 |
|-----------|--------|
| HP | 106 |
| こうげき | 90 |
| ぼうぎょ | 130 |
| とくこう | 90 |
| とくぼう | 154 |
| すばやさ | 110 |

> 努力値 (EV) は 0 を前提とする（捕獲直後の個体）。

---

## 5. 認識失敗時のリトライ

性格またはステータスの画像認識に失敗した場合、**同じ frame2 のまま** Step 1 に戻って再試行する。
リトライ上限は `_MAX_RETRIES = 3` 回で、上限到達時は `"False"` として記録する。

Seed 逆算結果が `"False"` / `"MultipleSeeds"` の場合はリトライ対象外であり、そのまま記録して次の trial へ進む。

> 元スクリプトでは失敗時に `frame2 += 2` で補正する方式が採用されていたが、
> frame2 の変更はエンカウントタイミング自体を変えてしまい「同じ条件での再試行」という意味を持たないため、
> NyX 移植では frame2 は常に設定値のまま変更しない方針とした。

---

## 6. 画像認識（OCR）

NyX フレームワークの画像処理 API (`ImageProcessor`) を使用し、PaddleOCR ベースの OCR で性格・ステータスを認識する。

> **元実装との差異**: 元スクリプト (`初期Seed特定.csx`) ではテンプレートマッチングで桁ごとに認識していたが、
> NyX 移植では OCR に統一する。テンプレート画像の管理が不要になり、対象ポケモンの変更にも柔軟に対応できる。

### 6.1 共通パターン: ROI クロップ → OCR

既存の ID 調整マクロ (`frlg_id_rng`) と同じパターンを踏襲する:

```python
from nyxpy.framework.core.imgproc.processor import ImageProcessor

image = cmd.capture()

# ROI クロップ → 白パディング付与 → OCR
x, y, w, h = roi
cropped = image[y : y + h, x : x + w]
padded = cv2.copyMakeBorder(
    cropped, pad, pad, pad, pad,
    borderType=cv2.BORDER_CONSTANT,
    value=(255, 255, 255),
)
text = ImageProcessor(padded).get_text(language="ja")
```

| 項目 | 値 |
|------|-----|
| OCR エンジン | PaddleOCR (言語: `"ja"` / `"en"`) |
| 前処理 | `ImageProcessor` 内部で自動適用 (`enhance_for_ocr`) |
| 白パディング | 各辺 40px（OCR 精度向上 + スナップショット視認性） |
| キャッシュ | `OCRProcessor.get_instance()` でエンジンをシングルトン管理 |

### 6.2 性格認識（OCR）

#### アルゴリズム

1. キャプチャ画像を取得
2. 性格表示領域 (`roi_nature`) をクロップ
3. 白パディングを付与
4. `ImageProcessor(padded).get_text(language="ja")` で日本語テキストを OCR 認識
5. 認識結果を性格名テーブルで照合し、英語名に変換

```python
# 性格名 JPN → EN 変換テーブル
NATURE_JPN_TO_EN: dict[str, str] = {
    "がんばりや": "Hardy",
    "さみしがり": "Lonely",
    "ゆうかん": "Brave",
    "いじっぱり": "Adamant",
    "やんちゃ": "Naughty",
    "ずぶとい": "Bold",
    "すなお": "Docile",
    "のんき": "Relaxed",
    "わんぱく": "Impish",
    "のうてんき": "Lax",
    "おくびょう": "Timid",
    "せっかち": "Hasty",
    "まじめ": "Serious",
    "ようき": "Jolly",
    "むじゃき": "Naive",
    "ひかえめ": "Modest",
    "おっとり": "Mild",
    "れいせい": "Quiet",
    "てれや": "Bashful",
    "うっかりや": "Rash",
    "おだやか": "Calm",
    "おとなしい": "Gentle",
    "なまいき": "Sassy",
    "しんちょう": "Careful",
    "きまぐれ": "Quirky",
}
```

- テーブルに存在しない文字列が返された場合は認識失敗として扱う
- PaddleOCR のゲーム内フォント認識精度が不十分な場合、OCR 用の前処理（閾値化・拡大等）で対処する  
  それでも不足する場合はテンプレートマッチングへのフォールバックを検討する

#### 性格 ROI（`roi_nature`）

Switch / JPN / 720p のみ（NyX スコープ）:

| Hardware | Region | Resolution | x | y | w | h |
|----------|--------|------------|---|---|---|---|
| Switch | JPN | 720p | 197 | 519 | 86 | 43 |

### 6.3 ステータス認識（OCR）

#### アルゴリズム

1. キャプチャ画像を取得
2. ステータス数値表示領域 (`roi_stats`) をクロップ（6ステータスぶん各1つの ROI）
3. 白パディングを付与
4. `ImageProcessor(padded).get_digits(language="en")` で数字を OCR 認識
5. 認識結果を `int` に変換、有効範囲内かをバリデーション

```python
STAT_VALID_RANGES: dict[str, tuple[int, int]] = {
    "HP":  (228, 250),
    "Atk": (117, 167),
    "Def": (168, 228),
    "SpA": (117, 167),
    "SpD": (198, 266),
    "Spe": (143, 198),
}
```

- 認識結果が有効範囲外の場合は認識失敗として扱う
- `get_digits` は内部で `extract_digits`（数字以外をフィルタ）を使用するため、  
  余計な文字が混入しても数字のみが抽出される

> **Note**: 元実装では桁ごとに ROI を分割してテンプレートマッチングしていたが、
> OCR では数値全体を1つの ROI でまとめて認識するため、桁ごとの ROI 分割は不要。

#### ステータス ROI（`roi_stats`）

Switch / JPN / 720p のみ（NyX スコープ）:

| ステータス | x | y | w | h | 備考 |
|-----------|---|---|---|---|------|
| HP | 1016 | 95 | 121 | 45 | 元実装 10の位 x〜1の位 右端をカバー |
| こうげき | 1011 | 172 | 121 | 45 | |
| ぼうぎょ | 1011 | 227 | 121 | 45 | |
| とくこう | 1011 | 282 | 121 | 45 | |
| とくぼう | 1011 | 337 | 121 | 45 | |
| すばやさ | 1011 | 393 | 121 | 45 | |

> **ROI 導出根拠**: 元実装の桁別 ROI から算出。
> - x: 10の位 ROI の x (1054〜1059) からさらに左に 1桁ぶん (≈38px) の余裕を取り、3桁の数字全体をカバー
> - w: 3桁ぶんの幅 (≈121px = 40px/桁 × 3 + マージン)
> - y, h: 元実装の行ごとの値をそのまま使用
>
> 実機スクリーンショットでの検証・微調整が必要。

---

## 7. 初期Seed逆算アルゴリズム（DetermineInitialSeed）

個体生成ロジック（LCG32 / PID / IV）および突合処理の詳細は、独立した仕様書に分離した。

> **→ [frlg_seed_solver.md](frlg_seed_solver.md)** を参照

以下は要約:

- **入力**: 画像認識で取得した性格名 + 6ステータス実数値 + 種族値・レベル + フレーム探索パラメータ
- **処理**: 16bit 初期Seed (0x0000〜0xFFFF) × フレーム範囲 `[min_advance, max_advance]` を全探索し、LCG32 で PID/IV を生成 → 性格の一致を確認後、IV から実数値を順方向に計算し観測値と `==` で突合
- **出力**: 一致候補が 1 つなら (4桁 HEX の Seed, advance) / 0 なら `("False", None)` / 2 つ以上なら `("MultipleSeeds", None)`

認識失敗時は同一 frame2 でリトライする（→ §5）。Seed 逆算結果はそのまま記録する。

---

## 8. 出力形式

### 8.1 CSV フォーマット

1フレーム = 1行。各フレームについて `trials` 回分の Seed 測定結果と、対応する advance を記録する（文字コード: UTF-8）。

出力先: `{output_dir}/{file_name}.csv`

```csv
frame,sound,button_mode,seed_1,seed_2,seed_3,seed_4,seed_5,adv_1,adv_2,adv_3,adv_4,adv_5
2090,モノラル,ヘルプ,A3F1,A3F1,A3F1,A3F1,A3F1,741,741,741,741,741
2091,モノラル,ヘルプ,7C02,False,7C02,7C02,7C02,742,,742,742,742
2092,モノラル,ヘルプ,1234,,,,,743,,,,
```

| カラム | 型 | 説明 |
|--------|------|------|
| `frame` | `int` | `frame1 + frame1_offset` の値 |
| `sound` | `str` | サウンド設定（`モノラル` / `ステレオ`） |
| `button_mode` | `str` | ボタンモード設定（`ヘルプ` / `LR` / `かたて`） |
| `seed_1` … `seed_N` | `str` | 各測定回の Seed 結果。`XXXX`（4桁 HEX）/ `False` / `MultipleSeeds` / 空欄（未測定） |
| `adv_1` … `adv_N` | `str` | 各測定回の advance 値。Seed 特定成功時のみ記録、それ以外は空欄 |

- ヘッダー行あり
- 測定ごとに `seed_N` カラムが埋まる。未測定のカラムは空欄
- 同一フレームでも測定ごとに異なる Seed が出る可能性があるため、全結果をそのまま記録する
- マクロ再開時は、既存 CSV を読み込み、`seed_N` が埋まっていないフレームから続行する
- `sound` と `button_mode` は全行同一値（設定ファイルからの値がそのまま記録される）

### 8.2 デバッグ画像

OCR 認識に使用したキャプチャ画像を `{output_dir}/img/` に保存する（毎回上書き）。

| ファイル名 | 内容 |
|----------|------|
| `nature.png` | 性格認識に使用した画面キャプチャ |
| `stats.png` | 実数値認識に使用した画面キャプチャ |

> 認識失敗時のデバッグに使用する。保存先ディレクトリは `initialize()` 時に自動作成される。

---

## 9. 通知

### 9.1 Discord 通知

マクロ完了時に Discord Webhook で通知を送信する。

| 条件 | メッセージ |
|------|----------|
| 初期Seed収集完了 | `"[FRLG初期Seed集め自動化] 初期Seedを{max_frame}Fまで取得したので、プログラムを終了します。"` |

通知にはキャプチャ画像が添付される。

---

## 10. フレームタイマー (`_start_timer` / `_consume_timer`)

ID調整マクロ (`frlg_id_rng`) と同じタイマーパターンを使用する。

### 10.1 アルゴリズム

```python
def _start_timer() -> float:
    """高精度タイマーの開始時刻を返す。"""
    return time.perf_counter()

def _consume_timer(
    cmd: Command, start_time: float, total_frames: float, fps: float
) -> None:
    """開始時刻からの経過時間を差し引き、残りフレーム分だけ待機する。"""
    target_seconds = total_frames / fps
    elapsed = time.perf_counter() - start_time
    remaining = target_seconds - elapsed
    if remaining > 0:
        cmd.wait(remaining)
```

`_start_timer()` でタイマー起点を記録し、途中の操作（ボタン入力・wait）を実行した後、
`_consume_timer()` で「起点 + 指定フレーム数」に達するまでの残り時間だけ待機する。
操作の所要時間は自然に吸収されるため、**事前にオフセットを差し引く必要がない**。

### 10.2 フレーム ↔ 秒の変換

本マクロにおけるフレーム数はすべて wall-clock 時間の単位であり、以下の関係で実時間と変換する:

$$
\text{seconds} = \frac{\text{frames}}{\text{fps}}, \quad \text{fps} = 60.0
$$

例: `frame1 = 2090` → $2090 / 60.0 \approx 34.83$ 秒

| Hardware | FPS |
|----------|-----|
| Switch | 60.0 |

### 10.3 タイマー計測範囲

本マクロには **2つのタイマー** が存在する。

#### frame1 タイマー（初期Seed決定）

| 要素 | 内容 |
|------|------|
| **開始地点** | ゲーム起動 A の**直前** (`t1 = _start_timer()`) |
| **計測中の操作** | `A(dur=0.20)` ゲーム起動 → ゲームローディング |
| **消化** | `_consume_timer(cmd, t1, frame1 + frame1_offset, fps)` |
| **消化直後** | frame2 タイマー開始 → OP送り |

```
リセット: HOME → X → A → A (wait=0.50)
                        ↓ ★ t1 = _start_timer()
ゲーム起動:  A(dur=0.20)
                        [ゲームローディング]
                        ↓ ★ _consume_timer(t1, frame1 + frame1_offset, fps)
                        ↓ = 初期Seed決定タイミング
```

#### frame2 タイマー（エンカウント）

| 要素 | 内容 |
|------|------|
| **開始地点** | frame1 タイマー消化完了直後 (`t2 = _start_timer()`) |
| **計測中の操作** | OP送り・つづきから・回想スキップ（すべてタイマーに自然吸収） |
| **消化** | `_consume_timer(cmd, t2, frame2 + frame2_offset, fps)` |
| **消化直後** | ルギアに話しかける A → エンカウント |

```
                        ↓ ★ t2 = _start_timer()
OP送り:     A(dur=3.50, wait=1.00)
つづきから:  A(dur=0.20, wait=1.50)
回想スキップ: B(dur=0.50, wait=2.00)
                        [残りフレーム分を待機]
                        ↓ ★ _consume_timer(t2, frame2 + frame2_offset, fps)
エンカウント: A(dur=0.10, ...)
```

#### タイマー一覧（総括）

| タイマー | 起点 | 計測中の操作 | 消化後のアクション | フレーム数 |
|---------|------|-------------|-------------------|----------|
| frame1 | ゲーム起動 A の直前 | A(dur=0.20) + ゲームローディング | frame2 タイマー開始 | `frame1 + frame1_offset` |
| frame2 | frame1 消化完了直後 | OP送り + つづきから + 回想スキップ | エンカウント A | `frame2 + frame2_offset` |

### 10.4 負のフレーム警告

`remaining <= 0` の場合（操作の所要時間が指定フレーム数を超過）、操作が間に合っていない旨の警告を出力して待機をスキップする。

---

## 11. NyX移植時の設計メモ

### 11.1 スコープ

NyX移植では **Switch (720p)** のみを対象とする。以下はスコープ外
（→ [frlg_initial_seed_deferred.md](frlg_initial_seed_deferred.md) に詳細を記録）:
- GC 固有のリセット手順・ROI 座標（§2）
- 1080p 固有の ROI 座標（§3）
- キー入力調査モード（§4）
- 海外版 (Region) 固有補正（§2.4）
- 設定EXE起動 (`SkipSettingsExe`)（§7）
- Shift_JIS エンコーディング（UTF-8 に統一）（§8）

### 11.2 画像認識の方針

元スクリプトはテンプレートマッチングで性格・ステータスを認識していたが、NyX移植では **OCR (PaddleOCR)** に統一する。
既存の `ImageProcessor` API を使用し、ID調整マクロ (`frlg_id_rng`) と同じパターン（ROI クロップ → 白パディング → OCR）を採用する。

| 認識対象 | 元スクリプト | NyX 方針 |
|---------|-------------|------|
| 性格 | テンプレートマッチング (25枚) | `ImageProcessor.get_text(language="ja")` → 性格名テーブルで照合 |
| ステータス値 | テンプレートマッチング (桁ごと) | `ImageProcessor.get_digits(language="en")` → 有効範囲でバリデーション |

OCR 統一のメリット:
- テンプレート画像の用意・管理が不要
- 対象ポケモンやレベルの変更時に ROI とバリデーション範囲の調整のみで対応可能
- リージョンごとのテンプレートフォント差異を吸収できる
- 既存の `OCRProcessor` シングルトンキャッシュでエンジン初期化コストを共有

### 11.3 RNG ライブラリ

元スクリプトは `PokemonPRNG.LCG32.StandardLCG` を使用。NyX では Python で同等の LCG32 実装を用意する。

```python
class LCG32:
    """GBA ポケモン用 32bit 線形合同法 乱数生成器"""

    A = 0x41C64E6D
    C = 0x00006073
    MASK = 0xFFFFFFFF

    # 逆方向用定数
    A_INV = 0xEEB9EB65
    C_INV = 0x0A3561A1

    def __init__(self, seed: int) -> None:
        self._seed = seed & self.MASK

    def advance(self, n: int = 1) -> None:
        for _ in range(n):
            self._seed = (self.A * self._seed + self.C) & self.MASK

    def back(self, n: int = 1) -> None:
        for _ in range(n):
            self._seed = (self.A_INV * self._seed + self.C_INV) & self.MASK

    def get_rand(self) -> int:
        self.advance()
        return (self._seed >> 16) & 0xFFFF

    @property
    def seed(self) -> int:
        return self._seed
```

### 11.4 クラス構成案

```
macros/
  frlg_initial_seed/
    __init__.py
    macro.py                  # メインマクロクラス (FrlgInitialSeedMacro)
    seed_solver.py            # DetermineInitialSeed の移植（LCG32 + 逆算ロジック）
    pokemon_gen.py            # generate_pokemon(), Pokemon dataclass (calc_stats 含む)
    nature.py                 # 性格ID・性格補正テーブル
    recognizer.py             # 性格認識・ステータス認識のラッパー
    config.py                 # 設定パラメータ定義 (dataclass)
```

> 元実装にあった `stat_calculator.py` (IV 逆変換関数) は不要。
> 順方向変換は `Pokemon.calc_stats()` メソッドに集約 (→ [frlg_seed_solver.md](frlg_seed_solver.md) §3.4)。

### 11.5 API マッピング

| 元スクリプト (NxInterface) | NyXフレームワーク (Command) |
|---------------------------|---------------------------|
| `Press(Button.A, 0.20, 1.30)` | `cmd.press(Button.A, dur=0.20, wait=1.30)` |
| `Press(Button.HOME, 0.15, 0.50)` | `cmd.press(Button.HOME, dur=0.15, wait=0.50)` |
| `Press(Direction.UP, 0.10, 0.10)` | `cmd.press(Hat.UP, dur=0.10, wait=0.10)` |
| `Hold(Direction.DOWN)` | `cmd.hold(Hat.DOWN)` |
| `HoldEnd(Direction.DOWN)` | `cmd.release(Hat.DOWN)` |
| `Wait(seconds)` | `cmd.wait(seconds)` |
| `GetCapture()` | `cmd.capture()` |
| `IsContainTemplateMax(img, paths, ...)` | `ImageProcessor(img).get_text()` / `get_digits()` |
| `Console.WriteLine(...)` | `cmd.log(...)` |
| `SendDiscord(msg, img)` | `cmd.notify(msg, img)` |
| `DateTime.Now` + `Stopwatch` スピンウェイト | `time.perf_counter()` ベースのタイマー |

### 11.6 設計決定事項

| 項目 | 決定 | 備考 |
|------|------|------|
| **ハードウェア** | Switch (720p) のみ | GC・1080p はスコープ外 |
| **フレームタイマー** | `_start_timer()` / `_consume_timer()` | ID調整マクロと同一パターン。offset の事前差し引きは行わず、操作の所要時間をタイマーで自然吸収 |
| **性格認識** | OCR (`ImageProcessor.get_text`) | PaddleOCR で日本語テキスト認識、テーブルで英語名に変換 |
| **ステータス認識** | OCR (`ImageProcessor.get_digits`) | PaddleOCR で数値認識、有効範囲でバリデーション |
| **出力形式** | UTF-8 の CSV（ヘッダー付き、`trials` 回分カラム） | TXT ・ Shift_JIS は廃止 |
| **Seed逆算探索範囲** | `[min_advance, max_advance]` 閉区間 | LCG advance 数。frame2 を目安にユーザーが設定 |
| **RNG** | Python 実装の LCG32 | `PokemonPRNG.dll` の代替 |
| **キー入力調査モード** | 別仕様書として Phase 2 で整備 | → [frlg_initial_seed_deferred.md](frlg_initial_seed_deferred.md) §4 |
| **中断対応** | メインループ各ステップで `cmd.stop()` チェック | ID調整マクロと同様 |

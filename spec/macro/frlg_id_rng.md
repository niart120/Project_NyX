# FRLG ID調整マクロ 仕様書

> **元ファイル**: `FRLG_ID調整.csx`（C# Script）  
> **対象タイトル**: ポケットモンスター ファイアレッド・リーフグリーン (FRLG)  
> **目的**: ニューゲーム開始時の乱数制御により、目標のトレーナーID (TID) を取得する  
> **移植スコープ**: Switch (720p) のみ。GC 固有処理・VEGA 固有処理はスコープ外

---

## 1. 概要

ゲームのソフトリセット → ニューゲーム開始 → TID確認 を自動で繰り返し、
画像認識で読み取ったTIDが目標値と一致するまでループするマクロである。

主要なRNG制御ポイントは以下の3つのフレームタイマーで、
各タイマーの待機時間を精密に制御することで目標TIDの出現を狙う。

| タイマー | 制御ポイント | 説明 |
|----------|-------------|------|
| **OPFrame** | オープニング待機 | リセット後〜OP送り開始までの待機フレーム |
| **Frame1** | 名前入力画面突入 | 性別選択完了〜名前入力画面のA押下までの待機フレーム |
| **Frame2** | 名前入力決定 | 名前入力画面突入〜名前決定後の会話進行までの待機フレーム |
| **Frame3** | ゲーム開始確定 | ライバル名前決定後〜主人公の家へ遷移するA押下までの待機フレーム |

> **Frame3** にはリージョンごとの固定オフセット補正がかかる（後述）。

---

## 2. 設定パラメータ

元スクリプトの `Settings` クラスから抽出。NyXマクロへの移植時は TOML 設定ファイルで管理し、`initialize()` の `args` dict 経由で受け取る。

### 2.1 基本設定

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `region` | `str` | `"JPN"` | ゲームリージョン。`JPN` / `ENG` / `FRA` / `ITA` / `ESP` / `NOE` |
| `tid` | `int` | `0` | 目標トレーナーID (0–65535) |
| `trainer_name` | `str` | `"ナッツァ"` | 主人公の名前 |
| `rival_name` | `str` | `"グリーン"` | ライバルの名前 |
| `default_rival_name` | `bool` | `False` | `True` の場合デフォルト名を使用（名前入力をスキップ） |
| `gender` | `str` | `"おとこのこ"` | 性別選択。`"おとこのこ"` / `"おんなのこ"` |
| `report_on_match` | `bool` | `True` | TID一致時にゲーム内でレポートを書くか |

### 2.2 フレームタイミング

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `frame1` | `float` | `1235.0` | Frame1 待機フレーム数 |
| `frame2` | `float` | `1267.0` | Frame2 待機フレーム数 |
| `frame3` | `float` | `6609.0` | Frame3 待機フレーム数（補正前） |
| `op_frame` | `float` | `468.0` | OP待機フレーム数 |
| `fps` | `float` | `59.7275` | フレームレート（1Fの時間 = 1000/fps ms） |

### 2.3 インクリメントモード

自動でフレーム値をずらしながら探索するモード。

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `frame_increment_mode` | `bool` | `False` | Frame1/Frame2 インクリメント探索を有効化 |
| `frame1_min` / `frame1_max` | `float` | `1200.0` / `1500.0` | Frame1 の探索範囲 |
| `frame2_min` / `frame2_max` | `float` | `1200.0` / `1600.0` | Frame2 の探索範囲 |
| `op_increment_mode` | `bool` | `False` | OPFrame インクリメント探索を有効化 |
| `op_frame_min` / `op_frame_max` | `float` | `382.0` / `1000.0` | OPFrame の探索範囲 |
| `id_tolerance_range` | `int` | `50` | インクリメントモード時のTID許容誤差 |
| `select_plus` | `int` | `0` | Selectズレ回避/発生用の追加キーボード切替回数 |

### 2.4 ハードウェア前提

NyXでは **Switch（720p）のみ** をターゲットとする。GC 固有処理および 1080p 固有 ROI はスコープ外。
NyXの `capture()` は常に 1280×720 にリスケールするため、720p ROI 座標をそのまま使用する。

---

## 3. メインループ フロー

> **ループ**: Step 1〜16 を TID が目標値と一致するまで繰り返す。

#### Step 0: 初期化
- 設定読み込み（TOML → `args` dict）
- フレームカウンタ・インクリメント状態の初期化

#### Step 1: ソフトリセット
- `A+B+X+Y` 同時押し (`dur=0.30, wait=0.10`)

#### Step 2: OP待機
- `A` (`dur=0.20, wait=6.00`) → `A` (`dur=0.20`)
- OPFrame 分のタイマーを消化（`_wait_frames()`）

#### Step 3: OP送り → ニューゲーム選択
- `A` → 0.167s → `A` → 3.350s
- `↓` → `A` （「さいしょからはじめる」）
- `A` 連打（そうさせつめい・あらすじ）

#### Step 4: イントロ会話送り
- リージョンごとにタイミングが異なる（→ §4.2）

#### Step 5: 性別選択
- `おとこのこ`: `A` → 2.5s
- `おんなのこ`: `↓` → `A` → 2.5s

#### Step 6: Frame1 タイマー消化
- `_wait_frames()` で残存時間を待機

#### Step 7: 名前入力（主人公）
- `A` → 名前入力画面へ遷移
- `enter_name(trainer_name)`（→ §5）
- Select 操作（`select_plus` 回の Y ボタンモード切替）
- `START` で名前確定

#### Step 8: Frame2 タイマー消化
- `_wait_frames()` で残存時間を待機

#### Step 9: 名前決定後の会話進行
- リージョンごとにタイミングが異なる（→ §4.3）

#### Step 10: ライバル名前入力
- `default_rival_name = True` → `↓` → `A` → 1.0s（デフォルト名採用）
- `default_rival_name = False` → `A` → `enter_name(rival_name)` → `A` → 1.8s

#### Step 11: ライバル名確定後の会話
- リージョンごとにタイミングが異なる（→ §4.4）

#### Step 12: Frame3 タイマー消化
- `_wait_frames()` で残存時間を待機

#### Step 13: ゲーム開始（主人公の家へ）
- `A` → JPN: 4.5s / その他: 6.0s 待機

#### Step 14: TID 確認画面を開く（トレーナーカード）
- `PLUS` (`dur=0.10, wait=0.30`) — ゲーム内メニューを開く
- `↓` (`dur=0.10, wait=0.20`) — 「ポケモンずかん」→「**トレーナーカード**」へカーソル移動
- `A` (`dur=0.10, wait=2.20`) — トレーナーカードを開く（描画完了まで待機）

トレーナーカード画面にはプレイヤーの **TID（トレーナーID / IDNo.）が5桁で表示** される。
この画面をキャプチャし、TID表示領域を OCR で読み取る（→ Step 15）。

> TID の表示位置はリージョンによりフォントやラベル幅が異なるため、OCR 用 ROI がリージョンごとに定義されている（§6.2）。

#### Step 15: TID 認識（OCR）
- トレーナーカード画面をキャプチャし、リージョン別 ROI で TID 表示領域を切り出し
- PaddleOCR で 5 桁の数値文字列を一括認識
- 認識失敗 or 値が 0–65535 範囲外 → **Step 1 へ戻る**

#### Step 16: TID 判定
- **完全一致** → 通知送信 → （`report_on_match` なら §9.2 レポート書き込み） → **終了**
- **インクリメントモード時に許容範囲内** → 通知送信 → 探索続行
- **不一致** → フレームインクリメント（§8） → **Step 1 へ戻る**

---

## 4. リージョン別タイミング詳細

### 4.1 Frame3 補正値

Frame3 設定値からリージョンごとのオフセットを減算してから使用する。

| リージョン | 補正値 (減算) |
|-----------|--------------|
| JPN | 143 |
| ENG | 198 |
| ESP | 151 |
| FRA | 154 |
| ITA | 185 |
| NOE | 157 |

### 4.2 イントロ会話送り (Step 4)

名前の入力画面に至るまでの A 連打シーケンス。リージョンで会話テキスト量・演出時間が異なるため、待機時間がすべて異なる。

#### JPN
```
A(0.1s) → 0.6s → A(0.1s) → 0.6s → A(0.1s) → 0.4s     # オーキド博士
A(0.1s) → 1.6s → A(0.1s) → 0.5s → A(0.1s) → 0.6s     # ニドラン♀登場
A(0.1s) → 0.5s → A(0.1s) → 0.5s → A(0.1s) → 0.7s
A(0.1s) → 2.6s → A(0.1s) → 2.3s                        # ニドラン♀退場
```

#### ENG
```
wait(0.50s)
A(0.1s) → 1.0s → A(0.1s) → 0.6s → A(0.1s) → 1.1s     # オーキド博士
A(0.1s) → 2.1s → A(0.1s) → 1.3s → A(0.1s) → 0.6s     # ニドラン♀登場
A(0.1s) → 0.6s
A(0.1s) → 2.9s → A(0.1s) → 2.6s                        # ニドラン♀退場
```

#### FRA / ITA
```
wait(1.00s)
A(0.1s) → 0.6s → A(0.1s) → 1.2s                        # オーキド博士
A(0.1s) → 1.9s → A(0.1s) → 1.4s → A(0.1s) → 0.7s     # ニドラン♀登場
A(0.1s) → 0.6s → A(0.1s) → 1.0s
A(0.1s) → 2.7s → A(0.1s) → 2.6s                        # ニドラン♀退場
```

#### NOE
```
wait(1.00s)
A(0.1s) → 0.9s → A(0.1s) → 1.0s → A(0.1s) → 1.1s     # オーキド博士
A(0.1s) → 1.8s → A(0.1s) → 1.7s → A(0.1s) → 0.5s     # ニドラン♀登場
A(0.1s) → 0.6s → A(0.1s) → 1.5s
A(0.1s) → 2.8s → A(0.1s) → 2.7s                        # ニドラン♀退場
```

#### ESP
```
wait(0.50s)
A(0.1s) → 0.6s → A(0.1s) → 1.2s                        # オーキド博士
A(0.1s) → 1.6s → A(0.1s) → 0.9s → A(0.1s) → 0.4s     # ニドラン♀登場
A(0.1s) → 0.4s → A(0.1s) → 0.7s → A(0.1s) → 0.7s
A(0.1s) → 2.6s → A(0.1s) → 2.4s                        # ニドラン♀退場
```

### 4.3 名前決定後〜ライバル登場 (Step 9)

#### JPN
```
A(0.1s) → 1.8s → A(0.1s) → 2.5s    # 名前決定
A(0.1s) → 0.7s → A(0.1s) → 0.7s → A(0.1s) → 0.7s    # ライバル登場
```

#### ENG
```
A(0.1s) → 2.2s → A(0.1s) → 2.8s    # 名前決定
A(0.1s) → 1.3s → A(0.1s) → 1.1s    # ライバル登場
```

#### FRA / NOE
```
A(0.1s) → 2.5s → A(0.1s) → 2.8s    # 名前決定
A(0.1s) → 1.2s → A(0.1s) → 1.6s    # ライバル登場 (NOE: 第2待機は1.6s)
```

#### ITA
```
A(0.1s) → 2.5s → A(0.1s) → 2.8s    # 名前決定
A(0.1s) → 1.6s                       # ライバル登場
```

#### ESP
```
A(0.1s) → 2.2s → A(0.1s) → 2.5s    # 名前決定
A(0.1s) → 1.1s → A(0.1s) → 1.6s    # ライバル登場
```

### 4.4 ライバル名確定後の会話 (Step 11)

#### JPN
```
A(0.1s) → 0.7s → A(0.1s) → 2.4s    # 名前確定
A(0.1s) → 0.7s → A(0.1s) → 0.7s    # 会話
```

#### ESP
```
A(0.1s) → 0.7s → A(0.1s) → 2.4s    # 名前確定
A(0.1s) → 0.9s → A(0.1s) → 0.9s    # 会話
```

#### ENG
```
A(0.1s) → 0.9s → A(0.1s) → 2.4s    # 名前確定
A(0.1s) → 0.9s                       # 会話
```

#### FRA / ITA
```
A(0.1s) → 1.2s → A(0.1s) → 2.9s    # 名前確定
A(0.1s) → 1.0s → A(0.1s) → 1.5s    # 会話
```

#### NOE
```
A(0.1s) → 1.2s → A(0.1s) → 2.9s    # 名前確定
A(0.1s) → 1.1s → A(0.1s) → 1.8s    # 会話
```

### 4.5 リージョン固有パラメータ一覧

各セクションに散在するリージョン依存値を一覧に集約する。実装時は `RegionTiming` 等のデータクラスにこの表の値をそのまま格納する。

| パラメータ | JPN | ENG | FRA | ITA | ESP | NOE |
|-----------|-----|-----|-----|-----|-----|-----|
| **Frame3 補正値** (§4.1) | 143 | 198 | 154 | 185 | 151 | 157 |
| **イントロ冒頭 wait** (§4.2) | 0.0s | 0.5s | 1.0s | 1.0s | 0.5s | 1.0s |
| **イントロ A 回数** (§4.2) | 11 | 10 | 10 | 10 | 11 | 10 |
| **名前確認 A 回数** (§4.3) | 5 | 4 | 4 | 3 | 4 | 4 |
| **ライバル確認 A 回数** (§4.4) | 4 | 3 | 4 | 4 | 4 | 4 |
| **ゲーム開始 wait** (Step 13) | 4.5s | 6.0s | 6.0s | 6.0s | 6.0s | 6.0s |
| **キーボードレイアウト** (§5.3) | JPN | ENG | FRA | ENG | ENG | NOE |
| **TID OCR ROI (x,y,w,h)** (§6.2) | 869,91,190,46 | 888,86,127,47 | 893,86,127,47 | 893,86,127,47 | 915,86,127,47 | 888,86,127,47 |
| **レポート A 回数** (§9.2) | 7 | 6 | 6 | 7 | 6 | 9 |
| **レポート A 待機** (§9.2) | 1.0s | 1.5s | 1.5s | 1.5s | 1.5s | 1.5s |

> **Note**: イントロ・名前確認・ライバル確認の各シーケンスは A 回数だけでなく各ステップの待機時間も異なる。
> 詳細なタイミング値は §4.2〜§4.4 の個別シーケンスを参照のこと。

---

## 5. 名前入力ロジック (EnterName)

ソフトキーボード上でカーソルを移動し、1文字ずつ入力する。リージョンによってキーボードレイアウトが大きく異なる。

### 5.1 共通アルゴリズム

```
1. 入力文字列を1文字ずつ処理
2. 文字に応じて必要なキーボードモードを判定
3. 現在モードと異なる場合、Y ボタンでモード切替（3モード循環）
4. キーボード配列上の目標座標を検索
5. MoveCursor() で現在カーソル位置から目標へ移動
6. A ボタンで文字確定
7. 濁点・半濁点が必要な場合、追加で対応キーに移動して入力
8. Select操作（select_plus 回のモード切替）は主人公名入力時のみ実施
9. START ボタンで名前入力完了
```

### 5.2 カーソル移動 (MoveCursor)

```
引数: (cursorX, cursorY, targetX, targetY, offset=0)
targetX += offset
while (cursorX, cursorY) ≠ (targetX, targetY):
    cursorX < targetX → RIGHT入力, cursorX++
    cursorX > targetX → LEFT入力, cursorX--
    cursorY < targetY → DOWN入力, cursorY++
    cursorY > targetY → UP入力, cursorY--
```

各方向入力は `dur=0.1s, wait=0.1s`。X軸とY軸は1ステップずつ同時に進む（斜め移動ではなく、1ループで水平1 + 垂直1 の入力）。

### 5.3 キーボードレイアウト

#### JPN — 3モード（ひらがな / カタカナ / 英数字）

**ひらがなモード:**  
```
行0: あいうえお　なにぬねの　やゆよ!?⏎
行1: かきくけこ　はひふへほ　わをん濁半
行2: さしすせそ　まみむめも　ゃゅょっー
行3: たちつてと　らりるれろ　ぁぃぅぇぉ
```
- 「濁」(x=16,y=1): 濁点入力キー  
- 「半」(x=17,y=1): 半濁点入力キー  
- 「⏎」(🅂): 確定キー

**カタカナモード:** ひらがなのカタカナ版（同配置）

**英数字モード:**  
```
行0: A B C D E F G H I J K L M N O P Q R S
行1: T U V W X Y Z 　0 1 2 3 4 5 6 7 8 9
行2: a b c d e f g h i j k l m n o p q r s
行3: t u v w x y z 　。・…『』「」/♂♀
```

**濁点・半濁点の処理:**  
- 濁点対象文字（が↔か, ざ↔さ, etc.）を入力する場合、ベース文字を入力後に「濁」キーを押す
- 半濁点対象文字（ぱ↔は, etc.）を入力する場合、ベース文字を入力後に「半」キーを押す
- 5文字目の場合は特殊オフセット処理あり

#### ENG / ESP / ITA — 3モード（大文字 / 小文字 / 数字記号）

**大文字モード:**  
```
行0: A B C D E F [殻] .
行1: G H I J K L [殻] ,
行2: M N O P Q R S [唐]
行3: T U V W X Y Z [唐]
```
- `殻`/`唐` は非入力文字（オフセット生成用プレースホルダ）
- `S`, `Z` 到達後 → offset=1
- `.`, `,` 到達後 → offset=2

**小文字モード:** 大文字の小文字版（同配置）

**数字記号モード:**  
```
行0: 0 1 2 3 4
行1: 5 6 7 8 9
行2: ! ? ♂ ♀ / -
行3: … " " ' '
```

#### FRA — 3モード（大文字 / 小文字 / 数字記号）

**大文字モード:**  
```
行0: A B C D E F G H . ×
行1: I J K L M N O P , ×
行2: Q R S T U V W X [辛] ×
行3: Y Z     -   [殻][唐][辛] ×
```
- オフセット: `G`/`O`/`W`系 → 1, `H`/`P`/`X`系 → 2, `.`/`,`/`辛` → 3

#### NOE — 3モード（大文字 / 小文字 / 数字記号）

FRA とほぼ同一レイアウトだが、記号の一部が独語特殊文字に置換:
- `Y Z Ä Ö Ü` (大文字4行目) / `y z ä ö ü` (小文字4行目)

---

## 6. TID画像認識

### 6.1 認識フロー

ゲーム内メニュー → トレーナーカードを開くと、画面上部に **IDNo. xxxxx** の形式で TID が5桁表示される。
NyXに搭載済みの PaddleOCR (`ImageProcessor.get_text()`) を使用し、この TID 表示エリアを丸ごと OCR で読み取る方針とする。
元スクリプトの1桁ずつテンプレートマッチングする手法に比べ、テンプレート画像の同梱が不要になり実装が簡潔になる。

```
1. トレーナーカード画面をキャプチャ取得 (cmd.capture)
2. リージョン別 ROI で TID 表示エリア (IDNo. の数字5桁部分) を crop_region で切り出し
3. PaddleOCR で数値文字列を認識
4. 認識結果を int に変換（数値以外の文字が混入した場合は認識失敗）
5. 値が 0–65535 の範囲外 → 認識失敗として棄却
```

> **フォールバック**: OCR の認識精度が不十分な場合は、テンプレートマッチングへの切り替えを検討する。

### 6.2 ROI座標 (720p / Switch 基準)

NyXの `capture()` は 1280×720 にリスケーリングするため、720p の ROI をそのまま使用可能。
OCR方式ではキャプチャ保存領域（TID 5桁全体の矩形）を `crop_region` として使用する。

| リージョン | x | y | w | h |
|-----------|-----|-----|-----|-----|
| JPN | 869 | 91 | 190 | 46 |
| ENG / NOE | 888 | 86 | 127 | 47 |
| FRA / ITA | 893 | 86 | 127 | 47 |
| ESP | 915 | 86 | 127 | 47 |

### 6.3 OCR設定

- 認識言語: `en` (数字のみのため英語モードで十分)
- 前処理: グレースケール変換 + コントラスト強調を推奨
- 認識領域にはリージョンごとのキャプチャ保存領域 ROI を使用

> **Note**: 元スクリプトは1桁ずつテンプレートマッチング（`Template/{hw}/{lang}/{digit}.png`）で認識していた。
> OCRで十分な精度が出なかった場合のフォールバック実装として参考にできる。

---

## 7. フレームタイマー

### 7.1 WaitTimer アルゴリズム

元スクリプトはスピンウェイト (`Stopwatch` ループ) で 1F (≈16.7ms) 精度の待機を実現していた。
NyX移植版では、まず既存の `cmd.wait()` ベース実装で動作検証し、精度不足が判明した場合に高精度タイマーを検討する。

`cmd.wait()` ベースでのタイマー消化は、フレーム数を秒に変換して `cmd.wait()` に渡す形とする:

```python
def _wait_frames(self, cmd: Command, total_frames: float, fps: float) -> None:
    """フレーム数を秒に変換して待機する。"""
    seconds = total_frames / fps
    if seconds > 0:
        cmd.wait(seconds)
```

> **精度に関する注意**: `time.sleep()` は OS スケジューラ依存であり、
> Windows では ~15ms のジッタがある。1F 精度が必要な場合は
> `time.perf_counter()` ベースのスピンウェイトを別途検討する。

### 7.2 タイマー設置タイミング

| タイマー | 開始地点 | 消化地点 |
|---------|---------|---------|
| OPFrame | リセット後の最初の A 押下前 | OP送り開始の A 押下前 |
| Frame1 | あらすじ会話送り完了後 | 名前入力画面突入の A 押下前 |
| Frame2 | 名前入力画面突入の A 押下後 | 名前決定後の会話進行前 |
| Frame3 | 名前決定後の会話開始 | ゲーム開始（主人公の家へ）の A 押下前 |

---

## 8. インクリメントロジック

### 8.1 Frame インクリメントモード

Frame1 と Frame2 を範囲内で +2 ずつ増加させながら探索する。

```
偶数パス: Frame1 = Frame1Min, Frame1Min+2, ..., Frame1Max
          Frame2 = Frame2Min, Frame2Min+2, ..., Frame2Max

奇数パス: Frame1 = Frame1Min+1, Frame1Min+3, ..., Frame1Max
          Frame2 = Frame2Min+1, Frame2Min+3, ..., Frame2Max
```

**繰り上がり規則:**
1. `Frame1 += 2` → `Frame1 > Frame1Max` なら Frame2 を +2 して Frame1 をリセット
2. `Frame2 > Frame2Max` なら偶数パス→奇数パスへ切り替え（または逆）
3. 範囲幅が 0F（Min == Max）の場合、その軸の奇数パスはスキップ

### 8.2 OP インクリメントモード

```
偶数パス: OPFrame = OPFrameMin, OPFrameMin+2, ..., OPFrameMax
奇数パス: OPFrame = OPFrameMin+1, OPFrameMin+3, ..., OPFrameMax
```

### 8.3 許容範囲判定

インクリメントモードでは、完全一致でなくても許容範囲内なら通知を出す。

```python
lower = tid - id_tolerance_range
upper = tid + id_tolerance_range

# 循環補正 (TID は 0–65535)
if lower < 0:
    lower += 65536
if upper > 65535:
    upper -= 65536

# 範囲が 0 を跨ぐ場合
if lower <= upper:
    match = lower <= recognized_id <= upper
else:
    match = recognized_id >= lower or recognized_id <= upper
```

---

## 9. 通知・レポート

### 9.1 Discord 通知

以下のタイミングで Discord Webhook による通知を送信する:
- インクリメントモードで許容範囲内のTIDを検出したとき
- 目標TIDと完全一致したとき

通知内容:
- テキスト: `"{i}回目：目的のIDを引けました。（Frame1：{f1}F、Frame2：{f2}F、OP待機：{op}F）"`
- 添付画像: キャプチャ画面のスクリーンショット

NyXでは `cmd.notify(text, img)` にマッピングする。

### 9.2 レポート書き込み

`report_on_match = True` の場合、TID一致後にゲーム内メニューからレポート（セーブ）を実行する。
リージョンごとにメニュー操作のA押下回数・待機時間が異なる。

---

## 10. NyX移植時の設計メモ

### 10.1 リファクタリング方針

元スクリプトは約1,550行のモノリシックな C# Script であり、リージョン分岐が `if/else` チェーンで **4箇所以上** に散在している。
NyX移植にあたっては「データとロジックの分離」を軸にリファクタリングし、可読性・保守性を大幅に改善する。

#### 10.1.1 問題点の整理

| # | 問題 | 元スクリプトでの該当箇所 | 影響 |
|---|------|------------------------|------|
| 1 | **リージョン分岐のコピペ** | イントロ会話送り / 名前決定後会話 / ライバル名確定後会話 / レポート書き込み の各所で 6リージョン分の `if/else` が出現 | 同じ構造のコードが繰り返され、修正時に全箇所を追う必要がある |
| 2 | **A連打シーケンスのハードコード** | `Press(Button.A, 0.1, 0.6)` の羅列が数十行にわたる | 「何を待っているか」が読み取りにくく、タイミング調整が困難 |
| 3 | **`EnterName` のリージョン別フル実装** | JPN / ENG・ESP・ITA / FRA / NOE の4パスが各100行超 | キーボードレイアウト（データ）とカーソル移動（ロジック）が密結合 |
| 4 | **インクリメントロジックの複雑さ** | 偶数/奇数パス切替 + Min==Max の特殊ケースが入り組んだ条件分岐 | バグが入りやすく、テストしにくい |
| 5 | **レポート書き込みの重複** | JPN / ENG・ESP・FRA / ITA / NOE で4ブロック、構造はほぼ同一 | A押下回数と待機時間だけが異なる |

#### 10.1.2 データ駆動化: リージョン別タイミングテーブル

問題 1, 2, 5 に対する解法。各リージョンの差分を **定数 dict** に集約し、ロジック側はリージョンキーで参照するだけにする。

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RegionTiming:
    """リージョンごとのタイミング定義"""
    frame3_offset: float
    intro_pre_wait: float                # Step 4 冒頭の wait (JPN=0, ENG=0.5, etc.)
    intro_sequence: list[tuple[float, float]]  # [(dur, wait), ...]
    name_confirm_sequence: list[tuple[float, float]]  # Step 9
    rival_confirm_sequence: list[tuple[float, float]]  # Step 11
    game_start_wait: float               # Step 13 (JPN=4.5, 他=6.0)
    report_a_presses: int                # レポート時の A 押下回数
    report_a_wait: float                 # レポート時の A 待機時間

REGION_TIMINGS: dict[str, RegionTiming] = {
    "JPN": RegionTiming(
        frame3_offset=143,
        intro_pre_wait=0.0,
        intro_sequence=[
            (0.1, 0.6), (0.1, 0.6), (0.1, 0.4),    # オーキド博士
            (0.1, 1.6), (0.1, 0.5), (0.1, 0.6),     # ニドラン♀登場
            (0.1, 0.5), (0.1, 0.5), (0.1, 0.7),
            (0.1, 2.6), (0.1, 2.3),                  # ニドラン♀退場
        ],
        name_confirm_sequence=[
            (0.1, 1.8), (0.1, 2.5),                  # 名前決定
            (0.1, 0.7), (0.1, 0.7), (0.1, 0.7),     # ライバル登場
        ],
        rival_confirm_sequence=[
            (0.1, 0.7), (0.1, 2.4),                  # 名前確定
            (0.1, 0.7), (0.1, 0.7),                  # 会話
        ],
        game_start_wait=4.5,
        report_a_presses=7,
        report_a_wait=1.0,
    ),
    # ENG, FRA, ITA, ESP, NOE も同様に定義
    ...
}
```

呼び出し側は分岐が不要になる:

```python
def _play_intro(self, cmd: Command, timing: RegionTiming) -> None:
    if timing.intro_pre_wait > 0:
        cmd.wait(timing.intro_pre_wait)
    self._press_a_sequence(cmd, timing.intro_sequence)

def _press_a_sequence(self, cmd: Command, sequence: list[tuple[float, float]]) -> None:
    """A ボタンの (dur, wait) シーケンスを順に実行する。"""
    for dur, wait in sequence:
        cmd.press(Button.A, dur=dur, wait=wait)
```

**効果**: リージョン分岐の `if/else` 4箇所 → 0箇所。タイミング調整はデータ変更のみで完結。

#### 10.1.3 名前入力のデータ・ロジック分離

問題 3 に対する解法。キーボードの **レイアウト定義（データ）** と **カーソル移動＋入力（ロジック）** を分離する。

```python
@dataclass(frozen=True)
class KeyboardLayout:
    """1つのキーボードモードのレイアウト"""
    grid: list[str]     # 各行の文字列（配列上の座標 = 文字位置）

@dataclass(frozen=True)
class RegionKeyboard:
    """リージョンごとのキーボード定義"""
    modes: list[KeyboardLayout]  # 3モード分 (循環切替)
    dakuten_map: dict[str, str] | None   # 濁点: 変換後 → 変換前
    handakuten_map: dict[str, str] | None  # 半濁点: 変換後 → 変換前
    dakuten_pos: tuple[int, int] | None    # 濁点キー座標
    handakuten_pos: tuple[int, int] | None # 半濁点キー座標
    compute_offset: Callable[[str], int] | None  # 文字→オフセット算出関数

# JPN 用定義例
JPN_KEYBOARD = RegionKeyboard(
    modes=[
        KeyboardLayout(["あいうえお空なにぬねの空やゆよ!?🅂空", ...]),  # ひらがな
        KeyboardLayout(["アイウエオ空ナニヌネノ空ヤユヨ!?🅂空", ...]),  # カタカナ
        KeyboardLayout(["ABCDEFGHIJKLMNOPQRS", ...]),                 # 英数字
    ],
    dakuten_map={"が": "か", "ぎ": "き", ...},
    handakuten_map={"ぱ": "は", ...},
    dakuten_pos=(16, 1),
    handakuten_pos=(17, 1),
    compute_offset=None,  # JPN はオフセット不要
)
```

入力ロジックは共通の1メソッドに集約:

```python
def _enter_name(self, cmd: Command, name: str, keyboard: RegionKeyboard) -> None:
    """キーボードレイアウトに基づいて名前を入力する。"""
    cursor_x, cursor_y = 0, 0
    current_mode = 0

    for char in name:
        target_char, need_dakuten, need_handakuten = self._resolve_char(char, keyboard)
        target_mode = self._find_mode(target_char, keyboard)

        # モード切替
        while current_mode != target_mode:
            cmd.press(Button.Y, dur=0.2, wait=0.5)
            current_mode = (current_mode + 1) % len(keyboard.modes)

        # 文字位置検索 → カーソル移動 → 入力
        tx, ty = self._find_char_pos(target_char, keyboard.modes[current_mode])
        offset = keyboard.compute_offset(target_char) if keyboard.compute_offset else 0
        cursor_x, cursor_y = self._move_cursor(cmd, cursor_x, cursor_y, tx + offset, ty)
        cmd.press(Button.A, dur=0.2, wait=0.2)

        # 濁点・半濁点処理
        if need_dakuten and keyboard.dakuten_pos:
            cursor_x, cursor_y = self._move_cursor(
                cmd, cursor_x, cursor_y, *keyboard.dakuten_pos
            )
            cmd.press(Button.A, dur=0.2, wait=0.2)
        # ...（半濁点も同様）
```

**効果**: 4パス（JPN / ENG系 / FRA / NOE） → **共通ロジック1本 + レイアウトデータ4セット**。

#### 10.1.4 インクリメントロジックの抽出

問題 4 に対する解法。偶数/奇数パスの2段スイープをジェネレータに切り出す。

```python
from typing import Iterator

def frame_sweep(min_val: float, max_val: float, step: float = 2.0) -> Iterator[float]:
    """偶数パス → 奇数パスの順にフレーム値を列挙する。"""
    # 偶数パス
    v = min_val
    while v <= max_val:
        yield v
        v += step
    # 奇数パス（範囲幅が 0 ならスキップ）
    if min_val < max_val:
        v = min_val + 1
        while v <= max_val:
            yield v
            v += step

def dual_frame_sweep(
    f1_min: float, f1_max: float,
    f2_min: float, f2_max: float,
) -> Iterator[tuple[float, float]]:
    """Frame1 × Frame2 の2軸スイープ。"""
    for f2 in frame_sweep(f2_min, f2_max):
        for f1 in frame_sweep(f1_min, f1_max):
            yield f1, f2
```

**効果**: 元スクリプトの40行超のインクリメント条件分岐 → **ジェネレータ10行 + テスト容易**。

#### 10.1.5 レポート書き込みの統合

問題 5 に対する解法。`RegionTiming` にレポート用パラメータを持たせ、共通メソッド化。

```python
def _write_report(self, cmd: Command, timing: RegionTiming) -> None:
    """ゲーム内レポートを書く。"""
    cmd.wait(1.0)
    cmd.press(Button.B, dur=0.10, wait=2.00)
    cmd.press(Hat.DOWN, dur=0.10, wait=0.50)
    for _ in range(timing.report_a_presses):
        cmd.press(Button.A, dur=0.10, wait=timing.report_a_wait)
    cmd.press(Hat.UP, dur=0.10, wait=0.30)
    cmd.press(Button.A, dur=0.10, wait=8.50)
```

**効果**: 4ブロック（計40行超）の重複 → **6行の共通メソッド**。

### 10.2 クラス構成案

上記リファクタリングを反映したモジュール構成:

```
macros/
  frlg_id_rng.py           # メインマクロクラス
  frlg_id_rng/
    __init__.py
    region_timing.py        # RegionTiming dataclass + REGION_TIMINGS dict
    keyboard_layout.py      # RegionKeyboard / KeyboardLayout + 各リージョン定義
    frame_sweep.py          # frame_sweep / dual_frame_sweep ジェネレータ
    tid_recognizer.py       # OCR によるTID認識ロジック
```

```python
class FrlgIdRngMacro(MacroBase):
    description = "FRLG TID乱数調整マクロ"
    tags = ["pokemon", "frlg", "rng", "tid"]

    def initialize(self, cmd: Command, args: dict) -> None:
        self._timing = REGION_TIMINGS[args["region"]]
        self._keyboard = REGION_KEYBOARDS[args["region"]]
        self._roi = TID_ROIS[args["region"]]
        # ... 他の設定
    
    def run(self, cmd: Command) -> None:
        for current_f1, current_f2 in self._frame_iterator():
            self._soft_reset(cmd)
            self._wait_op(cmd)
            self._select_new_game(cmd)
            self._play_intro(cmd, self._timing)
            self._select_gender(cmd)
            self._wait_frames(cmd, current_f1)
            self._enter_trainer_name(cmd)
            self._wait_frames(cmd, current_f2)
            self._press_a_sequence(cmd, self._timing.name_confirm_sequence)
            self._enter_rival_name(cmd)
            self._press_a_sequence(cmd, self._timing.rival_confirm_sequence)
            self._wait_frames(cmd, self._frame3)
            self._start_game(cmd)
            tid = self._recognize_tid(cmd)
            if tid is None:
                continue
            if self._check_tid(cmd, tid, current_f1, current_f2):
                return

    def finalize(self, cmd: Command) -> None:
        cmd.release()
```

### 10.3 API マッピング

| 元スクリプト (NxInterface) | NyXフレームワーク (Command) |
|---------------------------|---------------------------|
| `Press(Button.A, 0.20, 1.30)` | `cmd.press(Button.A, dur=0.20, wait=1.30)` |
| `Press(Button.A, Button.B, ..., 0.30, 0.10)` | `cmd.press(Button.A, Button.B, ..., dur=0.30, wait=0.10)` |
| `Press(Direction.UP, 0.10, 0.30)` | `cmd.press(Hat.UP, dur=0.10, wait=0.30)` |
| `Wait(0.50)` | `cmd.wait(0.50)` |
| `GetCapture()` | `cmd.capture()` |
| `SaveCapture(name, x, y, w, h)` | `cmd.capture(crop_region=(x,y,w,h))` + `cmd.save_img(name, img)` |
| `IsContainTemplateMax(img, paths, ...)` | `ImageProcessor(img).get_text(language='en')` で5桁一括認識 |
| `GetLineNotifyToken()` → Discord POST | `cmd.notify(text, img)` |
| `Console.WriteLine(...)` | `cmd.log(...)` |

### 10.4 設計決定事項

| 項目 | 決定 | 備考 |
|------|------|------|
| **フレームタイマー** | `cmd.wait()` ベースで実装 | 精度不足が判明した場合に `time.perf_counter()` スピンウェイトを検討 |
| **TID認識** | PaddleOCR (`ImageProcessor.get_text()`) で5桁一括取得 | テンプレートマッチは不要。精度不足時のフォールバックとして参考に残す |
| **GC対応** | **スコープ外** | GC 固有のリセット手順・ROI・Y軸反転は移植しない |
| **VEGA対応** | **スコープ外** | VEGA 固有タイミング・配列は移植しない |
| **設定管理** | TOML ファイル経由 | `initialize()` の `args` dict で受け渡し |
| **キーボード入力** | 現行の直線移動をそのまま移植 | 最短経路最適化は行わない |
| **中断対応** | `cmd.stop()` / `CancellationToken` を活用 | メインループ各ステップで割り込みチェック |
| **命名規則** | PEP 8 準拠 | ユーティリティ関数は `snake_case`、クラスは `PascalCase` |

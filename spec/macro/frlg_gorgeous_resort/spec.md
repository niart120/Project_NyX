# FRLG ゴージャスリゾート アキホおねだり マクロ 仕様書

> **元ファイル**: `FRLGアキホおねだり自動化.csx`（C# Script / NX Macro Controller 向け）  
> **対象タイトル**: ポケットモンスター ファイアレッド・リーフグリーン (FRLG)  
> **目的**: ゴージャスリゾートのアキホに乱数調整済みのポケモンを見せ、報酬アイテムを自動収集する  
> **移植スコープ**: Switch (720p) のみ。GC 固有処理はスコープ外  
> **関連仕様**: アキホおねだりの乱数ロジック → `selphy_rewards.md`

---

## 1. 概要

ゲームのソフトリセット → 起動 → 初期Seed決定待機 → つづきからはじめる →
アキホに話しかけてポケモン決定フレームを合わせる → 要求ポケモンを見せる →
報酬アイテムを受け取る → レポート → ループ、という一連の操作を自動で繰り返す。

乱数調整により、アキホが要求するポケモンと報酬アイテムを事前に制御する。
ユーザーは `selphy_rewards.md` のフレーム検索ロジック等で、
目的のポケモン+アイテムが得られるフレーム帯を事前に特定したうえで本マクロを実行する。

> **前提**:
> - セーブデータは「ゴージャスリゾート」のアキホの目の前で保存済み
> - 手持ちにアキホが要求するポケモンが入っている
> - 話の速さは「はやい」に設定済み

---

## 1.1 用語定義

| 用語 | 定義 |
|------|------|
| **フレーム (F)** | 1/60 秒を 1F とする時間単位。`seconds = frames / fps`, `frames = seconds × fps` |
| **frame1** | ゲーム起動から初期Seed決定までの待機フレーム数。初期Seedリストから取得した値 |
| **frame2** | 初期Seed決定以降、ポケモン決定処理が走るフレームまでの待機フレーム数 |
| **frame1_offset** | frame1 に加算するユーザー調整オフセット (default: 0) |
| **frame2_offset** | frame2 に加算する補正値。プラットフォームごとの内部遅延を吸収する。（→ §2.2） |
| **fps** | フレームレート。Switch = 60.0 |
| **初期Seed** | ゲーム起動時に決定される 16bit の乱数初期値 |

---

## 2. 設定パラメータ

NyX 移植時は TOML 設定ファイルで管理し、`initialize()` の `args` dict 経由で受け取る。

### 2.1 基本設定

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `language` | `str` | `"JPN"` | 言語リージョン |
| `frame1` | `int` | `2347` | 初期Seed決定フレーム |
| `frame2` | `int` | `610` | ポケモン決定フレーム |
| `target_item` | `str` | `"ゴージャスボール"` | 目標アイテム。指定なしで無制限ループ |
| `target_count` | `int` | `9999` | 目標アイテムの収集数。到達時に停止 |
| `target_pokemon` | `list[str]` | `[]` | アキホに見せるポケモン名のリスト（日本語カタカナ）。OCR 突合に使用。いずれかに一致すれば OK |
| `pokedex` | `list[int]` | `[]` | 全国図鑑の登録済み番号リスト（例: `[1, 4, 7, 25, ...]`）。空の場合は図鑑チェックを省略 |
| `fps` | `float` | `60.0` | フレームレート |

### 2.2 フレーム補正

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `frame1_offset` | `int` | `0` | frame1 に加算する微調整オフセット |
| `frame2_offset` | `int` | `322` | frame2 に加算するプラットフォーム補正値 |

> **frame2_offset の由来**: 元スクリプトでは Switch の場合 `Frame2 += 322` を適用している。
> これはゲーム内部でポケモン決定処理が走るタイミングと、
> 直接指定するフレーム値との間に生じるプラットフォーム固有の遅延を補正するためである。

### 2.3 通知設定

通知は既存マクロと同じく `cmd.notify()` を使用する。

| イベント | 通知内容 |
|---------|---------|
| 処理開始 | `"アキホおねだりマクロを開始 ({target_item} ×{target_count})。ETA: {eta}"` |
| バッグ上限到達 | `"手持ちのアイテムが上限に達したため停止"` + スクリーンショット |
| 目標数到達 | `"目標数に到達: {item} {count}個"` + スクリーンショット |

### 2.4 図鑑登録データ (`pokedex`)

`pokedex` は全国図鑑番号のリストとして TOML 設定で指定する。

```toml
# settings.toml の例
pokedex = [1, 4, 7, 25, 26, 133, 134, 135, 136, 150, 151]
```

#### 用途

| 用途 | 説明 |
|------|------|
| **起動時バリデーション** | `target_pokemon` の各ポケモンが図鑑に登録済みか検証し、未登録なら WARNING を出力 |
| **フレーム検索の精度向上** | `selphy_rewards.md` §7 の検索ロジックに `pokedex` を渡すことで、実際の RNG 消費数を正確に再現可能 |
| **デバッグ支援** | ポケモン決定のシミュレーション結果と実機結果の差異を追跡可能 |

> **`pokedex` が空の場合**: 図鑑関連の検証・シミュレーションをすべてスキップする。
> マクロの基本動作（OCR 突合 + アイテム回収）には影響しない。

---

## 3. メインループ フロー

> **ループ**: Step 1〜9 を繰り返し、目標数に到達するかバッグ上限に達するまで継続する。

### Step 0: 初期化

- 設定読み込み
- frame2 に `frame2_offset` を加算
- ループカウンタ・アイテムカウンタを初期化
- OCR エンジンのウォームアップ（`OCRProcessor.get_instance("ja")`）
    - 初回 OCR 呼び出し時のモデルロード遅延を、メインループ開始前に吸収する
    - ウォームアップ直後にダミー画像または直近キャプチャで 1 回 `get_text(language="ja")` を実行し、推論パイプラインを事前初期化する
- `pokedex` が指定されている場合、以下の初期化処理を実行:
  1. 全国図鑑番号 → 内部コードへの変換テーブルを構築（`species_code.md` §3.3 参照）
  2. `target_pokemon` に含まれる各ポケモン名を全国図鑑番号に逆引きし、
     `pokedex` に登録されているか検証する。未登録のポケモンがあれば WARNING ログを出力
  3. 登録済み内部コード集合 (`pokedex_internal`) を構築し、
     フレーム検索ロジック (`selphy_rewards.md` §7) での事前検証に利用可能にする

```python
# OCR ウォームアップ
ocr = OCRProcessor.get_instance("ja")
ocr.get_text(np.full((64, 256, 3), 255, dtype=np.uint8), language="ja")

# pokedex 初期化処理の概要
if self._cfg.pokedex:
    pokedex_internal = {
        NATIONAL_TO_INTERNAL[n]
        for n in self._cfg.pokedex
        if n in NATIONAL_TO_INTERNAL
    }
    for name in self._cfg.target_pokemon:
        nat = NAME_TO_NATIONAL.get(name)
        if nat is None:
            cmd.log(f"target_pokemon '{name}' は不明なポケモン名です", level="WARNING")
        elif nat not in self._cfg.pokedex:
            cmd.log(f"target_pokemon '{name}' (No.{nat}) は図鑑未登録です", level="WARNING")
    cmd.log(f"図鑑登録数: {len(self._cfg.pokedex)}種 → 内部コード {len(pokedex_internal)}種", level="INFO")
```

#### ETA 見積りと開始通知

初期化の最後に、1ループあたりの所要時間を見積もり、`target_count` から全体の ETA を算出して通知する。
OCR ウォームアップは 1 回だけ発生する固定コストとして別管理し、ETA には加算して通知する。

```python
# --- 初期化時の固定コスト (seconds) ---
_OCR_WARMUP_SECONDS = 3.0  # 初回モデルロードとダミー推論の概算

# --- 1ループあたりの見積り時間 (seconds) ---
_OVERHEAD_RESTART = 4.35    # Step 1: HOME操作からタイマー開始まで
_OVERHEAD_POST    = 30.0    # Step 5〜9: 会話終了・受渡し・OCR・レポート・退出・再入場

t_frame1 = (self._cfg.frame1 + self._cfg.frame1_offset) / self._cfg.fps
t_frame2 = (self._cfg.frame2 + self._cfg.frame2_offset) / self._cfg.fps
t_loop = _OVERHEAD_RESTART + t_frame1 + t_frame2 + _OVERHEAD_POST

total_seconds = _OCR_WARMUP_SECONDS + (t_loop * self._cfg.target_count)
eta = datetime.now() + timedelta(seconds=total_seconds)
eta_str = eta.strftime("%Y-%m-%d %H:%M")
t_loop_str = f"{t_loop:.1f}"

cmd.log(
    f"OCRウォームアップ見積: {_OCR_WARMUP_SECONDS:.1f}s, "
    f"1ループ見積: {t_loop_str}s"
    f" × {self._cfg.target_count}回"
    f" = {total_seconds/60:.0f}分"
    f" (ETA: {eta_str})",
    level="INFO",
)
cmd.notify(
    f"アキホおねだりマクロを開始"
    f" ({self._cfg.target_item} ×{self._cfg.target_count})。"
    f" ETA: {eta_str}",
)
```

##### 見積り時間の内訳

| 要素 | 算出式 | 典型値 (frame1=2347, frame2=610, offset=322) |
|------|--------|-----|
| OCR ウォームアップ | `_OCR_WARMUP_SECONDS` 固定 | 3.0s |
| Step 1 再起動 | `_OVERHEAD_RESTART` 固定 | 4.35s |
| frame1 タイマー | `(frame1 + frame1_offset) / fps` | 39.1s |
| frame2 タイマー | `(frame2 + frame2_offset) / fps` | 15.5s |
| Step 5〜9 固定操作 | `_OVERHEAD_POST` 固定 | 30.0s |
| **1ループ合計** | | **≈ 89s** |
| **開始からの初回総所要時間** | `OCRウォームアップ + 1ループ合計` | **≈ 92s** |

> **見積りの前提**: 毎ループが成功（Step 6 の OCR 突合がパス）すると仮定している。
> ポケモン不一致によるリトライが発生すると実際の所要時間は増加する。
> `_OVERHEAD_POST` はレポート書き込み時間の変動等を含むマージン込みの概算値。
> `_OCR_WARMUP_SECONDS` も環境差が大きいため、実装後に実測値で更新すること。

### Step 1: ゲーム再起動（Switch）

初期Seedはゲームプロセス起動時に決定されるため、HOME メニュー経由でゲームを終了→再起動する。
`frlg_initial_seed` と同一のパターンを使用する。

```
HOME (dur=0.15, wait=1.00)   # ホームメニューに戻る
X    (dur=0.20, wait=0.60)   # ゲーム終了メニューを開く
A    (dur=0.20, wait=1.20)   # 終了を確定
A    (dur=0.20, wait=0.80)   # ホーム画面からゲームを再選択
                             # ★ t1 = _start_timer()
A    (dur=0.20)              # ゲーム起動
```

### Step 2: frame1 タイマー消化（初期Seed決定）

- タイマーは Step 1 のゲーム起動 A **直前**に開始済み (`t1`)
- `_consume_timer(cmd, t1, frame1 + frame1_offset, fps)` で消化
- **消化完了 = 初期Seed決定タイミング**

### Step 3: OP送り → つづきからはじめる → 回想スキップ → アキホに話しかける

frame1 タイマー消化完了直後に frame2 タイマーを開始し、
以降のゲーム内操作はすべて frame2 タイマー内で実行される。

```python
t2 = _start_timer()                           # ★ frame2 タイマー開始

cmd.press(Button.A, dur=3.50, wait=1.00)       # OPをAで飛ばす
cmd.press(Button.A, dur=0.20, wait=0.30)       # つづきからはじめる
cmd.press(Button.B, dur=1.00, wait=1.80)       # 回想をBで飛ばす

# アキホに話しかける（1回目：ポケモン決定処理をトリガー）
cmd.press(Button.A, dur=0.10, wait=0.70)       # 話しかけ
cmd.press(Button.B, dur=0.10, wait=0.70)       # テキスト送り
cmd.press(Button.B, dur=0.10, wait=0.50)       # テキスト送り
```

### Step 4: frame2 タイマー消化（ポケモン・アイテム決定）

```python
_consume_timer(cmd, t2, frame2 + frame2_offset, fps)  # ★ frame2 タイマー消化
```

> 消化完了時点でアキホの要求ポケモンと報酬アイテムが乱数から決定される。

### Step 5: 1回目の会話を終了し、改めてアキホに話しかける

ポケモン決定後、現在の会話を終了してからアキホに改めて話しかけ、
要求ポケモンの確認と受け渡しを行う。

```python
# 1回目の会話を終了
cmd.press(Button.B, dur=0.10, wait=0.60)
cmd.press(Button.B, dur=0.10, wait=0.60)
cmd.press(Button.B, dur=0.10, wait=0.30)

# 改めてアキホに話しかける
cmd.press(Button.A, dur=0.10, wait=0.90)
```

### Step 6: ポケモン確認（OCR）

アキホに2回目に話しかけた際のダイアログから、
要求されたポケモン名を OCR で読み取り、`target_pokemon` リスト内のいずれかと突合する。

- `target_pokemon` が空の場合、ポケモン名チェックをスキップして常に受理する
- リスト内のいずれかに一致すれば OK（OR 条件）

```python
recognized = self._recognize_requested_pokemon(cmd)
if self._cfg.target_pokemon:  # リストが空でなければ突合
    if recognized is None or not self._matches_any_target(recognized):
        cmd.log(
            f"{i}回目：要求={recognized or '認識失敗'}"
            f"（期待={self._cfg.target_pokemon}）リセット",
            level="INFO",
        )
        continue  # Step 1 へ戻る
cmd.log(f"{i}回目：要求={recognized} — OK", level="DEBUG")
```

#### 認識アルゴリズム

1. キャプチャ画像を取得
2. ダイアログ内のポケモン名表示領域 (`roi_pokemon_name`) をクロップ
3. 白パディングを付与
4. `ImageProcessor(padded).get_text(language="ja")` で日本語テキストを OCR
5. 認識結果を `target_pokemon` リスト内の各名前と突合

#### 突合ロジック

```python
def _matches_any_target(self, recognized: str) -> bool:
    """OCR 認識結果が target_pokemon リスト内のいずれかと一致するか判定する。"""
    for target in self._cfg.target_pokemon:
        if recognized == target:
            return True
        if _edit_distance(recognized, target) <= self._FUZZY_THRESHOLD:
            return True
    return False
```

| パラメータ | 値 | 備考 |
|-----------|-----|------|
| `_FUZZY_THRESHOLD` | `1` | 編集距離の許容閾値。1文字の誤認識まで許容 |

> **辞書突合との併用**: ファジー突合に加え、全ポケモン名辞書（386種）との最短編集距離マッチングも
> 有効な代替手段である。OCR 結果を辞書内の最近傍に正規化してから `target_pokemon` と比較すれば、
> 精度がさらに向上する。実装時に OCR 精度を実測して最適な方式を選定すること。

#### ポケモン名 ROI

Switch / JPN / 720p（実機計測で確定する）:

| ROI 名 | x | y | w | h | 用途 |
|--------|---|---|---|---|------|
| `roi_pokemon_name` | TBD | TBD | TBD | TBD | ダイアログ中のポケモン名表示領域 |

### Step 7: ポケモン受け渡し → アイテム受領

要求ポケモンが正しい場合、ダイアログを進めてポケモンを見せ、
セバスチャン（執事）経由で報酬アイテムを受け取る。

```python
# アキホとの会話を進める
for _ in range(7):
    cmd.press(Button.B, dur=0.10, wait=0.70)  # テキスト送り

# セバスチャン登場・アイテム受取
cmd.press(Button.B, dur=0.10, wait=0.70)   # セバスチャン会話
cmd.press(Button.B, dur=0.10, wait=0.80)
cmd.press(Button.B, dur=0.10, wait=0.50)
cmd.press(Button.B, dur=0.10, wait=2.50)   # アイテム渡しアニメーション
cmd.press(Button.B, dur=0.10, wait=0.40)
cmd.press(Button.B, dur=0.10, wait=2.00)   # アイテム取得テキスト表示
```

### Step 8: アイテム認識 → カウント更新

受け取ったアイテムを OCR で識別し、カウンタを更新する。

```python
item = self._recognize_item(cmd)
if item == "BAG_FULL":
    cmd.log("バッグが上限に達したため停止", level="INFO")
    cmd.notify("手持ちのアイテムが上限に達したため停止", img=cmd.capture())
    break

self._item_counters[item] += 1
cmd.log(f"{i}回目：{item} {self._item_counters[item]}個", level="INFO")
```

#### 認識アルゴリズム

1. キャプチャ画像を取得
2. アイテム取得テキスト表示領域 (`roi_item_name`) をクロップ
3. 白パディングを付与
4. `ImageProcessor(padded).get_text(language="ja")` で日本語テキストを OCR
5. 認識結果をアイテム名辞書と突合

#### アイテム名辞書

```python
ITEM_NAMES: list[str] = [
    "ゴージャスボール",
    "おおきなしんじゅ",
    "しんじゅ",
    "ほしのすな",
    "ほしのかけら",
    "きんのたま",
    "ふしぎなアメ",
]

BAG_FULL_KEYWORD = "おかばん"  # バッグ上限検出用
```

突合は辞書内の各アイテム名に対して**部分一致検索**で行う。
OCR 結果に辞書の文字列が含まれていれば該当アイテムと判定する。
長い名前から順に照合することで、「しんじゅ」と「おおきなしんじゅ」の包含関係を正しく処理する。

```python
def _match_item(self, ocr_text: str) -> str | None:
    # バッグ上限チェック
    if BAG_FULL_KEYWORD in ocr_text:
        return "BAG_FULL"

    # 長い名前から順に照合（部分一致）
    for name in sorted(ITEM_NAMES, key=len, reverse=True):
        if name in ocr_text:
            return name

    return None
```

> **フォールバック**: OCR が失敗（`None` 返却）した場合、アイテム不明としてログに記録するが、
> ループは継続する（アイテムカウンタは更新しない）。乱数調整でアイテムは事前に既知であるため、
> 認識失敗が頻発する場合はフレーム設定の見直しを促す。

#### アイテム名 ROI

Switch / JPN / 720p（実機計測で確定する）:

| ROI 名 | x | y | w | h | 用途 |
|--------|---|---|---|---|------|
| `roi_item_name` | TBD | TBD | TBD | TBD | アイテム取得テキスト表示領域 |

### Step 9: レポート書き → 退出 → 再入場

アイテム受領後、セーブデータに書き込み、一度外に出てから再入場することで次のループに備える。

```python
# 会話を終える
cmd.press(Button.B, dur=0.10, wait=0.30)

# 外に出る（Y軸反転に注意: DOWN で上方向に移動）
cmd.press(LStick.UP, dur=1.50, wait=2.20)

# アキホの家に再入場
cmd.press(LStick.DOWN, dur=3.30, wait=0.10)

# レポートを書く
cmd.press(Button.PLUS, dur=0.10, wait=0.30)
cmd.press(LStick.UP, dur=0.10, wait=0.10)     # ×3
cmd.press(LStick.UP, dur=0.10, wait=0.10)
cmd.press(LStick.UP, dur=0.10, wait=0.10)
cmd.press(Button.A, dur=0.10, wait=1.00)       # 「レポートをかく」
cmd.press(Button.A, dur=0.10, wait=1.00)       # 確認
cmd.press(LStick.UP, dur=0.10, wait=0.10)      # 「はい」を選択
cmd.press(Button.A, dur=0.10, wait=0.50)       # レポート書き込み実行

# レポート完了待ち（メッセージウィンドウ消失を監視）
while self._is_message_window_visible(cmd):
    cmd.press(Button.B, dur=0.10, wait=0.30)
```

> **移動方向**: 元スクリプトでは GBA の画面座標系で Y 軸が反転している。
> NyX では `LStick.UP` / `LStick.DOWN` がゲーム世界の上下に対応するため、
> 家から出るときは `LStick.UP`（画面座標的には下に移動して出口へ向かう）を使用する。
> 仕様検証時に実機で方向を確認すること。

### Step 10: 目標達成チェック

```python
if (
    self._cfg.target_item
    and self._item_counters.get(self._cfg.target_item, 0) >= self._cfg.target_count
):
    cmd.log(f"目標数に到達: {self._cfg.target_item} {self._cfg.target_count}個", level="INFO")
    cmd.notify(f"目標数に到達: {self._cfg.target_item} {self._cfg.target_count}個", img=cmd.capture())
    break
```

---

## 4. 画像認識

本マクロではテキスト情報の取得に **OCR** を、UI 状態の検出に **輝度判定** を使用する。

### 4.1 OCR によるテキスト認識

ポケモン名・アイテム名などゲーム内テキストの認識に使用する。
既存マクロ (`frlg_initial_seed`) と同じ `ImageProcessor` + PaddleOCR パターンを踏襲する。

```python
def _ocr_roi(self, cmd: Command, roi: tuple[int, int, int, int], pad: int = 40) -> str | None:
    """指定 ROI をクロップし、OCR でテキストを返す。"""
    image = cmd.capture()
    x, y, w, h = roi
    cropped = image[y : y + h, x : x + w]
    padded = cv2.copyMakeBorder(
        cropped, pad, pad, pad, pad,
        borderType=cv2.BORDER_CONSTANT,
        value=(255, 255, 255),
    )
    text = ImageProcessor(padded).get_text(language="ja")
    return text.strip() if text else None
```

| 項目 | 値 |
|------|-----|
| OCR エンジン | PaddleOCR (言語: `"ja"`) |
| 前処理 | `ImageProcessor` 内部で自動適用 (`enhance_for_ocr`) |
| 白パディング | 各辺 40px（OCR 精度向上） |
| 解像度 | 720p（NyX スコープ） |

### 4.2 輝度判定（UI 状態検出）

メッセージウィンドウの有無を、ROI 内の **平均輝度** で判定する。
メッセージウィンドウが表示されている場合、対象領域は白背景のため平均輝度が高くなる。
ウィンドウが消えるとゲーム画面（暗い色調）に戻るため、閾値で判別が可能。

```python
def _is_message_window_visible(self, cmd: Command) -> bool:
    """メッセージウィンドウの有無を ROI 内平均輝度で検出する。"""
    image = cmd.capture()
    roi = self._roi_message
    cropped = image[roi.y:roi.y+roi.h, roi.x:roi.x+roi.w]
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))
    return mean_brightness > self._MESSAGE_BRIGHTNESS_THRESHOLD
```

| パラメータ | 値 | 備考 |
|-----------|-----|------|
| `_MESSAGE_BRIGHTNESS_THRESHOLD` | `240` | 実機で閾値を調整。白背景 ≈ 250+、通常背景 ≈ 100〜180 |

### 4.3 ROI 定義

Switch / JPN / 720p:

| ROI 名 | x | y | w | h | 用途 | 方式 |
|--------|---|---|---|---|------|------|
| `roi_pokemon_name` | TBD | TBD | TBD | TBD | ダイアログ中のポケモン名 | OCR |
| `roi_item_name` | TBD | TBD | TBD | TBD | アイテム取得テキスト | OCR |
| `roi_message` | 1056 | 474 | 89 | 223 | メッセージウィンドウ検出 | 輝度 |

---

## 5. タイマー管理

`frlg_initial_seed` と同一のタイマーパターンを使用する。

```python
def _start_timer() -> float:
    return time.perf_counter()

def _consume_timer(cmd: Command, start_time: float, total_frames: float, fps: float) -> None:
    target_seconds = total_frames / fps
    elapsed = time.perf_counter() - start_time
    remaining = target_seconds - elapsed
    if remaining > 0:
        cmd.wait(remaining)
    elif remaining < -0.5:
        cmd.log(f"タイマー超過: {-remaining:.3f}秒", level="WARNING")
```

### タイマーポイント

| タイマー | 起点 | 終点 | 意味 |
|---------|------|------|------|
| **t1** (frame1) | ゲーム起動 A 直前 | Step 2 消化完了 | 初期Seed決定タイミング |
| **t2** (frame2) | frame1 消化完了直後 | Step 4 消化完了 | ポケモン・アイテム決定タイミング |

> frame1 タイマー内の操作（A ボタン押下等）はタイマーに自然吸収される。
> frame2 タイマー内の操作（OP 送り、つづきから、回想スキップ、アキホへの話しかけ）も
> タイマーに自然吸収される。

---

## 6. 注意事項・制約

### 6.1 移動方向の検証

元スクリプトでは Y 軸反転 (`Direction DOWN = Direction.UP`) が適用されている。
NyX の `LStick` 入力がゲーム世界のどちらに対応するかは実機検証で確認すること。

### 6.2 テンプレート画像

本マクロではテンプレート画像を**一切使用しない**。
すべてのテキスト認識は OCR、UI 状態検出は輝度判定で行う。

### 6.3 ROI の実機計測

以下の ROI は実機のスクリーンショットから座標を計測して確定する必要がある:

- `roi_pokemon_name` — アキホがポケモン名を提示するダイアログ領域
- `roi_item_name` — アイテム取得時のテキスト表示領域

### 6.4 スコープ外

| 項目 | 備考 |
|------|------|
| GC プラットフォーム対応 | 元スクリプトに GC 用リセット手順あり。必要時に拡張 |
| 1080p 解像度対応 | 720p のみ対応。1080p は ROI・テンプレ再計測が必要 |
| JPN 以外の言語対応 | 元スクリプトでも JPN のみ実装済み |
| フレーム検索ツール | `selphy_rewards.md` に定義。本マクロの前提入力 |
| ポケモン図鑑登録状況の自動取得 | `pokedex` パラメータで手動指定。画面からの自動取得は別途 |

---

## 7. ディレクトリ構成

既存マクロ (`frlg_initial_seed`, `frlg_id_rng`) と同一のパッケージ規約に従う。

### 7.1 全体構成

```
Project_NyX/
├── macros/
│   └── frlg_gorgeous_resort/       # マクロ実装パッケージ
│       ├── __init__.py             # パッケージ公開: FrlgGorgeousResortMacro
│       ├── macro.py                # メインマクロクラス (MacroBase 継承)
│       ├── config.py               # 設定 dataclass (§2 のパラメータ定義)
│       ├── recognizer.py           # OCR / 輝度判定ヘルパー (§4)
│       ├── selphy_logic.py         # アキホおねだりの実行時 RNG ロジック
│       ├── frame_search.py         # フレーム探索・連続区間検出ロジック
│       └── species_data.py         # ポケモンコードテーブル (species_code.md §3)
├── static/
│   └── frlg_gorgeous_resort/       # マクロ静的リソース
│       └── settings.toml           # デフォルト設定ファイル
└── spec/
    └── macro/
        └── frlg_gorgeous_resort/   # 仕様書 (本ディレクトリ)
            ├── spec.md             # マクロ操作仕様 (本文書)
            ├── selphy_rewards.md   # RNG コアロジック仕様
            └── species_code.md     # ポケモンコードマッピング
```

### 7.2 各ファイルの責務

#### `macros/frlg_gorgeous_resort/`

| ファイル | 責務 | 対応仕様 |
|---------|------|---------|
| `__init__.py` | パッケージ公開。`FrlgGorgeousResortMacro` を export | — |
| `macro.py` | `MacroBase` を継承したメインクラス。`initialize()` / `run()` / `finalize()` を実装。Step 0〜10 のメインループ全体を担う | §3 全体 |
| `config.py` | `@dataclass` による設定定義。TOML から読み込んだ値を型安全に保持 | §2 |
| `recognizer.py` | `_ocr_roi()`, `_is_message_window_visible()`, `_recognize_requested_pokemon()`, `_recognize_item()`, `_matches_any_target()` など画像認識系ヘルパー | §4 |
| `selphy_logic.py` | `determine_pokemon()`, `determine_item()`, `determine_reward()` など、アキホおねだりの RNG コアロジックを保持。`macro.py` はこのモジュールを呼び出すだけに留める | `selphy_rewards.md` §4〜§6 |
| `frame_search.py` | 初期 Seed・図鑑登録状況・フレーム範囲から結果一覧を生成する解析ロジック。連続フレーム検出もここに置く | `selphy_rewards.md` §7 |
| `species_data.py` | `INTERNAL_TO_NATIONAL`, `NATIONAL_TO_INTERNAL`, `NATIONAL_TO_NAME`, `is_dummy()` などポケモンコード変換テーブルとユーティリティ | `species_code.md` §3 |

#### `static/frlg_gorgeous_resort/`

| ファイル | 内容 |
|---------|------|
| `settings.toml` | §2 の全パラメータのデフォルト値を記述。`pokedex` は空リスト |

> **テンプレート画像ディレクトリ (`img/`)**: 本マクロでは不要（§6.2）。
> テンプレートマッチングを一切使用しないため、`img/` ディレクトリは作成しない。

### 7.3 `selphy_rewards` ロジックの実装方針

`selphy_rewards.md` の内容は、そのまま 1 ファイルに写すのではなく、用途ごとに以下のように分割して実装する。

| 仕様の範囲 | 実装先 | 理由 |
|------|------|------|
| ポケモン決定ロジック (§4) | `macros/frlg_gorgeous_resort/selphy_logic.py` | 実行時に直接使用するため |
| アイテム決定ロジック (§5) | `macros/frlg_gorgeous_resort/selphy_logic.py` | 実行時に直接使用するため |
| ポケモンコード変換 (§3) | `macros/frlg_gorgeous_resort/species_data.py` | データテーブルとして独立させるため |
| フレーム検索ロジック (§7) | `macros/frlg_gorgeous_resort/frame_search.py` | 当該マクロとドメイン的な関係性が強く、同一パッケージで保守するため |

> **結論**: `selphy_rewards` の「実行時に必要なロジック」は `macros/frlg_gorgeous_resort` 配下に置く。
> 「フレーム探索・連続区間検出」も同一ドメインロジックとして `macros/frlg_gorgeous_resort` 配下で一元管理する。

### 7.4 命名規約

| 項目 | 規約 | 例 |
|------|------|-----|
| パッケージ名 | `frlg_gorgeous_resort` (snake_case) | `macros/frlg_gorgeous_resort/` |
| メインクラス | `Frlg` + 機能名 + `Macro` (PascalCase) | `FrlgGorgeousResortMacro` |
| 設定クラス | 機能名 + `Config` | `FrlgGorgeousResortConfig` |
| `__init__.py` | メインクラスのみ export | `__all__ = ["FrlgGorgeousResortMacro"]` |

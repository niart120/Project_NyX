# FRLG 野生乱数操作 マクロ 仕様書

> **対象タイトル**: ポケットモンスター ファイアレッド・リーフグリーン (FRLG)
> **目的**: ゲームリセットから「あまいかおり」によるエンカウントまでの乱数調整 1 回分を自動で実行する
> **移植スコープ**: Switch (720p) のみ
> **関連仕様**: [ゴージャスリゾート仕様](../frlg_gorgeous_resort/spec.md)

---

## 1. 概要

### 1.1 目的

ゲームのソフトリセット → 起動 → 初期 Seed 決定待機 → つづきからはじめる → 回想スキップ →
フィールド操作可能 →（おしえテレビの消化: オプション）→ メニューから「あまいかおり」を実行、
という一連の乱数調整操作を自動化する。

ゲームリセットからエンカウント発生までの **1 回分** を実行して終了する（ループしない）。

> **前提**:
> - セーブデータはフィールド上（草むら等、あまいかおりが有効な場所）で保存済み
> - 手持ちの最下段に「あまいかおり」を覚えたポケモンを配置済み
> - 話の速さは「はやい」に設定済み

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| **frame** | 1/60 秒を 1F とする時間単位。`seconds = frames / fps` |
| **advance** | LCG32 の seed を 1 step 前進させる操作。1 advance = 1 回の乱数消費 |
| **frame1** | ゲーム起動から初期 Seed 決定までの待機フレーム数（時間フレーム） |
| **target_advance** | 初期 Seed 決定以降、あまいかおり実行時までの目標 RNG advance 数 |
| **frame1_offset** | frame1 に加算するユーザー調整オフセット（frame 単位） |
| **advance_offset** | target_advance に加算するプラットフォーム補正値（advance 単位） |
| **rng_multiplier** | 1 フレームあたりの RNG 消費倍率。Switch = 2 |
| **fps** | フレームレート。Switch = 60.0 |
| **初期 Seed** | ゲーム起動時に決定される 16bit の乱数初期値 |
| **おしえテレビ** | FRLG の「ポケモンおしえテレビ」。フィールドで Y ボタンにより起動し、B ボタンで閉じる。表示中は毎フレーム **313 adv/F (GC) / 314 adv/F (Switch)** の速度で乱数を消費する高速消費モードである。起動・終了時の暗転中は消費速度が異なる |
| **あまいかおり** | ポケモンの技。フィールドで使用すると野生ポケモンとのエンカウントが発生する |
| **timer0** | ゲーム起動から初期 Seed 決定までを管理するタイマー（= frame1 タイマー） |
| **timer1** | 初期 Seed 決定後からあまいかおり実行までを管理するタイマー（= advance タイマー） |
| **timer_teachy** | おしえテレビの起動〜終了間の待機を管理するタイマー。おしえテレビ使用時のみ有効。`teachy_tv_consumption` から逆算したフレーム数を元に操作タイミングを制御する |

---

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `macros/shared/game_restart.py` | 新規 | ゲーム再起動共通ヘルパー |
| `macros/shared/frlg_opening.py` | 新規 | FRLG OP スキップ〜回想スキップ共通ヘルパー |
| `macros/frlg_wild_rng/__init__.py` | 新規 | パッケージ初期化 |
| `macros/frlg_wild_rng/macro.py` | 新規 | メインマクロクラス |
| `macros/frlg_wild_rng/config.py` | 新規 | 設定パラメータ dataclass |
| `static/frlg_wild_rng/settings.toml` | 新規 | 設定ファイル |

---

## 3. 設計方針

### アルゴリズム概要

乱数調整の核心は **2 つ（+ オプションで 1 つ）のタイマー**による時間制御である。

- **timer0 (frame1)**: ゲーム起動 → 初期 Seed 決定
  - `wait = (frame1 + frame1_offset) / fps`
- **timer1 (advance)**: 初期 Seed 決定 → あまいかおり実行
  - `wait = effective_advance / (fps × rng_multiplier)`
  - `effective_advance = target_advance + advance_offset - teachy_advance`
  - おしえテレビによる高速消費分を差し引いた残りをフィールド待機で消化する
- **timer_teachy** (オプション): フィールド操作可能 → おしえテレビ終了
  - `teachy_frames = (teachy_tv_consumption - teachy_tv_transition_correction) / (teachy_tv_adv_per_frame - rng_multiplier)`
  - `wait = teachy_frames / fps`
  - ユーザーが指定した `teachy_tv_consumption`（消費アドバンス数）から必要なフレーム数を逆算し、おしえテレビの表示時間を制御する

timer0 の起動・終了タイミングおよび timer1 の起動タイミングはゴージャスリゾートマクロと同一である。

### タイマー構造

```
[ゲーム再起動]
  ├─ ★ timer0 開始 (A ボタン直前)
  ├─ A (ゲーム起動)
  ├─ ... timer0 消化 ...
  │
  ├─ ★ timer1 開始 (timer0 消化完了直後)
  ├─ A (OP スキップ)
  ├─ A (つづきからはじめる)
  ├─ B (回想スキップ)
  ├─ ── フィールド操作可能 ──
  │
  ├─ [おしえテレビあり]
  │   ├─ ★ timer_teachy 開始
  │   ├─ Y (おしえテレビ起動)
  │   ├─ ... timer_teachy 消化 (consumption から逆算したフレーム数) ...
  │   └─ B (おしえテレビ終了)
  │
  ├─ X (メニュー) → ポケモン選択 → あまいかおり選択
  ├─ ... timer1 消化 ...
  └─ A (あまいかおり実行)
```

### 性能要件

| 指標 | 目標値 |
|------|--------|
| タイマー精度 | `perf_counter` ベース。フレーム単位の精度を維持 |
| 1 回あたり所要時間 | frame1 設定値に依存（典型: 40〜80 秒） |

### レイヤー構成

```
macros/frlg_wild_rng/
├── __init__.py    # パッケージ公開
├── macro.py       # メインマクロクラス (MacroBase 継承)
└── config.py      # 設定 dataclass
```

本マクロは 1 回実行で完了するシンプルな構成のため、recognizer.py や追加のロジックモジュールは不要である。

### 再利用性・依存設計

| 依存先 | モジュール | 用途 |
|--------|-----------|------|
| `nyxpy.framework` | `MacroBase`, `Command`, `Button`, `LStick` | フレームワーク基盤 |
| `macros.shared.timer` | `start_timer()`, `consume_timer()` | フレーム精度タイマー |
| `macros.shared.game_restart` | `restart_game()` | ゲーム再起動（新規共通化） |
| `macros.shared.frlg_opening` | `skip_opening_and_continue()` | FRLG OP スキップ〜回想スキップ（新規共通化） |

#### ゲーム再起動の共通化

HOME → X → A → A → A のゲーム再起動手順は `frlg_gorgeous_resort`・`frlg_initial_seed` でも同一パターンが使われている（wait 値のみ若干異なる）。これを `macros/shared/game_restart.py` に切り出す。

```python
# macros/shared/game_restart.py
def restart_game(cmd: Command) -> float:
    """HOME メニュー経由でゲームを終了→再起動し、timer0 の開始時刻を返す。

    Returns:
        start_timer() による timer0 開始時刻
    """
    cmd.press(Button.HOME, dur=0.15, wait=1.00)
    cmd.press(Button.X, dur=0.20, wait=0.60)
    cmd.press(Button.A, dur=0.20, wait=1.20)
    cmd.press(Button.A, dur=0.20, wait=0.80)
    t0 = start_timer()
    cmd.press(Button.A, dur=0.20)
    return t0
```

- 戻り値として timer0 の開始時刻を返す（A ボタン直前に `start_timer()` を呼ぶパターンは全マクロ共通）
- `Command` のみに依存し、純粋な操作シーケンスとして切り出す
- 既存の `frlg_gorgeous_resort`・`frlg_initial_seed` も本関数への移行を推奨する（別タスク）

#### OP スキップ〜回想スキップの共通化

OP スキップ → つづきから → 回想スキップの操作シーケンスも `frlg_gorgeous_resort`・`frlg_initial_seed` で共通である。これを `macros/shared/frlg_opening.py` に切り出す。

```python
# macros/shared/frlg_opening.py
def skip_opening_and_continue(cmd: Command) -> float:
    """OP スキップ → つづきからはじめる → 回想スキップを実行し、timer1 の開始時刻を返す。

    frame1 タイマー消化完了直後に呼び出すこと。
    関数の入口で timer1 を開始し、OP スキップ〜回想スキップまでの操作を
    timer1 の中に吸収させる。

    Returns:
        start_timer() による timer1 開始時刻
    """
    t1 = start_timer()
    cmd.press(Button.A, dur=3.50, wait=1.00)   # OP スキップ
    cmd.press(Button.A, dur=0.20, wait=0.30)   # つづきからはじめる
    cmd.press(Button.B, dur=1.00, wait=1.80)   # 回想スキップ
    return t1
```

**設計上の判断**:

- **共通化の境界**: 回想スキップ完了（＝フィールド操作可能状態）まで。後続操作はマクロごとに異なる（アキホに話しかける / おしえテレビ / あまいかおり等）ため、ここが自然な分割点となる
- **timer1 の管理**: 関数入口で `start_timer()` を呼び、戻り値で返す。呼び出し元は `restart_game()` の `t0` と `skip_opening_and_continue()` の `t1` の 2 つのタイマー時刻を管理する構造になるが、いずれも `consume_timer()` で消化するだけのシンプルなパターンであり問題ない
- **dur / wait の調整**: 共通化した値が全マクロで十分に動作する前提とする。マクロ固有の調整が必要になった場合は、個別のラッパーを検討する
- 既存の `frlg_gorgeous_resort`・`frlg_initial_seed` も本関数への移行を推奨する（別タスク）

- 副作用（ボタン入力・待機）は `Command` 経由に集約し、設定値管理は `config.py` に分離する

---

## 4. 実装仕様

### 設定パラメータ

#### 4.1 基本設定

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `frame1` | `int` | `2036` | 初期 Seed 決定フレーム（時間フレーム） |
| `target_advance` | `int` | `2049` | あまいかおり実行時までの目標 RNG advance 数 |
| `fps` | `float` | `60.0` | フレームレート |

#### 4.2 フレーム・RNG 補正

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `frame1_offset` | `float` | `7.0` | frame1 に加算する微調整オフセット（frame 単位） |
| `advance_offset` | `int` | `-148` | target_advance に加算するプラットフォーム補正値（advance 単位） |
| `rng_multiplier` | `int` | `2` | 1 フレームあたりの RNG 消費倍率。Switch = 2 |

> **advance_offset / rng_multiplier の由来**: ゴージャスリゾートマクロと同一。
> 詳細は [ゴージャスリゾート仕様 §2.2](../frlg_gorgeous_resort/spec.md) を参照。

#### 4.3 おしえテレビ設定

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `use_teachy_tv` | `bool` | `false` | おしえテレビを使用する場合 `true` |
| `teachy_tv_consumption` | `int` | `0` | おしえテレビで消費する目標アドバンス数。フレーム数はマクロが自動算出。`use_teachy_tv=true` 時のみ有効 |
| `teachy_tv_adv_per_frame` | `int` | `314` | テレビ表示中の RNG 消費速度 (adv/frame)。Switch = 314, GC = 313 |
| `teachy_tv_transition_correction` | `int` | `-12353` | 暗転補正定数 $C$（実測値）。詳細は [calibration_log.md](./calibration_log.md) 参照 |

> **おしえテレビの乱数消費モデル**:
>
> ユーザーは `teachy_tv_consumption` でおしえテレビが消費する目標アドバンス数を指定する。
> マクロは必要なフレーム数を逆算する:
>
> ```
> teachy_frames = (teachy_tv_consumption - teachy_tv_transition_correction)
>               / (teachy_tv_adv_per_frame - rng_multiplier)
> ```
>
> `consume_timer(t1, ...)` は timer1 開始からの壁時計時間で管理しており、
> おしえテレビの表示時間中もフィールド消費速度で進んだとみなされる。
> そのため、`effective_advance` からは `teachy_tv_consumption` をそのまま差し引く:
>
> ```
> effective_advance -= teachy_tv_consumption
> ```
>
> `teachy_tv_transition_correction` ($C$) は、おしえテレビの開閉時の暗転中に
> 高速消費が行われないことによる補正定数である。
> $F$ を変えた複数回の実測から $a = 314$ adv/F を確認済み、
> $C = -12{,}353$ を導出した（詳細は [calibration_log.md](./calibration_log.md)）。
>
> `target_advance` には外部ツールの値をそのまま入力すればよく、
> おしえテレビの ON/OFF 切替時に変更する必要はない。

#### 待機時間の導出式

| タイマー | 導出式 |
|---------|--------|
| timer0 (frame1) | `(frame1 + frame1_offset) / fps` |
| timer1 (advance) | `effective_advance / (fps × rng_multiplier)` |
| timer_teachy | `teachy_frames / fps`　※ `teachy_frames` は `teachy_tv_consumption` から逆算 |

`effective_advance` の算出:

```
effective_advance = target_advance + advance_offset
if use_teachy_tv:
    effective_advance -= teachy_tv_consumption
```

`teachy_frames`（おしえテレビの待機フレーム数）の逆算:

```
teachy_frames = (teachy_tv_consumption - teachy_tv_transition_correction)
              / (teachy_tv_adv_per_frame - rng_multiplier)
```

### メインフロー

> **1 回実行**: Step 1 〜 Step 7 を順に実行し、あまいかおり発動後にマクロ終了。

#### Step 0: 初期化

- 設定読み込み (`config.py` の `FrlgWildRngConfig.from_args(args)`)
- `target_advance` に `advance_offset` を加算し、`rng_multiplier` から実効 fps を算出
- 所要時間の見積もりをログ出力

```python
def initialize(self, cmd: Command, args: dict) -> None:
    self._cfg = FrlgWildRngConfig.from_args(args)
    cfg = self._cfg

    self._advance_wait_fps = cfg.fps * cfg.rng_multiplier
    self._effective_advance = cfg.target_advance + cfg.advance_offset

    # おしえテレビによる消費分を差し引き、フレーム数を逆算
    if cfg.use_teachy_tv:
        self._teachy_tv_frames = (
            cfg.teachy_tv_consumption
            - cfg.teachy_tv_transition_correction
        ) / (cfg.teachy_tv_adv_per_frame - cfg.rng_multiplier)
        self._effective_advance -= cfg.teachy_tv_consumption

    # 見積り
    t_frame1 = (cfg.frame1 + cfg.frame1_offset) / cfg.fps
    t_advance = self._effective_advance / self._advance_wait_fps
    t_total = _OVERHEAD_RESTART + t_frame1 + t_advance + _OVERHEAD_POST
    cmd.log(f"見積り所要時間: {t_total:.1f}s", level="INFO")
```

##### 見積り時間の内訳

| 要素 | 算出式 | 典型値 (frame1=2347, target_advance=610) |
|------|--------|-----|
| ゲーム再起動 | `_OVERHEAD_RESTART` 固定 | ≈ 4.35s |
| frame1 タイマー | `(frame1 + frame1_offset) / fps` | ≈ 39.1s |
| advance タイマー | `(target_advance + advance_offset) / (fps × rng_multiplier)` | ≈ 7.8s |
| OP〜エンカウント操作 | `_OVERHEAD_POST` 固定 | ≈ 15s |
| **合計** | | **≈ 66s** |

#### Step 1: ゲーム再起動

HOME メニュー経由でゲームを終了→再起動する。共通ヘルパー `restart_game()` を使用する。

```python
from macros.shared.game_restart import restart_game

self._t0 = restart_game(cmd)  # ★ timer0 開始時刻が返る
```

`restart_game()` の内部操作（§3 再利用性・依存設計 参照）:

```
HOME (dur=0.15, wait=1.00)   # ホームメニューに戻る
X    (dur=0.20, wait=0.60)   # ゲーム終了メニューを開く
A    (dur=0.20, wait=1.20)   # 終了を確定
A    (dur=0.20, wait=0.80)   # ホーム画面からゲームを再選択
                             # ★ timer0 = start_timer()
A    (dur=0.20)              # ゲーム起動
```

#### Step 2: frame1 タイマー消化（初期 Seed 決定）

```python
consume_timer(cmd, self._t0, cfg.frame1 + cfg.frame1_offset, cfg.fps)
```

- timer0 を Step 1 のゲーム起動 A **直前**に開始済み
- **消化完了 = 初期 Seed 決定タイミング**

#### Step 3: OP スキップ → つづきからはじめる → 回想スキップ

frame1 タイマー消化完了直後に共通ヘルパー `skip_opening_and_continue()` を呼び出す。
関数内部で timer1（advance タイマー）が開始され、以降のゲーム内操作はすべて timer1 内で実行される。

```python
from macros.shared.frlg_opening import skip_opening_and_continue

t1 = skip_opening_and_continue(cmd)  # ★ timer1 開始時刻が返る
```

`skip_opening_and_continue()` の内部操作（§3 再利用性・依存設計 参照）:

```
★ timer1 = start_timer()
A    (dur=3.50, wait=1.00)   # OP を A で飛ばす
A    (dur=0.20, wait=0.30)   # つづきからはじめる
B    (dur=1.00, wait=1.80)   # 回想を B で飛ばす
# → フィールド操作可能状態
```

#### Step 4: おしえテレビ（オプション）

`use_teachy_tv = true` の場合のみ実行する。

```python
if cfg.use_teachy_tv:
    timer_teachy = start_timer()               # ★ timer_teachy 開始
    cmd.press(Button.Y, dur=0.10, wait=0.50)   # おしえテレビ起動
    consume_timer(cmd, timer_teachy, self._teachy_tv_frames, cfg.fps)  # 待機時間消化
    cmd.press(Button.B, dur=0.10, wait=1.00)   # おしえテレビ終了
```

| タイミング | 説明 |
|-----------|------|
| timer_teachy 開始 | フィールド操作可能状態になった直後、Y ボタン押下直前 |
| Y ボタン | おしえテレビを起動 |
| timer_teachy 消化 | `teachy_tv_consumption` から逆算した `teachy_frames / fps` 秒の経過を待つ |
| B ボタン | おしえテレビを閉じる |

> **おしえテレビの乱数消費**: おしえテレビの表示中は毎フレーム **314 adv/F (Switch) / 313 adv/F (GC)** の
> 速度で RNG が消費される（フィールドの 2 adv/F の 157 倍）。
> ユーザーが `teachy_tv_consumption` で消費量を指定すると、
> マクロが必要なフレーム数を自動算出し、おしえテレビの表示時間を制御する。
> 起動・終了時の暗転中は消費速度が異なるため、`teachy_tv_transition_correction` で補正する。
>
> マクロが初期化時におしえテレビの消費量を自動で `target_advance` から差し引くため、
> ユーザーは外部ツールの値をそのまま `target_advance` に入力すればよい。
> おしえテレビの ON/OFF 切替時に `target_advance` を変更する必要はない。

#### Step 5: メニュー操作 → あまいかおり選択

おしえテレビ終了後（おしえテレビなしの場合はフィールド操作可能状態から直接）、
メニューを開いてあまいかおりを選択する。

```python
cmd.press(Button.X, dur=0.10, wait=0.50)       # 1. メニューを開く
cmd.press(LStick.DOWN, dur=0.10, wait=0.30)    # 2. "ポケモン" にカーソル
cmd.press(Button.A, dur=0.10, wait=1.00)       # 3. ポケモンメニューを開く
cmd.press(LStick.UP, dur=0.10, wait=0.20)      # 4. カーソルを上に移動（ラップアラウンド開始）
cmd.press(LStick.UP, dur=0.10, wait=0.20)      # 5. 最下段（あまいかおり持ち）にカーソル
cmd.press(Button.A, dur=0.10, wait=0.30)       # 6. コンテキストメニューを開く
cmd.press(LStick.DOWN, dur=0.10, wait=0.20)    # 7. "あまいかおり" にカーソル
```

> **前提**: あまいかおりを覚えたポケモンは常に手持ちの最下段に配置する。
> ポケモンメニューを開くとカーソルは先頭にあるため、`LStick.UP × 2` でリストが
> ラップアラウンドして最下段に移動する。

#### Step 6: timer1 消化 → あまいかおり実行

あまいかおりにカーソルが合った状態で timer1（advance タイマー）の残り時間を消化し、
消化完了直後に A ボタンで実行する。

```python
# timer1 の残りを消化
consume_timer(cmd, t1, self._effective_advance, self._advance_wait_fps)

# あまいかおり実行
cmd.press(Button.A, dur=0.10)
```

> timer1 の総待機時間は `effective_advance / (fps × rng_multiplier)` である。
> おしえテレビ使用時は `effective_advance` から高速消費分が差し引かれているため、
> timer1 のフィールド待機は短くなる。
> Step 3 〜 Step 5 で費やした時間（おしえテレビの実時間含む）は timer1 に自然吸収されるため、
> ここでは残り時間のみを消化する。

#### Step 7: マクロ終了

あまいかおり実行後、エンカウント演出が始まった時点でマクロを終了する。

```python
cmd.log("あまいかおり実行完了 — エンカウント待ち", level="INFO")
```

### インターフェース

```python
class FrlgWildRngMacro(MacroBase):
    """FRLG 野生乱数操作マクロ (Switch 720p)"""

    description = "FRLG 野生乱数操作マクロ (Switch 720p)"
    tags = ["pokemon", "frlg", "rng", "wild"]

    def initialize(self, cmd: Command, args: dict) -> None:
        """設定ファイルを読み込み、タイマーパラメータを算出する。"""
        ...

    def run(self, cmd: Command) -> None:
        """ゲームリセット → あまいかおり実行までの一連の操作を実行する。"""
        ...

    def finalize(self, cmd: Command) -> None:
        """マクロ終了処理。"""
        ...
```

```python
@dataclass
class FrlgWildRngConfig:
    """FRLG 野生乱数操作マクロの設定"""

    frame1: int = 2036
    target_advance: int = 2049
    fps: float = 60.0
    frame1_offset: float = 7.0
    advance_offset: int = -148
    rng_multiplier: int = 2
    use_teachy_tv: bool = False
    teachy_tv_consumption: int = 0
    teachy_tv_adv_per_frame: int = 314
    teachy_tv_transition_correction: int = -12353

    @classmethod
    def from_args(cls, args: dict) -> FrlgWildRngConfig: ...
```

---

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_config_from_args_defaults` | `FrlgWildRngConfig.from_args({})` がデフォルト値を返すこと |
| ユニット | `test_config_from_args_override` | 各パラメータのオーバーライドが正しく反映されること |
| ユニット | `test_config_teachy_tv_disabled` | `use_teachy_tv=false` 時におしえテレビパラメータが無視されること |
| ユニット | `test_teachy_tv_advance_calculation` | おしえテレビのフレーム逆算が正しいこと |
| ユニット | `test_effective_advance_with_teachy_tv` | おしえテレビありの effective_advance が正しく差し引かれること |
| ユニット | `test_timer_wait_calculation` | `(frame1 + frame1_offset) / fps` の算出が正しいこと |
| ユニット | `test_advance_wait_calculation` | `(target_advance + advance_offset) / (fps × rng_multiplier)` の算出が正しいこと |
| ユニット | `test_restart_game_returns_timer` | `restart_game()` が `float` を返し `start_timer()` 相当の時刻であること |
| ユニット | `test_skip_opening_returns_timer` | `skip_opening_and_continue()` が `float` を返し `start_timer()` 相当の時刻であること |
| 実機 | `test_wild_rng_no_teachy_tv` | おしえテレビなしでエンカウントまでの操作が正常に動作すること |
| 実機 | `test_wild_rng_with_teachy_tv` | おしえテレビありでエンカウントまでの操作が正常に動作すること |

---

## 6. 実装チェックリスト

- [ ] `macros/shared/game_restart.py` 作成（ゲーム再起動共通ヘルパー）
- [ ] `macros/shared/frlg_opening.py` 作成（OP スキップ〜回想スキップ共通ヘルパー）
- [ ] `static/frlg_wild_rng/settings.toml` 作成
- [ ] `macros/frlg_wild_rng/__init__.py` 作成
- [ ] `macros/frlg_wild_rng/config.py` 実装
- [ ] `macros/frlg_wild_rng/macro.py` 実装
- [ ] 共通部品の再利用確認（`macros.shared.timer` + `macros.shared.game_restart` + `macros.shared.frlg_opening` を使用）
- [ ] 既存マクロ (`frlg_gorgeous_resort`, `frlg_initial_seed`) の `_restart_game` / OP スキップを共通ヘルパーに移行（別タスク）
- [ ] ユニットテスト作成・パス（`config.py` は Command なしでテスト）
- [ ] 実機動作確認（おしえテレビなし）
- [ ] 実機動作確認（おしえテレビあり）
- [ ] ボタン dur / wait の実機チューニング

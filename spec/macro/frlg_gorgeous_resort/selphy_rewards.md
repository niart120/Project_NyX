# ゴージャスリゾート アキホおねだり コアロジック 仕様書

> **対象タイトル**: ポケットモンスター ファイアレッド・リーフグリーン (FRLG)  
> **目的**: アキホが要求するポケモンと報酬アイテムの決定に係る乱数処理を定義する  
> **スコープ**: コアロジック（ポケモン決定・アイテム決定）のみ。自動化操作処理は別途整理する  
> **参考**:
> - [毒電波にご注意を — アキホおねだりの乱数処理と自動化](https://dokudenpa.hatenablog.jp/entry/ResortGorgeousMonAndReward)
> - [改造ポケモン制作資料 Wiki — ポケモンコード](https://wikiwiki.jp/pokemonhack/%E3%83%9D%E3%82%B1%E3%83%A2%E3%83%B3%E3%82%B3%E3%83%BC%E3%83%89)

---

## 1. 概要

ゴージャスリゾートの NPC **アキホ** に話しかけると、指定されたポケモンを見せることで
報酬アイテムを受け取れるイベントが発生する。
要求ポケモンと報酬アイテムはいずれも **LCG32 の乱数値** によって決定される。

処理の流れ:

```
[話しかけ] → [ポケモン決定] → [アイテム決定] → [要求提示]
```

1. **ポケモン決定**: LCG の乱数値から内部コードを算出し、全国図鑑の登録状況と照合して要求ポケモンを決定する
2. **アイテム決定**: ポケモン決定の直後に消費される乱数値から報酬アイテムを決定する

プレイヤーは **250 歩以内** に要求ポケモンを見せる必要がある。
見せられなかった場合は再度話しかけて別のポケモンが要求される（再抽選）。

---

## 2. LCG32（線形合同法）

第3世代共通の乱数生成器。詳細は → `spec/macro/frlg_initial_seed/seed_solver.md` §2

$$
\text{seed}_{n+1} = (\text{0x41C64E6D} \times \text{seed}_n + \text{0x6073}) \bmod 2^{32}
$$

$$
\text{rand}(\text{seed}) = (\text{seed} \gg 16)\ \&\ \text{0xFFFF}
$$

本仕様では `rand` は上記の上位 16bit 値を指し、
`GetRand()` は seed を 1 step 前進させたうえで `rand` を返す操作を指す。

---

## 3. ポケモン内部コード

### 3.1 定義

第3世代では各ポケモンに全国図鑑番号とは**別の内部コード**が割り当てられている。

| 属性 | 値 |
|------|-----|
| 有効範囲 | `0x0001` 〜 `0x019B` (1 〜 411) |
| ダミーコード | `0x00FC` 〜 `0x0114` (252 〜 276, **25 個**) |
| 実ポケモン数 | 411 − 25 = **386** 種 |

ダミーコード（25 個）は未使用の内部コードであり、対応するポケモンが存在しない。

### 3.2 内部コードと全国図鑑番号の対応（抜粋）

内部コードは全国図鑑番号と一致しない。以下に主要な対応例を示す。

| 内部コード | 図鑑No. | ポケモン名 |
|-----------|---------|-----------|
| `0x0001` | 001 | フシギダネ |
| `0x0019` | 025 | ピカチュウ |
| `0x0006` | 006 | リザードン |
| `0x0097` | 151 | ミュウ |
| `0x00FB` | 251 | セレビィ |
| `0x00FC` 〜 `0x0114` | — | (ダミー) |
| `0x0115` | 252 | キモリ |
| `0x019A` | 386 | デオキシス |
| `0x019B` | 358 | チリーン |

> 完全な対応表は [ポケモンコード一覧](https://wikiwiki.jp/pokemonhack/%E3%83%9D%E3%82%B1%E3%83%A2%E3%83%B3%E3%82%B3%E3%83%BC%E3%83%89) を参照。

---

## 4. ポケモン決定ロジック

### 4.1 アルゴリズム

```
入力: 現在の LCG seed, 全国図鑑の登録状況
出力: 要求ポケモンの内部コード
```

```python
MAX_RETRY = 100
NUM_SPECIES_CODES = 411  # 0x019B

def determine_pokemon(lcg: LCG32, pokedex: set[int]) -> int:
    """アキホが要求するポケモンの内部コードを決定する。

    Args:
        lcg: 現在の乱数状態（破壊的に前進する）
        pokedex: 全国図鑑に登録済みのポケモンの内部コードの集合

    Returns:
        決定されたポケモンの内部コード
    """
    # Phase 1: 乱数による抽選（最大100回）
    for _ in range(MAX_RETRY):
        rand_value = lcg.get_rand()
        species_code = (rand_value % NUM_SPECIES_CODES) + 1
        if species_code in pokedex:
            return species_code

    # Phase 2: フォールバック — 登録済みポケモンを逆順検索
    for code in range(NUM_SPECIES_CODES, 0, -1):
        if code in pokedex:
            return code

    raise RuntimeError("図鑑に登録済みポケモンが1匹もいない")
```

### 4.2 処理の詳細

#### Phase 1: 乱数抽選

1. `GetRand()` で乱数値を取得（seed が 1 step 前進）
2. 内部コードを算出:

$$
\text{species\_code} = (\text{rand} \bmod 411) + 1
$$

3. 算出された内部コードに対応するポケモンが**全国図鑑に登録済み**かを判定
   - **登録済み** → そのポケモンを採用し、Phase 1 終了
   - **未登録** → 手順 1 に戻り再抽選
   - **ダミーコード** (`0x00FC`〜`0x0114`) → 対応するポケモンが存在しないため未登録と同等に扱われる
4. 最大 **100 回** まで再抽選する

> **乱数消費**: 未登録ポケモンが多いほど乱数消費数が増加する。
> 1 回の抽選で 1 消費し、N 回目で決定した場合、ポケモン決定だけで計 N 消費となる。

#### Phase 2: フォールバック

Phase 1 で 100 回試行しても登録済みポケモンが見つからなかった場合、
内部コード `0x019B` (411) から `0x0001` (1) への**逆順走査**で最初に見つかった
登録済みポケモンを採用する。

> この処理はほぼ発生しない。
> 図鑑登録数が極端に少ない状態でのみ到達し得るが、実用上は考慮不要。

### 4.3 図鑑登録状況の影響

| 状態 | 挙動 |
|------|------|
| 登録数が多い | 1〜数回の乱数消費でポケモンが決定される。フレームごとに異なるポケモンが選ばれやすい |
| 登録数が少ない | 乱数消費回数が増加する。また、**連続する複数フレームで同じポケモンが選ばれやすい** |
| ダミーコード該当 | 未登録と同じ扱い。乱数を 1 余分に消費して再抽選 |

> **乱数調整上のポイント**: 未登録ポケモンが多いほど、
> ポケモン決定に使われる乱数消費数が変動しやすく、
> 同一ポケモン・同一アイテムが連続するフレーム帯が出現しやすい。

---

## 5. アイテム決定ロジック

### 5.1 アルゴリズム

ポケモン決定の**直後**に 1 回 `GetRand()` して報酬アイテムを決定する。

```python
def determine_item(lcg: LCG32) -> str:
    """報酬アイテムを決定する。

    ポケモン決定直後の LCG 状態から呼び出すこと。

    Args:
        lcg: 現在の乱数状態（破壊的に前進する）

    Returns:
        アイテム名
    """
    rand_value = lcg.get_rand()
    value = rand_value % 100

    if value >= 30:
        return "ゴージャスボール"

    return ITEM_TABLE[value // 5]
```

### 5.2 アイテムテーブル

| `value` の範囲 | `value // 5` | アイテム | 確率 |
|----------------|-------------|---------|------|
| 0 〜 4 | 0 | おおきなしんじゅ | 5% |
| 5 〜 9 | 1 | しんじゅ | 5% |
| 10 〜 14 | 2 | ほしのすな | 5% |
| 15 〜 19 | 3 | ほしのかけら | 5% |
| 20 〜 24 | 4 | きんのたま | 5% |
| 25 〜 29 | 5 | ふしぎなアメ | 5% |
| 30 〜 99 | — | **ゴージャスボール** | **70%** |

> `value = rand_upper16 % 100` の値が **30 以上**であればゴージャスボールが選ばれる。
> 30 未満の場合は `value // 5` をインデックスとして上表のアイテムが決定される。

### 5.3 Python 定数定義

```python
ITEM_TABLE: list[str] = [
    "おおきなしんじゅ",   # 0: 0-4   (5%)
    "しんじゅ",           # 1: 5-9   (5%)
    "ほしのすな",         # 2: 10-14 (5%)
    "ほしのかけら",       # 3: 15-19 (5%)
    "きんのたま",         # 4: 20-24 (5%)
    "ふしぎなアメ",       # 5: 25-29 (5%)
]

LUXURY_BALL = "ゴージャスボール"  # 30-99 (70%)
```

---

## 6. 乱数消費まとめ

1 回のイベント（話しかけ → 要求ポケモン＋アイテム決定）で消費される乱数の総数:

$$
\text{消費数} = N_{\text{pokemon}} + 1_{\text{item}}
$$

| 要素 | 消費数 | 備考 |
|------|--------|------|
| ポケモン決定 | $N$ 回 ($1 \leq N \leq 100$) | 図鑑未登録による再抽選分を含む |
| アイテム決定 | 1 回 | ポケモン決定の直後に固定 1 消費 |
| **合計** | $N + 1$ | |

> **ポケモン決定に要する乱数消費が連続フレームで同数になる場合**、
> ポケモンとアイテムがセットで同一結果に収束する。
> これは乱数調整において安定性を高める要素となる。

---

## 7. フレーム検索ロジック

乱数調整ツールとして、指定した初期 Seed + フレーム範囲に対して
ポケモンとアイテムの全組み合わせを列挙する検索ロジックを以下に示す。

### 7.1 アルゴリズム

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AkihoResult:
    """1フレーム分のアキホおねだり結果"""
    frame: int
    species_code: int       # 内部コード
    species_name: str       # ポケモン名
    item: str               # アイテム名
    rng_pokemon_consumed: int  # ポケモン決定で消費した乱数回数


def search_akiho_frames(
    initial_seed: int,
    pokedex: set[int],
    frame_min: int,
    frame_max: int,
    species_name_map: dict[int, str],
) -> list[AkihoResult]:
    """指定フレーム範囲でアキホおねだりの結果を全列挙する。

    Args:
        initial_seed: 16bit 初期Seed（0x0000〜0xFFFF）
        pokedex: 図鑑登録済みポケモンの内部コード集合
        frame_min: 検索開始フレーム
        frame_max: 検索終了フレーム
        species_name_map: 内部コード→ポケモン名の辞書

    Returns:
        各フレームの結果リスト
    """
    results: list[AkihoResult] = []

    for frame in range(frame_min, frame_max + 1):
        # フレームごとに seed を初期状態から前進させる
        lcg = LCG32(initial_seed)
        lcg.advance(frame)

        # ポケモン決定
        pokemon_consumed = 0
        species_code = 0

        for attempt in range(MAX_RETRY):
            rand_value = lcg.get_rand()
            pokemon_consumed += 1
            code = (rand_value % NUM_SPECIES_CODES) + 1
            if code in pokedex:
                species_code = code
                break
        else:
            # フォールバック: 逆順検索
            for code in range(NUM_SPECIES_CODES, 0, -1):
                if code in pokedex:
                    species_code = code
                    break

        # アイテム決定
        rand_value = lcg.get_rand()
        value = rand_value % 100
        if value >= 30:
            item = LUXURY_BALL
        else:
            item = ITEM_TABLE[value // 5]

        results.append(AkihoResult(
            frame=frame,
            species_code=species_code,
            species_name=species_name_map.get(species_code, "???"),
            item=item,
            rng_pokemon_consumed=pokemon_consumed,
        ))

    return results
```

### 7.2 連続フレーム検出

乱数調整の安定性を高めるため、**同一ポケモン＋同一アイテムが連続するフレーム帯**を
検出する機能が有用である。

```python
def find_consecutive_runs(
    results: list[AkihoResult],
    min_run_length: int = 5,
) -> list[list[AkihoResult]]:
    """同一ポケモン+アイテムが min_run_length 以上連続する区間を返す。"""
    runs: list[list[AkihoResult]] = []
    current_run: list[AkihoResult] = []

    for result in results:
        if (
            current_run
            and current_run[-1].species_code == result.species_code
            and current_run[-1].item == result.item
        ):
            current_run.append(result)
        else:
            if len(current_run) >= min_run_length:
                runs.append(current_run)
            current_run = [result]

    if len(current_run) >= min_run_length:
        runs.append(current_run)

    return runs
```

> 参考元ツールでは連続数 **5** を強調表示の閾値としている。

---

## 8. 注意事項・制約

### 8.1 アイテム分岐の実装精度

本仕様書のアイテム決定ロジック（§5）における `value < 30` 時の分岐（`value // 5` でインデックス算出）は、参考記事の記述と確率分布から推定したものである。実際の ROM コードにおいて閾値ベースの分岐（`if/else` チェーン）で実装されている可能性がある。いずれの場合も各アイテム 5%・ゴージャスボール 70% の確率分布は同一である。

### 8.2 スコープ外

以下は本仕様書のスコープ外とし、別途整理する。

| 項目 | 備考 |
|------|------|
| 初期 Seed 決定のフレーム合わせ | → `frlg_initial_seed/spec.md` に準ずる |
| ポケモン決定フレームへの操作手順 | 自動化操作処理として別仕様書で定義 |
| 250 歩制限のカウント処理 | ゲーム内部処理。乱数ロジックとは独立 |
| 図鑑登録状況の画像認識・自動取得 | 自動化操作における入力手段の問題 |
| 内部コード ↔ 全国図鑑番号の完全変換テーブル | 外部リソース参照。実装時にデータとして保持 |

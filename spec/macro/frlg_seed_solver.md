# FRLG 初期Seed逆算ロジック 仕様書

> **関連マクロ**: FRLG 初期Seed特定マクロ (`frlg_initial_seed.md`)  
> **対象タイトル**: ポケットモンスター ファイアレッド・リーフグリーン (FRLG)  
> **目的**: 画像認識で取得した性格・実数値から、16bit 初期Seed を逆算する  
> **元実装**: `初期Seed特定.csx` の `DetermineInitialSeed()` 関数

---

## 1. 概要

本ドキュメントでは、FRLG 初期Seed特定マクロの中核ロジックである
**初期Seed逆算処理（Seed Solver）** を独立した仕様として定義する。

処理の流れは以下の3段階で構成される:

```
[入力] → [個体生成シミュレーション] → [突合判定] → [出力]
```

1. **入力**: 画像認識で取得した性格名・6ステータスの実数値 + 対象ポケモンの種族値・レベル + 探索フレーム範囲 `[min_advance, max_advance]`
2. **個体生成シミュレーション**: 16bit 初期Seed 全候補 (0x0000〜0xFFFF) × `[min_advance, max_advance]` の各組み合わせについて、LCG32 で PID・IV を生成
3. **突合判定**: 生成した PID から得られる性格と、IV から算出される実数値が観測値と一致するかを照合
4. **出力**: 一致した候補が **ちょうど1つ** なら、その初期Seedを返す

---

## 2. LCG32（線形合同法）

### 2.1 定義

FRLG（第3世代）の乱数生成器は **32bit 線形合同法 (LCG)** である。  
PokemonPRNG ライブラリの `StandardLCG` パッケージに相当する。

$$
\text{seed}_{n+1} = (A \times \text{seed}_n + C) \bmod 2^{32}
$$

| 定数 | 名前 | 値 |
|------|------|-----|
| $A$ | 乗数 | `0x41C64E6D` |
| $C$ | 加算 | `0x00006073` |

乱数値は上位 16bit を取り出して使用する:

$$
\text{rand}(\text{seed}) = (\text{seed} \gg 16)\ \&\ \text{0xFFFF}
$$

### 2.2 PokemonPRNG API との対応

元実装が使用する `PokemonPRNG.LCG32.StandardLCG` の API と、Python 移植時の対応を示す。

| PokemonPRNG API | 動作 | Python 実装 |
|-----------------|------|-------------|
| `seed.Advance(n)` | seed を `n` step 前進（破壊的） | `lcg.advance(n)` |
| `seed.Back(n)` | seed を `n` step 後退（破壊的） | `lcg.back(n)` |
| `seed.GetRand()` | `Advance(1)` + 上位 16bit を返す | `lcg.get_rand()` |
| `seed.NextSeed(n)` | `n` step 先の seed を返す（非破壊） | `lcg.peek(n)` |
| `seed.PrevSeed(n)` | `n` step 前の seed を返す（非破壊） | `lcg.peek_back(n)` |
| `seed.GetIndex(initial)` | 初期 seed からの消費数を計算 | （必要に応じて実装） |

### 2.3 Python 実装（LCG32）

```python
class LCG32:
    """GBA ポケモン用 32bit 線形合同法 乱数生成器"""

    A: int = 0x41C64E6D
    C: int = 0x00006073
    MASK: int = 0xFFFFFFFF

    # 逆方向用定数 (A_INV ≡ A^(-1) mod 2^32, C_INV ≡ -C × A^(-1) mod 2^32)
    A_INV: int = 0xEEB9EB65
    C_INV: int = 0x0A3561A1

    def __init__(self, seed: int) -> None:
        self._seed = seed & self.MASK

    @property
    def seed(self) -> int:
        return self._seed

    def advance(self, n: int = 1) -> None:
        """seed を n step 前進させる。"""
        for _ in range(n):
            self._seed = (self.A * self._seed + self.C) & self.MASK

    def back(self, n: int = 1) -> None:
        """seed を n step 後退させる。"""
        for _ in range(n):
            self._seed = (self.A_INV * self._seed + self.C_INV) & self.MASK

    def get_rand(self) -> int:
        """Advance(1) してから上位 16bit を返す。"""
        self.advance()
        return (self._seed >> 16) & 0xFFFF
```

> **Note**: `A_INV` と `C_INV` は以下の関係を満たす:
> $$A \times A_{\text{INV}} \equiv 1 \pmod{2^{32}}$$
> $$C_{\text{INV}} = (-C \times A_{\text{INV}}) \bmod 2^{32}$$
>
> これにより `Back` は `Advance` の逆操作として正しく機能する。

---

## 3. 個体生成ロジック（第3世代 野生/固定シンボル）

### 3.1 生成順序

FRLG の固定シンボル（手持ちポケモン）は、以下の順で LCG から乱数を消費して個体値を決定する。

```
seed[F] → GetRand() → lid (PIDの下位16bit)
seed[F+1] → GetRand() → hid (PIDの上位16bit)
seed[F+2] → GetRand() → hab (HP / Attack / Defense のIV)
seed[F+3] → GetRand() → scd (Speed / SpecialAttack / SpecialDefense のIV)
```

合計 **4回** の乱数消費で 1体分の個体が決定される。

### 3.2 PID（性格値）の構成

```
PID = lid | (hid << 16)
```

| フィールド | ビット範囲 | 乱数消費 |
|-----------|-----------|---------|
| 下位 16bit (lid) | PID[15:0] | 1回目の `GetRand()` |
| 上位 16bit (hid) | PID[31:16] | 2回目の `GetRand()` |

PID から以下が決定される:

| 属性 | 算出方法 |
|------|---------|
| **性格** | `PID % 25` → 性格ID (§3.5) |
| 性別 | `PID & 0xFF` と性別比率の比較（本マクロでは未使用） |
| 色違い判定 | TID/SID との XOR（本マクロでは未使用） |

### 3.3 IV（個体値）のビットパッキング

2つの 16bit 乱数値に 6 ステータス分の IV (各5bit) がパッキングされている。

**`hab` (3回目の GetRand)**:

| ビット範囲 | IV |
|-----------|-----|
| `hab & 0x1F` (bit 4:0) | HP |
| `(hab >> 5) & 0x1F` (bit 9:5) | Attack |
| `(hab >> 10) & 0x1F` (bit 14:10) | Defense |

**`scd` (4回目の GetRand)**:

| ビット範囲 | IV |
|-----------|-----|
| `scd & 0x1F` (bit 4:0) | Speed |
| `(scd >> 5) & 0x1F` (bit 9:5) | SpecialAttack |
| `(scd >> 10) & 0x1F` (bit 14:10) | SpecialDefense |

> 各 IV は $0 \leq IV \leq 31$ の範囲を取る。

### 3.4 コード表現

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Pokemon:
    """LCG から生成された個体のデータ"""
    pid: int
    nature_id: int
    iv_hp: int
    iv_atk: int
    iv_def: int
    iv_spa: int
    iv_spd: int
    iv_spe: int

    def calc_stats(
        self,
        base_stats: tuple[int, int, int, int, int, int],
        level: int,
        nature_multipliers: dict[str, float],
    ) -> tuple[int, int, int, int, int, int]:
        """種族値・レベル・性格補正から実数値 (HP, Atk, Def, SpA, SpD, Spe) を算出する。"""
        b_hp, b_atk, b_def, b_spa, b_spd, b_spe = base_stats

        hp = ((2 * b_hp + self.iv_hp) * level) // 100 + level + 10

        def _calc(base: int, iv: int, mult: float) -> int:
            return int(((2 * base + iv) * level // 100 + 5) * mult)

        atk = _calc(b_atk, self.iv_atk, nature_multipliers["Attack"])
        def_ = _calc(b_def, self.iv_def, nature_multipliers["Defense"])
        spa = _calc(b_spa, self.iv_spa, nature_multipliers["SpecialAttack"])
        spd = _calc(b_spd, self.iv_spd, nature_multipliers["SpecialDefense"])
        spe = _calc(b_spe, self.iv_spe, nature_multipliers["Speed"])

        return (hp, atk, def_, spa, spd, spe)


def generate_pokemon(lcg: LCG32) -> Pokemon:
    """現在の LCG 状態から個体を1体生成する。

    LCG を 4step 消費する。
    """
    lid = lcg.get_rand()
    hid = lcg.get_rand()
    hab = lcg.get_rand()
    scd = lcg.get_rand()

    pid = lid | (hid << 16)

    return Pokemon(
        pid=pid,
        nature_id=pid % 25,
        iv_hp=hab & 0x1F,
        iv_atk=(hab >> 5) & 0x1F,
        iv_def=(hab >> 10) & 0x1F,
        iv_spe=scd & 0x1F,
        iv_spa=(scd >> 5) & 0x1F,
        iv_spd=(scd >> 10) & 0x1F,
    )
```

### 3.5 性格ID テーブル

| ID | 性格 (EN) | 性格 (JP) | ID | 性格 (EN) | 性格 (JP) | ID | 性格 (EN) | 性格 (JP) |
|----|-----------|----------|----|-----------|----------|----|-----------|----------|
| 0 | Hardy | がんばりや | 9 | Lax | のうてんき | 18 | Bashful | てれや |
| 1 | Lonely | さみしがり | 10 | Timid | おくびょう | 19 | Rash | うっかりや |
| 2 | Brave | ゆうかん | 11 | Hasty | せっかち | 20 | Calm | おだやか |
| 3 | Adamant | いじっぱり | 12 | Serious | まじめ | 21 | Gentle | おとなしい |
| 4 | Naughty | やんちゃ | 13 | Jolly | ようき | 22 | Sassy | なまいき |
| 5 | Bold | ずぶとい | 14 | Naive | むじゃき | 23 | Careful | しんちょう |
| 6 | Docile | すなお | 15 | Modest | ひかえめ | 24 | Quirky | きまぐれ |
| 7 | Relaxed | のんき | 16 | Mild | おっとり | | | |
| 8 | Impish | わんぱく | 17 | Quiet | れいせい | | | |

### 3.6 性格補正テーブル

性格は攻撃・防御・特攻・特防・素早さのうち2つに上昇 ($\times 1.1$) と下降 ($\times 0.9$) の補正を与える。
無補正性格（Hardy / Docile / Serious / Bashful / Quirky）は全ステータス $\times 1.0$。

| 性格 | 上昇 (×1.1) | 下降 (×0.9) |
|------|-------------|-------------|
| Lonely | Attack | Defense |
| Brave | Attack | Speed |
| Adamant | Attack | SpecialAttack |
| Naughty | Attack | SpecialDefense |
| Bold | Defense | Attack |
| Relaxed | Defense | Speed |
| Impish | Defense | SpecialAttack |
| Lax | Defense | SpecialDefense |
| Timid | Speed | Attack |
| Hasty | Speed | Defense |
| Jolly | Speed | SpecialAttack |
| Naive | Speed | SpecialDefense |
| Modest | SpecialAttack | Attack |
| Mild | SpecialAttack | Defense |
| Quiet | SpecialAttack | Speed |
| Rash | SpecialAttack | SpecialDefense |
| Calm | SpecialDefense | Attack |
| Gentle | SpecialDefense | Defense |
| Sassy | SpecialDefense | Speed |
| Careful | SpecialDefense | SpecialAttack |

---

## 4. ステータス実数値計算

### 4.1 計算式

ゲーム内で表示されるステータスの実数値は、種族値・個体値・レベル・性格補正から以下の式で算出される。

#### HP

$$
\text{Stat}_{\text{HP}} = \left\lfloor \frac{(2 \times B_{\text{HP}} + IV_{\text{HP}}) \times Lv}{100} \right\rfloor + Lv + 10
$$

#### HP 以外（Atk / Def / SpA / SpD / Spe）

$$
\text{Stat} = \left\lfloor \left( \left\lfloor \frac{(2 \times B + IV) \times Lv}{100} \right\rfloor + 5 \right) \times M \right\rfloor
$$

| 記号 | 説明 |
|------|------|
| $B$ | 種族値 (Base Stat) |
| $IV$ | 個体値 ($0 \leq IV \leq 31$) |
| $Lv$ | レベル |
| $M$ | 性格補正倍率 ($0.9$ / $1.0$ / $1.1$) |

> **Note**: 努力値 (EV) は 0 を前提とする。捕獲直後の個体に対する処理のため。

### 4.2 突合での使い方: 順方向変換

突合時には、LCG から生成された IV を上記の式で**実数値に順方向変換**し、画像認識で得た観測値と `==` で直接比較する。

元実装（`初期Seed特定.csx`）では実数値 → IV 範囲への**逆変換**を行っていたが、
NyX 移植ではこれを採用せず、より素直な順方向変換方式を用いる。

| 方式 | 処理 | 判定 |
|------|------|------|
| **逆変換（元実装）** | 観測実数値 → IV 許容範囲 `[min, max]` を事前計算 | `min <= iv <= max` の範囲比較 |
| **順方向変換（NyX）** | LCG から得た IV → 実数値を計算 | `calc == observed` の等価比較 |

順方向変換のメリット:
- 逆変換関数 (`iv_range_hp`, `iv_range_stat`) が不要 — IV 0〜31 の全探索ロジックが消える
- 事前計算ステップが不要 — 前処理なしで本体ループに直行できる
- 突合が `==` 比較のみで済み、ロジックが単純明快
- `Pokemon.calc_stats()` メソッドに計算を閉じ込められるため、テストも容易

`Pokemon.calc_stats()` の実装は §3.4 を参照。

### 4.3 対象ポケモンのパラメータ

本マクロのデフォルト対象はルギア (Lv.70)。

| ステータス | 種族値 |
|-----------|--------|
| HP | 106 |
| Attack | 90 |
| Defense | 130 |
| SpecialAttack | 90 |
| SpecialDefense | 154 |
| Speed | 110 |

> 対象ポケモンをマクロ設定で変更可能にすることで、他のポケモンへの汎用性を確保できる。

---

## 5. 突合処理（Seed Solver）

### 5.1 入力

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `nature` | `str` | 画像認識で取得した性格名（英語名） |
| `stats` | `tuple[int, ...]` | 画像認識で取得した6ステータスの実数値 (HP, Atk, Def, SpA, SpD, Spe) |
| `base_stats` | `tuple[int, ...]` | 対象ポケモンの種族値 (HP, Atk, Def, SpA, SpD, Spe) |
| `level` | `int` | 対象ポケモンのレベル |
| `min_advance` | `int` | 探索フレーム下限（閉区間） |
| `max_advance` | `int` | 探索フレーム上限（閉区間） |

### 5.2 処理フロー

```
Step 1: 性格補正倍率を取得
Step 2: 16bit Seed 全探索 × フレーム範囲走査
Step 3: 各候補で個体生成 → 実数値を順方向計算 → 観測値と突合
Step 4: 一致候補数に応じて結果を返す
```

前処理は性格補正倍率の取得のみ。IV 逆変換の事前計算は不要。

#### Step 2〜3: 全探索 + 個体生成 + 突合

```python
def solve_initial_seed(
    nature: str,
    observed_stats: tuple[int, int, int, int, int, int],
    base_stats: tuple[int, int, int, int, int, int],
    level: int,
    min_advance: int,
    max_advance: int,
) -> str:
    """初期Seedを逆算する。

    Args:
        nature: 画像認識で取得した性格名 (英語名)
        observed_stats: 画像認識で取得した実数値 (HP, Atk, Def, SpA, SpD, Spe)
        base_stats: 対象ポケモンの種族値 (HP, Atk, Def, SpA, SpD, Spe)
        level: 対象ポケモンのレベル
        min_advance: 探索フレーム下限（閉区間）
        max_advance: 探索フレーム上限（閉区間）

    Returns:
        "XXXX"          -- 一意に特定できた場合 (4桁 HEX)
        "False"         -- 候補が見つからない場合
        "MultipleSeeds" -- 候補が2つ以上ある場合
    """
    nature_id = NATURE_TO_ID[nature]
    nature_mult = get_nature_multipliers(nature)

    result_count = 0
    result_seed = ""

    for initial_seed in range(0x10000):  # 0x0000 .. 0xFFFF
        lcg = LCG32(initial_seed)
        lcg.advance(min_advance)

        for f in range(min_advance, max_advance + 1):
            pokemon = generate_pokemon(lcg)

            if _matches(pokemon, nature_id, nature_mult,
                        observed_stats, base_stats, level):
                result_count += 1
                result_seed = f"{initial_seed:04X}"

            # generate_pokemon で 4step 進んだので 3step 戻る → 差分 +1
            lcg.back(3)

    if result_count == 0:
        return "False"
    elif result_count == 1:
        return result_seed
    else:
        return "MultipleSeeds"
```

#### Step 3 詳細: 突合判定 (`_matches`)

```python
def _matches(
    pokemon: Pokemon,
    expected_nature_id: int,
    nature_mult: dict[str, float],
    observed_stats: tuple[int, int, int, int, int, int],
    base_stats: tuple[int, int, int, int, int, int],
    level: int,
) -> bool:
    """生成された個体の実数値が観測値と一致するか判定する。"""
    # 1. 性格の早期棄却（96% がここで弾かれる）
    if pokemon.nature_id != expected_nature_id:
        return False

    # 2. IV → 実数値を順方向計算し、観測値と直接比較
    calc_stats = pokemon.calc_stats(base_stats, level, nature_mult)
    return calc_stats == observed_stats
```

判定順序:
1. **性格の一致**: `PID % 25 == expected_nature_id` — 不一致なら即棄却（25分の24の確率で棄却できるため高速）
2. **実数値の一致**: `Pokemon.calc_stats()` で IV → 実数値を順方向計算し、6ステータスの **tuple 同士を `==` で直接比較**

### 5.3 探索空間

| 軸 | 範囲 | 候補数 |
|----|------|--------|
| 初期Seed | `0x0000` 〜 `0xFFFF` | 65,536 |
| フレーム | `min_advance` 〜 `max_advance` | `max_advance - min_advance + 1` |
| **合計** | | $65{,}536 \times (\text{max\_advance} - \text{min\_advance} + 1)$ |

デフォルト設定 (`min_advance = 741`, `max_advance = 749`) では $65{,}536 \times 9 = 589{,}824$ 回の個体生成・突合となる。
性格の不一致で大半が即棄却されるため、実質的な計算コストは軽い。

### 5.4 元実装のパリティフィルタについて

元スクリプトでは Switch 環境限定で `FrameParity` パラメータにより偶数フレーム / 奇数フレームのみを探索する**パリティフィルタ**が実装されていた。

```csharp
// 元実装のパリティフィルタ（削除対象）
if (parity != "all")
{
    uint actualFrame = Frame2 - Range + frameOffset;
    if ((parity == "even" && actualFrame % 2 != 0) ||
        (parity == "odd"  && actualFrame % 2 == 0))
    {
        seed.Advance(1);
        continue;
    }
}
```

NyX 移植ではこのフィルタを**採用しない**。理由:
- フィルタの根拠が不明確であり、特定のハードウェア環境への経験的な最適化と推測される
- フィルタにより本来一致するべきSeedを見逃すリスクがある
- `[min_advance, max_advance]` の探索幅（デフォルト 9 フレーム）程度であれば全探索しても計算コストは無視できる

NyX では `min_advance` 〜 `max_advance` の**全フレームを無条件に探索**する。

### 5.5 結果の解釈

| 返却値 | 意味 | マクロ側の対応 |
|--------|------|---------------|
| `"XXXX"` (4桁 HEX) | 初期Seedが一意に特定された | 結果をファイルに書き込み、次のフレームへ進む |
| `"False"` | 一致する候補が見つからなかった | Frame2 補正 (+2) してリトライ |
| `"MultipleSeeds"` | 候補が2つ以上あり一意に絞れなかった | Frame2 補正 (+2) してリトライ |

> `"False"` / `"MultipleSeeds"` が返る主な原因は、画像認識の誤り、または Frame2 タイマーのズレ。
> Frame2 を +2 してリトライすることで自動補正される（→ `frlg_initial_seed.md` §5）。

---

## 6. Advance/Back による走査の仕組み

### 6.1 初期位置の設定

各初期Seed候補について、まず個体決定フレーム範囲の先頭まで LCG を前進させる。

```python
lcg = LCG32(initial_seed)
lcg.advance(start_frame)      # start_frame = min_advance
```

この時点で LCG の内部状態は `seed[start_frame]` に位置する。

### 6.2 フレームオフセットのイテレーション

`generate_pokemon()` は LCG を 4step 消費する。
次のフレームオフセットでは 前回より +1 の位置から開始したいため、`back(3)` で 3step 戻る。

```
offset=0: seed[S]     → GetRand×4 → seed[S+4] → Back(3) → seed[S+1]
offset=1: seed[S+1]   → GetRand×4 → seed[S+5] → Back(3) → seed[S+2]
offset=2: seed[S+2]   → GetRand×4 → seed[S+6] → Back(3) → seed[S+3]
...
```

これにより、$S, S+1, S+2, \ldots, S+2R$ の各フレーム位置について個体生成が行われる。

> **パリティフィルタを削除した場合**: 元実装で skip 分岐にあった `Advance(1)` が不要になり、
> 全フレームで `generate_pokemon()` → `back(3)` の統一パスとなる。ロジックが簡潔になる。

---

## 7. 計算例

### 7.1 入力条件

| 項目 | 値 |
|------|-----|
| 対象 | ルギア Lv.70 |
| 性格 | Adamant (いじっぱり, ID=3) |
| HP | 238 |
| Attack | 149 |
| Defense | 189 |
| SpecialAttack | 130 |
| SpecialDefense | 229 |
| Speed | 162 |
| Frame2 | 745 |
| min_advance | 741 |
| max_advance | 749 |

### 7.2 突合の流れ

性格 Adamant の補正: Attack ×1.1, SpecialAttack ×0.9

ある候補 Seed + フレームから生成された個体が以下だったとする:

| ステータス | 種族値 | IV (LCG生成) | 補正 | 計算結果 | 観測値 | 一致? |
|-----------|--------|-------------|------|---------|--------|------|
| HP | 106 | 15 | — | 238 | 238 | ✓ |
| Attack | 90 | 8 | ×1.1 | 149 | 149 | ✓ |
| Defense | 130 | 3 | ×1.0 | 189 | 189 | ✓ |
| SpecialAttack | 90 | 20 | ×0.9 | 130 | 130 | ✓ |
| SpecialDefense | 154 | 12 | ×1.0 | 229 | 229 | ✓ |
| Speed | 110 | 5 | ×1.0 | 162 | 162 | ✓ |

→ `calc_stats == observed_stats` が `True` → この候補がヒット

### 7.3 探索全体

```
探索空間: 65,536 seeds × 9 frames (741〜749) = 589,824 候補
→ 性格で約 96% を即棄却
→ 残り約 23,593 候補について calc_stats → == 比較
→ 通常は 0〜1 個に絞り込まれる
```

---

## 8. NyX 実装時の設計指針

### 8.1 モジュール構成

```
macros/
  frlg_initial_seed/
    seed_solver.py      # solve_initial_seed() — 本ドキュメントのメイン処理
    lcg32.py            # LCG32 クラス
    pokemon_gen.py      # generate_pokemon(), Pokemon dataclass (calc_stats 含む)
    nature.py           # NATURE_TO_ID, get_nature_multipliers()
```

> 元実装にあった `stat_calc.py` (IV 逆変換関数) は不要。順方向変換は `Pokemon.calc_stats()` に集約。

### 8.2 テスト方針

| テスト観点 | 内容 |
|-----------|------|
| LCG32 の前進・後退 | 既知の seed シーケンスとの照合 |
| generate_pokemon | 既知の seed から期待される PID/IV が生成されること |
| Pokemon.calc_stats | 既知の IV・種族値・レベル・性格に対する実数値の正しさ |
| solve_initial_seed | 既知の初期Seed + Frame2 に対して正しい Seed が返ること |
| solve_initial_seed (異常系) | 不正な実数値 → `"False"` / 複数候補 → `"MultipleSeeds"` |

### 8.3 パフォーマンス

- 全探索 $65{,}536 \times 9 = 589{,}824$ 回は Python でも 1 秒未満で完了する見込み
- 性格の早期棄却により実質的な `calc_stats` 呼び出しは全体の約 4% (≒ $1/25$)
- `calc_stats` は四則演算のみで構成されるため、1回あたりのコストは極めて低い
- それでも不足する場合は NumPy によるベクトル化や、C拡張の検討が可能

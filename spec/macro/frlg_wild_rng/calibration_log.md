# おしえテレビ消費モデル キャリブレーション記録

> **関連仕様**: [spec.md](./spec.md) §4.3 おしえテレビ設定

---

## 1. 目的

おしえテレビの乱数消費モデルに含まれるパラメータを実測により決定する。

- **消費速度** $a$ (adv/frame): テレビ表示中のフレームあたり RNG 消費数
- **暗転補正定数** $C$: おしえテレビの開閉時の暗転により高速消費が行われない区間の影響を表す定数

---

## 2. モデル

### 2.1 超過消費量の式

`consume_timer(t1, ...)` はフィールド上の消費速度 ($r$ = `rng_multiplier` = 2 adv/F) を前提に
壁時計時間で管理している。おしえテレビ使用時に差し引くべきは **フィールド基準との超過分**:

$$\text{teachy\_excess} = (a - r) \times F + C$$

- $a$: テレビ表示中の消費速度 (adv/frame)
- $r$: フィールド消費速度 = `rng_multiplier` = 2 (adv/frame)
- $F$: `teachy_tv_frames`（Y→B 間のフレーム数）
- $C$: 暗転補正定数 = `teachy_tv_transition_correction`

### 2.2 測定式

`transition_correction = 0` と仮置きしてマクロを実行し、hit した advance を特定する:

$$\Delta = \text{hit} - \text{target\_advance}$$

$$\Delta = \text{advance\_offset} + (a - 314) \times F + C$$

$F$ を変えた複数回の測定で連立方程式を解く:

$$a - 314 = \frac{\Delta_2 - \Delta_1}{F_2 - F_1}$$
$$C = \Delta_1 - \text{advance\_offset} - (a - 314) \times F_1$$

### 2.3 パラメータの分離不能性

当初は 2 パラメータ構成 (`transition_offset` / `transition_advance`) で管理していたが、
超過消費量の式に含まれるのは合成量 $C = T_{\text{adv}} - a \cdot T_{\text{off}}$ のみであり、
$F$ を変えても $T_{\text{off}}$ と $T_{\text{adv}}$ を個別に分離することはできない。
（分離には $a$ が異なる条件での測定が必要だが、Switch 固定では不可能。）

∴ 1 パラメータ `teachy_tv_transition_correction` ($= C$) に統合。

---

## 3. 測定条件

### 共通設定

| パラメータ | 値 |
|---|---|
| `frame1` | 2276 |
| `fps` | 60.0 |
| `frame1_offset` | 7.0 |
| `advance_offset` | -148 |
| `rng_multiplier` | 2 |
| `teachy_tv_adv_per_frame` | 314 |
| `transition_correction` (仮置き) | 0 |

> `advance_offset = -148` はおしえテレビ OFF の状態で事前にキャリブレーション済み。

---

## 4. 測定結果

| # | $F$ (frames) | target_advance | hit advance | $\Delta$ | timer1 概算 | $C$ |
|---|---|---|---|---|---|---|
| M1 | 120 | 40,000 | 27,489 | -12,511 | ~20s | -12,363 |
| M2 | 300 | 100,000 | 87,499 | -12,501 | ~52s | -12,353 |
| M3 | 120 | 44,000 | 31,499 | -12,501 | ~53s | -12,353 |
| M4 | 120 | 50,000 | 37,503 | -12,497 | ~103s | -12,349 |

$C$ の算出: $C = \Delta - \text{advance\_offset} - (a - 314) \times F$

$a = 314$ の場合: $C = \Delta - (-148) = \Delta + 148$

---

## 5. 分析

### 5.1 消費速度 $a$ の確認

M1 と M2 から:

$$a - 314 = \frac{(-12{,}501) - (-12{,}511)}{300 - 120} = \frac{10}{180} = 0.056$$

$a$ は整数（フレームごとの LCG 呼び出し回数）のため $a = 314$ が確認された。
差の 10 advance は測定ノイズ（§5.2 参照）。

### 5.2 $C$ の変動分析

| 仮説 | 予測 | 実測との整合性 |
|---|---|---|
| $C$ は timer1 長さに比例するドリフト | M4 ($103\text{s}$) で $C \approx -12{,}331$ | **否定** ($C = -12{,}349$) |
| $C$ は $F$ に依存 | M3 ($F=120$) で $C \approx -12{,}363$（M1 と同じ） | **否定** ($C = -12{,}353$) |
| $C$ は定数 + ランダムノイズ | $C \approx -12{,}355 \pm 8$ | **整合** |

4 点の統計:
- 平均: -12,354.5
- 全幅: 14 advance（= 7 ゲームフレーム）
- timer1 を 20s → 103s（5 倍）に変えても全幅はほぼ変わらない

### 5.3 ノイズ源の考察

10〜14 advance のばらつきは 5〜7 ゲームフレーム分に相当する。
主なノイズ源は以下の通り:

- `consume_timer` のフレーム境界におけるボタンタイミングのゆらぎ
  - A（あまいかおり）が 1F ずれると ±2 advance
  - B（おしえテレビ終了）のずれは timer1 に吸収されるが、フレーム境界の不確かさは残る
- hit 特定時の不確かさ（±1〜2 advance）

---

## 6. 結論

| パラメータ | 決定値 | 精度 |
|---|---|---|
| $a$ (`teachy_tv_adv_per_frame`) | **314** adv/F | 確定 |
| $C$ (`teachy_tv_transition_correction`) | **-12,353** | ±8 advance |

> 実装では $C = -12{,}353$ を採用。実運用時の hit 精度は ±8 advance 程度のばらつきを含む。

# FRLG 初期Seed特定マクロ — スコープ外機能 仕様書

> **関連マクロ**: [frlg_initial_seed.md](frlg_initial_seed.md)（Phase 1 仕様）  
> **対象タイトル**: ポケットモンスター ファイアレッド・リーフグリーン (FRLG)  
> **目的**: Phase 1 で除外した機能の仕様を保全し、将来の Phase 2 以降で実装する際の参照とする  
> **元ファイル**: `初期Seed特定.csx`（C# Script / NX Macro Controller 向け）

---

## 1. 本ドキュメントの位置づけ

Phase 1 仕様書 (`frlg_initial_seed.md`) のスコープは **Switch (720p) での初期Seed収集** に限定されている。
本ドキュメントでは、元スクリプトに存在したが Phase 1 から除外された以下の機能を記録する。

| 機能 | Phase | 備考 |
|------|-------|------|
| GC 固有処理 | 未定 | ハードウェア依存のリセット手順・FPS・ROI |
| 1080p 固有 ROI | 未定 | Switch Dock モード対応 |
| キー入力調査モード | Phase 2 | 独立した仕様書として整備予定 |
| 海外版 (ENG/ESP/ITA/FRA/NOE) 固有補正 | 未定 | frame2 補正・ROI 差分 |
| 設定EXE連携 (`SkipSettingsExe`) | — | NyX では不要（TOML 設定で代替） |
| Shift_JIS / TXT 出力 | — | UTF-8 CSV に統一 |

---

## 2. GC 固有処理

### 2.1 リセット手順

GC（GBA Player 経由）では HOME メニューリセットではなく、以下のシーケンスでリセットする。

```
ZR   (dur=0.10, wait=0.30)
A    (dur=0.20, wait=0.50)
←    (dur=0.10, wait=0.30)
A    (dur=0.20, wait=0.50)
A    (dur=0.20, wait=0.50)
PLUS+Y (dur=3.50, wait=0.50)   # GBA Player リセット
```

### 2.2 タイマー開始の差異

GC では frame1 タイマー開始後に追加の `A(dur=0.20)` が必要。

```
リセットシーケンス完了
  ↓ ← ★ t1 = _start_timer()
  A(dur=0.20)              # GC 固有の追加 A press
  [frame1 フレーム分を計測・消化]
  ↓ ← ★ _consume_timer(t1, frame1 + frame1_offset, fps)
OP送り: A(dur=3.50, wait=1.00)
```

### 2.3 GC 固有パラメータ

| パラメータ | GC デフォルト | Switch デフォルト | 差異の理由 |
|-----------|---------------|-------------------|-----------|
| `fps` | `59.7275` | `60.0` | GBA Player のフレームレート |
| `frame2` | `430` | `745` | ゲーム処理速度の差 |
| `frame2_offset` | `0` | `0` | ユーザー調整用（Phase 1 で default:0 に変更） |
| `min_advance` | `428` | `741` | `frame2 ± 2` 相当 |
| `max_advance` | `432` | `749` | 同上 |

### 2.4 海外版補正

`Region ≠ "JPN"` の場合、frame2 にリージョン固有の補正値を加算する（元スクリプトでは `Frame2Offset -= 7`）。
これはゲーム内テキスト処理のフレーム消費量がリージョンによって異なるため。

---

## 3. 1080p 固有 ROI

Switch Dock モード (1080p) では、720p の ROI 座標を 1.5 倍にスケーリングする必要がある。
Phase 1 では 720p のみをサポートし、1080p ROI は未定義。

| 項目 | 720p | 1080p (推定) |
|------|------|-------------|
| 性格 ROI | `(197, 519, 86, 43)` | `(296, 779, 129, 65)` |
| ステータス ROI (HP) | `(1016, 95, 121, 45)` | `(1524, 143, 182, 68)` |
| その他ステータス | §6.3 参照 | 1.5 倍スケーリング |

> **Note**: 1080p の ROI は実機スクリーンショットでの検証が必要。単純な 1.5 倍では
> サブピクセルのズレが起こる可能性があるため、微調整が発生しうる。

---

## 4. キー入力調査モード

### 4.1 概要

GBA の FRLG は、ゲーム起動〜ロード中にコントローラの入力状態（十字キー↓長押し、A長押しなど）が
あると、RNG の進行パスが変わり初期Seed に影響する。
キー入力調査モードは、このパターンを系統的にテストし
「この入力パターンの時にどの Seed が出るか」を記録するモードである。

元スクリプトでは `active_tab = 1` で切り替えていた。

### 4.2 キー入力パターン

| パターン | 説明 |
|---------|------|
| `"起動時から十字キー"` | 起動直後から↓を 1825F 長押し |
| `"起動時からA"` | 起動直後から A を 1825F 長押し |
| `"暗転から十字キー"` | 暗転後 `WaitTime`F 待機してから↓を `(1825 - WaitTime)`F 長押し |
| `"暗転からA"` | 暗転後 `WaitTime`F 待機してから A を `(1825 - WaitTime)`F 長押し |

### 4.3 フロー

```
while (i < ki_seeds):
    Step 1: ソフトリセット（初期Seed集めモードと同一）
    Step 2: タイマー開始
    Step 3: キー入力パターンに応じた長押し操作
        - "起動時から十字キー": Hold(↓) → Wait(1825/fps) → Release(↓)
        - "起動時からA":       Hold(A)  → Wait(1825/fps) → Release(A)
        - "暗転から十字キー":  Wait(WaitTime/fps) → Hold(↓) → Wait((1825-WaitTime)/fps) → Release(↓)
        - "暗転からA":         Wait(WaitTime/fps) → Hold(A) → Wait((1825-WaitTime)/fps) → Release(A)
    Step 4: _consume_timer(ki_frame1) で初期Seed決定フレームまで消化
    Step 5: frame2 タイマー開始 → OP送り → つづきからはじめる → 回想スキップ → _consume_timer(ki_frame2)
    Step 6: 個体生成 → 捕獲 → ステータス画面を開く
    Step 7: 性格認識・実数値認識（失敗時は frame2 += 2 でリトライ）
    Step 9: 初期Seed逆算
    Step 10: 結果をコンソール出力 + CSV 書き込み
    Step 11: WaitTime += Increment で次の試行へ
```

### 4.4 設定パラメータ

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `ki_key_input` | `str` | `"起動時から十字キー"` | キー入力パターン |
| `ki_frame1` | `int` | `2090` | 初期Seed決定フレーム |
| `ki_frame2` | `int` | `745` (Switch) | 初期Seed決定からエンカウントまでの待機フレーム数 |
| `ki_min_advance` | `int` | `741` | 探索フレーム下限 |
| `ki_max_advance` | `int` | `749` | 探索フレーム上限 |
| `ki_seeds` | `int` | `1` | 取得する初期Seed数 |
| `ki_key_input_wait_time` | `int` | `250` | 「暗転から〜」パターンの初期待機フレーム |
| `ki_wait_time_increment` | `int` | `10` | 各試行ごとの待機フレーム増分 |
| `ki_file_name` | `str` | `"Switch"` | 出力ファイル名 |
| `ki_sound` | `str` | `"モノラル"` | サウンド設定 |
| `ki_button_mode` | `str` | `"ヘルプ"` | ボタンモード設定 |

### 4.5 終了条件

| パターン | 終了条件 |
|---------|---------|
| `"起動時から十字キー"` / `"起動時からA"` | 1つ取得したら即終了 |
| `"暗転から十字キー"` | `WaitTime > 1825` |
| `"暗転からA"` | `WaitTime > 265` |
| 共通 | `i >= ki_seeds` |

### 4.6 KI タイマー

**KIFrame1 タイマー（初期Seed決定フレーム）:**

| 要素 | 内容 |
|------|------|
| **開始地点** | 初期Seed集めモードと同じ位置（ゲーム起動 A の直前） |
| **計測中の操作** | `A(dur=0.20)`（ゲーム起動）+ **キー入力パターンの Hold/Wait/Release がすべてタイマー計測時間内に実行される** |
| **消化地点** | `_consume_timer(kiStartTime, ki_frame1, fps)` の完了 |
| **消化直後のアクション** | OP送り `A(dur=3.50, wait=1.00)` |

```
リセット: HOME → X → A → A (wait=0.50)
                              ↓ ← ★ タイマー開始 (kiStartTime = _start_timer())
ゲーム起動:  A(dur=0.20)
                              [キー入力操作 (Hold → Wait → Release)]   ← タイマー計測中に実行
                              [ki_frame1 の残りフレームを消化]
                              ↓ ← ★ _consume_timer(kiStartTime, ki_frame1, fps)
OP送り:   A(dur=3.50, wait=1.00)
```

> **重要**: ゲーム起動 A(dur=0.20) およびキー入力操作にかかる時間はタイマーの一部として消費される。
> 例えば `ki_frame1 = 2090F` でゲーム起動に `12F` + キー入力操作に `1825F` 相当の時間を使った場合、
> `_consume_timer` は残り `253F` 分だけ追加待機する。

**KIFrame2 タイマー（エンカウント）:**

初期Seed集めモードの frame2 タイマーと同一の構造（frame1 タイマー消化完了直後に開始し、OP送り・つづきから・回想スキップを含む）。

### 4.7 KI モード出力

初期Seed集めモードと同じ CSV フォーマットだが、追加カラムとしてキー入力パターン情報が付与される。

```csv
frame,sound,button_mode,seed_1,key_input
2090,モノラル,ヘルプ,A3F1,暗転からA (250F)
```

### 4.8 Discord 通知

| 条件 | メッセージ |
|------|----------|
| KI 完了（暗転から〜） | `"[FRLGキー入力調査自動化] 初期Seedを{ki_seeds}つ取得したので、プログラムを終了します。"` |
| KI 完了（起動時から〜） | `"[FRLGキー入力調査自動化] 初期Seedを取得したので、プログラムを終了します。"` |

---

## 5. 元スクリプトの RunMode（廃止済み）

Phase 1 では `start_frame` / `max_frame` / `trials` + CSV 解析による自動再開に簡素化されたが、
元スクリプトには以下の RunMode が存在していた。

| `run_mode` | 説明 | Phase 1 での対応 |
|-----------|------|-----------------|
| `"normal"` | 既存出力ファイルの最終行から次のフレームを自動算出して開始 | CSV 自動再開で吸収 |
| `"startFrom"` | `start_frame` で指定したフレームから開始 | `start_frame` パラメータで代替 |
| `"anyFrame"` | 固定フレームを繰り返し実行（同一フレームで何度も Seed 取得） | `trials` 回測定で吸収 |
| `"continuous"` | 「連続」マーカー付きフレームの ±1 を再走査 | 廃止 |

### 5.1 「連続」マーカー

元スクリプトでは、同一 Seed が複数回出現した場合に `mode` フィールドに `"連続"` を含むマーカーが
付与される仕組みがあった。`"continuous"` RunMode はこのマーカーを検出して対象フレームの ±1 を
再走査する機能だった。

Phase 1 では `trials` 回測定により同一フレームの Seed 安定性が直接記録されるため、
「連続」マーカー機構は不要と判断し廃止した。

---

## 6. 元スクリプトの設定パラメータ（Phase 1 で除外されたもの）

| パラメータ | 型 | 元のデフォルト | 廃止理由 |
|-----------|-----|---------------|---------|
| `hardware` | `str` | `"GC"` | Switch 固定のためパラメータ不要 |
| `region` | `str` | `"JPN"` | JPN 固定（海外版は未定スコープ） |
| `resolution` | `str` | `"720p"` | 720p 固定 |
| `output_type` | `str` | `"csv"` | CSV 固定 |
| `active_tab` | `int` | `0` | KI モードを別仕様に分離 |
| `frame_parity` | `str` | `"odd"` | パリティフィルタ廃止（全フレーム探索） |
| `run_mode` | `str` | `"normal"` | RunMode 廃止（CSV 自動再開に統一） |
| `any_frame1` | `int` | `2500` | RunMode 廃止に伴い不要 |

---

## 7. 設定EXE連携

元スクリプトには、実行前に .NET の設定 GUI (`設定.exe`) を起動して JSON 設定ファイルを生成する
仕組みがあった (`SkipSettingsExe` フラグで制御)。

NyX では TOML 設定ファイル + `initialize()` の `args` dict で設定を管理するため、
設定EXE連携は完全に不要となる。

---

## 8. Shift_JIS / TXT 出力

元スクリプトの CSV 出力は Shift_JIS エンコーディングだった。
また、TXT 形式（スペース区切り・UTF-8）での出力もサポートしていた。

Phase 1 では UTF-8 の CSV（ヘッダー付き）に統一し、TXT・Shift_JIS は廃止した。

# FRLG 初期Seed収集 共通CSVフォーマット仕様

## 概要

複数人・複数環境での初期Seed収集データをマージするための共通記録フォーマット。

---

## 1. フォーマット

本マクロでは以下の 2 ファイルを出力する。

### initial_seeds.csv（共有用）

```
frame,seed,region,version,edition,sound_mode,button_mode,keyinput,hardware,fps,note
```

- Seed が一意に特定できた行 **のみ** を記録する
- `seed` は16進4桁のみ許容（`MULT` / `False` は書き込まない）
- 複数人でのデータマージを前提とした **クリーンなテーブル**

### initial_seeds_details.csv（詳細ログ）

```
frame,seed,region,version,edition,sound_mode,button_mode,keyinput,hardware,fps,advance,pokemon,level,hp,atk,def,spa,spd,spe,note
```

- 全測定結果を記録する（`MULT` / `False` を含む）
- 逆算の検証に必要な補助情報（advance, ターゲット種族, 実数値）を付加する
- デバッグ・異常値分析用の **完全ログ**

---

## 2. カラム(型)定義

```typescript

/** 初期Seed収集 共通CSVレコード */
type InitialSeedRecord = {
  /**
   * 待機フレーム数。1フレーム = 1/fps 秒。
   * ゲーム起動操作（HOMEメニューで A を押下した瞬間）を起点 (t=0) とし、
   * 初期Seedが決定されるタイミング（リザードン・フシギバナのスプラッシュ画面送り直前）
   * までのフレーム数。
   */
  frame: number; // 正整数

  /**
   * 逆算された16bit初期Seed。 16進4桁 (大文字・先頭ゼロ埋め)
   */
  seed: string; // e.g. "07A3", "FF00"

  /**
   * 言語リージョン。ゲームの言語設定。
   */
  region: "JPN" | "ENG" | "FRA" | "ITA" | "ESP" | "NOE";

  /**
   * ROM種別。ファイアレッド / リーフグリーン。
   */
  version: "FR" | "LG";

  /**
   * エディション種別。
   * - "Switch": Switch版
   * - "AGB-E2-20": 前期ROM
   * - "AGB-E2-30": 後期ROM
   */
  edition: "Switch" | "AGB-E2-20" | "AGB-E2-30";

  /**
   * ゲーム内「せってい」のサウンド設定。初期Seedの生成ロジックに影響する可能性があるため記録する。
   */
  sound_mode: "モノラル" | "ステレオ";

  /**
   * ゲーム内「せってい」のボタンモード設定。初期Seedの生成ロジックに影響する可能性があるため記録する。
   */
  button_mode: "ヘルプ" | "LR" | "かたて";

  /**
   * ゲーム起動時のキー入力パターン。
   *
   * - "none"             : キー入力なし
   * - "dpad_on_boot"     : ゲーム起動直後から スプラッシュ画面まで ↓ を Hold し続ける
   * - "a_on_boot"        : ゲーム起動直後から スプラッシュ画面まで A を Hold し続ける
   * - "dpad_after_fade"  : 起動後、「2004 Pokemon」が消えてから、星が流れる直前までタイミングで ↓ を Hold する
   * - "a_after_fade"     : 起動後、「2004 Pokemon」が消えてから、星が流れる直前までタイミングで A を Hold する
   */
  keyinput:　"none"　| "dpad_on_boot"　| "a_on_boot"　| "dpad_after_fade"　| "a_after_fade";

  /**
   * ゲームを実行する本体ハードウェア。
   */
  hardware: "Switch2" | "Switch" | "GC";

  /**
   * マクロ実行時の想定フレームレート。frame → 実待機時間の変換に利用。seconds = frame / fps。
   */
  fps: number; // 正の実数

  /**
   * 自由記述の備考欄 (省略可)。異常値の原因メモ、環境固有の注記などに使用する。
   */
  note?: string;
};

/**
 * 詳細ログ用レコード (initial_seeds_details.csv)
 *
 * InitialSeedRecord を拡張し、逆算の検証情報を付加する。
 * seed に "MULT" / "False" を許容する。
 */
type InitialSeedDetailRecord = Omit<InitialSeedRecord, "seed" | "note"> & {
  /**
   * 逆算された16bit初期Seed、または特殊値。
   * - 16進4桁: 一意に特定できた場合
   * - "MULT": 候補が2つ以上存在し一意に絞れなかった場合
   * - "False": 候補が見つからなかった場合
   */
  seed: string | "MULT" | "False";

  /**
   * Seed 逆算時にヒットした LCG advance 値。
   * seed が16進値のときのみ記録。"MULT" / "False" 時は空。
   */
  advance?: number; // 正整数

  /**
   * 逆算対象のポケモン種族名。
   */
  pokemon: string; // e.g. "ルギア"

  /**
   * 逆算対象のポケモンレベル。
   */
  level: number; // 正整数

  /** 画像認識で取得した実数値 (HP) */
  hp: number;
  /** 画像認識で取得した実数値 (こうげき) */
  atk: number;
  /** 画像認識で取得した実数値 (ぼうぎょ) */
  def: number;
  /** 画像認識で取得した実数値 (とくこう) */
  spa: number;
  /** 画像認識で取得した実数値 (とくぼう) */
  spd: number;
  /** 画像認識で取得した実数値 (すばやさ) */
  spe: number;

  /**
   * 自由記述の備考欄 (省略可)。
   */
  note?: string;
};
```

---

## 3. 早見表

### 共通カラム (両ファイル共通: 1–10, note)

| # | カラム | 必須 | 説明 | 値の例 |
|---|--------|------|------|--------|
| 1 | frame | Yes | 待機フレーム数 (→ §4 参照) | `2120` |
| 2 | seed | Yes | 16bit 初期Seed (16進4桁) | `BEAF`, `07A3` |
| 3 | region | Yes | 言語リージョン | `JPN`, `ENG`, `FRA` |
| 4 | version | Yes | ROM種別 | `FR`, `LG` |
| 5 | edition | Yes | エディション | `Switch`, `AGB-E2-20`, `AGB-E2-30` |
| 6 | sound_mode | Yes | サウンド設定 | `モノラル`, `ステレオ` |
| 7 | button_mode | Yes | ボタンモード設定 | `ヘルプ`, `LR`, `かたて` |
| 8 | keyinput | Yes | キー入力パターン (→ §5 参照) | `none` |
| 9 | hardware | Yes | 実行本体 | `Switch2`, `Switch`, `GC` |
| 10 | fps | Yes | フレームレート | `59.7275`, `60.0` |
| — | note | No | 備考 | |

> **initial_seeds.csv**: seed は16進4桁のみ。note は #11。
> **initial_seeds_details.csv**: seed に `MULT` / `False` を許容。#10 の後に詳細カラムが続き、note は末尾 (#20)。

### 詳細カラム (initial_seeds_details.csv のみ: 11–20)

| # | カラム | 必須 | 説明 | 値の例 |
|---|--------|------|------|--------|
| 11 | advance | No | LCG advance 値。seed が16進時のみ | `1340` |
| 12 | pokemon | Yes | 逆算対象ポケモン種族名 | `ルギア` |
| 13 | level | Yes | 逆算対象ポケモンレベル | `70` |
| 14 | hp | Yes | 実数値 HP | `253` |
| 15 | atk | Yes | 実数値 こうげき | `168` |
| 16 | def | Yes | 実数値 ぼうぎょ | `220` |
| 17 | spa | Yes | 実数値 とくこう | `172` |
| 18 | spd | Yes | 実数値 とくぼう | `258` |
| 19 | spe | Yes | 実数値 すばやさ | `194` |
| 20 | note | No | 備考 | |

---

## 4. frame の厳密な定義

```
HOMEメニュー
  ↓ A 押下  // frame の起点
  ↓
  [ゲームプロセス起動]
  ↓
  [タイトル画面 → OP スプラッシュ表示]
  ↓
  ★ frame フレーム経過
  ↓
  [OP 送り(初期Seed決定) → つづきからはじめる → 回想スキップ → エンカウント]
```

- 起点 = HOME メニューでゲームを起動する A ボタン押下の **直前** にタイマー開始
- 終点 = OPスプラッシュ画面(リザードン・フシギバナの画面)でのA ボタン押下の **直前** にタイマー終了
- 1 フレーム = $1 / \text{fps}$ 秒

---

## 5. keyinput パターン詳細

| 値 | 操作内容 | タイミング |
|----|----------|------------|
| `none` | キー入力なし | — |
| `dpad_on_boot` | 十字キー↓ を長押し | ゲーム起動 A 直後から frame 消化完了まで |
| `a_on_boot` | A ボタンを長押し | ゲーム起動 A 直後から frame 消化完了まで |
| `dpad_after_fade` | 十字キー↓ を長押し | 起動後、指定フレーム待機してから Hold 開始 |
| `a_after_fade` | A ボタンを長押し | 起動後、指定フレーム待機してから Hold 開始 |

- `*_on_boot` 系: ゲーム起動と同時に入力を開始し、初期Seed 決定フレームまで押し続ける
- `*_after_fade` 系: 起動後の暗転→画面復帰タイミングを狙い、一定フレーム経過後から入力を開始する。待機フレーム数はマクロ側の設定で制御する

---

## 6. CSV ルール

| 項目 | ルール |
|------|--------|
| ヘッダー行 | ファイル先頭に必ず 1 行 |
| 区切り文字 | カンマ (`,`)。値にカンマを含む場合はダブルクォートで囲む |
| seed の表記 | 大文字16進4桁・先頭ゼロ埋め (例: `07A3`)。details 側のみ `MULT` / `False` を許容 |
| 空値 | `note`, `advance` のみ空文字を許容する。他の必須カラムは空にしない |
| 1測定 = 1行 | 同一フレームで複数回測定しても、各結果を独立した行として記録する |

---

## 7. サンプル

### initial_seeds.csv

```csv
frame,seed,region,version,edition,sound_mode,button_mode,keyinput,hardware,fps,note
2120,7454,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,
2120,7454,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,
2120,2BC1,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,ブレ発生
2090,A3F1,JPN,FR,Switch,モノラル,ヘルプ,dpad_on_boot,Switch,59.7275,
2090,C820,JPN,FR,Switch,モノラル,ヘルプ,a_after_fade,Switch2,59.7275,
```

### initial_seeds_details.csv

```csv
frame,seed,region,version,edition,sound_mode,button_mode,keyinput,hardware,fps,advance,pokemon,level,hp,atk,def,spa,spd,spe,note
2120,7454,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,1340,ルギア,70,253,168,220,172,258,194,
2120,7454,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,1340,ルギア,70,253,168,220,172,258,194,
2120,2BC1,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,1340,ルギア,70,247,155,223,159,270,190,ブレ発生
2121,MULT,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,,ルギア,70,250,162,218,166,264,188,候補2つ
2121,False,JPN,FR,Switch,モノラル,ヘルプ,none,Switch,59.7275,,ルギア,70,248,170,215,175,255,201,認識失敗
```

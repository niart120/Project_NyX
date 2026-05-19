# マクロ開発者向け仕様提供 作業計画仕様書

> **文書種別**: 作業計画仕様。NyX のマクロ実装者へ公開 API、配置規約、テスト方法、AI agent へ渡す実装情報を提供するための方針と作業単位を定義する。
> **対象領域**: `README.md`, `docs\macro-development\`, `src\nyxpy\framework\`, `examples\`, `.github\skills\`, `spec\framework\rearchitecture\`, `spec\macro\`
> **目的**: Python 知識を持つ実装者と AI agent が、リポジトリを clone しない環境でもマクロを実装できる情報面を整える。
> **関連ドキュメント**: `README.md`, `spec/framework/rearchitecture/MACRO_MIGRATION_GUIDE.md`, `spec/framework/rearchitecture/RUNTIME_AND_IO_PORTS.md`, `spec/framework/rearchitecture/RESOURCE_FILE_IO.md`, `spec/framework/rearchitecture/CONFIGURATION_AND_RESOURCES.md`, `spec/macro/**/spec.md`

## 1. 概要

### 1.1 対象読者

一定の Python 知識を持ち、NyX の公開 API を使ってマクロを書く実装者を対象にする。読者は `class`、型ヒント、例外、pytest、TOML、PowerShell の基本を理解している前提でよい。

実装作業は人間が直接書く場合だけでなく、AI agent に依頼する場合を主対象に含める。人間向けには判断材料と確認手順を提供し、AI agent 向けには実装制約、入出力形式、禁止事項、参照すべき API を機械的に拾いやすい形で提供する。

### 1.2 背景

現状の README には最小マクロ例と主要コマンドがあるが、実装者が必要とする情報は `spec\framework\rearchitecture\` の内部設計仕様、`examples\macros`、個別マクロ仕様、テストに分散している。`spec\framework\rearchitecture\` は再設計時の判断材料としては有用だが、現行 API とのずれが出始めているため、マクロ開発者向けの正本にはしない。

この作業では、公開 API の仕様正本を `docs\macro-development\` と公開 API の docstring / 型ヒントへ移す。`spec\framework\rearchitecture\` は参照元・移行元として扱い、最新仕様の根拠にはしない。

正式公開後は、実装者がこのリポジトリを clone せず、別プロジェクトや専用 workspace で利用する可能性が高い。

```powershell
# マクロ実装プロジェクトから framework API を import する場合
uv add nyxpy

# CLI/GUI ツールとして使う場合
uv tool install nyxpy
```

`uv add` はマクロ実装側が `nyxpy.framework.*` を import するライブラリ依存として自然であり、`uv tool install` は `nyx-cli` / `nyx-gui` をツールとして使う導入に向く。現在の配布名は `project-nyx` であるため、正式公開時に PyPI 名を `nyxpy` にするか、配布名と import 名を分けるかは別途決める。

いずれの場合も、リポジトリ内の `spec\` や `examples\` に依存した案内だけでは不足する。パッケージとして取得した環境、エディタの補完、型検査、AI agent のコード読解のどこからでも、最低限の実装情報へ到達できる必要がある。

導入方式で最も違うのは、マクロを import する Python 環境である。

| 導入方式 | `nyx-cli` / `nyx-gui` の環境 | マクロから見える依存関係 | 向く用途 |
|----------|------------------------------|--------------------------|----------|
| `uv tool install nyxpy` | uv tool の隔離環境 | NyX と NyX の依存関係。マクロ固有の追加依存は別途 tool 環境へ入れる必要がある | 既存マクロを実行する利用者 |
| `uv add nyxpy` | マクロ実装プロジェクトの仮想環境 | そのプロジェクトの依存関係すべて | マクロを開発し、追加ライブラリやテストを同じ環境で扱う実装者 |

現行のマクロ探索は、workspace の `macros\` を一時的に import path へ追加して `MacroBase` 派生クラスを import する。そのため `uv tool install` でも、標準ライブラリと NyX 依存だけで書かれたマクロは動く。一方で、マクロが NyX には含まれない外部ライブラリを import する場合、tool の隔離環境にその依存が無いと import 失敗する。この点は利用者向け手順とマクロ実装者向け手順の両方で明記する。

## 2. 情報提供面の設計

### 2.1 提供面の分類

| 提供面 | 主な読者 | 役割 | 配布形態 |
|--------|----------|------|----------|
| `docs\macro-development\` | 人間、AI agent | 実装手順、公開 API の使い方、配置規約、テスト手順 | リポジトリ、将来のドキュメントサイト |
| `src\nyxpy\framework\...` の docstring | 人間、AI agent、エディタ | API の直近説明、引数、戻り値、例外、使用上の注意 | wheel / sdist に同梱 |
| 型ヒントと `py.typed` | エディタ、型検査、AI agent | 呼び出し可能な API と値の形を補完可能にする | wheel に同梱 |
| 最小テンプレート | 人間、AI agent | 新規マクロ作成時の正しい初期形 | パッケージ内データまたは CLI 生成 |
| サンプルマクロ | 人間、AI agent | 実装パターン、テスト、resources の読み方を示す | リポジトリ、将来は別配布も検討 |
| マクロ生成 skill | AI agent | 新規マクロ作成時の調査、雛形生成、テスト追加を手順化 | `.github\skills\` |
| AI agent 向け短縮仕様 | AI agent | 守るべき制約と参照 API を短く列挙 | skill、docs、パッケージ内データ |

### 2.2 PyPI 配布後の到達性

PyPI 配布後に clone なしで使う実装者向けには、次の到達経路を用意する。

| 到達経路 | 期待する使い方 | 必要な整備 |
|----------|----------------|------------|
| エディタ補完 | `MacroBase` や `Command` の docstring を見る | 公開 API の docstring と型ヒントを整備する |
| `python -m pydoc` | インストール済みパッケージから API 説明を見る | module / class / method docstring を公開 API に書く |
| CLI | ツール導入後にテンプレートや docs の場所を表示する | `uv tool install nyxpy` で使える `nyx-cli` から scaffold / docs URL を出す |
| パッケージ内テンプレート | ライブラリ依存またはツール導入後に新規マクロ雛形を生成する | template ファイルを package data として同梱する |
| 公開 docs | 詳細手順やサンプルを見る | `docs\macro-development\` をサイト化できる構成にする |

この計画では、最初に Markdown の正本を整理し、その後に docstring、型情報、テンプレート、CLI 導線を実装対象へ落とす。

### 2.3 API 仕様の生成方針

API 仕様は Markdown へ手で再掲し続けない。公開 API の docstring と型ヒントを正本に近づけ、サイト生成時に API リファレンスへ取り込む。概念説明と作例は `docs\macro-development\`、関数・クラス・引数・例外の近接仕様は docstring / 型ヒントを正本にする。

| 候補 | 特徴 | NyX での判断 |
|------|------|--------------|
| Sphinx + autodoc | Python module を import して docstring から API docs を生成できる。napoleon で Google / NumPy style docstring も扱える | API リファレンスの精度は高いが、Markdown 中心の手順書とは分離しやすい |
| MkDocs + mkdocstrings | Markdown ベースの docs に Python API リファレンスを差し込める | `docs\` を Markdown で育てる方針と相性がよく、第一候補 |
| pydoc | インストール済み環境で docstring を直接読む標準手段 | 公開 docs の代替ではなく、clone なし利用時の最低限の到達経路として扱う |

Sphinx も MkDocs も docstring 対応はできる。NyX では、手順書を Markdown で整備し、API だけ docstring から挿入したいので、まずは MkDocs + mkdocstrings を候補にする。API リファレンスの厳密性や外部 API との相互参照が主課題になった場合は Sphinx へ寄せる。

公開ドキュメントは GitHub Pages に統一する。GitHub Wiki も git repository として扱えるため CI から生成済み Markdown を push する運用は可能だが、通常の pull request review、branch protection、docs build 検証、package data 同梱の流れから外れやすい。SSOT を保つには、ソースを本リポジトリの `docs\` と docstring に置き、GitHub Pages へ生成物を配信する方が単純である。

### 2.4 AI agent 向け情報形式

AI agent は長い設計書より、明確な制約、正しい import、最小例、テストコマンド、禁止事項を拾いやすい。新規マクロ作成は Markdown のチェックリストを人間に読ませるより、専用 skill と雛形生成で誘導する。

| 文書 | 目的 | 記述内容 |
|------|------|----------|
| `.github\skills\macro-development\SKILL.md` | agent に新規マクロ作成・更新の手順を実行させる | 調査順、配置、雛形、テスト、禁止事項、完了条件 |
| `docs\macro-development\agent-brief.md` | skill を使えない agent や人間へ渡す短縮仕様 | 依存方向、標準配置、import、settings、resources、テストコマンド、禁止事項 |
| `docs\macro-development\macro-template.md` | 新規マクロ作成時の雛形説明 | ディレクトリ構造、最小コード、settings、テストの形 |
| 公開 API docstring | エディタ内で参照する仕様 | メソッドの意味、単位、例外、戻り値、実行時制約 |

`agent-brief.md` は、内部設計の詳細ではなく実装者が守る契約だけを書く。AI agent へ投入しやすいように、短い見出し、箇条書き、コード例、明示的な禁止事項を優先する。独立した `checklist.md` は必須成果物にしない。チェックリスト相当の内容は skill の完了条件と `macro-template.md` の末尾へ集約する。

### 2.5 AI 向けドキュメンテーションの周辺事情

現時点で、uv に AI 向けドキュメントを自動提供する専用機能は見当たらない。uv で使えるのは、tool の隔離環境、`uv add` による依存追加、`uv tool install --with` による追加依存注入など、実行環境の管理である。

Python packaging 側の標準としては、型情報配布のための `py.typed` がある。これは PEP 561 に基づく仕組みで、型検査器やエディタがインストール済み package の inline type hints を使えるようにする。AI agent にも補完・静的解析経由で効くため、公開 API は型ヒントと `py.typed` を整える。

AI agent 向けのコミュニティ慣習としては、次の候補がある。

| 形式 | 位置づけ | NyX での扱い |
|------|----------|--------------|
| `AGENTS.md` | coding agent 向けのリポジトリ内指示ファイル。build/test、規約、注意点を書く | repository 作業者向けに有効。マクロ利用者へ配る docs とは分ける |
| `llms.txt` | Web サイト上で LLM 向けに重要 Markdown へのリンクを示す提案 | docs をサイト化する場合の公開入口候補 |
| GitHub Copilot / CLI skills | 特定作業を agent に実行させる手順化 | NyX のマクロ生成では最も直接的。`macro-development` skill を候補にする |

## 3. 目標構成

### 3.1 名称

`macro-authoring` は文書執筆寄りの語感があるため使わない。NyX では実装・テスト・設定・配布まで含むので、ディレクトリ名は `docs\macro-development\` とする。日本語では「マクロ開発者向け」と呼ぶ。

### 3.2 `docs\macro-development\`

| 文書 | 内容 | 主な移設元 |
|------|------|------------|
| `docs\macro-development\README.md` | マクロ開発者向け目次、最短作成手順、関連仕様へのリンク | `README.md` 4章 |
| `docs\macro-development\agent-brief.md` | AI agent へ渡す短縮仕様、制約、禁止事項、テストコマンド | 本計画で新規 |
| `docs\macro-development\macro-layout.md` | `macros\`, `resources\`, `examples\macros`, `examples\resources` の使い分け | `README.md`, `MACRO_MIGRATION_GUIDE.md` |
| `docs\macro-development\macro-lifecycle.md` | `MacroBase.initialize/run/finalize`、実行引数、終了処理 | `README.md`, `RUNTIME_AND_IO_PORTS.md` |
| `docs\macro-development\command-api.md` | `Command` の操作 API、待機、キャプチャ、画像入出力、通知、ログ | `README.md`, `RUNTIME_AND_IO_PORTS.md` |
| `docs\macro-development\settings-and-resources.md` | `settings_path = "resource:settings.toml"`、`resources\<macro_id>`、assets、run outputs | `README.md`, `MACRO_MIGRATION_GUIDE.md` |
| `docs\macro-development\manifest.md` | `macro.toml` が必要な条件、entrypoint、metadata | `MACRO_MIGRATION_GUIDE.md` |
| `docs\macro-development\testing.md` | 単体テスト、実機テスト、`@pytest.mark.realdevice`、公開例のテスト配置 | `pyproject.toml`, `tests\`, `examples\tests` |
| `docs\macro-development\image-processing.md` | `ImageProcessor`、OCR、テンプレートマッチング、前処理の使い方と所掌範囲 | `src\nyxpy\framework\core\imgproc\` |
| `docs\macro-development\nintendo-3ds.md` | 3DS 向け定数、touch、sleep control、座標系、補助関数の使い方 | `src\nyxpy\framework\core\constants\controller.py`, `Command` |
| `docs\macro-development\sample-macros.md` | `examples\macros` / `examples\resources` / `examples\tests` の読み方 | 既存 examples 配置 |

### 3.3 公開ドキュメントの扱い

公開ドキュメントは GitHub Pages に統一する。GitHub Wiki は使わない。API 仕様、マクロ配置規約、利用手順のソースは本リポジトリの `docs\` と docstring に置き、CI で生成・検証した成果物だけを GitHub Pages へ公開する。

FAQ、既知の実機構成、動画付き手順なども、まずは `docs\user-guide\` または `docs\macro-development\` に置く。コードと同期しない補足情報が増えた場合も、公開面は GitHub Pages の中で分ける。

### 3.4 パッケージ同梱候補

clone なし利用を考えると、Markdown をリポジトリに置くだけでは足りない。次のいずれかを package data として同梱する案を検討する。

| 候補 | 目的 | 判断 |
|------|------|------|
| `nyxpy\templates\macro\` | `nyx-cli scaffold` の雛形 | 優先度高 |
| `nyxpy\docs\macro-development\agent-brief.md` | agent に渡す短縮仕様をインストール済み環境から取得 | 優先度中 |
| `examples\` 全体 | サンプルマクロをパッケージから参照 | wheel 肥大化と保守のため慎重に扱う |

package data を入れる場合は、`pyproject.toml` の hatchling 設定で同梱対象を明示する。どのファイルを wheel に含めるかは、配布サイズと更新頻度を見て決める。

## 4. 正本ルール

| 情報 | 正本 | 参照側の扱い |
|------|------|--------------|
| マクロ開発者向け公開契約 | `docs\macro-development\` | README には最小例だけを置く |
| `MacroBase` / `Command` の引数・戻り値・例外 | 対象 API の docstring と型ヒント | docs は使い方と例を説明する |
| Runtime / Resource I/O / settings の内部設計 | `spec\framework\rearchitecture\` | 移行元・参考資料として扱い、正本にはしない |
| 個別マクロ仕様 | `spec\macro\<macro_id>\spec.md` | サンプルや examples から必要に応じてリンクする |
| サンプル実装 | `examples\macros\`, `examples\resources\`, `examples\tests\` | 読み物として参照する。実装者の配置先にはしない |
| 履歴資料 | `spec\framework\archive\` | 現行仕様の根拠としては扱わない |

## 5. docstring 整備方針

docstring は進めるべきだが、Markdown docs の代替にはしない。役割は「インストール済み環境で、API のすぐ近くにある短い仕様」とする。

### 5.1 対象 API

優先して docstring を整備する対象は次の範囲に限定する。

| 対象 | 書く内容 |
|------|----------|
| `MacroBase` | lifecycle、各 method の呼び出し順、`args` の扱い、状態保持の注意 |
| `Command` | 各操作の単位、待機・キャンセル、画像入出力、通知、例外 |
| constants (`Button`, `Hat`, `LStick`, `RStick`) | 利用例、値の意味 |
| 3DS constants (`ThreeDSButton`, `TouchState`) | 3DS 固有ボタン、touch 入力、座標系、対応プロトコルの注意 |
| `MacroStopException` | 中断を表す例外としての扱い |
| `ImageProcessor` / `OCRProcessor` / template matcher | OCR、テンプレートマッチング、前処理、例外、初回ロードコスト |
| settings resolver の公開面 | `resource:` / `project:` などの settings path の意味 |

### 5.2 書かない内容

- GUI/CLI の使い方は docstring に書かない。
- 内部 Port / Adapter の設計理由は docstring に書かない。
- 長いチュートリアルは docs に置き、docstring にはリンクまたは短い例だけを書く。

### 5.3 形式

docstring は、要約、引数、戻り値、送出例外、短い例を持つ。型ヒントと重複する型名の羅列は避け、実装者が誤用しやすい制約を優先する。

```python
def wait(self, sec: float) -> None:
    """指定秒数だけ待機する。

    待機中も中断要求を確認する。長い処理では `time.sleep()` を直接呼ばず、
    このメソッドを使う。

    Raises:
        MacroStopException: 実行中断が要求された場合。
    """
```

## 6. 執筆ルール

- Python 知識を持つ読者を前提にし、基礎文法の説明はしない。
- 最小コード例、推奨配置、テスト例をセットで示す。
- `macros\` と `examples\macros` の使い分けを明記する。
- 実装者のマクロ本体は `macros\<macro_id>`、設定・画像資材は `resources\<macro_id>` に置く。`examples\` はサンプルの参照先であり、利用者に配置させる場所ではない。
- `resources\<macro_id>\settings.toml` と `settings_path = "resource:settings.toml"` を標準例にする。
- `macro.toml` や settings に保存する portable path は `/` を使う。
- PowerShell コマンド例を使う。
- AI agent 向け文書では、禁止事項を曖昧に書かない。
- 画像処理は NyX が提供する OCR / template matcher / 前処理を中心に扱う。OpenCV の一般的な解説は、NyX API と組み合わせる短い recipe に限定する。

## 7. 作業計画

### Phase 0: 現状棚卸し

| 作業 | 成果物 |
|------|--------|
| README のマクロ開発節を移設対象として分解する | README 移設対応表 |
| `spec\framework\rearchitecture\` から実装者向け公開契約だけを抽出する | macro-development 文書一覧の確定 |
| `examples\macros` / `examples\resources` / `examples\tests` の現行構成を確認する | examples の読み方一覧 |
| `MacroBase` / `Command` / constants の docstring と型ヒントの現状を確認する | docstring 整備対象一覧 |
| 3DS 向け定数・補助 API・座標系を確認する | 3DS 補足資料の対象一覧 |
| OCR / template matcher / 前処理 API を確認する | 画像処理資料の対象一覧 |

### Phase 1: agent に渡せる入口を作る

| 作業 | 成果物 |
|------|--------|
| `docs\macro-development\README.md` を作る | 実装者向け目次 |
| `docs\macro-development\agent-brief.md` を作る | AI agent 向け短縮仕様 |
| `.github\skills\macro-development\SKILL.md` を作る | AI agent によるマクロ生成・更新手順 |
| `docs\macro-development\macro-template.md` を作る | 雛形説明と完了前確認 |
| README のマクロ開発節を短くし、詳細文書へリンクする | README 改訂 |

### Phase 2: マクロ実装手順を分ける

| 作業 | 成果物 |
|------|--------|
| 配置規約と lifecycle を分離する | `macro-layout.md`, `macro-lifecycle.md` |
| `Command` API の公開面を整理する | `command-api.md` |
| settings / resources / outputs を整理する | `settings-and-resources.md` |
| manifest とテスト手順を整理する | `manifest.md`, `testing.md` |
| 3DS 向け補足をまとめる | `nintendo-3ds.md` |
| OCR と画像処理 API の使い方をまとめる | `image-processing.md` |
| examples の読み方をまとめる | `sample-macros.md` |

### Phase 3: パッケージから到達できる情報を増やす

| 作業 | 成果物 |
|------|--------|
| `MacroBase` / `Command` / constants の docstring を整備する | 公開 API docstring |
| `py.typed` の有無と型ヒント公開方針を確認する | PEP 561 対応方針 |
| マクロ雛形を package data として持つか決める | scaffold 方針 |
| `nyx-cli` から scaffold または docs URL を出す導線を検討する | CLI 導線案 |
| MkDocs + mkdocstrings による API リファレンス生成を検証する | docs 生成方式の判断 |
| GitHub Pages へ生成 docs を配信できるか確認する | 公開面の判断 |

### Phase 4: 重複削減と検証

| 作業 | 成果物 |
|------|--------|
| docs から内部仕様の再定義を削る | docs と spec の責務分離 |
| docstring と Markdown docs の矛盾を確認する | API 説明の整合 |
| 主要リンク、パス表記、PowerShell コマンド例を確認する | リンク・表記の修正差分 |

## 8. 受け入れ条件

- Python 知識を持つ実装者が、`docs\macro-development\README.md` から必要な文書へ移動できる。
- AI agent に `agent-brief.md` と対象マクロ仕様を渡せば、標準配置・公開 API・禁止事項を外しにくい。
- `MacroBase` / `Command` / constants の公開 API は、docstring と型ヒントから最低限の使い方が分かる。
- clone なし利用でも、エディタ補完、`pydoc`、CLI、公開 docs のいずれかから実装情報へ到達できる設計になっている。
- マクロ開発者向け docs は内部 Runtime 仕様を再定義せず、公開契約だけを説明している。
- `macros\` / `resources\` が実装者の配置先であり、`examples\macros` / `examples\resources` はサンプル参照先であることが明記されている。
- 3DS 向けマクロで使う定数、touch、座標系、補助 API へ到達できる。
- OCR と画像処理 API の所掌範囲が明記され、OpenCV の一般解説へ広げすぎていない。

## 9. 未決事項

| 論点 | 判断候補 | ドラフト上の仮置き |
|------|----------|--------------------|
| API リファレンス生成手段 | MkDocs + mkdocstrings / Sphinx + autodoc | Markdown 手順書と相性がよい MkDocs + mkdocstrings を第一候補 |
| agent brief を wheel に同梱するか | 同梱する / docs のみ | 同梱候補として検討 |
| scaffold を CLI に入れるか | `nyx-cli scaffold` / 別コマンド / なし | `nyx-cli scaffold` 候補 |
| examples 全体を package data に含めるか | 含める / 含めない / 別配布 | wheel 肥大化を避けるため慎重に扱う |
| GitHub Pages の構成 | MkDocs の直接 publish / GitHub Actions 生成 / 手動生成 | GitHub Actions で生成し Pages へ公開 |
| `spec\framework\rearchitecture\` の扱い | 正本 / 参考資料 / archive 化 | 正本にはしない。macro-development docs 作成時の参考資料 |
